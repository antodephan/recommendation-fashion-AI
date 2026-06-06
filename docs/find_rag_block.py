"""Find RAG figure table index in docx."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph

DOCX = Path(__file__).parent / "BAO_CAO_DO_AN_TOT_NGHIEP_v3.docx"


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
            if "RAG" in t or "Hình 3.8" in t or "Kiến trúc RAG" in t:
                lines.append(f"P{idx}: {t[:120]}")
        elif isinstance(block, Table):
            has_img = any(
                run._element.findall(".//" + qn("a:blip"))
                for row in block.rows
                for c in row.cells
                for p in c.paragraphs
                for run in p.runs
            )
            if has_img and 300 < idx < 500:
                lines.append(f"T{idx}: architecture/ui image table")
    out = Path(__file__).parent / "find_rag_out.txt"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(len(lines))


if __name__ == "__main__":
    main()
