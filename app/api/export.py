from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from app.database import get_db
from app.services.exporter import export_book

router = APIRouter(prefix="/api/books", tags=["export"])


@router.get("/{book_id}/export")
async def export(book_id: int, format: str = Query("txt", pattern="^(epub|txt)$")):
    async with get_db() as db:
        async with db.execute("SELECT title FROM books WHERE id=?", (book_id,)) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "书籍不存在")

    title = row["title"]
    data = await export_book(book_id, fmt=format)

    media_type = "application/epub+zip" if format == "epub" else "text/plain; charset=utf-8"
    filename = f"{title}_脱水版.{format}"
    encoded = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
    }

    return Response(content=data, media_type=media_type, headers=headers)


@router.get("/{book_id}/chapters/{chapter_id}/content")
async def chapter_content(book_id: int, chapter_id: int, version: str = Query("dehydrated")):
    from app.storage.files import read_chapter

    async with get_db() as db:
        async with db.execute(
            "SELECT raw_path, dehydrated_path, dehydrate_status FROM chapters WHERE id=? AND book_id=?",
            (chapter_id, book_id),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "章节不存在")

    if version == "dehydrated" and row["dehydrate_status"] == "done" and row["dehydrated_path"]:
        path = row["dehydrated_path"]
    else:
        path = row["raw_path"]

    try:
        text = await read_chapter(path)
    except Exception:
        raise HTTPException(500, "章节文件读取失败")

    # Strip ---CHAPTER_META--- from dehydrated content
    if version == "dehydrated":
        meta_idx = text.find("---CHAPTER_META---")
        if meta_idx != -1:
            text = text[:meta_idx].rstrip()

    return {"text": text, "version": version}
