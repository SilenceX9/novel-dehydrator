from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_db
from app.services.deepseek_client import chat_completion
from app.storage.files import read_chapter

router = APIRouter(prefix="/api/books", tags=["chat"])

QA_SYSTEM = """你是一个网文阅读助手。用户正在阅读一本小说的脱水版（精华提取版），你的任务是回答用户关于剧情、人物、设定等方面的问题。

规则：
- 基于提供的章节内容回答，不要编造原文没有的情节
- 回答简洁直接，避免冗长
- 如果问题超出已提供内容的范围，坦诚告知"""


class ChatRequest(BaseModel):
    chapter_id: int
    question: str
    history: list = []


@router.post("/{book_id}/chat")
async def chapter_chat(book_id: int, req: ChatRequest):
    async with get_db() as db:
        async with db.execute(
            "SELECT title FROM books WHERE id=?", (book_id,)
        ) as cur:
            book_row = await cur.fetchone()
        if not book_row:
            raise HTTPException(404, "书籍不存在")

        async with db.execute(
            "SELECT title, raw_path, dehydrated_path, dehydrate_status FROM chapters WHERE id=? AND book_id=?",
            (req.chapter_id, book_id),
        ) as cur:
            ch_row = await cur.fetchone()
        if not ch_row:
            raise HTTPException(404, "章节不存在")

    path = ch_row["dehydrated_path"] if ch_row["dehydrate_status"] == "done" and ch_row["dehydrated_path"] else ch_row["raw_path"]
    try:
        chapter_text = await read_chapter(path)
    except Exception:
        raise HTTPException(500, "章节内容读取失败")

    context = f"书名：《{book_row['title']}》\n章节：{ch_row['title']}\n\n【章节内容】\n{chapter_text}"

    messages = [
        {"role": "system", "content": QA_SYSTEM},
        {"role": "user", "content": context},
        {"role": "assistant", "content": "好的，我已经阅读了这个章节的内容，请问你有什么问题？"},
    ]
    for msg in req.history[-6:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": req.question})

    try:
        answer = await chat_completion(messages, stream=True)
    except Exception as e:
        raise HTTPException(500, f"AI 调用失败：{str(e)[:200]}")

    return {"answer": answer}
