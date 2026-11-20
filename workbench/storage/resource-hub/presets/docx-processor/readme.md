If the user asks to modify this skill, read this file before editing anything.

## Skill Structure

| Path | Purpose |
|------|---------|
| `SKILL.md` | Skill definition: the four routes (create / inspect / replace / unsupported-boundary), command examples with a `content.json` spec, the validation workflow, and the safety rules. Do not change the `name` field. |
| `user_preferences.md` | Stores persistent user preferences (e.g., default output directory, preferred spec conventions). Read before running; write back after changes. |
| `scripts/docx_ops.py` | The only executable. CLI with three subcommands built on python-docx: `create` (JSON spec → DOCX), `inspect` (structure summary JSON), and `replace` (bounded find/replace in body paragraphs and table cells). |
| `readme.md` | This file: the modification guide. |
| `LICENSE` | MIT License covering the package. Do not edit. |

## Modification Map

| Change Request | Primary File | Files Usually Updated Together | How to Validate |
|----------------|-------------|-------------------------------|-----------------|
| Add a new block type to the `create` spec (e.g., images, hyperlinks) | `scripts/docx_ops.py` (`create_document` block dispatch) | `SKILL.md` (the `content.json` example and the create route description) | Create a document using the new block type, reopen it with `inspect`, and confirm the expected paragraph/table/shape counts |
| Add a new CLI subcommand (e.g., extract text) | `scripts/docx_ops.py` (`main` parser + a new function) | `SKILL.md` (Commands section) | Run the new subcommand on a sample DOCX and confirm its JSON output is well-formed and correct |
| Change find/replace behavior (run-level vs. merged-text replacement) | `scripts/docx_ops.py` (`replace_in_paragraph`, `replace_document`) | `SKILL.md` (replace route wording if semantics change) | Replace a phrase that spans runs in a sample DOCX, then inspect the result and confirm only the intended text changed and no paragraph text was lost |
| Change validation rules (e.g., accept `.docm`, add overwrite protection) | `scripts/docx_ops.py` (`ensure_docx`, callers) | `SKILL.md` (Safety section) | Run each affected command with the new inputs and confirm it succeeds or fails with the intended message |
| Change how inspection counts or reports document structure | `scripts/docx_ops.py` (`inspect_document`) | `SKILL.md` (Validation section step 2) | Inspect a known DOCX and confirm each reported count matches what python-docx exposes |
| Update the safety boundaries narrative (macro files, rendering claims) | `SKILL.md` (Safety section) | None, unless a code change accompanies it | Re-read SKILL.md and confirm no stated boundary is contradicted by the script |
| Change license terms or attribution | `LICENSE` | None | No code change; verify the license header text is intact |

## Modification Rules

- Only modify files listed in the Modification Map.
- Do not change the `name` field in SKILL.md frontmatter.
- Keep file paths and references intact — they may be referenced by SKILL.md.
- Test after every change using the Validation section below.

## Common Change Recipes

**Recipe 1: Support a new `create` block type (e.g., `"image"`)**

1. Open `scripts/docx_ops.py` and add an `elif kind == "image":` branch in `create_document` that reads the path/size from the block and calls `document.add_picture(...)`.
2. Update the `content.json` example in `SKILL.md` to show the new block shape.
3. Validate: build a spec with the new block, run `python scripts/docx_ops.py create --spec spec.json --out out.docx`, then `python scripts/docx_ops.py inspect --input out.docx` and confirm `inline_shapes` reflects the image.

**Recipe 2: Add a `merge`-style command (e.g., concatenate two DOCX bodies)**

1. Add a new subparser and handler function in `scripts/docx_ops.py`, mirroring the existing subcommands and returning a JSON inspection result like the others.
2. Document the new command in the `SKILL.md` Commands section.
3. Validate: create two documents, merge them, then `inspect` the output and confirm paragraphs from both sources appear in order and the file reopens cleanly with python-docx.

**Recipe 3: Harden the replace command (e.g., add `--count-only`)**

1. Add `--count-only` to the `replace` subparser in `scripts/docx_ops.py`; when set, print the replacement count and do not write the output file.
2. Update the replace route description in `SKILL.md` only if the flag should be user-facing.
3. Validate: run `replace` with `--count-only` on a sample DOCX and confirm it reports the same count as a real replace; confirm no output file is created when the flag is set.

## Validation

Before finishing any change, verify all of these:

- [ ] `python scripts/docx_ops.py create --spec <spec>.json --out out.docx` runs and every block type in the spec is honored (unsupported types still fail with the intended error).
- [ ] Every produced file reopens with python-docx (`Document(path)`) with no exception.
- [ ] `inspect` output matches reality: paragraph/table/section/inline-shape counts and header/footer flags equal what python-docx reports for the same file.
- [ ] A `replace` roundtrip changes only the intended text — the before/after inspection reports differ only in the replaced string.
- [ ] Safety rules hold: non-`.docx` inputs are rejected, inputs are not overwritten by default, and `.docm`/`.xlsm` files are refused.
- [ ] No system packages were installed and no files were written outside the Workspace during testing.
- [ ] The `name` field in SKILL.md frontmatter is unchanged and `LICENSE` is untouched.
