import discord
from discord import app_commands
from pathlib import Path
from typing import Optional, Dict, List

from ui.embed_factory import EmbedFactory

IMAGES_ROOT = Path(__file__).resolve().parent.parent / "images"


def _resolve_image_path(file_path: str) -> Optional[Path]:
    candidate = Path(file_path)
    if candidate.is_file():
        return candidate
    nested = IMAGES_ROOT / file_path
    if nested.is_file():
        return nested
    matches = list(IMAGES_ROOT.rglob(Path(file_path).name))
    if matches:
        return matches[0]
    return None


@app_commands.command(name="stats", description="Show an adventurer's collection stats.")
@app_commands.describe(user="The user whose stats to show (default: you).")
async def stats(interaction: discord.Interaction, user: Optional[discord.User] = None) -> None:
    target = user or interaction.user
    db = getattr(interaction.client, "db", None)
    if db is None:
        await interaction.response.send_message("Database not available.", ephemeral=True)
        return

    user_row = db.get_user(str(target.id))
    if not user_row:
        embed = EmbedFactory.create_status_embed(
            {
                "title": f"📊 {target.name}'s chronicles",
                "description": "A magic scroll reveals your journey… but there are no cards yet.",
                "status": "warning",
            }
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
        return

    cursor = db.conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM user_characters uc
        JOIN users u ON uc.user_id = u.id
        WHERE u.discord_id = ?;
        """,
        (str(target.id),),
    )
    total = cursor.fetchone()["total"]

    if total == 0:
        embed = EmbedFactory.create_status_embed(
            {
                "title": f"📊 {target.name}'s chronicles",
                "description": "A magic scroll reveals your journey… but there are no cards yet.",
                "status": "warning",
            }
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
        return

    rarity_counts: Dict[str, int] = {"common": 0, "rare": 0, "epic": 0}
    cursor.execute(
        """
        SELECT r.name AS rarity, COUNT(*) AS cnt
        FROM user_characters uc
        JOIN users u ON uc.user_id = u.id
        JOIN images i ON uc.image_id = i.id
        JOIN rarities r ON i.rarity_id = r.id
        WHERE u.discord_id = ?
        GROUP BY r.name;
        """,
        (str(target.id),),
    )
    for row in cursor.fetchall():
        rarity_counts[row["rarity"].lower()] = row["cnt"]

    cursor.execute(
        """
        SELECT c.anime AS anime, COUNT(*) AS cnt
        FROM user_characters uc
        JOIN users u ON uc.user_id = u.id
        JOIN images i ON uc.image_id = i.id
        JOIN characters c ON i.character_id = c.id
        WHERE u.discord_id = ?
        GROUP BY c.anime
        ORDER BY cnt DESC
        LIMIT 5;
        """,
        (str(target.id),),
    )
    top_anime_rows = cursor.fetchall()

    cursor.execute(
        """
        SELECT c.id AS character_id, c.name AS character_name, c.anime AS character_anime,
               r.name AS rarity, uc.obtained_at AS obtained_at,
               i.id AS image_id, i.file_path
        FROM user_characters uc
        JOIN users u ON uc.user_id = u.id
        JOIN images i ON uc.image_id = i.id
        JOIN characters c ON i.character_id = c.id
        JOIN rarities r ON i.rarity_id = r.id
        WHERE u.discord_id = ?
        ORDER BY uc.obtained_at DESC
        LIMIT 5;
        """,
        (str(target.id),),
    )
    recent_rows: List[dict] = [dict(row) for row in cursor.fetchall()]
    recent_lines = [
        f"{row['character_name']} ({row['rarity'].title()}) — "
        f"{EmbedFactory.format_datetime(row['obtained_at'])}"
        for row in recent_rows
    ]
    card_image_path: Optional[Path] = None
    if recent_rows:
        first = recent_rows[0]
        card_image_path = _resolve_image_path(first.get("file_path", ""))
    stats_payload = {
        "total_cards": total,
        "common": rarity_counts.get("common", 0),
        "rare": rarity_counts.get("rare", 0),
        "epic": rarity_counts.get("epic", 0),
        "top_anime": [f"{row['anime']} ({row['cnt']})" for row in top_anime_rows] if top_anime_rows else [],
        "recent_cards": recent_lines if recent_lines else [],
    }

    embed = EmbedFactory.create_stats_embed(target.name, stats_payload)
    file = None
    if card_image_path and card_image_path.is_file():
        file = discord.File(str(card_image_path), filename=card_image_path.name)
        embed.set_image(url=f"attachment://{card_image_path.name}")

    if file:
        await interaction.response.send_message(embed=embed, file=file, ephemeral=False)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=False)


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(stats)
