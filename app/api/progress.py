import asyncio
import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from app.services.job_manager import JobManager
from app.database import get_db

router = APIRouter(prefix="/api/jobs", tags=["progress"])

KEEPALIVE_INTERVAL = 15  # seconds


@router.get("/{job_id}/stream")
async def job_stream(job_id: int, request: Request):
    async def event_generator():
        # Send current snapshot first
        async with get_db() as db:
            async with db.execute(
                "SELECT status, total_count, done_count, failed_count, current_chapter_id "
                "FROM jobs WHERE id=?",
                (job_id,),
            ) as cur:
                jrow = await cur.fetchone()

        if jrow:
            current = None
            if jrow["current_chapter_id"]:
                async with get_db() as db:
                    async with db.execute(
                        "SELECT id, title FROM chapters WHERE id=?",
                        (jrow["current_chapter_id"],),
                    ) as cur:
                        crow = await cur.fetchone()
                if crow:
                    current = {"id": crow["id"], "title": crow["title"]}

            yield {
                "event": "progress",
                "data": json.dumps({
                    "job_id": job_id,
                    "done": jrow["done_count"],
                    "failed": jrow["failed_count"],
                    "total": jrow["total_count"],
                    "status": jrow["status"],
                    "current": current,
                }, ensure_ascii=False),
            }

        mgr = JobManager.get()
        q = mgr.subscribe(job_id)

        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    msg = await asyncio.wait_for(q.get(), timeout=KEEPALIVE_INTERVAL)
                    event_type = msg["type"]
                    yield {
                        "event": event_type,
                        "data": json.dumps(msg["data"], ensure_ascii=False),
                    }
                    if event_type in ("done", "job_status") and msg["data"].get("status") in (
                        "completed", "paused", "cancelled", "failed",
                    ):
                        break
                except asyncio.TimeoutError:
                    yield {"event": "keepalive", "data": ""}
        finally:
            mgr.unsubscribe(job_id, q)

    return EventSourceResponse(event_generator())
