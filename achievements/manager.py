from __future__ import annotations

import asyncio
from typing import Dict, Optional

import discord

from achievements.definitions import ACHIEVEMENTS
from ui.embed_factory import EmbedFactory


class AchievementManager:
    """Handles achievement unlock logic and notifications."""

    def __init__(self, db, bot: Optional[discord.Client] = None) -> None:
        self.db = db
        self.bot = bot

    # ===========================
    # Public API
    # ===========================
    def record_guess(self, user_id: str, is_correct: bool) -> None:
        """Records a guess, updating counters and the fail streak."""
        self._ensure_user(user_id)
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET
                total_guesses = COALESCE(total_guesses, 0) + 1,
                fail_streak = CASE WHEN ? THEN 0 ELSE COALESCE(fail_streak, 0) + 1 END
            WHERE discord_id = ?;
            """,
            (1 if is_correct else 0, user_id),
        )
        self.db.conn.commit()
        self.check_all(user_id)

    def record_win(self, user_id: str, character_id: Optional[int], rarity: Optional[str]) -> None:
        """Records a win and checks every achievement."""
        self._ensure_user(user_id)
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            UPDATE users
            SET
                win_count = COALESCE(win_count, 0) + 1,
                total_cards_obtained = COALESCE(total_cards_obtained, 0) + 1,
                fail_streak = 0
            WHERE discord_id = ?;
            """,
            (user_id,),
        )
        self.db.conn.commit()
        self.check_all(user_id)

    def check_all(self, user_id: str) -> None:
        """Checks and grants every achievement based on the current state."""
        user = self.db.get_user(user_id)
        if not user:
            return

        cursor = self.db.conn.cursor()

        # Global totals, needed for COMPLETIONIST and ANIME_EXPLORER
        cursor.execute("SELECT COUNT(DISTINCT id) AS total FROM characters;")
        total_characters = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(DISTINCT anime) AS total FROM characters;")
        total_anime = cursor.fetchone()["total"]

        # Distinct characters/anime owned by the user
        cursor.execute(
            """
            SELECT COUNT(DISTINCT c.id) AS total
            FROM user_characters uc
            JOIN users u ON uc.user_id = u.id
            JOIN images i ON uc.image_id = i.id
            JOIN characters c ON i.character_id = c.id
            WHERE u.discord_id = ?;
            """,
            (user_id,),
        )
        user_characters = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(DISTINCT c.anime) AS total
            FROM user_characters uc
            JOIN users u ON uc.user_id = u.id
            JOIN images i ON uc.image_id = i.id
            JOIN characters c ON i.character_id = c.id
            WHERE u.discord_id = ?;
            """,
            (user_id,),
        )
        user_anime = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT 1
            FROM user_characters uc
            JOIN users u ON uc.user_id = u.id
            JOIN images i ON uc.image_id = i.id
            JOIN rarities r ON i.rarity_id = r.id
            WHERE u.discord_id = ? AND LOWER(r.name) = 'epic'
            LIMIT 1;
            """,
            (user_id,),
        )
        has_epic = cursor.fetchone() is not None

        conditions: Dict[str, bool] = {
            "FIRST_WIN": (user["win_count"] or 0) >= 1,
            "TEN_WINS": (user["win_count"] or 0) >= 10,
            "EPIC_HUNTER": has_epic,
            "OTAKU": (user["total_cards_obtained"] or 0) >= 100,
            "SNAIL": (user["fail_streak"] or 0) >= 20,
            "COMPLETIONIST": total_characters > 0 and user_characters >= total_characters,
            "ANIME_EXPLORER": total_anime > 0 and user_anime >= total_anime,
        }

        for code, unlocked in conditions.items():
            if unlocked:
                self.grant(user_id, code)

    def grant(self, user_id: str, code: str) -> None:
        """Grants an achievement if not already owned and sends the celebration embed."""
        if self.user_has(user_id, code):
            return

        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, name FROM achievements WHERE code = ?;", (code,))
        achievement_row = cursor.fetchone()
        if not achievement_row:
            # Insert the missing achievement from the definitions.
            name = ACHIEVEMENTS.get(code, {}).get("name", code)
            cursor.execute(
                "INSERT OR IGNORE INTO achievements (code, name) VALUES (?, ?);",
                (code, name),
            )
            self.db.conn.commit()
            cursor.execute("SELECT id, name FROM achievements WHERE code = ?;", (code,))
            achievement_row = cursor.fetchone()
            if not achievement_row:
                return

        cursor.execute(
            """
            INSERT OR IGNORE INTO user_achievements (user_id, achievement_id)
            VALUES (?, ?);
            """,
            (user_id, achievement_row["id"]),
        )
        self.db.conn.commit()

        username = self._get_username(user_id) or user_id
        embed = EmbedFactory.create_achievement_unlocked_embed(username, achievement_row["name"])
        asyncio.create_task(self._send_achievement_embed(embed))

    def user_has(self, user_id: str, code: str) -> bool:
        """Checks whether the user already owns a specific achievement."""
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM user_achievements ua
            JOIN achievements a ON ua.achievement_id = a.id
            WHERE ua.user_id = ? AND a.code = ?
            LIMIT 1;
            """,
            (user_id, code),
        )
        return cursor.fetchone() is not None

    # ===========================
    # Helpers
    # ===========================
    def _ensure_user(self, user_id: str) -> None:
        existing = self.db.get_user(user_id)
        if not existing:
            # Username unknown here; it gets updated elsewhere when available.
            self.db.create_or_get_user(user_id, user_id)

    def _get_username(self, user_id: str) -> Optional[str]:
        user = self.db.get_user(user_id)
        return user["username"] if user else None

    async def _send_achievement_embed(self, embed: discord.Embed) -> None:
        """Sends the embed to the round channel, if available."""
        if not self.bot:
            return

        channel = getattr(getattr(self.bot, "round_manager", None), "channel", None)
        if not channel:
            return
        try:
            await channel.send(embed=embed)
        except Exception:
            # Don't break the flow if sending fails.
            return
