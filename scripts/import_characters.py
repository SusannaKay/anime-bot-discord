"""Import script: fills the characters table from a plain text list.

Usage:
    python3 scripts/import_characters.py data/characters.txt

Line format:
    Anime -- rarity -- Name 1, Name 2, ...
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database import Database

ALLOWED_RARITIES = {"common", "rare", "epic"}


def normalize_name(name: str) -> str:
    """
    Normalizes a name: trims it, removes double commas, trailing dots and extra spaces,
    replaces curly quotes and capitalizes every word.
    """
    cleaned = name.strip()
    cleaned = cleaned.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    while ",," in cleaned:
        cleaned = cleaned.replace(",,", ",")
    cleaned = cleaned.rstrip(".")
    cleaned = " ".join(cleaned.split())
    parts = [word.capitalize() for word in cleaned.split(" ") if word]
    return " ".join(parts)


def validate_rarity(raw: str) -> str:
    """Validates and normalizes the rarity (common|rare|epic)."""
    rarity = raw.strip().lower()
    if rarity not in ALLOWED_RARITIES:
        raise ValueError(f"Invalid rarity: {raw}")
    return rarity


def parse_line(line: str) -> Tuple[str, str, List[str]]:
    """Parses a line formatted as 'Anime -- rarity -- Name1, Name2, ...'."""
    if "--" not in line:
        raise ValueError("Missing '--' separator.")

    parts = [segment.strip() for segment in line.split("--", 2)]
    if len(parts) < 3:
        raise ValueError("Invalid line format.")

    anime_raw, rarity_raw, names_raw = parts[0], parts[1], parts[2]
    anime = " ".join(anime_raw.strip().split())
    if not anime:
        raise ValueError("Missing anime title.")

    rarity = validate_rarity(rarity_raw)

    cleaned_names_str = names_raw.replace(",,", ",")
    names = [normalize_name(part) for part in cleaned_names_str.split(",")]
    names = [name for name in names if name]
    if not names:
        raise ValueError("Empty character list.")

    return anime, rarity, names


def insert_character(db: Database, anime: str, rarity: str, name: str) -> str:
    """Inserts a character and returns the outcome."""
    existing = db.get_character_by_name(name, anime=anime)
    if existing:
        print(f"DUPLICATE SKIPPED: {name} ({anime})")
        return "duplicate"
    try:
        created = db.add_character(name, anime, rarity, image_path=None)
        return "inserted" if created else "error"
    except Exception as exc:  # noqa: BLE001
        print(f"[ERR] Could not insert {name} ({anime}): {exc}")
        return "error"


def load_file(path: str) -> Iterable[str]:
    source = Path(path)
    if not source.is_file():
        print(f"[ERR] File not found: {path}")
        raise SystemExit(1)
    with source.open("r", encoding="utf-8") as handle:
        for raw in handle:
            yield raw.rstrip("\n")


def summary(anime_count: int, imported: int, duplicates: int, skipped: int) -> None:
    print("=== Import Summary ===")
    print(f"Anime imported: {anime_count}")
    print(f"Characters imported: {imported}")
    print(f"Duplicates: {duplicates}")
    print(f"Lines skipped: {skipped}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/import_characters.py <file_path>")
        raise SystemExit(1)

    file_path = sys.argv[1]
    db = Database(os.getenv("DB_PATH", str(ROOT / "bot.db")))

    imported = 0
    duplicates = 0
    skipped = 0
    anime_seen = set()

    # Characters already in the database are skipped, not deleted:
    # wiping the table would break the cards users already own.
    try:
        for idx, raw_line in enumerate(load_file(file_path), start=1):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "--" not in raw_line:
                continue

            try:
                anime, rarity, names = parse_line(raw_line)
            except ValueError as exc:
                skipped += 1
                print(f"[SKIP] Line {idx}: {exc}")
                continue

            anime_seen.add(anime)
            for name in names:
                status = insert_character(db, anime, rarity, name)
                if status == "inserted":
                    imported += 1
                elif status == "duplicate":
                    duplicates += 1
                else:
                    skipped += 1
    finally:
        db.close()

    summary(len(anime_seen), imported, duplicates, skipped)


if __name__ == "__main__":
    main()
