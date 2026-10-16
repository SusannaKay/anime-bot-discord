import discord


def setup_event_handlers(bot: discord.Client, round_manager) -> None:
    """Registers the Discord event handlers and connects them to the round manager.

    on_ready lives in bot.py, because it also syncs the slash commands.
    """

    @bot.event
    async def on_message(message: discord.Message) -> None:
        # Only handle messages in the round channel.
        if getattr(message.channel, "id", None) != getattr(round_manager, "channel_id", None):
            return

        await round_manager.check_guess(message)

        # Keep any text command extensions working.
        if hasattr(bot, "process_commands"):
            await bot.process_commands(message)
