"""Format-specific document conversion with shared output and error handling."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import mimetypes
from pathlib import Path
import re
from typing import Callable
from urllib.parse import quote


class ConversionError(Exception):
    """A document could not be converted into useful Markdown."""


@dataclass(frozen=True)
class ConversionOptions:
    export_images: bool = True
    cleanup_repeated_headers: bool = False


@dataclass
class ConversionResult:
    source: Path
    destination: Path
    image_files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class _ImageWriter:
    """Extract embedded images to a source-named sibling directory."""

    def __init__(self, source: Path, destination: Path, enabled: bool) -> None:
        self.enabled = enabled
        self.directory = destination.parent / source.stem
        self.relative_directory = source.stem
        self.image_files: list[Path] = []
        self._next_id = 1

    def add(self, data: bytes, content_type: str, fallback_name: str = "") -> str:
        if not self.enabled:
            return "[Image not exported]"
        extension = Path(fallback_name).suffix.lower()
        if not extension:
            extension = mimetypes.guess_extension(content_type) or ".bin"
        if not re.fullmatch(r"\.[a-z0-9]{1,8}", extension):
            extension = ".bin"

        self.directory.mkdir(parents=True, exist_ok=True)
        filename = f"image_{self._next_id:03d}{extension}"
        self._next_id += 1
        image_path = self.directory / filename
        image_path.write_bytes(data)
        self.image_files.append(image_path)
        relative = f"{self.relative_directory}/{filename}"
        return f"![{Path(filename).stem}]({quote(relative, safe='/._-')})"


def convert_document(
    source: str | Path,
    destination: str | Path,
    options: ConversionOptions | None = None,
) -> ConversionResult:
    """Convert one supported source file and write UTF-8 Markdown to destination."""
    source_path = Path(source)
    destination_path = Path(destination)
    settings = options or ConversionOptions()
    extension = source_path.suffix.casefold()
    image_writer = _ImageWriter(source_path, destination_path, settings.export_images)

    if not source_path.is_file():
        raise ConversionError(f"Source file does not exist: {source_path}")
    if extension == ".docx":
        markdown = _convert_docx(source_path, image_writer)
    elif extension == ".pdf":
        markdown = _convert_pdf(source_path, image_writer, settings)
    elif extension == ".txt":
        markdown = _decode_text(source_path.read_bytes())
    elif extension == ".rtf":
        markdown = _convert_rtf(source_path)
    else:
        raise ConversionError(f"Unsupported input format: {extension or '(no extension)'}")

    markdown = _normalize_markdown(markdown)
    if not markdown and not image_writer.image_files:
        raise ConversionError("The document did not contain extractable text or images.")

    try:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(markdown, encoding="utf-8", newline="\n")
    except OSError as error:
        raise ConversionError(f"Could not write Markdown file: {error}") from error

    return ConversionResult(
        source=source_path,
        destination=destination_path,
        image_files=image_writer.image_files,
    )


def _convert_docx(source: Path, images: _ImageWriter) -> str:
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        from docx.oxml.ns import qn

        document = Document(source)
        blocks: list[str] = []
        previous_was_list = False

        def append_block(content: str, *, is_list: bool = False) -> None:
            nonlocal previous_was_list
            if blocks:
                blocks.append("\n" if previous_was_list and is_list else "\n\n")
            blocks.append(content)
            previous_was_list = is_list

        for content_block in document.iter_inner_content():
            if isinstance(content_block, Table):
                table_markdown = _docx_table(content_block, document, images, qn)
                if table_markdown:
                    append_block(table_markdown)
                continue
            if not isinstance(content_block, Paragraph):
                continue
            paragraph = content_block
            content = _docx_paragraph(paragraph, document, images, qn)
            if not content.strip():
                previous_was_list = False
                continue
            style_name = paragraph.style.name if paragraph.style else ""
            is_list = False
            heading = re.match(r"Heading\s+(\d+)", style_name, re.IGNORECASE)
            if heading:
                level = min(max(int(heading.group(1)), 1), 6)
                content = f"{'#' * level} {content.strip()}"
            elif style_name.casefold() == "title":
                content = f"# {content.strip()}"
            elif style_name.casefold() == "subtitle":
                content = f"## {content.strip()}"
            else:
                list_info = _docx_list_info(paragraph, document, qn)
                if list_info:
                    level, ordered = list_info
                    marker = "1." if ordered else "-"
                    content = f"{'  ' * level}{marker} {content.strip()}"
                    is_list = True
            append_block(content, is_list=is_list)

        return "".join(blocks)
    except ConversionError:
        raise
    except Exception as error:
        raise ConversionError(f"Could not read DOCX document: {error}") from error


def _docx_paragraph(paragraph, document, images: _ImageWriter, qn: Callable[[str], str]) -> str:
    chunks: list[str] = []
    for run in paragraph.runs:
        text = run.text.replace("\r", "").replace("\n", "  \n")
        if text:
            if run.bold and run.italic:
                text = f"***{text}***"
            elif run.bold:
                text = f"**{text}**"
            elif run.italic:
                text = f"*{text}*"
            if run.underline:
                text = f"<u>{text}</u>"
            if run.font.strike:
                text = f"~~{text}~~"
            chunks.append(text)

        for blip in run._element.xpath(".//a:blip"):
            relationship_id = blip.get(qn("r:embed"))
            if not relationship_id:
                chunks.append("[Linked image]")
                continue
            relationship = document.part.rels.get(relationship_id)
            if relationship is None:
                chunks.append("[Image unavailable]")
                continue
            image_part = relationship.target_part
            chunks.append(images.add(image_part.blob, image_part.content_type, image_part.partname.filename))
    return "".join(chunks).strip()


def _docx_list_info(paragraph, document, qn: Callable[[str], str]) -> tuple[int, bool] | None:
    properties = paragraph._p.pPr
    numbering = properties.numPr if properties is not None else None
    if numbering is not None and numbering.numId is not None:
        num_id = str(numbering.numId.val)
        level = int(numbering.ilvl.val) if numbering.ilvl is not None else 0
        ordered = _docx_numbering_is_ordered(document, num_id, level, qn)
        return level, ordered

    style_name = paragraph.style.name.casefold() if paragraph.style else ""
    if style_name.startswith("list bullet"):
        return 0, False
    if style_name.startswith("list number"):
        return 0, True
    return None


def _docx_numbering_is_ordered(document, num_id: str, level: int, qn: Callable[[str], str]) -> bool:
    numbering = document.part.numbering_part.element
    for number in numbering.findall(qn("w:num")):
        if number.get(qn("w:numId")) != num_id:
            continue
        abstract_id = number.find(qn("w:abstractNumId"))
        if abstract_id is None:
            break
        for abstract in numbering.findall(qn("w:abstractNum")):
            if abstract.get(qn("w:abstractNumId")) != abstract_id.get(qn("w:val")):
                continue
            for level_element in abstract.findall(qn("w:lvl")):
                if int(level_element.get(qn("w:ilvl"), "0")) != level:
                    continue
                format_element = level_element.find(qn("w:numFmt"))
                return bool(format_element is not None and format_element.get(qn("w:val")) != "bullet")
    return False


def _docx_table(table, document, images: _ImageWriter, qn: Callable[[str], str]) -> str:
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    rows: list[list[str]] = []
    for row in table.rows:
        cells: list[str] = []
        for cell in row.cells:
            paragraphs: list[str] = []
            for block in cell.iter_inner_content():
                if isinstance(block, Paragraph):
                    paragraphs.append(_docx_paragraph(block, document, images, qn))
                elif isinstance(block, Table):
                    nested = _docx_table(block, document, images, qn)
                    if nested:
                        paragraphs.append(nested)
            cells.append(_clean_cell("\n".join(paragraphs)))
        rows.append(cells)
    if not rows:
        return ""
    width = max((len(row) for row in rows), default=0)
    if not width:
        return ""
    rows = [row + [""] * (width - len(row)) for row in rows]
    header = rows[0]
    separator = ["---"] * width
    body = rows[1:]
    return "\n".join([_markdown_row(header), _markdown_row(separator), *(_markdown_row(row) for row in body)])


def _convert_pdf(source: Path, images: _ImageWriter, options: ConversionOptions) -> str:
    try:
        import pymupdf

        document = pymupdf.open(source)
        try:
            return _convert_pdf_document(document, images, options)
        finally:
            document.close()
    except ConversionError:
        raise
    except Exception as error:
        raise ConversionError(f"Could not read PDF document: {error}") from error


def _convert_pdf_document(document, images: _ImageWriter, options: ConversionOptions) -> str:
    pages: list[str] = []
    page_texts: list[str] = []
    page_images: list[list[int]] = []
    for page in document:
        text = _pdf_page_content(page)
        page_texts.append(text)
        page_content = text
        page_images.append([xref for xref, *_rest in page.get_images(full=True)])
        if page_images[-1] and not images.enabled:
            page_content = f"{page_content}\n\n[Image not exported]" if page_content else "[Image not exported]"
        pages.append(page_content)

    all_text = "\n".join(page_texts)
    if len(re.sub(r"\s", "", all_text)) < 20:
        has_images = any(page_images)
        if has_images:
            raise ConversionError(
                "This PDF appears to be scanned or image-only. OCR is not included, so it has no extractable text."
            )
        raise ConversionError("This PDF contains no meaningful extractable text.")

    if images.enabled:
        seen_xrefs: set[int] = set()
        for page_index, xrefs in enumerate(page_images):
            for xref in xrefs:
                if xref in seen_xrefs:
                    continue
                seen_xrefs.add(xref)
                pages[page_index] = _extract_pdf_image(document, xref, images, pages[page_index])

    if options.cleanup_repeated_headers:
        pages = _remove_repeated_edge_lines(pages)
    return "\n\n".join(page for page in pages if page.strip())


def _pdf_page_content(page) -> str:
    tables: list[tuple[float, str, object]] = []
    try:
        finder = page.find_tables()
        for table in finder.tables:
            extracted = table.extract()
            markdown = _rows_to_markdown(extracted)
            if markdown:
                tables.append((float(table.bbox[1]), markdown, table.bbox))
    except Exception:
        # Text extraction remains useful when a PDF's table geometry is unreliable.
        tables.clear()

    text_blocks: list[tuple[float, float, str]] = []
    for block in page.get_text("blocks", sort=True):
        if len(block) < 5 or not isinstance(block[4], str) or not block[4].strip():
            continue
        if any(_bbox_overlap(block[:4], table_bbox) for _, _, table_bbox in tables):
            continue
        text_blocks.append((float(block[1]), float(block[0]), block[4].strip()))

    events = [(top, left, text) for top, left, text in text_blocks]
    events.extend((top, -1.0, markdown) for top, markdown, _bbox in tables)
    events.sort(key=lambda event: (event[0], event[1]))
    body = "\n\n".join(text for _, _, text in events)
    return body


def _extract_pdf_image(document, xref: int, images: _ImageWriter, page_content: str) -> str:
    try:
        extracted = document.extract_image(xref)
    except Exception:
        return f"{page_content}\n\n[Image unavailable]" if page_content else "[Image unavailable]"
    if not extracted:
        return page_content
    image_markdown = images.add(
        extracted["image"],
        mimetypes.guess_type(f"image.{extracted.get('ext', 'bin')}")[0] or "application/octet-stream",
        f"image.{extracted.get('ext', 'bin')}",
    )
    return f"{page_content}\n\n{image_markdown}" if page_content else image_markdown


def _bbox_overlap(left, right) -> bool:
    return not (left[2] <= right[0] or left[0] >= right[2] or left[3] <= right[1] or left[1] >= right[3])


def _remove_repeated_edge_lines(pages: list[str]) -> list[str]:
    if len(pages) < 2:
        return pages
    edge_lines: list[str] = []
    for page in pages:
        lines = [line.strip() for line in page.splitlines() if line.strip()]
        edge_lines.extend(line for line in lines[:2] + lines[-2:] if len(line) <= 100)
    threshold = max(2, int(len(pages) * 0.6 + 0.999))
    repeated = {line for line, count in Counter(edge_lines).items() if count >= threshold}
    if not repeated:
        return pages
    return ["\n".join(line for line in page.splitlines() if line.strip() not in repeated) for page in pages]


def _convert_rtf(source: Path) -> str:
    try:
        from striprtf.striprtf import rtf_to_text

        raw = _decode_text(source.read_bytes())
        return rtf_to_text(raw)
    except Exception as error:
        raise ConversionError(f"Could not read RTF document: {error}") from error


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _normalize_markdown(markdown: str) -> str:
    markdown = markdown.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    markdown = "\n".join(line.rstrip() for line in markdown.splitlines())
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    return markdown.strip() + ("\n" if markdown.strip() else "")


def _clean_cell(value: str | None) -> str:
    return (value or "").replace("\r", "").replace("\n", "<br>").replace("|", "\\|").strip()


def _markdown_row(values) -> str:
    return "| " + " | ".join(_clean_cell(str(value) if value is not None else "") for value in values) + " |"


def _rows_to_markdown(rows) -> str:
    normalized = [[_clean_cell(value) for value in row] for row in rows if row]
    if not normalized:
        return ""
    width = max(len(row) for row in normalized)
    normalized = [row + [""] * (width - len(row)) for row in normalized]
    return "\n".join(
        [_markdown_row(normalized[0]), _markdown_row(["---"] * width)]
        + [_markdown_row(row) for row in normalized[1:]]
    )
