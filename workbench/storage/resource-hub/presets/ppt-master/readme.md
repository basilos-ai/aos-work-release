# PPT Master — Maintenance Guide (Localized Build)

This package is a privacy-localized derivation of the PPT Master presentation workflow. Maintain it with the same rules as any ordinary Workbench Skill.

## File map

| Path | Purpose |
|---|---|
| `SKILL.md` | Entry point: global execution discipline, route selection, and the localization boundary. |
| `user_preferences.md` | Persistent preferences explicitly approved by the user. |
| `references/` | Design standards, image/style/palette catalogs, native PPTX interfaces, and `localization.md` (the change list). |
| `workflows/` | Route authorities: `routing.md`, `generate-pptx.md`, `create-template.md`, `edit-native-pptx.md`, profiles, stages, and governance. |
| `scripts/` | Local Python tooling (SVG authoring, PPTX export, validation, preview servers, conversions) plus `tests/`. |
| `templates/` | Local assets: style workspaces, charts, tables, diagrams, icons, sounds, and SVG presets. |
| `requirements.txt` | Local-only Python dependencies. |

## Localization invariants (do not regress)

1. No `.env`, `.env.example`, credential file, API key, token, or secret is ever stored in the package or read from disk by its scripts. `config.py`'s env-file loader is a no-op by design.
2. No direct external API call is possible from a packaged script. `image_gen.py`, `image_search.py`, `notes_to_audio.py`, `latex_render.py`, and `web_to_md.py` are disabled entry points that fail with messages pointing to `references/localization.md`.
3. External image generation, web image search, cloud TTS, web fetching, and remote LaTeX rendering are out of scope. Local substitutes: user-supplied images, `image_treat.py` / `slice_images.py` local processing, local audio files, native formula markers compiled to OMML by `svg_to_pptx.py`.
4. No provenance, attribution, author, license, or sponsor file is packaged. Adaptation lineage lives in the delivery report that accompanied this build.
5. If an external service becomes genuinely necessary, it must be provided as a separate Connector and invoked only via `workbench_action_search` + `workbench_action_execute` with the user's explicit authorization — never through code in this package.

## Modification rules

- Keep `SKILL.md` frontmatter minimal: `name` and a capability-and-trigger `description` only.
- Keep the exact lowercase names `readme.md` and `user_preferences.md`; never add an uppercase `README.md`.
- One responsibility per routed authority; keep scripts deterministic and local.
- When you add a script, register it in this map and keep it free of network and credential code.

## Validation checklist

1. `SKILL.md` has valid YAML frontmatter; `name: ppt-master` matches the directory name.
2. `readme.md` and `user_preferences.md` are exact lowercase, present, non-empty.
3. No `README.md`, `LICENSE`, `SPONSORS*`, `PROVENANCE*`, `AUTHORS*`, `*.env*`, or `.pem`/`.key` files exist anywhere under the package root.
4. `grep -rIEn 'sk-[A-Za-z0-9]{10,}|AIza[0-9A-Za-z_-]{20,}|r8_[A-Za-z0-9]{10,}' .` returns nothing.
5. No packaged script imports `image_backends`, `image_sources`, `tts_backends`, `attribution_guard`, `google.genai`, or `edge_tts`.
6. `python3 -m py_compile` passes on every `scripts/*.py`; the local test suite under `scripts/tests/` passes with the trimmed `requirements.txt`.
7. Every reference and command in `SKILL.md` and `workflows/` points to a packaged file or a documented local runtime dependency.