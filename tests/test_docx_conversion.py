"""General regression checks built from synthetic DOCX documents."""
from __future__ import annotations

import base64
from pathlib import Path
import tempfile
import unittest

from docx import Document
from docx.shared import Inches
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

from src.docmark.conversion.engine import ConversionError, ConversionOptions, convert_document


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
    "l1sAAAAASUVORK5CYII="
)


class DocxConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "Synthetic.docx"
        doc = Document()
        title = doc.add_paragraph()
        title.add_run("GENERAL STRUCTURE SAMPLE").bold = True
        doc.add_heading("General DOCX fixture", 1)
        p = doc.add_paragraph()
        p.add_run("Bold").bold = True
        p.add_run(" and ")
        p.add_run("italic").italic = True
        p.add_run("; café Ελληνικά 日本語.")
        doc.add_paragraph("First item", style="List Number")
        doc.add_paragraph("Second item", style="List Number")
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text, table.cell(0, 1).text = "Name", "Value"
        table.cell(1, 0).text, table.cell(1, 1).text = "A | B", "Line one\nLine two"
        nested = table.cell(1, 1).add_table(rows=1, cols=1)
        nested.cell(0, 0).text = "Nested"
        merged = doc.add_table(rows=2, cols=2)
        merged.cell(0, 0).merge(merged.cell(0, 1)).text = "Merged header"
        merged.cell(1, 0).text, merged.cell(1, 1).text = "left", "right"
        vertical = doc.add_table(rows=2, cols=1)
        vertical.cell(0, 0).merge(vertical.cell(1, 0)).text = "Vertical merged"
        p = doc.add_paragraph("Picture: ")
        p.add_run().add_picture(self._image_stream(), width=Inches(.15))
        doc.add_paragraph("Repeated picture:").add_run().add_picture(self._image_stream(), width=Inches(.15))
        # Representative Office Math fraction: x = a/b.
        math_xml = f'''<m:oMath {nsdecls('m')}><m:r><m:t>x=</m:t></m:r><m:f><m:num><m:r><m:t>a</m:t></m:r></m:num><m:den><m:r><m:t>b</m:t></m:r></m:den></m:f></m:oMath>'''
        math_paragraph = doc.add_paragraph()
        math_paragraph._p.append(parse_xml(math_xml))
        math_paragraph.add_run(" (3)")
        doc.sections[0].header.paragraphs[0].text = "Synthetic header"
        doc.sections[0].footer.paragraphs[0].text = "Synthetic footer"
        doc.add_page_break()
        doc.add_paragraph("After explicit page break")
        doc.save(self.source)

    @staticmethod
    def _image_stream():
        from io import BytesIO
        return BytesIO(PNG)

    def tearDown(self):
        self.temp.cleanup()

    def test_general_content_and_media(self):
        out = self.root / "out" / "Synthetic.md"
        result = convert_document(self.source, out)
        text = out.read_text(encoding="utf-8")
        for expected in ("# **GENERAL STRUCTURE SAMPLE**", "# General DOCX fixture", "**Bold**", "*italic*", "café Ελληνικά 日本語",
                         "1. First item", "| Name | Value |", r"\|", "Merged header", "left", "right",
                         r"\frac{a}{b}", "After explicit page break"):
            self.assertIn(expected, text)
        self.assertEqual(len(result.image_files), 1)
        self.assertTrue(any("nested table" in warning for warning in result.warnings))
        self.assertTrue(any("Header/footer" in warning for warning in result.warnings))
        self.assertTrue((out.parent / "Synthetic" / result.image_files[0].name).is_file())
        self.assertIn("Synthetic/", text)
        self.assertIn("| Merged header | Merged header |", text)
        self.assertGreaterEqual(text.count("| Vertical merged |"), 2)
        self.assertIn(r"\tag{3}", text)

    def test_images_off_and_non_docx_rejected(self):
        out = self.root / "no_images.md"
        result = convert_document(self.source, out, ConversionOptions(export_images=False))
        self.assertEqual(result.image_files, [])
        self.assertIn("image export is off", out.read_text(encoding="utf-8"))
        txt = self.root / "file.txt"
        txt.write_text("not docx")
        with self.assertRaises(ConversionError):
            convert_document(txt, self.root / "file.md")


if __name__ == "__main__":
    unittest.main()
