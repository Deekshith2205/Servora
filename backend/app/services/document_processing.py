"""[RAG] Phase 2/3 — extracting, cleaning, and chunking an uploaded
document (#231-#233 upload support, #237 text extraction, #238 text
cleaning, #239 chunking, #240 chunk metadata generation).

Three concerns, kept in one module since they're a strict pipeline with
no other caller (`app/services/knowledge_retrieval.py` is the only
thing that calls any of this):

1. ``extract_segments()`` — file_type-specific extraction into a list of
   segments, each already carrying whatever real structural metadata
   that file type has (a PDF's page number, a DOCX's nearest preceding
   Heading-style paragraph). A .txt file has neither — its one segment
   has both fields ``None``, honestly, not a fabricated "page 1".
2. ``clean_text()`` — whitespace/control-character normalization.
3. ``chunk_segments()`` — packs each segment's cleaned text into
   overlapping, paragraph/sentence-boundary-aware chunks, and returns
   ``char_start``/``char_end`` as real offsets into the FULL document's
   cleaned text (concatenating every segment in order) — matching
   ``KnowledgeChunk.chunk_metadata_json``'s own docstring, not offsets
   local to one segment.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pypdf
from docx import Document as DocxDocument

# Target chunk size and overlap, in characters — sized for a real Gemini
# embedding call (well under any token limit) while staying large enough
# that a chunk is still a coherent, citable unit of policy text rather
# than a fragment.
_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 150

# Supported file types — [RAG] #231/#232/#233.
SUPPORTED_FILE_TYPES = frozenset({"pdf", "docx", "txt"})


class UnsupportedFileTypeError(ValueError):
    """Raised for a file_type outside SUPPORTED_FILE_TYPES — [RAG] #234."""


@dataclass
class Segment:
    text: str
    page_number: int | None
    section_heading: str | None


@dataclass
class Chunk:
    text: str
    page_number: int | None
    section_heading: str | None
    char_start: int
    char_end: int


def extract_segments(file_path: str, file_type: str) -> list[Segment]:
    """Dispatch to the file_type-specific extractor. Raises
    ``UnsupportedFileTypeError`` for anything outside pdf/docx/txt —
    [RAG] #234's own document-validation requirement."""
    if file_type == "pdf":
        return _extract_pdf(file_path)
    if file_type == "docx":
        return _extract_docx(file_path)
    if file_type == "txt":
        return _extract_txt(file_path)
    raise UnsupportedFileTypeError(
        f"Unsupported file_type {file_type!r} — must be one of {sorted(SUPPORTED_FILE_TYPES)}."
    )


def _extract_pdf(file_path: str) -> list[Segment]:
    reader = pypdf.PdfReader(file_path)
    segments: list[Segment] = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            segments.append(Segment(text=text, page_number=i + 1, section_heading=None))
    return segments


def _extract_docx(file_path: str) -> list[Segment]:
    """Groups paragraphs by the nearest preceding Heading-style
    paragraph, matching the way a real policy document is actually
    organized. python-docx has no reliable notion of a "page" (page
    breaks are a rendering-time concept Word computes, not something
    stored per-paragraph) — page_number is honestly ``None`` throughout,
    never a fabricated estimate."""
    doc = DocxDocument(file_path)
    segments: list[Segment] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def _flush() -> None:
        if current_lines:
            segments.append(
                Segment(text="\n".join(current_lines), page_number=None, section_heading=current_heading)
            )

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue
        style_name = (para.style.name or "") if para.style else ""
        if style_name.startswith("Heading") or style_name == "Title":
            _flush()
            current_lines = []
            current_heading = text
        else:
            current_lines.append(text)
    _flush()
    return segments


def _extract_txt(file_path: str) -> list[Segment]:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if not text.strip():
        return []
    return [Segment(text=text, page_number=None, section_heading=None)]


# --------------------------------------------------------------------- #
# Cleaning — [RAG] #238
# --------------------------------------------------------------------- #

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_MULTI_BLANK_LINES_RE = re.compile(r"\n{3,}")
_TRAILING_SPACES_RE = re.compile(r"[ \t]+\n")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")


def clean_text(text: str) -> str:
    """Normalizes whitespace and strips control characters left over
    from PDF/DOCX extraction (form-feeds, stray null bytes) — never
    touches real punctuation or wording, so a citation still reads as
    the source document actually wrote it."""
    text = _CONTROL_CHARS_RE.sub("", text)
    text = _TRAILING_SPACES_RE.sub("\n", text)
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


# --------------------------------------------------------------------- #
# Chunking — [RAG] #239/#240
# --------------------------------------------------------------------- #

def chunk_segments(
    segments: list[Segment], chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP
) -> list[Chunk]:
    """Cleans and chunks every segment in order, returning
    ``char_start``/``char_end`` as offsets into the full document's
    cleaned text (each segment's own cleaned text, joined with "\\n\\n",
    in order) — matching ``KnowledgeChunk.chunk_metadata_json``'s
    docstring. Chunks never span two segments (a PDF page boundary, a
    DOCX section boundary) — a chunk that straddled two pages would have
    no single correct page_number to cite, so this keeps every chunk's
    attribution unambiguous."""
    chunks: list[Chunk] = []
    global_offset = 0
    for segment in segments:
        cleaned = clean_text(segment.text)
        if not cleaned:
            continue
        for piece_text, piece_start, piece_end in _pack_into_windows(cleaned, chunk_size, overlap):
            chunks.append(
                Chunk(
                    text=piece_text,
                    page_number=segment.page_number,
                    section_heading=segment.section_heading,
                    char_start=global_offset + piece_start,
                    char_end=global_offset + piece_end,
                )
            )
        # +2 for the "\n\n" that would join this segment to the next in
        # the full document's cleaned text, kept consistent even though
        # no single joined string is ever actually materialized.
        global_offset += len(cleaned) + 2
    return chunks


def _pack_into_windows(text: str, chunk_size: int, overlap: int) -> list[tuple[str, int, int]]:
    """Slides a window across ``text``, snapping each window's end to
    the nearest paragraph break, then sentence break, within a lookback
    margin — so a chunk reads as a coherent unit of prose rather than
    being cut mid-sentence. Falls back to a hard cut only when no
    natural break exists nearby (e.g. one very long unbroken sentence).
    """
    n = len(text)
    if n <= chunk_size:
        return [(text, 0, n)]

    windows: list[tuple[str, int, int]] = []
    start = 0
    lookback = min(200, chunk_size // 2)

    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            margin_start = max(start, end - lookback)
            margin = text[margin_start:end]
            best_break = max(margin.rfind("\n\n"), margin.rfind(". "), margin.rfind("\n"))
            if best_break != -1:
                end = margin_start + best_break + 1

        piece = text[start:end]
        stripped = piece.strip()
        if stripped:
            leading_ws = len(piece) - len(piece.lstrip())
            piece_start = start + leading_ws
            piece_end = piece_start + len(stripped)
            windows.append((stripped, piece_start, piece_end))

        if end >= n:
            break
        # Always make forward progress even if overlap >= the advance
        # a boundary-snap produced, to guarantee loop termination.
        start = max(end - overlap, start + 1)

    return windows
