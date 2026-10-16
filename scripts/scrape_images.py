#!/usr/bin/env python3
"""Downloads one image per character from Bing (via icrawler), for every
character in the database that doesn't have an image yet.

Usage:
    python3 scripts/scrape_images.py
"""
import os
import random
import re
import sqlite3
import tempfile
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

from icrawler.builtin import BingImageCrawler
from PIL import Image, UnidentifiedImageError

DB_PATH = Path(os.getenv("DB_PATH", str(Path(__file__).resolve().parent.parent / "bot.db")))
IMAGES_ROOT = Path(__file__).resolve().parent.parent / "images"
TMP_ROOT = IMAGES_ROOT / "_tmp"
MIN_SIZE = 300


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[\s-]+", "_", text) or "character"


def sanitize_anime(anime: str) -> str:
    cleaned = anime.strip().replace("\\", "-").replace("/", "-")
    cleaned = re.sub(r"[<>:\"|?*]", "", cleaned)
    return cleaned or "anime"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def prepare_image(path: Path) -> tuple[Optional[bytes], str]:
    """Validates the image and converts it to JPEG; returns (bytes, reason_if_none)."""
    try:
        with Image.open(path) as img:
            fmt = (img.format or "").lower()
            if fmt == "webp" and getattr(img, "is_animated", False):
                return None, "animated webp"
            if img.width < MIN_SIZE or img.height < MIN_SIZE:
                return None, f"too small {img.width}x{img.height}"
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            return buffer.getvalue(), ""
    except (UnidentifiedImageError, OSError) as exc:
        return None, f"corrupted/unreadable ({exc})"


def crawl_one_image(query: str, destination_dir: Path) -> Optional[Path]:
    ensure_dir(destination_dir)
    crawler = BingImageCrawler(
        downloader_threads=1,
        storage={"root_dir": str(destination_dir)},
    )
    try:
        crawler.crawl(keyword=query, max_num=1, min_size=(MIN_SIZE, MIN_SIZE), file_idx_offset=0)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERR] Bing crawler error: {exc}")
        return None

    files = sorted(destination_dir.glob("*"))
    return files[0] if files else None


def scrape_single_image(anime: str, name: str, out_path: Path) -> bool:
    queries = [
        f"{name} {anime} anime art portrait",
        f"{name} {anime} anime",
        f"{name} {anime} character portrait",
    ]

    for attempt, query in enumerate(queries, start=1):
        print(f"[TRY] {name} ({anime}) — Attempt {attempt} — Query: {query}")
        with tempfile.TemporaryDirectory(dir=TMP_ROOT) as tmpdir:
            tmp_dir_path = Path(tmpdir)
            downloaded = crawl_one_image(query, tmp_dir_path)
            if not downloaded:
                print("[WARN] No image found")
                continue

            prepared, reason = prepare_image(downloaded)
            if not prepared:
                print(f"[FAIL] Image discarded ({reason})")
                continue

            ensure_dir(out_path.parent)
            with out_path.open("wb") as handle:
                handle.write(prepared)

            print(f"[OK] Image saved: {out_path.name}")
            return True

    print(f"[FAIL] No valid image for {name}\n")
    return False


def main() -> None:
    print("=== SCRAPER — LOADING CHARACTERS ===")
    ensure_dir(IMAGES_ROOT)
    ensure_dir(TMP_ROOT)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, name, anime FROM characters
        WHERE image_path IS NULL OR TRIM(image_path) = ''
        """
    )
    characters = cur.fetchall()

    if not characters:
        print("Every character already has an image 🎉")
        return

    total = len(characters)
    ok = 0
    fail = 0

    for idx, (char_id, name, anime) in enumerate(characters, start=1):
        print(f"\n[{idx}/{total}] {name} ({anime})")
        anime_dir = IMAGES_ROOT / sanitize_anime(anime)
        char_slug = slugify(name)
        out_path = anime_dir / f"{char_slug}.jpg"

        success = scrape_single_image(anime, name, out_path)

        if success:
            img_path = f"images/{sanitize_anime(anime)}/{char_slug}.jpg"
            cur.execute("UPDATE characters SET image_path = ? WHERE id = ?", (img_path, char_id))
            ok += 1
        else:
            fail += 1

        conn.commit()
        time.sleep(random.uniform(1.0, 2.0))

    conn.close()

    print("\n=== RESULT ===")
    print(f"Total       : {total}")
    print(f"Downloaded  : {ok}")
    print(f"Failed      : {fail}")
    print(f"Images in   : images/")
    print("==============================")


if __name__ == "__main__":
    main()
