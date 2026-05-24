from typing import List, Dict, Optional, Tuple


def detect_structure(chapters: List[Dict], has_nested_toc: bool) -> Tuple[List[Dict], List[Dict]]:
    """
    Returns (volumes, chapters_with_volume_id_placeholder).
    volumes: [{"title": str, "seq": int, "detect_source": str}]
    chapters: same list with "volume_seq" key added (int or None)
    """
    # If epub already has nested TOC, volumes are set via chapter["volume"]
    if has_nested_toc:
        return _from_volume_field(chapters, source="toc")

    # Keyword-based detection: look for "篇/卷/部/册" in chapter titles
    volume_keywords = re.compile(r"[篇卷部册]")
    volume_positions = []
    for i, ch in enumerate(chapters):
        title = ch.get("title", "")
        if volume_keywords.search(title) and len(title) <= 25:
            volume_positions.append((i, title))

    if volume_positions:
        return _from_volume_positions(chapters, volume_positions, source="keyword")

    # Use pre-set volume field (from txt parser's VOLUME_RE)
    has_volume_field = any(ch.get("volume") for ch in chapters)
    if has_volume_field:
        return _from_volume_field(chapters, source="keyword")

    # No volumes detected
    return [], chapters


def _from_volume_field(chapters: List[Dict], source: str):
    volumes = []
    vol_seq_map: Dict[str, int] = {}
    seq = 0

    for ch in chapters:
        vol_title = ch.get("volume")
        if vol_title and vol_title not in vol_seq_map:
            seq += 1
            vol_seq_map[vol_title] = seq
            volumes.append({"title": vol_title, "seq": seq, "detect_source": source})
        ch["volume_seq"] = vol_seq_map.get(vol_title) if vol_title else None

    return volumes, chapters


def _from_volume_positions(chapters: List[Dict], positions: List[Tuple], source: str):
    volumes = []
    seq = 0
    # Build range: position[i] ~ position[i+1]-1 belongs to volume[i]
    breaks = [pos for pos, _ in positions] + [len(chapters)]

    for idx, (start, vol_title) in enumerate(positions):
        seq += 1
        volumes.append({"title": vol_title, "seq": seq, "detect_source": source})
        end = breaks[idx + 1]
        for i in range(start, end):
            chapters[i]["volume_seq"] = seq

    # Chapters before first volume marker
    first_break = breaks[0]
    for i in range(first_break):
        chapters[i]["volume_seq"] = None

    return volumes, chapters


import re
