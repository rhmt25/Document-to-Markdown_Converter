"""General purpose DOCX to Markdown conversion."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import mimetypes
from pathlib import Path
import re
from urllib.parse import quote


class ConversionError(Exception):
    """A DOCX document could not be converted."""


@dataclass(frozen=True)
class ConversionOptions:
    export_images: bool = True


@dataclass
class ConversionResult:
    source: Path
    destination: Path
    image_files: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class _ImageWriter:
    def __init__(self, destination: Path, enabled: bool) -> None:
        self.enabled = enabled
        self.directory = destination.parent / destination.stem
        self.image_files: list[Path] = []
        self._names: dict[str, str] = {}

    def add(self, data: bytes, content_type: str, source_key: str = "") -> str:
        if not self.enabled:
            return "[Image omitted; image export is off]"
        digest = hashlib.sha256(data).hexdigest()
        key = source_key or digest
        if key in self._names:
            name = self._names[key]
        else:
            ext = mimetypes.guess_extension(content_type) or ".bin"
            if ext == ".jpe":
                ext = ".jpg"
            self.directory.mkdir(parents=True, exist_ok=True)
            name = f"image_{len(self._names) + 1:03d}{ext}"
            (self.directory / name).write_bytes(data)
            self._names[key] = name
            self.image_files.append(self.directory / name)
        relative = f"{self.directory.name}/{name}"
        return f"![{Path(name).stem}]({quote(relative, safe='/._-')})"


def convert_document(source: str | Path, destination: str | Path,
                    options: ConversionOptions | None = None) -> ConversionResult:
    """Convert one DOCX to UTF-8 Markdown, extracting embedded pictures optionally."""
    source_path, destination_path = Path(source), Path(destination)
    if source_path.suffix.casefold() != ".docx":
        raise ConversionError("Only .docx files are supported.")
    if not source_path.is_file():
        raise ConversionError(f"Source DOCX does not exist: {source_path}")
    writer = _ImageWriter(destination_path, (options or ConversionOptions()).export_images)
    warnings: list[str] = []
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph
        from docx.oxml.ns import qn

        document = Document(source_path)
        if any(section.header.paragraphs and any(p.text.strip() for p in section.header.paragraphs)
               or section.footer.paragraphs and any(p.text.strip() for p in section.footer.paragraphs)
               for section in document.sections):
            warnings.append("Header/footer text was not inserted into the Markdown body.")
        blocks: list[str] = []
        has_seen_content = False
        for block in document.iter_inner_content():
            if isinstance(block, Table):
                rendered = _table(block, document, writer, qn, warnings)
                if rendered:
                    blocks.append(rendered)
                    prior_list = False
                continue
            if not isinstance(block, Paragraph):
                continue
            rendered = _paragraph(block, document, writer, qn)
            if not rendered.strip():
                continue
            style = block.style.name if block.style else ""
            style_id = block.style.style_id if block.style else ""
            heading = re.match(r"Heading\s*(\d+)", style, re.I) or re.match(r"Heading([1-6])", style_id, re.I)
            if heading:
                rendered = f"{'#' * min(max(int(heading.group(1)), 1), 6)} {rendered.strip()}"
            elif style.casefold() == "title":
                rendered = f"# {rendered.strip()}"
            elif style.casefold() == "subtitle":
                rendered = f"## {rendered.strip()}"
            else:
                raw_text = block.text.strip()
                inferred_title = (
                    not has_seen_content and 8 <= len(raw_text) <= 180
                    and raw_text == raw_text.upper()
                    and any(char.isalpha() for char in raw_text)
                    and not re.search(r"[.!?]$", raw_text)
                    and any(run.bold for run in block.runs)
                )
                if inferred_title:
                    rendered = f"# {rendered.strip()}"
                info = _list_info(block, document, qn)
                if info and not inferred_title:
                    level, ordered = info
                    rendered = f"{'  ' * level}{'1.' if ordered else '-'} {rendered.strip()}"
            blocks.append(rendered)
            has_seen_content = True
        markdown = _normalize("\n\n".join(blocks))
        if not markdown and not writer.image_files:
            raise ConversionError("The DOCX did not contain extractable body text or images.")
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_text(markdown, encoding="utf-8", newline="\n")
        return ConversionResult(source_path, destination_path, writer.image_files, warnings)
    except ConversionError:
        raise
    except Exception as error:
        raise ConversionError(f"Could not convert DOCX: {error}") from error


def _paragraph(paragraph, document, images: _ImageWriter, qn) -> str:
    from docx.text.run import Run
    parts: list[str] = []

    def visit(element) -> None:
        if element.tag in (qn("w:del"), qn("w:moveFrom")):
            return
        if element.tag == qn("w:r"):
            run = Run(element, paragraph)
            value = run.text.replace("\r", "").replace("\n", "  \n")
            if value:
                value = _format_run(value, run)
                parts.append(value)
            for blip in element.xpath(".//a:blip"):
                rid = blip.get(qn("r:embed"))
                rel = document.part.rels.get(rid) if rid else None
                if rel is None:
                    parts.append("[Image unavailable]")
                else:
                    image = rel.target_part
                    parts.append(images.add(image.blob, image.content_type, rid))
            for image_data in element.iter("{urn:schemas-microsoft-com:vml}imagedata"):
                rid = image_data.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                rel = document.part.rels.get(rid) if rid else None
                if rel is not None:
                    image = rel.target_part
                    parts.append(images.add(image.blob, image.content_type, rid))
            return
        if element.tag in (qn("m:oMath"), qn("m:oMathPara")):
            latex = _math(element)
            if latex:
                parts.append(f"\uFFF0{latex}\uFFF1")
            return
        for child in element:
            visit(child)

    for child in paragraph._p:
        visit(child)
    value = "".join(parts).strip()
    tokens = list(re.finditer("\uFFF0(.*?)\uFFF1", value))
    for token in reversed(tokens):
        context = value[:token.start()] + value[token.end():]
        labels = re.findall(r"\((\d{1,3})\)", context)
        is_display = len(tokens) == 1 and (not context.strip() or (labels and not re.sub(r"\s|\(\d{1,3}\)", "", context)))
        math_body = token.group(1) + (f" \\tag{{{labels[-1]}}}" if is_display and labels else "")
        math = f"$$\n{math_body}\n$$" if is_display else f"${math_body}$"
        if is_display:
            value = math
        else:
            value = value[:token.start()] + math + value[token.end():]
    return value


def _format_run(value: str, run) -> str:
    # Preserve spaces outside delimiters to avoid changing word boundaries.
    leading = value[:len(value) - len(value.lstrip())]
    trailing = value[len(value.rstrip()):]
    core = value.strip()
    if not core:
        return value
    if run.font.superscript:
        core = f"<sup>{core}</sup>"
    elif run.font.subscript:
        core = f"<sub>{core}</sub>"
    if run.font.strike:
        core = f"~~{core}~~"
    if run.underline:
        core = f"<u>{core}</u>"
    if run.italic:
        core = f"*{core}*"
    if run.bold:
        core = f"**{core}**"
    return leading + core + trailing


def _math(element) -> str:
    ns = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
    def direct(node, name):
        child = node.find(ns + name)
        return render(child) if child is not None else ""
    def children(node):
        return "".join(render(c) for c in node if not c.tag.endswith(("Pr", "Pr2")))
    def render(node):
        name = node.tag.rsplit("}", 1)[-1]
        if name == "t":
            text = node.text or ""
            return r"\times " if text == "\ufffd" else text.replace("_", r"\_")
        if name in {"oMath", "oMathPara", "e", "num", "den", "sub", "sup", "deg", "r", "fName", "lim"}:
            return children(node)
        if name == "f":
            return rf"\frac{{{direct(node,'num')}}}{{{direct(node,'den')}}}"
        if name == "rad":
            degree, body = direct(node, "deg"), direct(node, "e")
            return rf"\sqrt[{degree}]{{{body}}}" if degree else rf"\sqrt{{{body}}}"
        if name == "sSub": return f"{direct(node,'e')}_{{{direct(node,'sub')}}}"
        if name == "sSup": return f"{direct(node,'e')}^{{{direct(node,'sup')}}}"
        if name == "sSubSup": return f"{direct(node,'e')}_{{{direct(node,'sub')}}}^{{{direct(node,'sup')}}}"
        if name == "d": return rf"\left({direct(node,'e')}\right)"
        if name == "nary":
            props = node.find(ns + "naryPr")
            ch = props.find(ns + "chr") if props is not None else None
            op = ch.get(ns + "val", "∑") if ch is not None else "∑"
            return rf"\{op}_{{{direct(node,'sub')}}}^{{{direct(node,'sup')}}} {direct(node,'e')}"
        if name in {"bar", "acc", "groupChr"}:
            return rf"\overline{{{direct(node,'e')}}}" if name == "bar" else rf"\hat{{{direct(node,'e')}}}"
        return children(node)
    return render(element).strip()


def _list_info(paragraph, document, qn):
    ppr = paragraph._p.pPr
    numpr = ppr.numPr if ppr is not None else None
    if numpr is None or numpr.numId is None:
        name = paragraph.style.name.casefold() if paragraph.style else ""
        return (0, False) if name.startswith("list bullet") else ((0, True) if name.startswith("list number") else None)
    num_id = str(numpr.numId.val)
    level = int(numpr.ilvl.val) if numpr.ilvl is not None else 0
    numbering = document.part.numbering_part.element
    for num in numbering.findall(qn("w:num")):
        if num.get(qn("w:numId")) != num_id: continue
        abstract_id = num.find(qn("w:abstractNumId"))
        if abstract_id is None: break
        for abstract in numbering.findall(qn("w:abstractNum")):
            if abstract.get(qn("w:abstractNumId")) != abstract_id.get(qn("w:val")): continue
            for lvl in abstract.findall(qn("w:lvl")):
                if int(lvl.get(qn("w:ilvl"), "0")) == level:
                    fmt = lvl.find(qn("w:numFmt"))
                    return level, bool(fmt is not None and fmt.get(qn("w:val")) != "bullet")
    return level, False


def _table(table, document, images, qn, warnings: list[str]) -> str:
    """Render a logical table grid; merged values repeat into their grid slots."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    tbl = table._tbl
    grid_width = len(tbl.tblGrid.gridCol_lst) if tbl.tblGrid is not None else 0
    grid_width = max(grid_width, max((len(row.cells) for row in table.rows), default=0))
    rows: list[list[str]] = []
    seen_cells: set[object] = set()
    cell_values: dict[object, str] = {}
    for row in table.rows:
        rendered: list[str] = []
        for cell in row.cells:
            identity = cell._tc
            if identity in seen_cells:
                rendered.append(cell_values.get(identity, ""))
                continue
            seen_cells.add(identity)
            content = []
            for block in cell.iter_inner_content():
                if isinstance(block, Paragraph):
                    content.append(_paragraph(block, document, images, qn))
                elif isinstance(block, Table):
                    nested = _table(block, document, images, qn, warnings)
                    if nested:
                        content.append(re.sub(r"\s*\|\s*", " / ", nested.replace("\n", " ")))
                        warnings.append("A nested table was flattened inside its parent Markdown cell.")
            cell_value = _cell("<br>".join(filter(None, content)))
            cell_values[identity] = cell_value
            rendered.append(cell_value)
        rows.append((rendered + [""] * max(0, grid_width - len(rendered)))[:grid_width])
    if not rows or not grid_width:
        return ""
    return "\n".join([_row(rows[0]), _row(["---"] * grid_width), *(_row(row) for row in rows[1:])])


def _cell(value: str) -> str:
    value = re.sub(r"\s*\n\s*", "<br>", value.strip())
    return value.replace("|", r"\|")


def _row(values) -> str:
    return "| " + " | ".join(_cell(str(v or "")) for v in values) + " |"


def _normalize(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    value = "\n".join(line.rstrip() for line in value.splitlines())
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip() + ("\n" if value.strip() else "")
