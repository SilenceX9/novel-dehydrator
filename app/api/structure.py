from fastapi import APIRouter, HTTPException
from app.database import get_db
from app.models.schema import BookStructureOut, VolumeOut, ChapterOut

router = APIRouter(prefix="/api/books", tags=["structure"])


@router.get("/{book_id}/structure", response_model=BookStructureOut)
async def get_structure(book_id: int):
    async with get_db() as db:
        async with db.execute(
            "SELECT has_volumes FROM books WHERE id=?", (book_id,)
        ) as cur:
            brow = await cur.fetchone()
        if not brow:
            raise HTTPException(404, "书籍不存在")

        has_volumes = bool(brow["has_volumes"])

        async with db.execute(
            "SELECT id, title, seq FROM volumes WHERE book_id=? ORDER BY seq",
            (book_id,),
        ) as cur:
            vol_rows = await cur.fetchall()

        async with db.execute(
            """SELECT id, title, seq, volume_id, raw_char_count, dehydrate_status,
                      dehydrated_char_count, compression_ratio, error_msg
               FROM chapters WHERE book_id=? ORDER BY seq""",
            (book_id,),
        ) as cur:
            ch_rows = await cur.fetchall()

    # Group chapters by volume
    vol_map: dict[int, list] = {}
    loose: list = []
    for ch in ch_rows:
        ch_out = ChapterOut(
            id=ch["id"],
            title=ch["title"],
            seq=ch["seq"],
            raw_char_count=ch["raw_char_count"],
            dehydrate_status=ch["dehydrate_status"],
            dehydrated_char_count=ch["dehydrated_char_count"] or 0,
            compression_ratio=ch["compression_ratio"],
            error_msg=ch["error_msg"],
        )
        vid = ch["volume_id"]
        if vid:
            vol_map.setdefault(vid, []).append(ch_out)
        else:
            loose.append(ch_out)

    volumes = [
        VolumeOut(id=v["id"], title=v["title"], seq=v["seq"], chapters=vol_map.get(v["id"], []))
        for v in vol_rows
    ]

    return BookStructureOut(
        book_id=book_id,
        has_volumes=has_volumes,
        volumes=volumes,
        loose_chapters=loose,
    )
