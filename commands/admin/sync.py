import discord
from discord import app_commands

from . import mod_only


@mod_only()
@app_commands.command(name="sync_commands", description="Sync the slash commands in the current server.")
async def sync_commands(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return

    try:
        synced = await interaction.client.tree.sync(guild=guild)
    except Exception as exc:  # noqa: BLE001
        await interaction.response.send_message(f"Sync failed: {exc}", ephemeral=True)
        return

    await interaction.response.send_message(
        f"Sync completed in {guild.name}: {len(synced)} commands registered.", ephemeral=True
    )


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(sync_commands)
