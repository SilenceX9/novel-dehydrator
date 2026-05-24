import re
from typing import List, Dict, Optional
from charset_normalizer import from_path

CHAPTER_RE = re.compile(
    r"^[\s　]*第[零一二三四五六七八九十百千万\d]+[章节回集][\s　].*$",
    re.MULTILINE,
)
VOLUME_RE = re.compile(
    r"^[\s　]*(?:第[零一二三四五六七八九十百千\d]*)?[^\n第]{1,15}[篇卷部册][\s　]*$",
    re.MULTILINE,
)


def _detect_and_read(file_path: str) -> str:
    result = from_path(file_path).best()
    if result is None:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    return str(result)


def parse_txt(file_path: str) -> Dict:
    content = _detect_and_read(file_path)

    import os
    filename = os.path.basename(file_path)
    # Try to extract title from filename
    title = filename.rsplit(".", 1)[0] if "." in filename else filename

    chapters: List[Dict] = []
    current_volume: Optional[str] = None
    current_title: Optional[str] = None
    current_lines: List[str] = []

    def flush_chapter():
        if current_title is not None:
            chapters.append({
                "title": current_title,
                "text": "\n".join(current_lines).strip(),
                "volume": current_volume,
            })

    for line in content.splitlines():
        stripped = line.strip()
        # Volume match (must not look like a chapter line)
        if VOLUME_RE.match(line) and not CHAPTER_RE.match(line) and len(stripped) <= 20:
            flush_chapter()
            current_volume = stripped
            current_title = None
            current_lines = []
        elif CHAPTER_RE.match(line):
            flush_chapter()
            current_title = stripped
            current_lines = []
        else:
            if current_title is not None:
                current_lines.append(line)

    flush_chapter()

    # If no chapters detected, treat whole content as one chapter
    if not chapters:
        chapters = [{"title": "全文", "text": content.strip(), "volume": None}]

    return {"title": title, "author": "", "chapters": chapters, "has_nested_toc": False}
