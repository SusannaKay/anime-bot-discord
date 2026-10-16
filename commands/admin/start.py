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
@app_commands.command(name="start", description="Manually start a new round.")
async def start(interaction: discord.Interaction) -> None:
    try:
        rm = _get_round_manager(interaction)
    except RuntimeError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    if rm.current_round_active:
        await interaction.response.send_message(
            "A portal is already open… you can't summon two cards at once.",
            ephemeral=True,
        )
        return

    await rm.start_round()
    rm.queue_next_round()

    embed = EmbedFactory.create_status_embed(
        {
            "title": "▶️ Summoning Started",
            "description": "A new energy gathers… the round begins!",
            "status": "success",
        }
    )
    await interaction.response.send_message(embed=embed, ephemeral=False)


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(start)
