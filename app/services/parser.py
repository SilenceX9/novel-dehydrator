import asyncio
from pathlib import Path

import aiosqlite

from app.database import get_db
from app.storage.files import write_raw_chapter
from app.services.structure_detector import detect_structure
from app.services.deepseek_client import _get_runtime_settings


async def parse_book(book_id: int, file_path: str, source_format: str):
    try:
        await _do_parse(book_id, file_path, source_format)
    except Exception as e:
        async with get_db() as db:
            await db.execute(
                "UPDATE books SET parse_status='failed', parse_error=?, updated_at=datetime('now') WHERE id=?",
                (str(e)[:500], book_id),
            )
            await db.commit()
        raise


async def _do_parse(book_id: int, file_path: str, source_format: str):
    # Run heavy parsing in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()

    if source_format == "epub":
        from app.services.epub_parser import parse_epub
        parsed = await loop.run_in_executor(None, parse_epub, file_path)
    else:
        from app.services.txt_parser import parse_txt
        parsed = await loop.run_in_executor(None, parse_txt, file_path)

    raw_chapters = parsed["chapters"]
    has_nested = parsed.get("has_nested_toc", False)

    # Detect two-level structure
    volumes, chapters_with_vol = detect_structure(raw_chapters, has_nested)

    async with get_db() as db:
        # Update book title/author from parsed metadata
        author = parsed.get("author", "").strip()
        if not author:
            try:
                cfg = await _get_runtime_settings()
                model_name = cfg.get("model", "")
                if "deepseek" in model_name.lower():
                    author = "DeepSeek"
                else:
                    author = model_name.split("-")[0].capitalize() if model_name else "AI"
            except Exception:
                author = "AI"
        await db.execute(
            "UPDATE books SET title=?, author=?, updated_at=datetime('now') WHERE id=?",
            (parsed["title"], author, book_id),
        )

        # Insert volumes
        vol_seq_to_id: dict = {}
        for vol in volumes:
            cursor = await db.execute(
                "INSERT INTO volumes (book_id, title, seq, detect_source) VALUES (?, ?, ?, ?)",
                (book_id, vol["title"], vol["seq"], vol["detect_source"]),
            )
            vol_seq_to_id[vol["seq"]] = cursor.lastrowid

        # Insert chapters and write raw files
        for seq, ch in enumerate(chapters_with_vol, start=1):
            vol_seq = ch.get("volume_seq")
            volume_id = vol_seq_to_id.get(vol_seq) if vol_seq else None

            cursor = await db.execute(
                """INSERT INTO chapters (book_id, volume_id, title, seq, raw_path, raw_char_count)
                   VALUES (?, ?, ?, ?, '', ?)""",
                (book_id, volume_id, ch["title"], seq, len(ch["text"])),
            )
            chapter_id = cursor.lastrowid

            # Write raw text file (async)
            raw_path = await write_raw_chapter(book_id, chapter_id, ch["text"])

            await db.execute(
                "UPDATE chapters SET raw_path=? WHERE id=?",
                (raw_path, chapter_id),
            )

        total = len(chapters_with_vol)
        has_volumes = 1 if volumes else 0
        await db.execute(
            """UPDATE books SET total_chapters=?, has_volumes=?, parse_status='done',
               updated_at=datetime('now') WHERE id=?""",
            (total, has_volumes, book_id),
        )
        await db.commit()
