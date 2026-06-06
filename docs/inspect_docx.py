"""Inspect BAO_CAO docx for figures and diagram tables."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

DOCX = Path(__file__).parent / "BAO_CAO_DO_AN_TOT_NGHIEP_v3.docx"
OUT = Path(__file__).parent / "inspect_docx_output.txt"


def iter_block_items(parent):
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl

    for child in parent.element.body:
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def has_image(paragraph: Paragraph) -> bool:
    for run in paragraph.runs:
        blips = run._element.findall(".//" + qn("a:blip"))
        if blips:
            return True
    return False


def main() -> None:
    doc: DocumentType = Document(str(DOCX))
    lines: list[str] = []

    idx = 0
    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            t = block.text.strip()
            if t and ("Hình" in t or "hình" in t or "Sơ đồ" in t or "Kiến trúc" in t):
                img = has_image(block)
                lines.append(f"[P{idx}] img={img} | {t[:200]}")
            elif has_image(block):
                lines.append(f"[P{idx}] IMAGE_ONLY | {t[:80]}")
            idx += 1
        elif isinstance(block, Table):
            cell = block.rows[0].cells[0].text if block.rows else ""
            preview = cell.replace("\n", " ")[:180]
            is_diagram = any(
                k in cell
                for k in (
                    "+--",
                    "┌",
                    "│",
                    "->",
                    "Frontend",
                    "Backend",
                    "PostgreSQL",
                    "Next.js",
                    "FastAPI",
                    "Qdrant",
                    "Redis",
                    "Nginx",
                )
            )
            lines.append(f"[T{idx}] diagram={is_diagram} len={len(cell)} | {preview}")
            idx += 1

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(lines)} lines to {OUT}")


if __name__ == "__main__":
    main()
