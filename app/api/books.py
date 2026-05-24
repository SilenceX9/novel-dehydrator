import asyncio
import shutil
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from app.config import UPLOADS_DIR
from app.database import get_db
from app.models.schema import BookOut
from app.storage.files import delete_book_files

router = APIRouter(prefix="/api/books", tags=["books"])

ALLOWED_EXTENSIONS = {"epub", "txt"}


@router.get("", response_model=list[BookOut])
async def list_books():
    async with get_db() as db:
        async with db.execute(
            "SELECT b.id, b.title, b.author, b.source_format, b.total_chapters, b.has_volumes, "
            "b.parse_status, b.parse_error, b.created_at, "
            "(SELECT COUNT(*) FROM chapters c WHERE c.book_id = b.id AND c.dehydrate_status = 'done') as dehydrated_count "
            "FROM books b ORDER BY b.id DESC"
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/upload")
async def upload_book(file: UploadFile = File(...)):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式 .{ext}，请上传 epub 或 txt")

    # Create DB record first (to get book_id)
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO books (title, source_format, source_path, parse_status) VALUES (?, ?, '', 'pending')",
            (Path(file.filename).stem, ext),
        )
        book_id = cur.lastrowid
        await db.commit()

    # Save uploaded file
    save_path = UPLOADS_DIR / f"{book_id}.{ext}"
    with open(save_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Update source_path
    async with get_db() as db:
        await db.execute(
            "UPDATE books SET source_path=?, parse_status='parsing', updated_at=datetime('now') WHERE id=?",
            (str(save_path), book_id),
        )
        await db.commit()

    # Kick off async parse
    from app.services.parser import parse_book
    asyncio.create_task(parse_book(book_id, str(save_path), ext))

    return {"book_id": book_id, "parse_status": "parsing"}


@router.get("/{book_id}", response_model=BookOut)
async def get_book(book_id: int):
    async with get_db() as db:
        async with db.execute(
            "SELECT b.id, b.title, b.author, b.source_format, b.total_chapters, b.has_volumes, "
            "b.parse_status, b.parse_error, b.created_at, "
            "(SELECT COUNT(*) FROM chapters c WHERE c.book_id = b.id AND c.dehydrate_status = 'done') as dehydrated_count "
            "FROM books b WHERE b.id=?",
            (book_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "书籍不存在")
    return dict(row)


@router.delete("/{book_id}")
async def delete_book(book_id: int):
    async with get_db() as db:
        async with db.execute("SELECT source_path FROM books WHERE id=?", (book_id,)) as cur:
            row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "书籍不存在")

        # Delete uploaded file
        src = Path(row["source_path"])
        if src.exists():
            src.unlink(missing_ok=True)

        # Delete chapter files
        delete_book_files(book_id)

        await db.execute("DELETE FROM books WHERE id=?", (book_id,))
        await db.commit()

    return {"ok": True}
