from __future__ import annotations


DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 150


def split_text(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be greater than or equal to 0 and less than chunk_size")

    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_text(paragraph, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
            continue

        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            chunks.append(current)
        current = paragraph

    if current:
        chunks.append(current)

    if chunk_overlap <= 0 or len(chunks) <= 1:
        return chunks
    return _add_chunk_overlap(chunks, chunk_overlap=chunk_overlap)


def _split_long_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunk = text[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        next_start = start + chunk_size - chunk_overlap
        if next_start <= start:
            break
        start = next_start
    return chunks


def _add_chunk_overlap(chunks: list[str], *, chunk_overlap: int) -> list[str]:
    overlapped = [chunks[0]]
    for previous, current in zip(chunks[:-1], chunks[1:], strict=True):
        prefix = previous[-chunk_overlap:].strip()
        if prefix and not current.startswith(prefix):
            overlapped.append(f"{prefix}\n\n{current}")
        else:
            overlapped.append(current)
    return overlapped
