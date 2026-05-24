import aiofiles
import os
from pathlib import Path
from app.config import BOOKS_DIR


def raw_chapter_path(book_id: int, chapter_id: int) -> str:
    p = BOOKS_DIR / str(book_id) / "raw"
    p.mkdir(parents=True, exist_ok=True)
    return str(p / f"{chapter_id}.txt")


def dehydrated_chapter_path(book_id: int, chapter_id: int) -> str:
    p = BOOKS_DIR / str(book_id) / "dehydrated"
    p.mkdir(parents=True, exist_ok=True)
    return str(p / f"{chapter_id}.txt")


async def write_raw_chapter(book_id: int, chapter_id: int, text: str) -> str:
    path = raw_chapter_path(book_id, chapter_id)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(text)
    return path


async def write_dehydrated_chapter(path: str, text: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    tmp = path + ".tmp"
    async with aiofiles.open(tmp, "w", encoding="utf-8") as f:
        await f.write(text)
    os.replace(tmp, path)


async def read_chapter(path: str) -> str:
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        return await f.read()


def delete_book_files(book_id: int):
    import shutil
    book_dir = BOOKS_DIR / str(book_id)
    if book_dir.exists():
        shutil.rmtree(book_dir)
