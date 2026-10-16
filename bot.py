"""Main entrypoint of the Discord bot: loads commands and the round manager, then starts the bot."""

import asyncio
import importlib.util
import os
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from achievements import AchievementManager
from database import Database
from round_manager import RoundManager
import event_handlers


# ==========================================
# Config and environment variables
# ==========================================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID_RAW = os.getenv("ROUND_CHANNEL_ID")
DB_PATH = os.getenv("DB_PATH", "bot.db")

if not TOKEN:
    raise SystemExit("DISCORD_TOKEN is missing from .env")

if not CHANNEL_ID_RAW:
    raise SystemExit("ROUND_CHANNEL_ID is missing from .env")

try:
    CHANNEL_ID = int(CHANNEL_ID_RAW)
except ValueError as exc:
    raise SystemExit("ROUND_CHANNEL_ID must be an integer.") from exc


def _env_minutes(name: str, default: int) -> int:
    """Reads an optional env variable expressed in minutes and returns seconds."""
    raw = os.getenv(name)
    if not raw:
        return default * 60
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer (minutes).") from exc
    if value < 1:
        raise SystemExit(f"{name} must be at least 1 minute.")
    return value * 60


ROUND_MIN_DELAY = _env_minutes("ROUND_MIN_DELAY_MINUTES", 5)
ROUND_MAX_DELAY = _env_minutes("ROUND_MAX_DELAY_MINUTES", 30)
ROUND_TIMEOUT = _env_minutes("ROUND_TIMEOUT_MINUTES", 10)


# ==========================================
# Bot and database setup
# ==========================================
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.db = Database(DB_PATH)
bot.achievements = AchievementManager(bot.db, bot)


# ==========================================
# Dynamic command loading
# ==========================================
def load_command_modules(bot_instance: commands.Bot) -> int:
    """Scans commands/ (subfolders included) and registers every module that has setup()."""
    commands_dir = Path(__file__).parent / "commands"
    if not commands_dir.exists():
        print("[WARN] commands/ folder not found, no commands loaded.")
        return 0

    loaded = 0
    for file in commands_dir.rglob("*.py"):
        if file.name.startswith("__"):
            continue
        rel_parts = file.relative_to(commands_dir).with_suffix("").parts
        module_name = ".".join(("commands",) + rel_parts)
        try:
            spec = importlib.util.spec_from_file_location(module_name, file)
            if not spec or not spec.loader:
                print(f"[CMD][SKIP] {module_name}: invalid spec")
                continue

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if hasattr(module, "setup"):
                module.setup(bot_instance)
                loaded += 1
                print(f"[CMD][OK] {module_name} loaded")
            else:
                print(f"[CMD][SKIP] {module_name}: no setup function")
        except Exception as exc:  # noqa: BLE001
            print(f"[CMD][ERR] {module_name}: {exc}")
    return loaded


# ==========================================
# Round Manager, commands and event handlers
# ==========================================
command_count = load_command_modules(bot)
print(f"[INIT] Commands loaded: {command_count}")

round_manager = RoundManager(
    bot,
    channel_id=CHANNEL_ID,
    db=bot.db,
    achievement_manager=bot.achievements,
    min_delay_seconds=ROUND_MIN_DELAY,
    max_delay_seconds=ROUND_MAX_DELAY,
    round_timeout_seconds=ROUND_TIMEOUT,
)
event_handlers.setup_event_handlers(bot, round_manager)
print("[INIT] Round Manager ready")
bot.round_manager = round_manager  # type: ignore[attr-defined]
bot._ready_ran = False  # type: ignore[attr-defined]


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
    """Handles slash command errors with clear messages."""
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "You need moderator permissions to run this command.", ephemeral=True
        )
        return
    raise error


@bot.event
async def on_ready() -> None:
    if getattr(bot, "_ready_ran", False):  # type: ignore[attr-defined]
        print(f"[READY] Bot reconnected as {bot.user}")
        return

    # Round channel
    round_manager.channel = bot.get_channel(CHANNEL_ID)
    if round_manager.channel:
        print(f"[READY] Round channel: #{round_manager.channel.name}")
    else:
        print(f"[WARN] Channel with ID {CHANNEL_ID} not found.")

    # Sync commands
    try:
        synced = await bot.tree.sync()
        print(f"[SYNC] Global slash commands synced: {len(synced)}")
    except Exception as exc:  # noqa: BLE001
        print(f"[SYNC][ERR] Global sync failed: {exc}")
        synced = []

    for guild in bot.guilds:
        try:
            guild_synced = await bot.tree.sync(guild=guild)
            print(f"[SYNC] {guild.name} ({guild.id}): {len(guild_synced)} commands synced")
        except Exception as exc:  # noqa: BLE001
            print(f"[SYNC][ERR] Sync failed for guild {guild.id}: {exc}")

    print(f"[READY] Bot online as {bot.user}")

    # First round and scheduler
    await round_manager.start_round()
    round_manager.queue_next_round()
    print("[READY] First round started")

    bot._ready_ran = True  # type: ignore[attr-defined]


if __name__ == "__main__":
    bot.run(TOKEN)
