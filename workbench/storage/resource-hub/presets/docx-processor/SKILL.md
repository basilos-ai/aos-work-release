---
name: minimax-docx
description: Create, inspect, and perform bounded edits on DOCX files in Workspace using python-docx. Use for reports, proposals, contracts, forms, text replacement, headings, paragraphs, tables, and template-preserving edits that do not require Microsoft Word, LibreOffice, .NET, or desktop automation.
---

# minimax-docx Runtime Edition

This edition swaps the original .NET/OpenXML and LibreOffice installation chain for Runtime-installable Python packages. Keep every input and output in Workspace.

## Routes

- Create a simple document: use `scripts/docx_ops.py create` with a JSON specification.
- Inspect structure before editing: use `scripts/docx_ops.py inspect`.
- Replace text without rebuilding the document: use `scripts/docx_ops.py replace`.
- For complex template restyling, section-level header/footer changes, tracked changes, macros, or `.doc` conversion, stop and report the unsupported boundary. Do not claim Word-equivalent rendering.

## Commands

```bash
python scripts/docx_ops.py create --spec content.json --out output.docx
python scripts/docx_ops.py inspect --input input.docx --out inspection.json
python scripts/docx_ops.py replace --input input.docx --out output.docx --find OLD --replace NEW
```

`content.json` example:

```json
{
  "title": "Quarterly Report",
  "author": "Finance Team",
  "blocks": [
    {"type": "heading", "level": 1, "text": "Summary"},
    {"type": "paragraph", "text": "Key result."},
    {"type": "bullets", "items": ["Item A", "Item B"]},
    {"type": "table", "headers": ["Metric", "Value"], "rows": [["Revenue", "100"]]}
  ]
}
```

## Validation

1. Reopen every produced file with `python-docx`.
2. Run `inspect` and verify paragraph, table, section, image, header, and footer counts.
3. For edits, compare the inspection report before and after and confirm only the intended text changed.
4. If layout matters, render through an approved document-rendering capability. When unavailable, label visual fidelity `unverified`.

## Safety

- Never overwrite an input unless the user explicitly asks and a recoverable copy exists.
- Preserve macros by refusing `.docm`/`.xlsm`-style files in this edition; `python-docx` does not provide a safe macro-preserving workflow here.
- Do not install system packages or write to HOME.
- Ordinary Python dependencies such as `python-docx` and `lxml` may be installed by the Runtime and do not count as Skill modification.
