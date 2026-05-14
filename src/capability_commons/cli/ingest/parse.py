"""Pass 0: Parse PDFs into page-preserving markdown segments."""
from __future__ import annotations

import re
from pathlib import Path

import orjson
import yaml

from capability_commons.cli.ingest.models import SourceSegment
from capability_commons.cli.ingest.project import IngestProject


PAGE_SEPARATOR_DASHES = "-" * 48
# marker-pdf paginate_output format: "\n\n{N}{'-'*48}\n\n" preceding each page
# (N is 0-indexed). We normalize this to <!-- PAGE M --> markers (1-indexed).
_MARKER_PAGE_RE = re.compile(
    r"\n*\{(\d+)\}" + re.escape(PAGE_SEPARATOR_DASHES) + r"-*\n*"
)


def _normalize_marker_pagination(markdown: str) -> str:
    """Convert marker's `{N}----...----` page separators into `<!-- PAGE M -->`."""
    def repl(m: re.Match) -> str:
        page_1indexed = int(m.group(1)) + 1
        return f"\n\n<!-- PAGE {page_1indexed} -->\n\n"
    return _MARKER_PAGE_RE.sub(repl, markdown)


def convert_pdf_to_markdown(pdf_path: str) -> dict:
    """Convert a PDF to markdown using marker. Thin wrapper for mockability.

    Uses ``paginate_output=True`` so the rendered markdown contains explicit
    page separators which we normalize into ``<!-- PAGE N -->`` markers.
    """
    try:
        from marker.converters.pdf import PdfConverter
        from marker.config.parser import ConfigParser
        from marker.models import create_model_dict
    except ImportError:
        raise ImportError(
            "marker-pdf is required for PDF parsing. "
            "Install with: pip install -e '.[ingest]'"
        )

    config_parser = ConfigParser({"paginate_output": True})
    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=create_model_dict(),
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
    )
    rendered = converter(pdf_path)
    metadata = getattr(rendered, "metadata", {}) or {}
    page_stats = metadata.get("page_stats", [])
    n_pages = len(page_stats) if page_stats else max(
        1, len(_MARKER_PAGE_RE.findall(rendered.markdown))
    )
    markdown = _normalize_marker_pagination(rendered.markdown)
    return {
        "markdown": markdown,
        "pages": [{"page": i + 1} for i in range(n_pages)],
    }


def markdown_to_segments(
    markdown: str,
    source_id: str,
    base_page: int = 1,
) -> list[SourceSegment]:
    """Split markdown into segments at heading boundaries with page tracking.

    Page markers are HTML comments like ``<!-- PAGE N -->``. The PDF converter
    inserts these via ``_normalize_marker_pagination`` (from marker's
    ``paginate_output``); plain markdown sources can include them manually. If
    no markers are present, all segments default to *base_page*.

    Segments that span a page boundary correctly report ``page_start`` (the
    page at the segment's first non-marker character) and ``page_end`` (the
    last page touched by the segment).
    """
    # If the input came in with raw marker separators, normalize first so we
    # can treat <!-- PAGE N --> as the single canonical page-marker form.
    if _MARKER_PAGE_RE.search(markdown):
        markdown = _normalize_marker_pagination(markdown)

    heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    page_re = re.compile(r"<!--\s*PAGE\s+(\d+)\s*-->", re.IGNORECASE)
    segments: list[SourceSegment] = []

    # Build page map: list of (char_offset, page_number) where the marker SETS
    # the page for content at and after that offset.
    page_breaks: list[tuple[int, int]] = []
    for m in page_re.finditer(markdown):
        page_breaks.append((m.end(), int(m.group(1))))

    def _page_at(char_pos: int) -> int:
        """Return the page number at a given character position."""
        page = base_page
        for offset, pg in page_breaks:
            if offset <= char_pos:
                page = pg
            else:
                break
        return page

    def _last_content_pos(start: int, end: int) -> int:
        """Return the position of the last non-marker, non-whitespace char
        in markdown[start:end], or `start` if the range has no such char.

        Used so a segment ending right before a `<!-- PAGE N -->` marker is
        attributed to its actual content page, not the next page.
        """
        # Mask out marker spans that overlap [start, end).
        spans = [
            (m.start(), m.end())
            for m in page_re.finditer(markdown, start, end)
        ]

        def in_marker(pos: int) -> bool:
            for s, e in spans:
                if s <= pos < e:
                    return True
            return False

        pos = end - 1
        while pos >= start:
            if not in_marker(pos) and not markdown[pos].isspace():
                return pos
            pos -= 1
        return start

    # Find all heading positions
    splits: list[tuple[int, list[str]]] = []
    heading_stack: list[str] = []

    for match in heading_re.finditer(markdown):
        level = len(match.group(1))
        title = match.group(2).strip()
        heading_stack = heading_stack[: level - 1]
        heading_stack.append(title)
        splits.append((match.start(), list(heading_stack)))

    def _clean_text(start: int, end: int) -> str:
        """Strip page markers from a segment slice and trim whitespace."""
        return page_re.sub("", markdown[start:end]).strip()

    if not splits:
        text = _clean_text(0, len(markdown))
        if text:
            segments.append(SourceSegment(
                source_id=source_id,
                segment_id=f"{source_id}::seg_000001",
                page_start=_page_at(0),
                page_end=_page_at(_last_content_pos(0, len(markdown))),
                heading_path=[],
                text=text,
                start_char=0,
                end_char=len(markdown),
            ))
        return segments

    for i, (start, heading_path) in enumerate(splits):
        end = splits[i + 1][0] if i + 1 < len(splits) else len(markdown)
        text = _clean_text(start, end)
        if not text:
            continue

        seg_num = i + 1
        segments.append(SourceSegment(
            source_id=source_id,
            segment_id=f"{source_id}::seg_{seg_num:06d}",
            page_start=_page_at(start),
            page_end=_page_at(_last_content_pos(start, end)),
            heading_path=heading_path,
            text=text,
            start_char=start,
            end_char=end,
        ))

    return segments


def run_parse(project: IngestProject) -> None:
    """Execute Pass 0: parse all source PDFs into segments."""
    from rich.console import Console

    console = Console()
    all_segments: list[SourceSegment] = []
    source_records: list[dict] = []

    for source in project.manifest.sources:
        source_path = project.root / source.file
        console.print(f"  Parsing [bold]{source.file}[/bold]...")

        if source_path.suffix.lower() == ".pdf":
            result = convert_pdf_to_markdown(str(source_path))
            markdown = result["markdown"]
            n_pages = len(result.get("pages", []))
        else:
            # Assume text/markdown file
            markdown = source_path.read_text()
            n_pages = 1

        segments = markdown_to_segments(markdown, source.id)
        all_segments.extend(segments)

        source_records.append({
            "source_id": source.id,
            "title": source.title,
            "source_kind": source.source_kind,
            "file": source.file,
            "pages": n_pages,
            "segments": len(segments),
        })
        console.print(f"    → {len(segments)} segments from {n_pages} pages")

    # Write segments JSONL
    with open(project.segments_file, "wb") as f:
        for seg in all_segments:
            f.write(orjson.dumps(seg.model_dump()) + b"\n")

    # Write source manifest
    source_manifest_path = project.segments_dir / "source_manifest.yaml"
    with open(source_manifest_path, "w") as f:
        yaml.dump(source_records, f, default_flow_style=False)

    project.mark_pass_complete("parse")
    console.print(f"[green]Parse complete:[/green] {len(all_segments)} segments from {len(project.manifest.sources)} source(s)")
