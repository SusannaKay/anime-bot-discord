import discord
from discord import app_commands

from ui.embed_factory import EmbedFactory


@app_commands.command(name="leaderboard", description="Show the card collectors leaderboard.")
async def leaderboard(interaction: discord.Interaction) -> None:
    db = getattr(interaction.client, "db", None)
    if db is None:
        await interaction.response.send_message("Database not available.", ephemeral=True)
        return

    cursor = db.conn.cursor()
    cursor.execute(
        """
        SELECT u.username, u.discord_id, COUNT(uc.id) AS total_cards
        FROM users u
        LEFT JOIN user_characters uc ON uc.user_id = u.id
        GROUP BY u.id
        ORDER BY total_cards DESC, u.username ASC
        LIMIT 10;
        """
    )
    rows = cursor.fetchall()

    entries = [(row["username"], row["total_cards"]) for row in rows]
    embed = EmbedFactory.create_leaderboard_embed(entries)

    await interaction.response.send_message(embed=embed, ephemeral=False)


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(leaderboard)
