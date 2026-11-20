# Localization Boundary (read before choosing a route)

This build is a privacy-localized derivation of the original PPT Master skill. The core local capability is fully preserved: SVG page authoring, native DrawingML/PPTX export, template workspaces (Brand / Style / Layout / Deck), native PPTX round-trip editing, charts, tables, diagrams, icons, animations, transitions, sound design, and video packaging. What changed is the *external* surface: every feature that required an API key, a credential file, or a direct call to a third-party service is disabled.

## Disabled capabilities and their local substitutes

| Original capability | Why disabled | Local substitute in this build |
|---|---|---|
| `image_gen.py` + `image_backends/` — cloud image generation (OpenAI/Gemini/Qwen/Zhipu/Volcengine/Tencent/Stability/BFL/Ideogram/MiniMax/SiliconFlow/FAL/Replicate/OpenRouter/ModelScope) | Sends prompts and business content to third parties; requires API keys; billed | User-supplied images; local `image_treat.py` (fit/blur/duotone/gray), `slice_images.py` (sheet slicing), `rotate_images.py`; SVG-native illustration stays fully available |
| `image_search.py` + `image_sources/` — web image search/download (Openverse/Wikimedia/Pexels/Pixabay) | Outbound network fetches, provider tracking, keyed providers | User-supplied image folders; `references/` palettes/renderings/type catalogs remain as design guidance |
| `notes_to_audio.py` + `tts_backends/` — narration TTS (edge-tts, ElevenLabs, MiniMax, Qwen, CosyVoice) | Sends full slide notes to cloud TTS engines; keyed providers send voice content abroad | Local audio files placed in the project `audio/` directory; narration notes are still written for later use |
| `web_to_md.py` — web page → Markdown fetching | Arbitrary URL fetch tool (SSRF surface, TLS-fingerprint impersonation) | Ask the user to supply page text/files; the fetch function raises a clear disabled error |
| `latex_render.py` — remote LaTeX → PNG (CodeCogs/Wikimedia/QuickLaTeX/MathPad) | Sends formula content to third parties | Native formula markers in SVG compiled to editable PowerPoint OMML by `svg_to_pptx.py` |
| `gemini_watermark_remover.py` | — | Retained local tool: reverse-blend watermark removal (Pillow/numpy), no network, no API key |
| `.env` loading in `config.py` (`load_prefixed_env_file`) | Credential file reads (CWD, skill dir, repo root, `~/.ppt-master/.env`) | No-op by design; scripts never read credentials from disk |
| `update_repo.py` | Pulls and auto-installs from an upstream Git remote | Removed; this package is immutable in place |
| `attribution_guard.py`, `SPONSORS*`, `LICENSE` placement inside the package | Author/provenance enforcement and sponsor promotion conflict with packaging standards and local privacy | Removed; lineage is recorded in the external delivery report |
| `requirements.txt` cloud entries (`google-genai`, `edge-tts`, `curl_cffi`) | Pull in provider SDKs and open network channels | Removed; file now lists local-only dependencies |

## What still works (unchanged core)

- **Generate PPTX** (Default / Quick): Plan → Do·Check·Act; spec/lock or Quick; hand-authored compact SVG; `svg_quality_checker.py` gates; `svg_to_pptx.py` native export; charts via XlsxWriter/python-pptx.
- **Create Template**: `brand` / `style` / `layout` / `deck` workspaces from local PPTX/SVG/images/PDFs/texts/documents.
- **Edit Native PPTX**: `pptx_to_svg.py --roundtrip` byte-preserving round trip, native motion overlay, transitions, notes.
- **Local servers**: `confirm_ui/`, `svg_editor/`, live preview — bound to localhost only, for in-loop confirmation and annotation.
- **Local conversion**: `source_to_md/` (PDF/DOCX/XLSX/HTML/EPUB/IPYNB to Markdown), with remote-image downloads disabled inside HTML conversion.
- **Tests**: 17 local regression tests under `scripts/tests/`.

## Re-enablement boundary (the only sanctioned path)

If an external capability is genuinely required later, it must be delivered as a separate Connector resource (API-Key or OAuth2 per the Connector standard), and the runtime must discover it with `workbench_action_search` and invoke it only through `workbench_action_execute` with the schemas returned by that search. Credentials then live in Workbench-managed encrypted storage, never in this package. No packaged script may add direct API calls, embedded keys, or `.env` handling; such changes regress the localization and must be rejected in review.