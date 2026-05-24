import aiosqlite
from app.config import DB_PATH

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS books (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title           TEXT NOT NULL,
    author          TEXT DEFAULT '',
    source_format   TEXT NOT NULL,
    source_path     TEXT NOT NULL,
    total_chapters  INTEGER DEFAULT 0,
    has_volumes     INTEGER DEFAULT 0,
    parse_status    TEXT DEFAULT 'pending',
    parse_error     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS volumes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id       INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    title         TEXT NOT NULL,
    seq           INTEGER NOT NULL,
    detect_source TEXT,
    UNIQUE(book_id, seq)
);

CREATE TABLE IF NOT EXISTS chapters (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id               INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    volume_id             INTEGER REFERENCES volumes(id) ON DELETE SET NULL,
    title                 TEXT NOT NULL,
    seq                   INTEGER NOT NULL,
    raw_path              TEXT NOT NULL,
    raw_char_count        INTEGER DEFAULT 0,
    dehydrate_status      TEXT DEFAULT 'pending',
    dehydrated_path       TEXT,
    dehydrated_char_count INTEGER DEFAULT 0,
    compression_ratio     REAL,
    error_msg             TEXT,
    retry_count           INTEGER DEFAULT 0,
    processed_at          TEXT,
    UNIQUE(book_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_chapters_book   ON chapters(book_id, seq);
CREATE INDEX IF NOT EXISTS idx_chapters_status ON chapters(book_id, dehydrate_status);

CREATE TABLE IF NOT EXISTS jobs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id            INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    status             TEXT DEFAULT 'running',
    scope_type         TEXT NOT NULL,
    total_count        INTEGER NOT NULL,
    done_count         INTEGER DEFAULT 0,
    failed_count       INTEGER DEFAULT 0,
    current_chapter_id INTEGER,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS job_chapters (
    job_id     INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    chapter_id INTEGER NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, chapter_id)
);

CREATE TABLE IF NOT EXISTS app_settings (
    id               INTEGER PRIMARY KEY CHECK (id = 1),
    deepseek_api_key TEXT    DEFAULT '',
    deepseek_model   TEXT    DEFAULT 'deepseek-v4-flash',
    deepseek_base_url TEXT   DEFAULT 'https://api.deepseek.com',
    concurrency      INTEGER DEFAULT 5,
    system_prompt    TEXT    DEFAULT ''
);
INSERT OR IGNORE INTO app_settings (id) VALUES (1);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(CREATE_TABLES_SQL)
        # Migrate: add new columns to existing tables
        try:
            await db.execute("ALTER TABLE app_settings ADD COLUMN concurrency INTEGER DEFAULT 5")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE app_settings ADD COLUMN system_prompt TEXT DEFAULT ''")
        except Exception:
            pass
        await db.commit()


class get_db:
    async def __aenter__(self) -> aiosqlite.Connection:
        self.conn = await aiosqlite.connect(DB_PATH)
        self.conn.row_factory = aiosqlite.Row
        return self.conn

    async def __aexit__(self, *args):
        await self.conn.close()
