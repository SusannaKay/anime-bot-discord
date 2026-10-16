"""
SQLite database module for the Discord bot.
Creates the tables and handles CRUD operations on users, characters and images.
"""

import random
import sqlite3
from typing import Any, Dict, List, Optional


class Database:
    """Object-oriented wrapper around the bot's SQLite database."""

    def __init__(self, db_path: str = "bot.db") -> None:
        # Open the connection and use a row factory to get dict-like rows
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        # Set up the schema and the default rarities
        self.create_tables()
        self.ensure_default_rarities()

    # ===========================
    # Setup and basic utilities
    # ===========================
    def create_tables(self) -> None:
        """Creates every table the bot needs, if it doesn't exist yet."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT UNIQUE,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_guesses INTEGER DEFAULT 0,
                fail_streak INTEGER DEFAULT 0,
                win_count INTEGER DEFAULT 0,
                total_cards_obtained INTEGER DEFAULT 0
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rarities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                weight INTEGER
            );
            """
        )
        self._ensure_characters_table(cursor)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id INTEGER,
                rarity_id INTEGER,
                file_path TEXT,
                FOREIGN KEY(character_id) REFERENCES characters(id),
                FOREIGN KEY(rarity_id) REFERENCES rarities(id)
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                image_id INTEGER,
                obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(image_id) REFERENCES images(id)
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_achievements (
                user_id TEXT NOT NULL,
                achievement_id INTEGER NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, achievement_id)
            );
            """
        )
        self._ensure_user_stat_columns(cursor)
        self._populate_achievements(cursor)
        self.conn.commit()

    def ensure_default_rarities(self) -> None:
        """Inserts the base rarities with their weights, if missing."""
        defaults = {
            "common": 70,
            "rare": 25,
            "epic": 5,
        }
        cursor = self.conn.cursor()
        for name, weight in defaults.items():
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO rarities (name, weight) VALUES (?, ?);",
                    (name, weight),
                )
            except sqlite3.Error as exc:
                print(f"[ERROR] Could not insert rarity {name}: {exc}")
        self.conn.commit()

    def _ensure_characters_table(self, cursor: sqlite3.Cursor) -> None:
        """Recreates the characters table with the current schema, if needed."""
        cursor.execute("PRAGMA table_info(characters);")
        existing_columns = {row["name"] for row in cursor.fetchall()}
        desired_columns = {"id", "name", "anime", "rarity", "image_path"}
        if existing_columns != desired_columns:
            try:
                cursor.execute("DROP TABLE IF EXISTS characters;")
            except sqlite3.Error as exc:  # noqa: BLE001
                print(f"[WARN] Could not drop the characters table: {exc}")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                anime TEXT NOT NULL,
                rarity TEXT NOT NULL CHECK(rarity IN ('common','rare','epic')),
                image_path TEXT DEFAULT NULL,
                UNIQUE(name, anime)
            );
            """
        )

    def _ensure_user_stat_columns(self, cursor: sqlite3.Cursor) -> None:
        """Adds the user stats columns if missing (soft migration)."""
        cursor.execute("PRAGMA table_info(users);")
        existing_columns = {row["name"] for row in cursor.fetchall()}
        desired = {
            "total_guesses": "INTEGER DEFAULT 0",
            "fail_streak": "INTEGER DEFAULT 0",
            "win_count": "INTEGER DEFAULT 0",
            "total_cards_obtained": "INTEGER DEFAULT 0",
        }
        for column, ddl in desired.items():
            if column not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {ddl};")
                except sqlite3.OperationalError as exc:
                    print(f"[WARN] Could not add column {column}: {exc}")

    def _populate_achievements(self, cursor: sqlite3.Cursor) -> None:
        """Fills the achievements table from the static definitions."""
        try:
            from achievements.definitions import ACHIEVEMENTS
        except Exception as exc:  # noqa: BLE001
            print(f"[WARN] Could not import the achievement definitions: {exc}")
            return

        for code, payload in ACHIEVEMENTS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO achievements (code, name) VALUES (?, ?);",
                (code, payload.get("name", code)),
            )

    def close(self) -> None:
        """Closes the connection."""
        if self.conn:
            self.conn.close()

    # ===========================
    # Helpers
    # ===========================
    def _get_rarity_by_name(self, name: str) -> Optional[sqlite3.Row]:
        """Gets a rarity by name (case-insensitive)."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM rarities WHERE LOWER(name) = LOWER(?);",
            (name,),
        )
        return cursor.fetchone()

    def _get_or_create_rarity(self, name: str, weight: int = 0) -> sqlite3.Row:
        """Gets the rarity, or creates it if missing."""
        rarity = self._get_rarity_by_name(name)
        if rarity:
            return rarity
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO rarities (name, weight) VALUES (?, ?);",
            (name, weight),
        )
        self.conn.commit()
        return self._get_rarity_by_name(name)

    # ===========================
    # Users
    # ===========================
    def create_or_get_user(self, discord_id: str, username: str) -> Optional[sqlite3.Row]:
        """Creates the user if it doesn't exist, then returns it."""
        existing = self.get_user(discord_id)
        if existing:
            if username and existing["username"] != username:
                cursor = self.conn.cursor()
                cursor.execute(
                    "UPDATE users SET username = ? WHERE discord_id = ?;",
                    (username, discord_id),
                )
                self.conn.commit()
            return existing
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (discord_id, username) VALUES (?, ?);",
                (discord_id, username),
            )
            self.conn.commit()
        except sqlite3.Error as exc:
            print(f"[ERROR] Could not create user {discord_id}: {exc}")
            return None
        return self.get_user(discord_id)

    def get_user(self, discord_id: str) -> Optional[sqlite3.Row]:
        """Gets a user by discord_id."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE discord_id = ?;", (discord_id,))
        return cursor.fetchone()

    def get_user_inventory(self, discord_id: str) -> List[sqlite3.Row]:
        """Alias of get_inventory, kept for compatibility."""
        return self.get_inventory(discord_id)

    # ===========================
    # Characters
    # ===========================
    def add_character(
        self,
        name: str,
        anime: str,
        rarity: str,
        image_path: Optional[str] = None,
    ) -> Optional[sqlite3.Row]:
        """Adds a character unless it already exists (same name and anime)."""
        existing = self.get_character_by_name(name, anime=anime)
        if existing:
            return existing

        normalized_rarity = (rarity or "").strip().lower()
        if normalized_rarity not in {"common", "rare", "epic"}:
            print(f"[ERROR] Invalid rarity '{rarity}' for {name}.")
            return None

        cursor = self.conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO characters (name, anime, rarity, image_path)
                VALUES (?, ?, ?, ?);
                """,
                (name.strip(), anime.strip(), normalized_rarity, image_path),
            )
            self.conn.commit()
        except sqlite3.Error as exc:
            print(f"[ERROR] Could not add character {name}: {exc}")
            return None
        return self.get_character_by_name(name, anime=anime)

    def get_character_by_name(self, name: str, anime: Optional[str] = None) -> Optional[sqlite3.Row]:
        """Returns a character by name and, optionally, anime."""
        cursor = self.conn.cursor()
        if anime:
            cursor.execute(
                "SELECT * FROM characters WHERE name = ? AND anime = ?;",
                (name, anime),
            )
        else:
            cursor.execute(
                "SELECT * FROM characters WHERE name = ?;",
                (name,),
            )
        return cursor.fetchone()

    def get_random_character(self) -> Optional[Dict[str, Any]]:
        """Returns a random character, with the rarity taken from its record."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT id, name, anime, rarity, image_path
            FROM characters
            ORDER BY RANDOM()
            LIMIT 1;
            """
        )
        character = cursor.fetchone()
        if not character:
            print("[WARN] No characters available.")
            return None
        return {
            "id": character["id"],
            "name": character["name"],
            "anime": character["anime"],
            "rarity": character["rarity"],
            "image_path": character["image_path"],
        }

    def clear_characters(self) -> None:
        """Empties the characters table."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM characters;")
        self.conn.commit()

    # ===========================
    # Images
    # ===========================
    def add_image(self, character_id: int, rarity: str, file_path: str) -> Optional[sqlite3.Row]:
        """Registers an image for a character and rarity."""
        rarity_row = self._get_rarity_by_name(rarity)
        if not rarity_row:
            rarity_row = self._get_or_create_rarity(rarity)

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT * FROM images
            WHERE character_id = ? AND rarity_id = ? AND file_path = ?;
            """,
            (character_id, rarity_row["id"], file_path),
        )
        existing = cursor.fetchone()
        if existing:
            return existing

        try:
            cursor.execute(
                """
                INSERT INTO images (character_id, rarity_id, file_path)
                VALUES (?, ?, ?);
                """,
                (character_id, rarity_row["id"], file_path),
            )
            self.conn.commit()
        except sqlite3.Error as exc:
            print(f"[ERROR] Could not insert image {file_path}: {exc}")
            return None
        cursor.execute("SELECT * FROM images WHERE id = last_insert_rowid();")
        return cursor.fetchone()

    def get_images_by_character(self, character_id: int) -> List[sqlite3.Row]:
        """Returns every image linked to a character."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT i.*, r.name AS rarity_name FROM images i
            JOIN rarities r ON i.rarity_id = r.id
            WHERE i.character_id = ?;
            """,
            (character_id,),
        )
        return cursor.fetchall()

    def get_random_image_for_character(self, character_id: int, rarity: Optional[str]) -> Optional[sqlite3.Row]:
        """Picks a random image for a character, preferring the given rarity."""
        rarity_row = self._get_rarity_by_name(rarity) if rarity else None

        cursor = self.conn.cursor()
        if rarity_row:
            cursor.execute(
                """
                SELECT * FROM images
                WHERE character_id = ? AND rarity_id = ?;
                """,
                (character_id, rarity_row["id"]),
            )
            images = cursor.fetchall()
        else:
            cursor.execute(
                """
                SELECT * FROM images
                WHERE character_id = ?;
                """,
                (character_id,),
            )
            images = cursor.fetchall()

        if not images:
            return None
        return random.choice(images)

    # ===========================
    # User inventory
    # ===========================
    def add_image_to_user(self, discord_id: str, image_id: int) -> bool:
        """Adds an image to the user's inventory."""
        user = self.get_user(discord_id)
        if not user:
            print(f"[ERROR] User with discord_id {discord_id} not found.")
            return False

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT 1 FROM user_characters
            WHERE user_id = ? AND image_id = ?;
            """,
            (user["id"], image_id),
        )
        if cursor.fetchone():
            print(f"[INFO] Image {image_id} is already in the inventory of user {discord_id}.")
            return True

        try:
            cursor.execute(
                "INSERT INTO user_characters (user_id, image_id) VALUES (?, ?);",
                (user["id"], image_id),
            )
            self.conn.commit()
            return True
        except sqlite3.Error as exc:
            print(f"[ERROR] Could not add the image to user {discord_id}: {exc}")
            return False

    def get_inventory(self, discord_id: str) -> List[Dict[str, Any]]:
        """Returns the user's full inventory, with image, character and rarity details."""
        user = self.get_user(discord_id)
        if not user:
            print(f"[ERROR] User with discord_id {discord_id} not found.")
            return []

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                uc.id AS user_character_id,
                uc.obtained_at,
                i.id AS image_id,
                i.file_path,
                c.id AS character_id,
                c.name AS character_name,
                c.anime AS character_anime,
                c.rarity AS rarity
            FROM user_characters uc
            JOIN images i ON uc.image_id = i.id
            JOIN characters c ON i.character_id = c.id
            WHERE uc.user_id = ?
            ORDER BY uc.obtained_at DESC;
            """,
            (user["id"],),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
