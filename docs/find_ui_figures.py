"""Find Hình 5.x / 6.x and UI screenshot placeholders in docx."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph

DOCX = Path(__file__).parent / "BAO_CAO_DO_AN_TOT_NGHIEP_v3.docx"
OUT = Path(__file__).parent / "ui_figures_map.txt"


def iter_blocks(doc):
    for child in doc.element.body:
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)


def main() -> None:
    doc = Document(str(DOCX))
    lines: list[str] = []
    for idx, block in enumerate(iter_blocks(doc)):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if t and ("Hình 5" in t or "Hình 6" in t or "5." in t[:4] or "Phụ lục G" in t):
                lines.append(f"[P{idx}] {t[:200]}")
        elif isinstance(block, Table):
            cell = block.rows[0].cells[0].text[:120] if block.rows else ""
            if cell and len(cell) < 200:
                lines.append(f"[T{idx}] table: {cell.replace(chr(10), ' ')[:120]}")
    # also scan all paragraphs for figure list
    for idx, block in enumerate(iter_blocks(doc)):
        if isinstance(block, Paragraph):
            t = block.text
            if "Hình 5." in t or "Hình 6." in t:
                lines.append(f"[P{idx}] MATCH: {t[:250]}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(lines)} lines")


if __name__ == "__main__":
    main()
