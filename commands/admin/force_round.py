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
@app_commands.command(name="force_round", description="Force the current round to close and a new one to start right away.")
async def force_round(interaction: discord.Interaction) -> None:
    try:
        rm = _get_round_manager(interaction)
    except RuntimeError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    # Cancel timers and reset the current state
    rm.cancel_scheduled_round()
    if hasattr(rm, "_reset_round_state"):
        rm._reset_round_state()
    else:
        if hasattr(rm, "cancel_round_timeout"):
            rm.cancel_round_timeout()
        rm.current_round_active = False
        rm.current_character_id = None
        rm.current_character_name = None
        rm.current_rarity = None
        rm.current_image_id = None
        rm.current_image_path = None
        rm.current_anime = None

    await rm.start_round()
    rm.queue_next_round()

    embed = EmbedFactory.create_status_embed(
        {
            "title": "⚡ Round forced",
            "description": "The future is rewritten! A new round appears instantly.",
            "status": "success",
        }
    )
    await interaction.response.send_message(embed=embed, ephemeral=False)


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(force_round)
