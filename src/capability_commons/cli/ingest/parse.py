"""Pass 0: Parse PDFs into page-preserving markdown segments."""
from __future__ import annotations

import re
from pathlib import Path

import orjson
import yaml

from capability_commons.cli.ingest.models import SourceSegment
from capability_commons.cli.ingest.project import IngestProject


def convert_pdf_to_markdown(pdf_path: str) -> dict:
    """Convert a PDF to markdown using marker. Thin wrapper for mockability."""
    try:
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
    except ImportError:
        raise ImportError(
            "marker-pdf is required for PDF parsing. "
            "Install with: pip install -e '.[ingest]'"
        )

    converter = PdfConverter(artifact_dict=create_model_dict())
    rendered = converter(pdf_path)
    return {
        "markdown": rendered.markdown,
        "pages": [{"page": i + 1} for i in range(len(rendered.pages))],
    }


def markdown_to_segments(
    markdown: str,
    source_id: str,
    base_page: int = 1,
) -> list[SourceSegment]:
    """Split markdown into segments at heading boundaries with page tracking.

    Page markers are HTML comments like ``<!-- PAGE N -->`` inserted by the
    PDF converter or manually.  If no markers are present, all segments
    default to *base_page*.
    """
    heading_re = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    page_re = re.compile(r"<!--\s*PAGE\s+(\d+)\s*-->", re.IGNORECASE)
    segments: list[SourceSegment] = []

    # Build page map: list of (char_offset, page_number)
    page_breaks: list[tuple[int, int]] = []
    for m in page_re.finditer(markdown):
        page_breaks.append((m.start(), int(m.group(1))))

    def _page_at(char_pos: int) -> int:
        """Return the page number at a given character position."""
        page = base_page
        for offset, pg in page_breaks:
            if offset <= char_pos:
                page = pg
            else:
                break
        return page

    # Find all heading positions
    splits: list[tuple[int, list[str]]] = []
    heading_stack: list[str] = []

    for match in heading_re.finditer(markdown):
        level = len(match.group(1))
        title = match.group(2).strip()
        heading_stack = heading_stack[: level - 1]
        heading_stack.append(title)
        splits.append((match.start(), list(heading_stack)))

    if not splits:
        if markdown.strip():
            segments.append(SourceSegment(
                source_id=source_id,
                segment_id=f"{source_id}::seg_000001",
                page_start=_page_at(0),
                page_end=_page_at(len(markdown) - 1),
                heading_path=[],
                text=markdown.strip(),
                start_char=0,
                end_char=len(markdown.strip()),
            ))
        return segments

    for i, (start, heading_path) in enumerate(splits):
        end = splits[i + 1][0] if i + 1 < len(splits) else len(markdown)
        text = markdown[start:end].strip()
        if not text:
            continue

        seg_num = i + 1
        segments.append(SourceSegment(
            source_id=source_id,
            segment_id=f"{source_id}::seg_{seg_num:06d}",
            page_start=_page_at(start),
            page_end=_page_at(end - 1),
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
