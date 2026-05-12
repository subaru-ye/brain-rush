from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | {".pdf"}


@dataclass
class LoadedDocument:
    path: Path
    text: str
    source_type: str
    metadata: dict


def load_local_document(path: str | Path) -> LoadedDocument:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Document file does not exist: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"Document path is not a file: {resolved}")

    suffix = resolved.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise ValueError(f"Unsupported document type {suffix!r}; supported types: {supported}")

    if suffix in TEXT_SUFFIXES:
        text = resolved.read_text(encoding="utf-8-sig")
        source_type = "markdown" if suffix in {".md", ".markdown"} else "txt"
        metadata = _base_metadata(resolved)
    else:
        text, page_count = _read_pdf_text(resolved)
        source_type = "pdf"
        metadata = {**_base_metadata(resolved), "pageCount": page_count}

    if not text.strip():
        raise ValueError(f"Document does not contain extractable text: {resolved}")

    return LoadedDocument(
        path=resolved,
        text=text,
        source_type=source_type,
        metadata=metadata,
    )


def _base_metadata(path: Path) -> dict:
    stat = path.stat()
    return {
        "fileName": path.name,
        "extension": path.suffix.lower(),
        "fileSize": stat.st_size,
        "absolutePath": str(path),
    }


def _read_pdf_text(path: Path) -> tuple[str, int]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("PDF import requires pypdf; install backend requirements first") from exc

    reader = PdfReader(str(path))
    page_texts = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(text for text in page_texts if text), len(reader.pages)
