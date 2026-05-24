from typing import List, Dict, Optional
from ebooklib import epub, ITEM_DOCUMENT
from bs4 import BeautifulSoup


def _item_text(item) -> str:
    soup = BeautifulSoup(item.get_content(), "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    lines = []
    for p in soup.find_all(["p", "div"]):
        text = p.get_text(separator="", strip=True)
        if text:
            lines.append(text)
    return "\n".join(lines) if lines else soup.get_text(separator="\n", strip=True)


def _build_items_map(book: epub.EpubBook) -> Dict[str, object]:
    items_map: Dict[str, object] = {}
    for item in book.get_items_of_type(ITEM_DOCUMENT):
        name = item.get_name()
        items_map[name] = item
        # Also index by basename for loose href matching
        items_map[name.split("/")[-1]] = item
    return items_map


def _toc_entries(toc, items_map, parent_volume=None) -> List[Dict]:
    results = []
    for entry in toc:
        if isinstance(entry, epub.Link):
            href = entry.href.split("#")[0]
            item = items_map.get(href) or items_map.get(href.split("/")[-1])
            text = _item_text(item) if item else ""
            results.append({
                "title": entry.title or "（无标题）",
                "text": text,
                "volume": parent_volume,
            })
        elif isinstance(entry, tuple):
            section, children = entry
            vol_title = section.title if hasattr(section, "title") else str(section)
            results.extend(_toc_entries(children, items_map, parent_volume=vol_title))
        elif isinstance(entry, list):
            results.extend(_toc_entries(entry, items_map, parent_volume))
    return results


def parse_epub(file_path: str) -> Dict:
    book = epub.read_epub(file_path, options={"ignore_ncx": False})

    meta_title = book.get_metadata("DC", "title")
    meta_author = book.get_metadata("DC", "creator")
    title = meta_title[0][0] if meta_title else "未知书名"
    author = meta_author[0][0] if meta_author else ""

    items_map = _build_items_map(book)

    # Check if TOC has nested structure (indicates volumes)
    has_nested = any(isinstance(e, tuple) for e in book.toc)

    chapters = _toc_entries(book.toc, items_map)

    # Deduplicate by title+volume to handle malformed TOCs
    seen = set()
    deduped = []
    for ch in chapters:
        key = (ch["title"], ch["volume"])
        if key not in seen:
            seen.add(key)
            deduped.append(ch)

    return {
        "title": title,
        "author": author,
        "chapters": deduped,
        "has_nested_toc": has_nested,
    }
