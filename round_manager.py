import asyncio
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import discord

from achievements.manager import AchievementManager
from database import Database
from ui.embed_factory import EmbedFactory


class RoundManager:
    """Handles the whole lifecycle of the bot's guessing rounds."""

    def __init__(
        self,
        bot: discord.Client,
        channel_id: int,
        db: Optional[Database] = None,
        images_base_path: str = "images",
        achievement_manager: Optional[AchievementManager] = None,
        min_delay_seconds: int = 5 * 60,
        max_delay_seconds: int = 30 * 60,
        round_timeout_seconds: int = 10 * 60,
    ) -> None:
        self.bot = bot
        self.channel_id = channel_id
        self.channel: Optional[discord.TextChannel] = None
        self.db = db or Database()
        self.images_base_path = Path(images_base_path)
        self.achievements = achievement_manager
        self.min_delay_seconds = min_delay_seconds
        self.max_delay_seconds = max(max_delay_seconds, min_delay_seconds)
        self.round_timeout_seconds = round_timeout_seconds

        self.current_round_active: bool = False
        self.current_character_id: Optional[int] = None
        self.current_character_name: Optional[str] = None
        self.current_rarity: Optional[str] = None
        self.current_image_id: Optional[int] = None
        self.current_image_path: Optional[str] = None
        self.current_anime: Optional[str] = None
        self.next_round_task: Optional[asyncio.Task] = None
        self.next_round_eta: Optional[datetime] = None
        self.debug_mode: bool = False
        self.round_timeout_task: Optional[asyncio.Task] = None
        self.round_timeout_eta: Optional[datetime] = None

    async def start_round(self) -> bool:
        """Starts a new round if none is running. Returns True if it started."""
        if self.current_round_active:
            print("[INFO] A round is already active, start_round ignored.")
            return True

        if not self.channel:
            self.channel = self.bot.get_channel(self.channel_id)

        if not self.channel:
            print(f"[ERROR] Channel {self.channel_id} not found, can't start the round.")
            return False

        character = self.db.get_random_character()
        if not character:
            print("[WARN] No characters available to start a round.")
            return False

        image_row = self.db.get_random_image_for_character(character["id"], character["rarity"])
        image_path = None
        image_id: Optional[int] = None
        if image_row:
            resolved = self._resolve_image_path(
                image_row["file_path"],
                anime=character.get("anime"),
                character_name=character["name"],
                rarity=character["rarity"],
            )
            if resolved:
                image_path = resolved
                image_id = image_row["id"]
        if not image_path and character.get("image_path"):
            resolved = self._resolve_image_path(
                character["image_path"],
                anime=character.get("anime"),
                character_name=character["name"],
                rarity=character["rarity"],
            )
            if resolved:
                image_path = resolved

        # If we found a valid path but no row in the images table,
        # create the entry on the fly so the card can be given to the winner.
        if image_path and image_id is None:
            db_file_path = character.get("image_path") or str(image_path)
            created_image = self.db.add_image(character["id"], character["rarity"], db_file_path)
            if created_image:
                image_id = created_image["id"]

        if not image_path:
            print(f"[WARN] No image found for {character['name']} ({character['rarity']}).")
            return False

        # Save the round state before announcing it in the channel.
        self.current_round_active = True
        self.current_character_id = character["id"]
        self.current_character_name = character["name"]
        self.current_rarity = character["rarity"]
        self.current_image_id = image_id
        self.current_image_path = str(image_path)
        self.current_anime = character.get("anime")

        await self._announce_new_round(image_path)
        print(f"[ROUND] New round started with {self.current_character_name} ({self.current_rarity}).")
        if self.debug_mode:
            print(f"[DEBUG] Round started with character {self.current_character_name}")
        self._schedule_round_timeout()
        return True

    async def close_round(self, winner_discord_id: str, winner_username: str) -> None:
        """Closes the current round, gives out the prize and schedules the next one."""
        if not self.current_round_active:
            print("[INFO] No active round to close.")
            return

        self.cancel_round_timeout()

        if not self.channel:
            self.channel = self.bot.get_channel(self.channel_id)

        if (
            self.current_image_id is None
            and self.current_character_id is not None
            and self.current_rarity
            and self.current_image_path
        ):
            created_image = self.db.add_image(
                self.current_character_id,
                self.current_rarity,
                self.current_image_path,
            )
            if created_image:
                self.current_image_id = created_image["id"]

        user = self.db.create_or_get_user(winner_discord_id, winner_username)
        if user and self.current_image_id is not None:
            self.db.add_image_to_user(winner_discord_id, self.current_image_id)

        if self.achievements:
            self.achievements.record_win(
                winner_discord_id,
                self.current_character_id,
                self.current_rarity,
            )

        embed = EmbedFactory.create_victory_embed(
            winner_username,
            self.current_character_name or "Unknown",
            self.current_rarity or "common",
        )

        file_attachment = self._build_file_attachment(self.current_image_path)
        if file_attachment:
            embed.set_image(url=f"attachment://{file_attachment.filename}")

        if self.channel:
            if file_attachment:
                await self.channel.send(embed=embed, file=file_attachment)
            else:
                await self.channel.send(embed=embed)

        self._reset_round_state()
        self.queue_next_round()
        print("[ROUND] Round closed, next one scheduled.")
        if self.debug_mode:
            print(f"[DEBUG] Round closed, winner {winner_username}")

    async def check_guess(self, message: discord.Message) -> None:
        """Checks whether the message contains the right answer."""
        if not self.current_round_active:
            return
        if not message.content:
            return
        if message.author.bot:
            return

        user_id = str(message.author.id)
        username = message.author.name
        self.db.create_or_get_user(user_id, username)

        guess = message.content.strip().lower()
        target = (self.current_character_name or "").strip().lower()
        is_correct = guess == target
        if self.achievements:
            self.achievements.record_guess(user_id, is_correct)
        if is_correct:
            await self.close_round(user_id, username)

    async def schedule_next_round(self) -> None:
        """Waits a random interval and starts a new round, retrying if it fails."""
        delay_seconds = (
            random.randint(5, 10)
            if self.debug_mode
            else random.randint(self.min_delay_seconds, self.max_delay_seconds)
        )
        self.next_round_task = asyncio.current_task()

        try:
            while True:
                self.next_round_eta = datetime.utcnow() + timedelta(seconds=delay_seconds)
                minutes, seconds = divmod(delay_seconds, 60)
                print(f"[SCHEDULER] Next round in {minutes}m {seconds}s.")

                try:
                    await asyncio.sleep(delay_seconds)
                    started = await self.start_round()
                    if started:
                        return

                    # If start_round failed (e.g. missing image), retry in 60s.
                    print("[SCHEDULER][WARN] start_round did not start, retrying in 60s.")
                    delay_seconds = 60
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    print(f"[SCHEDULER][ERR] Error while starting the round: {exc}. Retrying in 60s.")
                    delay_seconds = 60
        finally:
            self.next_round_task = None
            self.next_round_eta = None

    def queue_next_round(self) -> None:
        """Cancels any pending timer and creates a new one."""
        self.cancel_scheduled_round()
        self.next_round_task = asyncio.create_task(self.schedule_next_round())

    def cancel_scheduled_round(self) -> None:
        """Cancels the next round timer, if any."""
        if self.next_round_task and not self.next_round_task.done():
            self.next_round_task.cancel()
        self.next_round_task = None
        self.next_round_eta = None

    def enable_debug(self) -> None:
        """Turns debug mode on (rounds every few seconds, verbose logs)."""
        self.debug_mode = True

    def disable_debug(self) -> None:
        """Turns debug mode off."""
        self.debug_mode = False

    async def _announce_new_round(self, image_path: Path) -> None:
        """Sends the round embed with the card image to the channel."""
        if not self.channel:
            return

        embed = EmbedFactory.create_round_embed(
            self.current_character_name or "???",
            self.current_rarity or "common",
            str(image_path),
        )
        if self.current_anime:
            embed.add_field(name="Saga", value=self.current_anime, inline=True)

        image_to_send = Path(image_path)
        file = discord.File(str(image_to_send), filename=image_to_send.name)
        await self.channel.send(embed=embed, file=file)

    def _reset_round_state(self) -> None:
        """Clears the internal state for the next round."""
        self.cancel_round_timeout()
        self.current_round_active = False
        self.current_character_id = None
        self.current_character_name = None
        self.current_rarity = None
        self.current_image_id = None
        self.current_image_path = None
        self.current_anime = None

    def _resolve_image_path(
        self,
        file_path: str,
        anime: Optional[str],
        character_name: str,
        rarity: str,
    ) -> Optional[Path]:
        """
        Resolves an image path, handling both full paths and bare filenames.
        Tries a few combinations, including the images/<anime>/<character>/<rarity>/ layout.
        """
        path_candidate = Path(file_path)
        if path_candidate.is_file():
            return path_candidate

        structured_candidates = [
            self.images_base_path / file_path,
        ]

        if anime:
            structured_candidates.append(
                self.images_base_path / anime / character_name / rarity / file_path
            )

        for candidate in structured_candidates:
            if candidate.is_file():
                return candidate

        matches = list(self.images_base_path.rglob(Path(file_path).name))
        if matches:
            return matches[0]
        return None

    def _build_file_attachment(self, image_path: Optional[str]) -> Optional[discord.File]:
        """Builds a discord.File attachment from a local path."""
        if not image_path:
            return None
        path = Path(image_path)
        if not path.exists():
            return None
        return discord.File(str(path), filename=path.name)

    def _schedule_round_timeout(self) -> None:
        """Sets a timeout that closes the round automatically if nobody guesses."""
        self.cancel_round_timeout()
        self.round_timeout_eta = datetime.utcnow() + timedelta(seconds=self.round_timeout_seconds)
        self.round_timeout_task = asyncio.create_task(self._round_timeout_worker())

    async def _round_timeout_worker(self) -> None:
        try:
            await asyncio.sleep(self.round_timeout_seconds)
            if not self.current_round_active:
                return
            try:
                await self._handle_round_timeout()
            except Exception as exc:  # noqa: BLE001
                print(f"[ROUND][ERR] Error during timeout: {exc}")
                # On error, reset anyway and try to schedule the next round.
                self._reset_round_state()
                self.queue_next_round()
        except asyncio.CancelledError:
            return
        finally:
            self.round_timeout_task = None
            self.round_timeout_eta = None

    def cancel_round_timeout(self) -> None:
        """Cancels the timeout timer of the current round."""
        if self.round_timeout_task and not self.round_timeout_task.done():
            self.round_timeout_task.cancel()
        self.round_timeout_task = None
        self.round_timeout_eta = None

    async def _handle_round_timeout(self) -> None:
        """Closes the round when the timeout expires with no winner, and schedules the next one."""
        if not self.channel:
            self.channel = self.bot.get_channel(self.channel_id)

        embed = EmbedFactory.create_round_timeout_embed(
            self.current_character_name or "Unknown",
            self.current_rarity or "common",
            timeout_minutes=self.round_timeout_seconds // 60,
        )

        file_attachment = self._build_file_attachment(self.current_image_path)
        if self.channel:
            if file_attachment:
                embed.set_image(url=f"attachment://{file_attachment.filename}")
                await self.channel.send(embed=embed, file=file_attachment)
            else:
                await self.channel.send(embed=embed)

        self._reset_round_state()
        self.queue_next_round()
        print("[ROUND] No winner, round closed on timeout.")
