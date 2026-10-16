import discord
from discord import app_commands

from ui.embed_factory import EmbedFactory


@app_commands.command(
    name="sug",
    description="Send a suggestion without affecting the current round.",
)
@app_commands.describe(message="The suggestion or comment you want to send.")
async def suggest(interaction: discord.Interaction, message: str) -> None:
    channel = interaction.channel
    if channel is None or not isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
        await interaction.response.send_message(
            "Can't send a suggestion in this channel.", ephemeral=True
        )
        return

    embed = EmbedFactory.create_suggestion_embed(interaction.user.name, message)

    await channel.send(embed=embed)
    await interaction.response.send_message("Suggestion sent, the round is unaffected.", ephemeral=True)


def setup(bot: discord.Client) -> None:
    bot.tree.add_command(suggest)
