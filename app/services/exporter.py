import asyncio
from pathlib import Path
from typing import Optional

from ebooklib import epub

from app.database import get_db
from app.storage.files import read_chapter


async def export_book(book_id: int, fmt: str = "txt") -> bytes:
    async with get_db() as db:
        async with db.execute(
            "SELECT title, author FROM books WHERE id=?", (book_id,)
        ) as cur:
            book_row = await cur.fetchone()
        if not book_row:
            raise ValueError("Book not found")
        book_title, author = book_row["title"], book_row["author"] or ""

        async with db.execute(
            """SELECT id, title, seq, raw_path, dehydrated_path, dehydrate_status
               FROM chapters WHERE book_id=? AND dehydrate_status='done' ORDER BY seq""",
            (book_id,),
        ) as cur:
            chapters = await cur.fetchall()

    if fmt == "epub":
        return await _export_epub(book_title, author, chapters)
    else:
        return await _export_txt(book_title, chapters)


def _strip_meta(text: str) -> str:
    """Remove ---CHAPTER_META--- section from dehydrated text."""
    idx = text.find("---CHAPTER_META---")
    return text[:idx].rstrip() if idx != -1 else text


async def _export_txt(book_title: str, chapters) -> bytes:
    lines = [f"《{book_title}》脱水版\n\n"]
    for ch in chapters:
        path = ch["dehydrated_path"] or ch["raw_path"]
        if not path:
            continue
        try:
            text = _strip_meta(await read_chapter(path))
        except Exception:
            text = "（章节内容缺失）"
        lines.append(f"\n{ch['title']}\n\n{text}\n")
    return "\n".join(lines).encode("utf-8")


async def _export_epub(book_title: str, author: str, chapters) -> bytes:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _build_epub_sync, book_title, author, chapters)


def _build_epub_sync(book_title: str, author: str, chapters) -> bytes:
    import asyncio as _asyncio
    import io

    book = epub.EpubBook()
    book.set_title(f"{book_title} 脱水版")
    book.set_language("zh")
    if author:
        book.add_author(author)

    spine = ["nav"]
    toc = []

    for ch in chapters:
        path = ch["dehydrated_path"] or ch["raw_path"]
        try:
            text = _strip_meta(Path(path).read_text(encoding="utf-8")) if path else "（内容缺失）"
        except Exception:
            text = "（章节内容缺失）"

        # Escape HTML
        import html
        text_html = "".join(
            f"<p>{html.escape(line)}</p>" for line in text.splitlines() if line.strip()
        )

        item_id = f"chapter_{ch['id']}"
        c = epub.EpubHtml(
            title=ch["title"],
            file_name=f"{item_id}.xhtml",
            lang="zh",
        )
        c.content = f"<html><body><h2>{html.escape(ch['title'])}</h2>{text_html}</body></html>"
        book.add_item(c)
        spine.append(c)
        toc.append(epub.Link(f"{item_id}.xhtml", ch["title"], item_id))

    book.toc = toc
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    buf = io.BytesIO()
    epub.write_epub(buf, book)
    return buf.getvalue()
