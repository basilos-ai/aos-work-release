If the user asks to modify this skill, read this file before editing anything.

## Skill Structure

| Path | Purpose |
|------|---------|
| `SKILL.md` | Skill definition: the three routes (CREATE / FILL / REFORMAT), the route table mapping intents to scripts, the 15 document types and their cover patterns, the `content.json` block-type catalog, accent-color selection guidance, and the environment/dependency table. Do not change the `name` field. |
| `user_preferences.md` | Stores persistent user preferences (e.g., default doc type, default output path). Read before running; write back after changes. |
| `design/design.md` | The aesthetic layer: the "one rule" (design rooted in content), palette logic and anti-patterns, typography/type-scale/spacing systems, the 13 cover pattern specs, inner-page restraint rules, the quality bar, and the full block-type reference with chart/flowchart/math/bibliography guidance. |
| `scripts/make.sh` | Unified bash CLI: `check` (verify deps), `fix` (install reportlab/pypdf/matplotlib), `run` (full CREATE pipeline), `fill` (inspect/fill forms), `reformat` (parse → CREATE), `demo` (build demo.pdf). |
| `scripts/palette.py` | Generates `tokens.json` from document metadata: `PALETTES` (per-doc-type cover/accent/text colors and cover pattern), `FONT_PAIRS` (mood → font selection), type-scale/layout tokens, and `--accent`/`--cover-bg` overrides with auto-derived `accent_lt`. |
| `scripts/render_cover.py` | Browser-free A4 cover renderer using ReportLab: background, accent rule/bar, title wrap, subtitle, author/date. Honors tokens from `tokens.json`. |
| `scripts/render_body.py` | Body-page renderer from `tokens.json` + `content.json`: ParagraphStyle factory, header/footer decoration, and per-block renderers (headings, body, bullets, numbered, callout, table, image, figure, code, math, chart, flowchart, bibliography, divider, caption, pagebreak, spacer). |
| `scripts/merge.py` | Merges `cover.pdf` + `body.pdf` into the final PDF, sets `/Title` metadata, and runs QA warnings (cover page count, very small/large output). |
| `scripts/fill_inspect.py` | Inspects fillable form fields in an existing PDF via pypdf: per-field name, type (text/checkbox/dropdown/radio/signature), current value, allowed values, and page number. |
| `scripts/fill_write.py` | Fills form fields in an existing PDF via pypdf: writes `/V` and `/AS` values, sets `/NeedAppearances`, validates dropdown/radio values, and reports filled/not-found/error fields. |
| `scripts/reformat_parse.py` | Converts `.md`/`.txt`/`.pdf`/`.json` input into `content.json` for the CREATE pipeline: Markdown parser (headings, math, code fences, blockquotes, lists, tables), plain-text heuristics, PDF text extraction, and content.json pass-through validation. |
| `readme.md` | This file: the modification guide. |
| `LICENSE` | MIT License covering the package. Do not edit. |

## Modification Map

| Change Request | Primary File | Files Usually Updated Together | How to Validate |
|----------------|-------------|-------------------------------|-----------------|
| Add a new document type / cover pattern | `scripts/palette.py` (`PALETTES`, `FONT_PAIRS`) | `SKILL.md` (doc-type table), `design/design.md` (cover pattern spec), `scripts/make.sh` (usage comment listing types) | Run `bash scripts/make.sh run --title T --type <newtype> --out out.pdf` and confirm a cover is rendered with the new pattern |
| Add a new content block type | `scripts/render_body.py` (`build_story` dispatch + `_add_*` renderer) | `SKILL.md` (block-type table), `design/design.md` (block-type reference), `scripts/reformat_parse.py` (`VALID_TYPES`) | Render a `content.json` containing the new block and confirm it appears in the PDF body |
| Change typography or layout tokens (sizes, margins, gaps) | `scripts/palette.py` (`build_tokens` token values) | `design/design.md` (type scale / spacing tables) | Rebuild a demo with `bash scripts/make.sh demo` and visually confirm the new sizes/margins apply to both cover and body |
| Change the cover design (layout, colors, patterns) | `scripts/render_cover.py` | `design/design.md` (cover section), `SKILL.md` (doc-type table) | Render each affected doc type and confirm the cover matches the updated spec with no text clipping |
| Change accent color guidance or default palettes | `SKILL.md` (accent guidance table) | `design/design.md` (accent rules), `scripts/palette.py` (`PALETTES`) | Pass `--accent "#HEX"` for a test color and confirm `accent_lt` is auto-derived and the accent contrast stays readable |
| Change FILL field handling (types, validation, output) | `scripts/fill_write.py` | `scripts/fill_inspect.py` (field type resolution), `SKILL.md` (Route B) | Inspect a form PDF, fill it with valid + invalid values, and confirm filled/validation error counts match expectations |
| Change REFORMAT parsing rules | `scripts/reformat_parse.py` | `SKILL.md` (Route C), `design/design.md` if block guidance changes | Parse each supported input format and confirm the resulting `content.json` blocks match intent |
| Change make.sh commands/options or exit codes | `scripts/make.sh` | `SKILL.md` (command examples) | Run the new command/flag and confirm it works and that `bash scripts/make.sh check` still exits 0 with deps present |

