"""Extract diagram table contents from BAO_CAO docx."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph

DOCX = Path(__file__).parent / "BAO_CAO_DO_AN_TOT_NGHIEP_v3.docx"
OUT = Path(__file__).parent / "diagram_contents.txt"

DIAGRAM_IDS = {298, 307, 313, 329, 334, 340, 355, 369, 374, 384, 391, 642}


def iter_block_items(parent):
    for child in parent.element.body:
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def main() -> None:
    doc: DocumentType = Document(str(DOCX))
    lines: list[str] = []
    idx = 0
    for block in iter_block_items(doc):
        if isinstance(block, Table):
            cell = block.rows[0].cells[0].text if block.rows else ""
            if idx in DIAGRAM_IDS:
                lines.append(f"=== TABLE {idx} (len={len(cell)}) ===")
                lines.append(cell)
                lines.append("")
        idx += 1
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
