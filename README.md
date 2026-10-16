# Anime Card Bot

A Discord bot that turns a channel into an anime guessing game.

Every now and then the bot drops a character card in the channel. The first person who types the right name wins the card and adds it to their collection. Cards have rarities, there's a leaderboard, and there are achievements for the truly dedicated (and for the truly unlucky).

I built it for a server of friends who argue way too much about anime. It ran for a while on an old Raspberry Pi inside Docker. It's retired now, so it's here in case you want your own.

---

## Features

- **Automatic rounds**: a random character appears every 5–30 minutes (configurable)
- **Guess by typing**: no commands needed, just write the name in the channel
- **Timeout**: if nobody guesses in 10 minutes, the card dissolves and the answer is revealed
- **Rarities**: common, rare and epic, each with its own color and icon
- **Collections**: browse your cards page by page with `/pool`
- **Stats and leaderboard**: who has the most cards, which anime you collect the most
- **Achievements**: unlocked automatically and announced in the channel
- **Mod commands**: start, stop, force a round, check status, debug mode

---

## Run your own bot

Six steps, about 15 minutes plus the time the image download takes.

### 1. Create the bot on Discord

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) and create a new application.
2. In **Bot**, click **Reset Token** and copy it. This is your `DISCORD_TOKEN`: treat it like a password.
3. Still in **Bot**, turn on **Message Content Intent**. Without it the bot can't read the guesses, and you'll spend an hour wondering why nobody ever wins. Ask me how I know.
4. In **OAuth2 → URL Generator**, select the scopes `bot` and `applications.commands`, and these permissions: *Send Messages*, *Embed Links*, *Attach Files*, *Read Message History*.
5. Open the generated URL and invite the bot to your server.

### 2. Install

You need Python 3.11+.

