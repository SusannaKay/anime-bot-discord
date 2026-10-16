import discord
from discord import app_commands

from . import mod_only
from ui.embed_factory import EmbedFactory


def _get_round_manager(interaction: discord.Interaction):
    rm = getattr(interaction.client, "round_manager", None)
    if not rm:
        raise RuntimeError("RoundManager not available.")
    return rm


@mod_only()
@app_commands.command(name="stop", description="Stop the round loop.")
async def stop(interaction: discord.Interaction) -> None:
    try:
        rm = _get_round_manager(interaction)
    except RuntimeError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    rm.current_round_active = False
    rm.cancel_scheduled_round()
    if hasattr(rm, "cancel_round_timeout"):
        rm.cancel_round_timeout()

    embed = EmbedFactory.create_status_embed(
        {
            "title": "⛔ Summoning paused",
            "description": "The mystic flow calms down. No new round will be summoned until you start it again.",
            "status": "warning",
        }
    )
    await interaction.response.send_message(embed=embed, ephemeral=False)


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(stop)
