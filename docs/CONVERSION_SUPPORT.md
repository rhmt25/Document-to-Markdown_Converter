# Conversion support and limitations

The converter accepts Microsoft Word `.docx` files. It reads document structure and produces UTF-8 Markdown. It does not convert legacy `.doc`, macro-enabled `.docm`, PDF, or other formats.

## Supported content

| DOCX content | Output behavior |
| --- | --- |
| Body paragraphs | Preserved in document order, with paragraph boundaries |
| Title, subtitle, and heading styles | Rendered as Markdown headings |
| Bold and italic | Rendered with Markdown emphasis |
| Underline, superscript, and subscript | Rendered with small HTML tags where Markdown has no equivalent |
| Strikethrough | Rendered using Markdown strikethrough syntax |
| Ordered and unordered lists | Rendered with nested indentation where numbering definitions are available |
| Ordinary tables | Rendered as Markdown pipe tables |
| Horizontally merged cells | Values are repeated in their logical grid slots |
| Nested tables | Flattened into parent cells and reported as a warning |
| Embedded pictures in body paragraphs and table cells | Extracted once when image export is enabled; linked by a relative path |
| Native Office Math | Common fractions, radicals, scripts, sums, and accents are converted to LaTeX |
| Inline and display LaTeX in Markdown | Rendered as MathML in Preview when supported |

## Limitations

- Markdown cannot preserve page layout, columns, floating placement, exact typography, or merged-cell geometry.
- Complex or nested table layouts are simplified. Validate important tables against the source document.
- Header and footer text is not inserted in the Markdown body; the converter reports a warning when it finds such text.
- Footnotes, endnotes, comments, tracked changes, text boxes, and unusual DrawingML/VML structures may not be represented fully.
- Images containing equations or tables remain images. There is no OCR or image-to-table reconstruction.
- Floating picture placement may differ from Word's visual layout.
- The Office Math converter handles common structures; unsupported constructs may be simplified or not preserved exactly.
- Preview uses local rendering. JavaScript and remote page access are disabled. Supported formulas render as MathML; unsupported TeX remains visible as text.

## Output behavior

For `Report.docx`, the default Markdown destination is `Report.md`. When image export is enabled, extracted pictures are placed under a sibling `Report/` folder. The Markdown links use relative paths such as `Report/image_001.png`, so the Markdown file and media folder should be kept together.

When image export is disabled, the converter writes no picture files and inserts `[Image omitted; image export is off]` where an image was found.
