import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.database import get_db
from app.services.dehydrator import dehydrate_chapter
from app.storage.files import read_chapter, write_dehydrated_chapter, dehydrated_chapter_path


@dataclass
class JobContext:
    job_id: int
    task: Optional[asyncio.Task] = None
    pause_requested: bool = False
    subscribers: List[asyncio.Queue] = field(default_factory=list)


class JobManager:
    _instance: Optional["JobManager"] = None

    def __init__(self):
        self._jobs: Dict[int, JobContext] = {}

    @classmethod
    def get(cls) -> "JobManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Public API ──────────────────────────────────────────────

    async def start_job(self, job_id: int):
        chapter_ids = await self._pending_chapters(job_id)
        ctx = JobContext(job_id=job_id)
        self._jobs[job_id] = ctx
        ctx.task = asyncio.create_task(self._run(job_id, chapter_ids, ctx))

    async def pause_job(self, job_id: int):
        ctx = self._jobs.get(job_id)
        if ctx:
            ctx.pause_requested = True
            # Immediately broadcast pause_pending so frontend shows feedback
            await self._broadcast(job_id, "job_status", {
                "job_id": job_id, "status": "pause_pending",
            })

    async def resume_job(self, job_id: int):
        chapter_ids = await self._pending_chapters(job_id)
        async with get_db() as db:
            await db.execute(
                "UPDATE jobs SET status='running', updated_at=datetime('now') WHERE id=?",
                (job_id,),
            )
            await db.commit()

        ctx = self._jobs.get(job_id)
        if ctx is None:
            ctx = JobContext(job_id=job_id)
            self._jobs[job_id] = ctx
        ctx.pause_requested = False
        ctx.task = asyncio.create_task(self._run(job_id, chapter_ids, ctx))

    async def cancel_job(self, job_id: int):
        ctx = self._jobs.get(job_id)
        if ctx and ctx.task and not ctx.task.done():
            ctx.task.cancel()
        async with get_db() as db:
            await db.execute(
                "UPDATE jobs SET status='cancelled', updated_at=datetime('now') WHERE id=?",
                (job_id,),
            )
            await db.commit()
        await self._broadcast(job_id, "job_status", {"job_id": job_id, "status": "cancelled"})

    def subscribe(self, job_id: int) -> asyncio.Queue:
        ctx = self._jobs.get(job_id)
        if ctx is None:
            ctx = JobContext(job_id=job_id)
            self._jobs[job_id] = ctx
        q: asyncio.Queue = asyncio.Queue()
        ctx.subscribers.append(q)
        return q

    def unsubscribe(self, job_id: int, q: asyncio.Queue):
        ctx = self._jobs.get(job_id)
        if ctx and q in ctx.subscribers:
            ctx.subscribers.remove(q)

    # ── Internal ─────────────────────────────────────────────────

    async def _get_concurrency(self) -> int:
        """Read concurrency from DB settings, fallback to config."""
        try:
            async with get_db() as db:
                async with db.execute("SELECT concurrency FROM app_settings WHERE id=1") as cur:
                    row = await cur.fetchone()
            if row and row["concurrency"]:
                return max(1, min(row["concurrency"], 500))
        except Exception:
            pass
        from app.config import settings
        return settings.dehydrate_concurrency

    async def _pending_chapters(self, job_id: int) -> List[int]:
        async with get_db() as db:
            async with db.execute(
                """SELECT c.id FROM job_chapters jc
                   JOIN chapters c ON c.id = jc.chapter_id
                   WHERE jc.job_id = ?
                     AND c.dehydrate_status IN ('pending', 'failed', 'processing')
                   ORDER BY c.seq""",
                (job_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [r[0] for r in rows]

    async def _broadcast(self, job_id: int, event_type: str, data: dict):
        ctx = self._jobs.get(job_id)
        if not ctx:
            return
        msg = {"type": event_type, "data": data}
        dead = []
        for q in ctx.subscribers:
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            ctx.subscribers.remove(q)

    async def _do_pause(self, job_id: int):
        """Execute pause: update DB + broadcast."""
        async with get_db() as db:
            await db.execute(
                "UPDATE jobs SET status='paused', updated_at=datetime('now') WHERE id=?",
                (job_id,),
            )
            await db.commit()
        await self._broadcast(job_id, "job_status", {"job_id": job_id, "status": "paused"})

    async def _process_one(self, job_id: int, chapter_id: int, ctx: JobContext,
                           book_id: int, book_title: str, total_chapters: int,
                           sem: asyncio.Semaphore):
        """Process a single chapter with semaphore-controlled concurrency."""
        async with sem:
            if ctx.pause_requested:
                return

            # Fetch chapter info
            async with get_db() as db:
                async with db.execute(
                    "SELECT title, raw_path, seq FROM chapters WHERE id=?",
                    (chapter_id,),
                ) as cur:
                    row = await cur.fetchone()
            if not row:
                return
            ch_title = row["title"]
            raw_path = row["raw_path"]
            ch_seq = row["seq"]

            # Mark processing
            async with get_db() as db:
                await db.execute(
                    "UPDATE chapters SET dehydrate_status='processing' WHERE id=?",
                    (chapter_id,),
                )
                await db.execute(
                    "UPDATE jobs SET current_chapter_id=?, updated_at=datetime('now') WHERE id=?",
                    (chapter_id, job_id),
                )
                await db.commit()

            # Broadcast current progress
            async with get_db() as db:
                async with db.execute(
                    "SELECT done_count, failed_count, total_count FROM jobs WHERE id=?",
                    (job_id,),
                ) as cur:
                    jrow = await cur.fetchone()
            done, failed, total = jrow["done_count"], jrow["failed_count"], jrow["total_count"]
            await self._broadcast(job_id, "progress", {
                "job_id": job_id,
                "done": done, "failed": failed, "total": total,
                "current": {"id": chapter_id, "title": ch_title},
            })

            # Dehydrate
            try:
                raw_text = await read_chapter(raw_path)
                dehydrated_text = await dehydrate_chapter(
                    book_title, ch_title, raw_text,
                    chapter_seq=ch_seq, total_chapters=total_chapters,
                )

                # Save result
                dpath = dehydrated_chapter_path(book_id, chapter_id)
                await write_dehydrated_chapter(dpath, dehydrated_text)

                ratio = len(dehydrated_text) / max(len(raw_text), 1)

                async with get_db() as db:
                    await db.execute(
                        """UPDATE chapters SET dehydrate_status='done', dehydrated_path=?,
                           dehydrated_char_count=?, compression_ratio=?,
                           processed_at=datetime('now') WHERE id=?""",
                        (dpath, len(dehydrated_text), ratio, chapter_id),
                    )
                    await db.execute(
                        "UPDATE jobs SET done_count=done_count+1, updated_at=datetime('now') WHERE id=?",
                        (job_id,),
                    )
                    await db.commit()
                await self._broadcast(job_id, "chapter_done", {
                    "chapter_id": chapter_id,
                    "status": "done",
                    "compression_ratio": round(ratio, 3),
                })

            except Exception as e:
                err_msg = str(e)[:500]
                async with get_db() as db:
                    await db.execute(
                        """UPDATE chapters SET dehydrate_status='failed',
                           error_msg=?, retry_count=retry_count+1 WHERE id=?""",
                        (err_msg, chapter_id),
                    )
                    await db.execute(
                        "UPDATE jobs SET failed_count=failed_count+1, updated_at=datetime('now') WHERE id=?",
                        (job_id,),
                    )
                    await db.commit()
                await self._broadcast(job_id, "chapter_failed", {
                    "chapter_id": chapter_id,
                    "status": "failed",
                    "error": err_msg[:200],
                })

    async def _run(self, job_id: int, chapter_ids: List[int], ctx: JobContext):
        if not chapter_ids:
            async with get_db() as db:
                await db.execute(
                    "UPDATE jobs SET status='completed', updated_at=datetime('now') WHERE id=?",
                    (job_id,),
                )
                await db.commit()
            await self._broadcast(job_id, "done", {
                "job_id": job_id, "status": "completed", "done": 0, "failed": 0, "total": 0,
            })
            return

        # Pre-fetch book info
        async with get_db() as db:
            async with db.execute(
                "SELECT book_id FROM chapters WHERE id=?", (chapter_ids[0],)
            ) as cur:
                row = await cur.fetchone()
            book_id = row["book_id"]
            async with db.execute(
                "SELECT title, total_chapters FROM books WHERE id=?", (book_id,)
            ) as cur:
                brow = await cur.fetchone()
            book_title = brow["title"] if brow else ""
            total_chapters = brow["total_chapters"] if brow else 0

        concurrency = await self._get_concurrency()
        sem = asyncio.Semaphore(concurrency)

        # Process chapters in concurrent batches
        # Use batched approach so pause can take effect between batches
        batch_size = concurrency
        for i in range(0, len(chapter_ids), batch_size):
            if ctx.pause_requested:
                await self._do_pause(job_id)
                return

            batch = chapter_ids[i:i + batch_size]
            tasks = [
                self._process_one(job_id, cid, ctx, book_id, book_title, total_chapters, sem)
                for cid in batch
            ]
            await asyncio.gather(*tasks)

            # Check pause after batch
            if ctx.pause_requested:
                await self._do_pause(job_id)
                return

        # All chapters processed
        async with get_db() as db:
            await db.execute(
                "UPDATE jobs SET status='completed', updated_at=datetime('now') WHERE id=?",
                (job_id,),
            )
            await db.commit()
            async with db.execute(
                "SELECT done_count, failed_count, total_count FROM jobs WHERE id=?",
                (job_id,),
            ) as cur:
                jrow = await cur.fetchone()
        await self._broadcast(job_id, "done", {
            "job_id": job_id,
            "status": "completed",
            "done": jrow["done_count"],
            "failed": jrow["failed_count"],
            "total": jrow["total_count"],
        })
