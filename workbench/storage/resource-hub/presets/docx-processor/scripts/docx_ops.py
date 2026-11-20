#!/usr/bin/env python3
"""Small, auditable DOCX operations for the Workbench Runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from docx import Document
def ensure_docx(path: Path) -> None:
    if path.suffix.lower() != ".docx":
        raise SystemExit("Only .docx files are supported")


def inspect_document(path: Path) -> dict:
    ensure_docx(path)
    document = Document(path)
    return {
        "path": str(path.resolve()),
        "paragraphs": len(document.paragraphs),
        "nonempty_paragraphs": sum(bool(p.text.strip()) for p in document.paragraphs),
        "tables": len(document.tables),
        "table_rows": [len(table.rows) for table in document.tables],
        "sections": len(document.sections),
        "inline_shapes": len(document.inline_shapes),
        "headers_with_text": sum(bool(section.header.paragraphs and section.header.paragraphs[0].text.strip()) for section in document.sections),
        "footers_with_text": sum(bool(section.footer.paragraphs and section.footer.paragraphs[0].text.strip()) for section in document.sections),
        "title": document.core_properties.title or "",
        "author": document.core_properties.author or "",
    }


def create_document(spec_path: Path, output: Path) -> None:
    ensure_docx(output)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    document = Document()
    document.core_properties.title = str(spec.get("title", ""))
    document.core_properties.author = str(spec.get("author", ""))
    if spec.get("title"):
        document.add_heading(str(spec["title"]), level=0)
    for block in spec.get("blocks", []):
        kind = block.get("type")
        if kind == "heading":
            document.add_heading(str(block.get("text", "")), level=max(1, min(9, int(block.get("level", 1)))))
        elif kind == "paragraph":
            document.add_paragraph(str(block.get("text", "")))
        elif kind == "bullets":
            for item in block.get("items", []):
                document.add_paragraph(str(item), style="List Bullet")
        elif kind == "numbered":
            for item in block.get("items", []):
                document.add_paragraph(str(item), style="List Number")
        elif kind == "table":
            headers = [str(value) for value in block.get("headers", [])]
            rows = [[str(value) for value in row] for row in block.get("rows", [])]
            column_count = max([len(headers), *(len(row) for row in rows)], default=0)
            if column_count == 0:
                continue
            table = document.add_table(rows=1 if headers else 0, cols=column_count)
            table.style = "Table Grid"
            if headers:
                for index, value in enumerate(headers):
                    table.rows[0].cells[index].text = value
            for row in rows:
                cells = table.add_row().cells
                for index, value in enumerate(row):
                    cells[index].text = value
        elif kind == "pagebreak":
            document.add_page_break()
        else:
            raise SystemExit(f"Unsupported block type: {kind}")
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    Document(output)


def replace_in_paragraph(paragraph, find: str, replacement: str) -> int:
    if find not in paragraph.text:
        return 0
    count = paragraph.text.count(find)
    for run in paragraph.runs:
        if find in run.text:
            run.text = run.text.replace(find, replacement)
    if find in paragraph.text:
        merged = paragraph.text.replace(find, replacement)
        for run in paragraph.runs:
            run.text = ""
        if paragraph.runs:
            paragraph.runs[0].text = merged
        else:
            paragraph.add_run(merged)
    return count


def replace_document(source: Path, output: Path, find: str, replacement: str) -> int:
    ensure_docx(source); ensure_docx(output)
    document = Document(source)
    count = 0
    for paragraph in document.paragraphs:
        count += replace_in_paragraph(paragraph, find, replacement)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.paragraphs:
                    count += replace_in_paragraph(paragraph, find, replacement)
    output.parent.mkdir(parents=True, exist_ok=True)
    document.save(output)
    Document(output)
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create"); create.add_argument("--spec", required=True); create.add_argument("--out", required=True)
    inspect = sub.add_parser("inspect"); inspect.add_argument("--input", required=True); inspect.add_argument("--out")
    replace = sub.add_parser("replace"); replace.add_argument("--input", required=True); replace.add_argument("--out", required=True); replace.add_argument("--find", required=True); replace.add_argument("--replace", required=True)
    args = parser.parse_args()
    if args.command == "create":
        create_document(Path(args.spec), Path(args.out)); result = inspect_document(Path(args.out))
    elif args.command == "inspect":
        result = inspect_document(Path(args.input))
    else:
        changed = replace_document(Path(args.input), Path(args.out), args.find, args.replace)
        result = {"replacements": changed, "inspection": inspect_document(Path(args.out))}
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if getattr(args, "out", None) and args.command == "inspect":
        Path(args.out).write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
