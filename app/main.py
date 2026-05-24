from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import BASE_DIR, DB_PATH
from app.database import init_db, get_db
from app.api import books, structure, jobs, progress, export, settings, chat, prompts

TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Crash recovery: reset stuck jobs and processing chapters
    async with get_db() as db:
        await db.execute(
            "UPDATE jobs SET status='paused', updated_at=datetime('now') WHERE status='running'"
        )
        await db.execute(
            "UPDATE chapters SET dehydrate_status='pending' WHERE dehydrate_status='processing'"
        )
        await db.commit()
    yield


app = FastAPI(title="小说速读", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

app.include_router(books.router)
app.include_router(structure.router)
app.include_router(jobs.router)
app.include_router(progress.router)
app.include_router(export.router)
app.include_router(settings.router)
app.include_router(chat.router)
app.include_router(prompts.router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/book/{book_id}", response_class=HTMLResponse)
async def book_detail(request: Request, book_id: int):
    return templates.TemplateResponse("book.html", {"request": request, "book_id": book_id})


@app.get("/book/{book_id}/reader", response_class=HTMLResponse)
async def reader(request: Request, book_id: int):
    return templates.TemplateResponse("reader.html", {"request": request, "book_id": book_id})