## Modification Rules

- Only modify files listed in the Modification Map.
- Do not change the `name` field in SKILL.md frontmatter.
- Keep file paths and references intact — they may be referenced by SKILL.md.
- Test after every change using the Validation section below.

## Common Change Recipes

**Recipe 1: Add a new document type (e.g., `briefing`) with its own cover pattern**

1. Add a `briefing` entry to `PALETTES` in `scripts/palette.py` (cover colors, accent, `cover_pattern`, `mood`), then add the mood's font pair to `FONT_PAIRS` if it does not exist.
2. Document the new pattern in `design/design.md` (a numbered cover-pattern spec) and add the row to the doc-type table in `SKILL.md`.
3. Update the doc-type list in the `make.sh` usage comment.
4. Validate: run `bash scripts/make.sh run --title "Briefing" --type briefing --content content.json --out out.pdf`, then open the PDF and confirm the cover matches the new spec and the body still renders.

**Recipe 2: Add a new content block type (e.g., `quote`)**

1. Add an `_add_quote(story, item, ctx)` renderer in `scripts/render_body.py` using the token system (accent/`acc_lt`/styles), then register it in `build_story`.
2. Add the block to the block-type table in `SKILL.md`, the block reference in `design/design.md`, and to `VALID_TYPES` in `scripts/reformat_parse.py`.
3. Validate: build a `content.json` with the `quote` block, render it via `make.sh run`, and confirm it renders and that a `.json` reformat pass-through keeps the block without a warning.

**Recipe 3: Add a `--draft` watermark flag to `make.sh run`**

1. Add the flag to `cmd_run` argument parsing in `scripts/make.sh` and forward it to `render_body.py` (or pass through an environment variable).
2. Handle the watermark in `scripts/render_body.py` (e.g., diagonal text in `_decorate`).
3. Document the new flag in the `make.sh` usage help and in `SKILL.md` if user-facing.
4. Validate: run `bash scripts/make.sh run --title T --type report --content content.json --out out.pdf --draft` and confirm every body page shows the watermark while the cover stays clean.

**Recipe 4: Retune body typography (e.g., larger body text)**

1. Edit the type-scale values in `build_tokens` in `scripts/palette.py` (e.g., `size_body` from 10.5 to 11, `line_gap` accordingly).
2. Update the type-scale table in `design/design.md` to match.
3. Validate: `bash scripts/make.sh demo`, open `demo.pdf`, and confirm body text renders at the new size with comfortable leading and no overflow in tables/code blocks.

## Validation

Before finishing any change, verify all of these:

- [ ] `bash scripts/make.sh check` passes with reportlab, pypdf (and matplotlib for math/chart/flowchart) installed; exit code is 0.
- [ ] `bash scripts/make.sh demo` completes and produces `demo.pdf` with a cover, body pages, chart, math, and flowchart all rendering.
- [ ] A CREATE run for each doc type listed in `SKILL.md` produces a PDF whose cover matches the pattern in `design/design.md`.
- [ ] Every block type documented in `SKILL.md`/`design/design.md` is actually handled in `render_body.py`'s `build_story`, and unknown types in `reformat_parse.py` still produce a warning rather than a crash.
- [ ] The FILL roundtrip works: `fill_inspect.py` lists field names/types and `fill_write.py` fills a sample form, reports `filled_count`, and flags invalid dropdown/radio values and `not_found` keys.
- [ ] REFORMAT works for all four input formats (`.md`, `.txt`, `.pdf`, `.json`) and produces a renderable `content.json`.
- [ ] The one-accent rule holds: the accent appears only on cover elements, section rules, callout borders, table headers, and page-header rules — not on body text or headings.
- [ ] No element bleeds off the page, page numbers are present, and the accent does not appear more than ~8 times per page on average.
- [ ] The `name` field in SKILL.md frontmatter is unchanged and `LICENSE` is untouched.
