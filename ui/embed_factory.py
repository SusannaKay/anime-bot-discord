from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import discord

AUTHOR_ICON = "https://i.imgur.com/VQbM8eF.png"
AUTHOR_NAME = "Astral Chronicler"
FOOTER_TEXT = "AnimeCard Bot • Powered by astral energy"

RARITY_COLORS: Dict[str, int] = {
    "common": 0x4CAF50,
    "rare": 0x2196F3,
    "epic": 0x9C27B0,
}

# Twemoji PNG URLs for each rarity (lightweight, stable icons)
RARITY_ICONS: Dict[str, str] = {
    "common": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f343.png",  # leaf
    "rare": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f31f.png",  # glowing star
    "epic": "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f52e.png",  # crystal ball
}

ACHIEVEMENT_ICON = "https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f3c6.png"  # trophy


class EmbedFactory:
    """Central factory for themed, consistent embeds."""

    @staticmethod
    def _base_embed(
        title: str,
        description: str,
        color: Optional[int] = None,
        *,
        thumbnail_url: Optional[str] = None,
        footer_extra: Optional[str] = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=title,
            description=description,
            color=color or 0x2196F3,
            timestamp=datetime.utcnow(),
        )
        embed.set_author(name=AUTHOR_NAME, icon_url=AUTHOR_ICON)
        footer_text = FOOTER_TEXT if not footer_extra else f"{footer_extra} • {FOOTER_TEXT}"
        embed.set_footer(text=footer_text)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        return embed

    @staticmethod
    def _color_for_rarity(rarity_name: Optional[str]) -> int:
        return RARITY_COLORS.get((rarity_name or "").lower(), 0x2196F3)

    @staticmethod
    def _icon_for_rarity(rarity_name: Optional[str]) -> Optional[str]:
        return RARITY_ICONS.get((rarity_name or "").lower())

    @staticmethod
    def format_datetime(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.strftime("%d %b %Y, %H:%M")
        except Exception:
            return value

    @staticmethod
    def create_round_embed(character_name: str, rarity_name: str, image_path: str) -> discord.Embed:
        rarity_label = (rarity_name or "Unknown").title()
        embed = EmbedFactory._base_embed(
            title="🔮 New Round!",
            description=(
                "A card of astral energy emerges from the portal…\n"
                f"Rarity: **{rarity_label}**\n"
                "Guess the character!"
            ),
            color=EmbedFactory._color_for_rarity(rarity_name),
            thumbnail_url=EmbedFactory._icon_for_rarity(rarity_name),
        )
        embed.add_field(name="Summoned aura", value=f"??? ({rarity_label})", inline=True)
        embed.set_image(url=f"attachment://{Path(image_path).name}")
        return embed

    @staticmethod
    def create_victory_embed(username: str, character_name: str, rarity_name: str) -> discord.Embed:
        rarity_label = (rarity_name or "Unknown").title()
        embed = EmbedFactory._base_embed(
            title=f"🏆 {username} wins!",
            description=(
                "The energy of the multiverse smiles upon you.\n"
                f"You claimed the **{character_name}** card!"
            ),
            color=EmbedFactory._color_for_rarity(rarity_name),
            thumbnail_url=EmbedFactory._icon_for_rarity(rarity_name),
        )
        embed.add_field(name="Rarity", value=rarity_label, inline=True)
        embed.add_field(name="Chronicle", value="The portal closes… until a new card emerges.", inline=False)
        return embed

    @staticmethod
    def create_round_timeout_embed(character_name: str, rarity_name: str, timeout_minutes: int = 10) -> discord.Embed:
        rarity_label = (rarity_name or "Unknown").title()
        embed = EmbedFactory._base_embed(
            title="⏳ The portal falls silent",
            description=(
                "No adventurer solved the mystery in time.\n"
                f"The **{character_name}** card ({rarity_label}) dissolves into astral sparks."
            ),
            color=0xF1C40F,
            thumbnail_url=EmbedFactory._icon_for_rarity(rarity_name),
        )
        embed.add_field(name="Outcome", value=f"Round closed on timeout ({timeout_minutes} minutes)", inline=False)
        embed.add_field(name="Next portal", value="A new round will be summoned soon.", inline=False)
        return embed

    @staticmethod
    def create_pool_page_embed(username: str, card_info: Dict[str, str]) -> discord.Embed:
        rarity = card_info.get("rarity")
        rarity_label = (rarity or "Unknown").title()
        page_label = card_info.get("page_label")
        embed = EmbedFactory._base_embed(
            title=f"📜 {username}'s collection",
            description="The grimoire turns a glowing page of your conquests.",
            color=EmbedFactory._color_for_rarity(rarity),
            thumbnail_url=EmbedFactory._icon_for_rarity(rarity),
            footer_extra=page_label,
        )
        embed.add_field(name="Character", value=card_info.get("character_name", "Unknown"), inline=True)
        embed.add_field(name="Anime", value=card_info.get("character_anime", "??"), inline=True)
        embed.add_field(name="Rarity", value=rarity_label, inline=True)

        obtained_at = card_info.get("obtained_at")
        if obtained_at:
            embed.add_field(
                name="Obtained on",
                value=EmbedFactory.format_datetime(obtained_at),
                inline=False,
            )

        file_path = card_info.get("file_path", "")
        if file_path:
            embed.set_image(url=f"attachment://{Path(file_path).name}")
        return embed

    @staticmethod
    def create_leaderboard_embed(entries: Sequence[Tuple[str, int]]) -> discord.Embed:
        embed = EmbedFactory._base_embed(
            title="🏆 Astral Leaderboard",
            description="The bravest heroes who unveiled the mysteries of the astral cards.",
            color=0x2196F3,
        )
        if not entries:
            embed.add_field(
                name="Silence in the hall",
                value="No adventurer has collected any cards yet.",
                inline=False,
            )
            return embed

        lines: List[str] = []
        medals = ["🥇", "🥈", "🥉"]
        for idx, (username, count) in enumerate(entries, 1):
            medal = medals[idx - 1] if idx <= len(medals) else ""
            label = f"#{idx}"
            prefix = f"{medal} {label}".strip()
            lines.append(f"{prefix} {username} — **{count}** cards")
        embed.add_field(name="Top Collectors", value="\n".join(lines), inline=False)
        return embed

    @staticmethod
    def create_stats_embed(username: str, stats: Dict[str, object]) -> discord.Embed:
        embed = EmbedFactory._base_embed(
            title=f"📊 {username}'s chronicles",
            description="A magic scroll reveals your journey…",
            color=0x2196F3,
        )
        embed.add_field(name="Total cards", value=str(stats.get("total_cards", 0)), inline=True)
        embed.add_field(name="Common", value=str(stats.get("common", 0)), inline=True)
        embed.add_field(name="Rare", value=str(stats.get("rare", 0)), inline=True)
        embed.add_field(name="Epic", value=str(stats.get("epic", 0)), inline=True)

        top_anime: Iterable[str] = stats.get("top_anime", [])
        anime_value = ", ".join(top_anime) if top_anime else "None"
        embed.add_field(name="Most collected anime", value=anime_value, inline=False)

        recent_cards: Iterable[str] = stats.get("recent_cards", [])
        recent_value = "\n".join(recent_cards) if recent_cards else "No recent cards."
        embed.add_field(name="Latest cards", value=recent_value, inline=False)
        return embed

    @staticmethod
    def create_achievement_unlocked_embed(username: str, achievement_name: str) -> discord.Embed:
        """Celebration embed for an unlocked achievement."""
        return EmbedFactory._base_embed(
            title="🏆 Achievement Unlocked!",
            description=f"{username} unlocked **{achievement_name}**!",
            color=0xF1C40F,
            thumbnail_url=ACHIEVEMENT_ICON,
        )

    @staticmethod
    def create_achievements_overview_embed(
        username: str, unlocked_lines: Iterable[str], locked_lines: Iterable[str]
    ) -> discord.Embed:
        embed = EmbedFactory._base_embed(
            title=f"🎖️ {username}'s archive",
            description="The tome lists the milestones reached and those still to conquer.",
            color=0xF1C40F,
            thumbnail_url=ACHIEVEMENT_ICON,
        )
        unlocked_value = "\n".join(unlocked_lines) if unlocked_lines else "No achievements unlocked."
        locked_value = "\n".join(locked_lines) if locked_lines else "You've got them all! ⭐️"
        embed.add_field(name="Unlocked", value=unlocked_value, inline=False)
        embed.add_field(name="Locked", value=locked_value, inline=False)
        return embed

    @staticmethod
    def create_suggestion_embed(author: str, text: str) -> discord.Embed:
        embed = EmbedFactory._base_embed(
            title=f"💬 A whisper from {author}",
            description=text,
            color=0x9C27B0,
        )
        embed.add_field(
            name="Narrator's note",
            value="Suggestions don't change the fate of the current round.",
            inline=False,
        )
        return embed

    @staticmethod
    def create_status_embed(state_info: Dict[str, object]) -> discord.Embed:
        title = state_info.get("title", "📟 System Status")
        description = state_info.get(
            "description",
            "A crystal lens reveals the bot's arcane flows…",
        )
        status = state_info.get("status", "info")
        colors = {
            "success": 0x4CAF50,
            "info": 0x2196F3,
            "warning": 0xF1C40F,
            "error": 0xE74C3C,
        }
        color = state_info.get("color") or colors.get(str(status).lower(), 0x2196F3)
        embed = EmbedFactory._base_embed(
            title=str(title),
            description=str(description),
            color=color,
            thumbnail_url=state_info.get("thumbnail"),  # type: ignore[arg-type]
        )

        fields: Iterable[Tuple[str, str, bool]] = state_info.get("fields", [])
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
        return embed
