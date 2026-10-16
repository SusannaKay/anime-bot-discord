import discord
from discord import app_commands
from typing import Dict, List, Optional

from achievements.definitions import ACHIEVEMENTS
from ui.embed_factory import EmbedFactory


@app_commands.command(name="achievements", description="Show the badges an adventurer has unlocked.")
@app_commands.describe(user="The user whose progress to show (default: you).")
async def achievements(interaction: discord.Interaction, user: Optional[discord.User] = None) -> None:
    target = user or interaction.user
    db = getattr(interaction.client, "db", None)
    if db is None:
        await interaction.response.send_message("Database not available.", ephemeral=True)
        return

    cursor = db.conn.cursor()
    cursor.execute(
        """
        SELECT a.code, a.name, ua.timestamp
        FROM user_achievements ua
        JOIN achievements a ON ua.achievement_id = a.id
        WHERE ua.user_id = ?
        ORDER BY ua.timestamp ASC;
        """,
        (str(target.id),),
    )
    rows = cursor.fetchall()
    unlocked_map: Dict[str, dict] = {row["code"]: row for row in rows}

    unlocked_lines: List[str] = []
    locked_lines: List[str] = []
    for code, payload in ACHIEVEMENTS.items():
        name = payload.get("name", code)
        if code in unlocked_map:
            ts_label = EmbedFactory.format_datetime(unlocked_map[code]["timestamp"])
            unlocked_lines.append(f"✅ {name} — {ts_label}")
        else:
            locked_lines.append(f"⬜ {name}")

    embed = EmbedFactory.create_achievements_overview_embed(target.name, unlocked_lines, locked_lines)
    await interaction.response.send_message(embed=embed, ephemeral=False)


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(achievements)
