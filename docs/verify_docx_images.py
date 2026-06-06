"""Verify images embedded in BAO_CAO docx."""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import Table
from docx.text.paragraph import Paragraph

DOCX = Path(__file__).parent / "BAO_CAO_DO_AN_TOT_NGHIEP_v3.docx"
OUT = Path(__file__).parent / "verify_images.txt"


def iter_block_items(parent):
    for child in parent.element.body:
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def table_has_image(table: Table) -> bool:
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                for run in p.runs:
                    if run._element.findall(".//" + qn("a:blip")):
                        return True
    return False


def main() -> None:
    doc = Document(str(DOCX))
    lines = []
    img_count = 0
    for idx, block in enumerate(iter_block_items(doc)):
        if isinstance(block, Table) and table_has_image(block):
            img_count += 1
            # get caption from next paragraphs - skip
            lines.append(f"block {idx}: TABLE with image")
        elif isinstance(block, Paragraph):
            for run in block.runs:
                if run._element.findall(".//" + qn("a:blip")):
                    img_count += 1
                    lines.append(f"block {idx}: PARA with image | {block.text[:60]}")
    lines.insert(0, f"Total embedded images in body: {img_count}")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
