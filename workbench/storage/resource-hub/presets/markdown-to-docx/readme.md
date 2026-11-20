If the user asks to modify this skill, read this file before editing anything.

## Skill Structure

| Path | Purpose |
|------|---------|
| `SKILL.md` | Skill definition: invocation criteria, the quick workflow (input source → template → output), the built-in template catalog, main command examples, and pandoc-related notes. Do not change the `name` field. |
| `user_preferences.md` | Stores persistent user preferences (e.g., default built-in template, default `--highlight-style`). Read before running; write back after changes. |
| `scripts/markdown_to_docx.py` | Main converter CLI. Wraps pandoc: builds the pandoc command (input file or raw string, reference doc, metadata, TOC, numbered sections, resource path), validates args, and prints a JSON result. Also holds its own `BUILTIN_TEMPLATES` registry. |
| `scripts/build_builtin_templates.py` | Generator that produces the built-in DOCX reference templates into `assets/templates/`. Defines the `THEMES` dict (colors, fonts, sizes per template) and rewrites pandoc's default `reference.docx` theme/styles XML. |
| `assets/examples/sample.md` | Sample Markdown used to smoke-test conversions (headings, table, code block, CLI example). |
| `readme.md` | This file: the modification guide. |

> Note: `assets/templates/*.docx` (referenced by SKILL.md and by `markdown_to_docx.py`) does not ship with the package — it is generated at runtime by `scripts/build_builtin_templates.py`. Do not delete that generator; without it the converter fails on built-in templates.

## Modification Map

| Change Request | Primary File | Files Usually Updated Together | How to Validate |
|----------------|-------------|-------------------------------|-----------------|
| Add a new built-in template | `scripts/build_builtin_templates.py` (add entry to `THEMES`) | `scripts/markdown_to_docx.py` (add matching entry to its `BUILTIN_TEMPLATES` dict), `SKILL.md` (Built-in templates list) | Run `python3 scripts/build_builtin_templates.py`, then `python3 scripts/markdown_to_docx.py --list-templates` and confirm the new name appears |
| Restyle an existing template (colors, fonts, sizes) | `scripts/build_builtin_templates.py` (edit a `THEMES` entry) | `SKILL.md` only if the template's description in the catalog changes | Regenerate templates and convert `assets/examples/sample.md`; open the DOCX and confirm the new accent/font is applied to headings and body |
| Change pandoc conversion behavior (markdown extensions, highlight style, extra flags) | `scripts/markdown_to_docx.py` (`build_command`, `build_parser`) | `SKILL.md` (command examples) | Run `python3 scripts/markdown_to_docx.py --print-command --input-file assets/examples/sample.md --output /tmp/out.docx` and verify the emitted pandoc command contains the new flags |
| Add or change metadata/resource-path handling | `scripts/markdown_to_docx.py` (`build_command` metadata and resource sections) | `SKILL.md` (Metadata and assets section) | Convert a Markdown file that references a local image and confirm the image resolves in the DOCX; pass `--title`/`--author` and check the DOCX properties |
| Change validation rules or error messages | `scripts/markdown_to_docx.py` (`validate_args`, `resolve_template`) | None typically | Run the script with no input, with both `--input-file` and `--markdown`, and with a missing file; confirm each fails with the intended message and a non-zero exit code |
| Update the sample file used for testing | `assets/examples/sample.md` | `SKILL.md` if the shown command changes | Convert the sample and confirm every construct in it (headings, table, fenced code) survives into the DOCX |
| Change the quick workflow or template rules narrative | `SKILL.md` | `scripts/markdown_to_docx.py` if CLI behavior is also changed | Re-read SKILL.md and confirm every flag and template name it mentions exists in the CLI |

## Modification Rules

- Only modify files listed in the Modification Map.
- Do not change the `name` field in SKILL.md frontmatter.
- Keep file paths and references intact — they may be referenced by SKILL.md.
- Test after every change using the Validation section below.

## Common Change Recipes

**Recipe 1: Add a new built-in template (e.g., "midnight-dark")**

1. Add a `midnight-dark` entry to the `THEMES` dict in `scripts/build_builtin_templates.py`, following the structure of existing themes (accent colors, latin/Hans fonts, sizes, code token colors).
2. Add a matching `midnight-dark` entry to the `BUILTIN_TEMPLATES` dict in `scripts/markdown_to_docx.py` with the correct `assets/templates/midnight-dark.docx` path and description.
3. Regenerate templates: `python3 scripts/build_builtin_templates.py`.
4. List templates to confirm registration: `python3 scripts/markdown_to_docx.py --list-templates` (new name must appear).
5. Add the template to the "Built-in templates" list in `SKILL.md`.
6. Validate: convert `assets/examples/sample.md` with `--builtin-template midnight-dark` and open the DOCX to confirm the styling is applied.

**Recipe 2: Retune the look of an existing template (e.g., make modern-blue use a darker heading)**

1. Edit the `modern-blue` entry in the `THEMES` dict in `scripts/build_builtin_templates.py` (e.g., change `heading_color`).
2. Regenerate templates: `python3 scripts/build_builtin_templates.py`.
3. Convert `assets/examples/sample.md` with `--builtin-template modern-blue`.
4. Validate: open the DOCX and confirm headings/links/body reflect the new color and that body text size and spacing were not accidentally changed.

**Recipe 3: Add a new CLI option (e.g., `--no-highlight` to disable syntax highlighting)**

1. Add the `--no-highlight` flag to `build_parser()` in `scripts/markdown_to_docx.py`.
2. In `build_command()`, drop the `--syntax-highlighting` argument when the flag is set.
3. Update the example commands in `SKILL.md` only if you want the new flag documented.
4. Validate: run with `--print-command --input-file assets/examples/sample.md --output /tmp/out.docx --no-highlight` and confirm the pandoc command no longer contains a highlight style; then run without the flag and confirm it does.

## Validation

Before finishing any change, verify all of these:

- [ ] `pandoc` is on `PATH` (`which pandoc` succeeds) — the converter and the template generator both require it.
- [ ] `python3 scripts/markdown_to_docx.py --list-templates` runs and lists exactly the templates defined in both `BUILTIN_TEMPLATES` (markdown_to_docx.py) and `THEMES` (build_builtin_templates.py) — the two registries are in sync.
- [ ] `python3 scripts/build_builtin_templates.py` completes and produces `assets/templates/*.docx` for every theme.
- [ ] `python3 scripts/markdown_to_docx.py --input-file assets/examples/sample.md --output /tmp/sample.docx --builtin-template modern-blue --toc --number-sections` exits 0 and the resulting DOCX opens (contains headings, the table, and the code block).
- [ ] The raw-string path works: `python3 scripts/markdown_to_docx.py --markdown '# Hi' --output /tmp/hi.docx` exits 0.
- [ ] Error paths behave: exactly one of `--input-file`/`--markdown` is required, missing files raise the intended message, and a missing built-in template tells the user to run `scripts/build_builtin_templates.py`.
- [ ] No temp files leak after a raw-string conversion (the converter's tempfile is cleaned up).
- [ ] The `name` field in SKILL.md frontmatter is unchanged.
