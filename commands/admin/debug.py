import discord
from discord import app_commands
from discord.app_commands import Choice

from . import mod_only
from ui.embed_factory import EmbedFactory


def _get_round_manager(interaction: discord.Interaction):
    rm = getattr(interaction.client, "round_manager", None)
    if not rm:
        raise RuntimeError("RoundManager not available.")
    return rm


@app_commands.choices(
    mode=[
        Choice(name="on", value="on"),
        Choice(name="off", value="off"),
    ]
)
@mod_only()
@app_commands.command(name="dbg", description="Turn the bot's debug mode on or off.")
async def debug(interaction: discord.Interaction, mode: Choice[str]) -> None:
    try:
        rm = _get_round_manager(interaction)
    except RuntimeError as exc:
        await interaction.response.send_message(str(exc), ephemeral=True)
        return

    if mode.value == "on":
        rm.enable_debug()
        rm.cancel_scheduled_round()
        if hasattr(rm, "cancel_round_timeout"):
            rm.cancel_round_timeout()
        if hasattr(rm, "_reset_round_state"):
            rm._reset_round_state()
        await rm.start_round()
        rm.queue_next_round()

        embed = EmbedFactory.create_status_embed(
            {
                "title": "🐞 Debug Mode On",
                "description": "Rounds will now follow each other every few seconds.",
                "status": "warning",
            }
        )
    else:
        rm.disable_debug()
        embed = EmbedFactory.create_status_embed(
            {
                "title": "🐞 Debug Mode Off",
                "description": (
                    "Back to normal behaviour "
                    f"({rm.min_delay_seconds // 60}–{rm.max_delay_seconds // 60} minutes between rounds)."
                ),
                "status": "success",
            }
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(debug)
