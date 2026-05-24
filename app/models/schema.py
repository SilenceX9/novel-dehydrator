from pydantic import BaseModel
from typing import Optional, List


class BookOut(BaseModel):
    id: int
    title: str
    author: str
    source_format: str
    total_chapters: int
    has_volumes: bool
    parse_status: str
    parse_error: Optional[str]
    created_at: str
    dehydrated_count: int = 0


class ChapterOut(BaseModel):
    id: int
    title: str
    seq: int
    raw_char_count: int
    dehydrate_status: str
    dehydrated_char_count: int
    compression_ratio: Optional[float]
    error_msg: Optional[str]


class VolumeOut(BaseModel):
    id: int
    title: str
    seq: int
    chapters: List[ChapterOut] = []


class BookStructureOut(BaseModel):
    book_id: int
    has_volumes: bool
    volumes: List[VolumeOut] = []
    loose_chapters: List[ChapterOut] = []


class JobOut(BaseModel):
    id: int
    book_id: int
    status: str
    scope_type: str
    total_count: int
    done_count: int
    failed_count: int
    current_chapter_id: Optional[int]
    created_at: str


class StartJobRequest(BaseModel):
    scope_type: str  # 'volumes' | 'chapters'
    volume_ids: Optional[List[int]] = None
    chapter_ids: Optional[List[int]] = None