```bash
git clone https://github.com/SusannaKay/anime-bot-discord.git
cd anime-bot-discord
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows the activation command is `.venv\Scripts\activate`, and `python` instead of `python3`.

### 3. Configure

```bash
cp .env.example .env
```

Then open `.env` and fill in `DISCORD_TOKEN` and `ROUND_CHANNEL_ID`.

To get the channel ID: in Discord go to *Settings → Advanced* and turn on *Developer Mode*, then right click the channel → *Copy Channel ID*.

### 4. Load the characters

The repo comes with a list of about 320 characters from 69 anime in `data/characters.txt`. Import it into the database:

```bash
python3 scripts/import_characters.py data/characters.txt
```

### 5. Download the images

Images are **not** included in the repo (they're fan art and official art from the internet, not mine to redistribute). The scraper downloads one image per character from Bing:

```bash
python3 scripts/scrape_images.py
```

It takes a while: it waits 1–2 seconds between characters to be polite. Images end up in `images/<Anime>/<character_name>.jpg`.

The scraper takes the first decent result, so a few images will come out wrong (a different character, a weird crop, a meme). To redo one, delete the file, reset that character in the database and run the script again. It only processes characters without an image:

```bash
rm "images/Berserk/guts.jpg"
sqlite3 bot.db "UPDATE characters SET image_path = NULL WHERE name = 'Guts';"
python3 scripts/scrape_images.py
```

If you'd rather use your own picture, just overwrite the downloaded file, keeping the same path and name: the bot will use the new one.

### 6. Run

```bash
python3 bot.py
```

The first round starts as soon as the bot is online.

Slash commands can take a minute to show up the first time. If they don't appear at all, run `/sync_commands` or restart Discord.

### Troubleshooting

| Problem | Fix |
| ------- | --- |
| `DISCORD_TOKEN is missing from .env` | You skipped step 3, or `.env` is not in the folder you're running the bot from |
| The bot posts rounds but nobody ever wins | Message Content Intent is off (step 1.3) |
| `Channel with ID ... not found` | Wrong `ROUND_CHANNEL_ID`, or the bot can't see that channel |
| `No characters available to start a round` | You skipped step 4 |
| `No image found for ...` | You skipped step 5, or the scraper failed for that character |
| Mod commands say you need permissions | See [who counts as a mod](#for-mods) |

---

## Running with Docker

```bash
docker compose up -d --build
```

The whole folder is mounted inside the container, so the database and the images stay on your machine and survive rebuilds. Steps 4 and 5 still need to be done once, on the host.

To update after pulling new changes:

```bash
git pull
docker compose up -d --build
```

---

## Configuration

Everything lives in `.env`:

| Variable | Required | Default | What it does |
| -------- | -------- | ------- | ------------ |
| `DISCORD_TOKEN` | yes | | Bot token |
| `ROUND_CHANNEL_ID` | yes | | Channel where rounds happen |
| `DB_PATH` | no | `bot.db` | Path of the SQLite database |
| `ROUND_MIN_DELAY_MINUTES` | no | `5` | Minimum wait between rounds |
| `ROUND_MAX_DELAY_MINUTES` | no | `30` | Maximum wait between rounds |
| `ROUND_TIMEOUT_MINUTES` | no | `10` | How long a round stays open |

The wait between rounds is random, somewhere between the minimum and the maximum. It keeps people checking the channel.

---

## Commands

### For everyone

| Command | What it does |
| ------- | ------------ |
| `/pool [user]` | Browse a card collection, with buttons to flip the pages |
| `/stats [user]` | Total cards, cards per rarity, favourite anime, latest cards |
| `/leaderboard` | Top 10 collectors |
| `/achievements [user]` | Unlocked and locked achievements |
| `/sug <message>` | Post a comment in the channel without it counting as a guess |

To guess, you don't need a command: just type the name in the round channel.

### For mods

| Command | What it does |
| ------- | ------------ |
| `/start` | Start a round now |
| `/stop` | Stop the round loop |
| `/force_round` | Close the current round and start a new one immediately |
| `/reset_session` | Reset the in-memory state (the database is not touched) |
| `/status` | Current round, answer included, and time until the next one. Only you can see the reply |
| `/dbg on\|off` | Debug mode: a new round every few seconds, handy for testing |
| `/sync_commands` | Re-sync the slash commands in the current server |

Who counts as a mod: anyone with *Administrator*, *Manage Server*, *Manage Messages* or *Timeout Members*, or anyone with a role that has "mod" in its name.

---

## Achievements

| Achievement | How to get it |
| ----------- | ------------- |
| 🏅 First Win | Win your first round |
| 🔥 10 Wins | Win 10 rounds |
| 💎 Epic Hunter | Get an epic card |
| 🤓 Walking Otaku Encyclopedia | Collect 100 cards |
| 🐌 Snail Mode | Get 20 wrong guesses in a row (it's an achievement, not a judgement) |
| 🌟 Absolute Completionist | Own every character |
| 🗺️ Anime Explorer | Own at least one character from every anime |

They're defined in `achievements/definitions.py`, and the unlock conditions are in `achievements/manager.py`.

---

## Adding your own characters

Edit `data/characters.txt`. One line per anime and rarity:

```text
Delicious in Dungeon -- common -- Laios Touden, Marcille Donato
Delicious in Dungeon -- rare -- Chilchuck Tims
Delicious in Dungeon -- epic -- Senshi
```

Then import again and download the missing images:

```bash
python3 scripts/import_characters.py data/characters.txt
python3 scripts/scrape_images.py
```

Characters that are already in the database are skipped, so you can run the import as many times as you want without touching the cards people already own.

The rarity belongs to the character, not to the round: Senshi is always epic. Characters are picked at random, so how often each rarity shows up depends only on how many characters you put in each one. With the default list it's roughly 4 common, 3 rare and 2 epic out of every 9 rounds, so if you want epics to feel special, keep that list short.

---

## How it works

```text
bot.py
 ├── Database            SQLite: users, characters, images, cards, achievements
 ├── AchievementManager  counts guesses and wins, unlocks achievements
 └── RoundManager
      ├── start_round    random character → embed with the image in the channel
      ├── check_guess    every message in the channel is compared with the answer
      ├── close_round    winner gets the card → next round is scheduled
      └── timeout        no winner in time → answer revealed → next round
```

- `bot.py` reads `.env`, creates the bot and loads every module in `commands/` automatically.
- `round_manager.py` is the heart of the game: rounds, scheduler and timeout.
- `ui/embed_factory.py` builds every embed, so the style stays the same everywhere.
- `commands/` has one file per slash command. To add a new one, create a file with a `setup(bot)` function and it gets loaded at startup.

The guess has to match the character name exactly. Upper/lower case and extra spaces don't matter, but accents and spelling do.

---

## Project structure

```text
.
├── bot.py                  entrypoint
├── round_manager.py        game logic
├── database.py             SQLite layer
├── event_handlers.py       on_message → guesses
├── achievements/           definitions and unlock logic
├── commands/               slash commands
│   └── admin/              mod-only commands
├── ui/embed_factory.py     all the embeds
├── scripts/
│   ├── import_characters.py
│   └── scrape_images.py
├── data/characters.txt     character list
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Known limitations

- One round channel per bot instance. If you want it in two servers, run two instances with two databases.
- Exact-match guessing: typing "Bocchi" won't count for "Hitori "Bocchi" Gotoh". A fuzzier match would be a nice improvement.
- The scraper takes the first decent image Bing returns, so a few characters will need a manual fix.

---

## License

[MIT](LICENSE). The code is free to use. The anime characters obviously belong to their creators.
