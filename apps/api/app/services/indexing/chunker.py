from __future__ import annotations

from dataclasses import dataclass
from typing import List

@dataclass
class Chunk:
    text: str
    start_line: int
    end_line: int

MIN_CHUNK_CHARS = 80

def should_skip_file(path: str) -> bool:
    p = path.lower()

    # Skip README and markdown docs
    if p.endswith("readme.md"):
        return True
    if p.endswith(".md"):
        return True

    # Skip non-code text noise
    if p.endswith((".txt", ".rst")):
        return True

    return False


def chunk_text_by_lines(
        text: str, 
        path: str,
        max_chars: int = 1800, 
        overlap_lines: int = 10
        ) -> List[Chunk]:
    """
    Simple chunker:
    - splits by lines
    - tries to keep chunks under max_chars
    - overlaps a few lines to preserve context
    """
    if should_skip_file(path):
        return []
    lines = text.splitlines()
    chunks: List[Chunk] = []

    i = 0
    while i < len(lines):
        start = i
        buf = []
        chars = 0

        while i < len(lines) and chars + len(lines[i]) + 1 <= max_chars:
            buf.append(lines[i])
            chars += len(lines[i]) + 1
            i += 1

        end = max(start, i - 1)
        chunk_text = "\n".join(buf).strip()
        if len(chunk_text) >= MIN_CHUNK_CHARS:
            chunks.append(
                Chunk(
                    text=chunk_text,
                    start_line=start + 1,
                    end_line=end + 1,
                )
            )
        # overlap
        i = max(i - overlap_lines, i) if overlap_lines <= 0 else max(start, i - overlap_lines)

        # if we didn't move forward (very long single line), force progress
        if i == start:
            i = start + 1

    return chunks