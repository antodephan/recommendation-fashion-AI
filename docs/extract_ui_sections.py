"""Extract Phụ lục G and chapter 5/6 UI sections from docx."""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph

DOCX = Path(__file__).parent / "BAO_CAO_DO_AN_TOT_NGHIEP_v3.docx"
OUT = Path(__file__).parent / "ui_sections.txt"


def iter_blocks(doc):
    for child in doc.element.body:
        if isinstance(child, CT_P):
            yield Paragraph(child, doc)
        elif isinstance(child, CT_Tbl):
            yield Table(child, doc)


def main() -> None:
    doc = Document(str(DOCX))
    lines: list[str] = []
    capture = False
    for idx, block in enumerate(iter_blocks(doc)):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if re.match(r"^5\.\s", t) or t.startswith("CHƯƠNG 5") or "Thiết kế giao diện" in t:
                capture = True
            if t.startswith("Phụ lục G"):
                capture = True
            if capture and t:
                lines.append(f"[{idx}] {t[:300]}")
            if t.startswith("Phụ lục H") or (t.startswith("CHƯƠNG 7") and capture):
                capture = False
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(len(lines))


if __name__ == "__main__":
    main()
