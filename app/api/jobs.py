from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_db
from app.models.schema import JobOut, StartJobRequest
from app.services.job_manager import JobManager

router = APIRouter(prefix="/api", tags=["jobs"])

# ── Token / cost estimation (no LLM, pure calculation) ──

# Chinese text: ~0.6 tokens per character (empirical average)
CHARS_PER_TOKEN = 1.67

# Pricing per million tokens (CNY)
MODEL_PRICING = {
    "deepseek-v4-flash": {"input": 0.1, "output": 0.4},
    "deepseek-v4-pro":   {"input": 0.5, "output": 2.0},
}
DEFAULT_PRICING = {"input": 0.5, "output": 2.0}

# System prompt ~800 tokens overhead per call
SYSTEM_PROMPT_TOKENS = 800


class EstimateRequest(BaseModel):
    chapter_ids: list[int]


@router.post("/books/{book_id}/estimate")
async def estimate_cost(book_id: int, req: EstimateRequest):
    """Estimate token usage and cost for dehydrating selected chapters."""
    if not req.chapter_ids:
        return {"total_chars": 0, "input_tokens": 0, "output_tokens": 0, "cost_yuan": 0}

    placeholders = ",".join("?" * len(req.chapter_ids))
    async with get_db() as db:
        async with db.execute(
            f"SELECT id, raw_char_count FROM chapters WHERE id IN ({placeholders}) AND book_id=?",
            req.chapter_ids + [book_id],
        ) as cur:
            rows = await cur.fetchall()

        # Get model name for pricing
        async with db.execute("SELECT deepseek_model FROM app_settings WHERE id=1") as cur:
            srow = await cur.fetchone()
        model = srow["deepseek_model"] if srow else "deepseek-v4-flash"

    total_chars = sum(r["raw_char_count"] for r in rows)
    num_chapters = len(rows)

    # Input: raw text tokens + system prompt per chapter
    input_tokens = int(total_chars / CHARS_PER_TOKEN) + SYSTEM_PROMPT_TOKENS * num_chapters
    # Output: ~35% of input raw tokens (compression ratio)
    output_tokens = int(total_chars * 0.35 / CHARS_PER_TOKEN)

    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    return {
        "total_chars": total_chars,
        "num_chapters": num_chapters,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "model": model,
        "cost_yuan": round(cost, 4),
    }


@router.post("/books/{book_id}/jobs", response_model=JobOut)
async def start_job(book_id: int, req: StartJobRequest):
    async with get_db() as db:
        # Resolve chapter IDs from scope
        if req.scope_type == "volumes" and req.volume_ids:
            placeholders = ",".join("?" * len(req.volume_ids))
            async with db.execute(
                f"SELECT id FROM chapters WHERE book_id=? AND volume_id IN ({placeholders}) ORDER BY seq",
                [book_id] + req.volume_ids,
            ) as cur:
                rows = await cur.fetchall()
            chapter_ids = [r["id"] for r in rows]
        elif req.scope_type == "chapters" and req.chapter_ids:
            chapter_ids = req.chapter_ids
        else:
            raise HTTPException(400, "scope_type 必须是 volumes 或 chapters，且对应 ids 不能为空")

        if not chapter_ids:
            raise HTTPException(400, "没有找到可脱水的章节")

        # Create job
        cur = await db.execute(
            "INSERT INTO jobs (book_id, scope_type, total_count) VALUES (?, ?, ?)",
            (book_id, req.scope_type, len(chapter_ids)),
        )
        job_id = cur.lastrowid

        # Link chapters
        await db.executemany(
            "INSERT OR IGNORE INTO job_chapters (job_id, chapter_id) VALUES (?, ?)",
            [(job_id, cid) for cid in chapter_ids],
        )
        # Reset failed/processing chapters to pending
        placeholders = ",".join("?" * len(chapter_ids))
        await db.execute(
            f"""UPDATE chapters SET dehydrate_status='pending'
                WHERE id IN ({placeholders}) AND dehydrate_status IN ('failed','processing')""",
            chapter_ids,
        )
        await db.commit()

        async with db.execute(
            "SELECT id, book_id, status, scope_type, total_count, done_count, "
            "failed_count, current_chapter_id, created_at FROM jobs WHERE id=?",
            (job_id,),
        ) as cur:
            jrow = await cur.fetchone()

    await JobManager.get().start_job(job_id)
    return dict(jrow)


@router.get("/jobs/{job_id}", response_model=JobOut)
async def get_job(job_id: int):
    async with get_db() as db:
        async with db.execute(
            "SELECT id, book_id, status, scope_type, total_count, done_count, "
            "failed_count, current_chapter_id, created_at FROM jobs WHERE id=?",
            (job_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "任务不存在")
    return dict(row)


@router.post("/jobs/{job_id}/pause")
async def pause_job(job_id: int):
    await JobManager.get().pause_job(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/resume")
async def resume_job(job_id: int):
    await JobManager.get().resume_job(job_id)
    return {"ok": True}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int):
    await JobManager.get().cancel_job(job_id)
    return {"ok": True}


@router.get("/books/{book_id}/jobs/latest")
async def latest_job(book_id: int):
    async with get_db() as db:
        async with db.execute(
            "SELECT id, status, total_count, done_count, failed_count FROM jobs "
            "WHERE book_id=? ORDER BY id DESC LIMIT 1",
            (book_id,),
        ) as cur:
            row = await cur.fetchone()
    if not row:
        return None
    return dict(row)
