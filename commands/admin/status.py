import discord
from discord import app_commands
from datetime import datetime

from . import mod_only
from ui.embed_factory import EmbedFactory


def _get_round_manager(interaction: discord.Interaction):
    rm = getattr(interaction.client, "round_manager", None)
    if not rm:
        raise RuntimeError("RoundManager not available.")
    return rm


def _format_eta(rm) -> str:
    if rm.next_round_eta:
        remaining = rm.next_round_eta - datetime.utcnow()
        if remaining.total_seconds() > 0:
            minutes, seconds = divmod(int(remaining.total_seconds()), 60)
            return f"{minutes}m {seconds}s"
    return "Not scheduled"


@mod_only()
@app_commands.command(name="status", description="Show the current Round Manager state (visible only to you).")
async def status(interaction: discord.Interaction) -> None:
    try:
        rm = _get_round_manager(interaction)
    except RuntimeError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    active = "Yes" if rm.current_round_active else "No"
    eta = _format_eta(rm)

    fields = [
        ("Round active", active, True),
        ("Character", rm.current_character_name or "N/A", True),
        ("Rarity", (rm.current_rarity or "N/A"), True),
        ("Image", rm.current_image_path or "N/A", False),
        ("Next round in", eta, True),
    ]

    embed = EmbedFactory.create_status_embed(
        {
            "title": "📟 Current Bot Status",
            "description": "A crystal lens reveals the bot's arcane flows…",
            "status": "info",
            "fields": fields,
        }
    )

    # Ephemeral: the embed contains the answer of the current round.
    await interaction.response.send_message(embed=embed, ephemeral=True)


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(status)
