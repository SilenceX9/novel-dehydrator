from app.services.deepseek_client import chat_completion
from app.services.prompts import (
    DEHYDRATE_SYSTEM, DEHYDRATE_USER, CHUNK_HINT,
    POSITION_HINT_EARLY, POSITION_HINT_NORMAL,
)
from app.config import settings
from app.database import get_db


def _split_into_chunks(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    # Split on blank lines first, fall back to newlines
    paragraphs = text.split("\n\n") if "\n\n" in text else text.split("\n")
    chunks = []
    current = []
    current_len = 0
    for para in paragraphs:
        if current_len + len(para) > limit and current:
            chunks.append("\n\n".join(current) if "\n\n" in text else "\n".join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)
    if current:
        chunks.append("\n\n".join(current) if "\n\n" in text else "\n".join(current))
    return chunks


async def _get_system_prompt() -> str:
    """Read custom system prompt from DB; fall back to default."""
    try:
        async with get_db() as db:
            async with db.execute("SELECT system_prompt FROM app_settings WHERE id=1") as cur:
                row = await cur.fetchone()
        if row and row["system_prompt"] and row["system_prompt"].strip():
            return row["system_prompt"].strip()
    except Exception:
        pass
    return DEHYDRATE_SYSTEM


async def dehydrate_chapter(
    book_title: str,
    chapter_title: str,
    raw_text: str,
    chapter_seq: int = 1,
    total_chapters: int = 1,
) -> str:
    chunks = _split_into_chunks(raw_text, settings.chunk_char_limit)

    system_prompt = await _get_system_prompt()

    # Early chapters (first 20%) get gentler compression
    is_early = total_chapters > 0 and (chapter_seq / total_chapters) <= 0.2
    position_hint = POSITION_HINT_EARLY if is_early else POSITION_HINT_NORMAL

    if len(chunks) == 1:
        return await _dehydrate_chunk(
            book_title, chapter_title, chunks[0],
            chunk_hint="", position_hint=position_hint,
            chapter_seq=chapter_seq, total_chapters=total_chapters,
            system_prompt=system_prompt,
        )

    results = []
    total = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        hint = CHUNK_HINT.format(total=total, idx=idx)
        part = await _dehydrate_chunk(
            book_title, chapter_title, chunk,
            chunk_hint=hint, position_hint=position_hint,
            chapter_seq=chapter_seq, total_chapters=total_chapters,
            system_prompt=system_prompt,
        )
        results.append(part)

    return "\n\n".join(results)


async def _dehydrate_chunk(
    book_title: str,
    chapter_title: str,
    text: str,
    chunk_hint: str,
    position_hint: str,
    chapter_seq: int,
    total_chapters: int,
    system_prompt: str,
) -> str:
    user_content = DEHYDRATE_USER.format(
        book_title=book_title,
        chapter_title=chapter_title,
        chapter_seq=chapter_seq,
        total_chapters=total_chapters,
        position_hint=position_hint,
        chunk_hint=chunk_hint,
        raw_text=text,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    return await chat_completion(messages, stream=True)
