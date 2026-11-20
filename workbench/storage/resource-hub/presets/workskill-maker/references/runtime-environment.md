# Workbench Sandbox Runtime Baseline

Read this reference during requirement analysis for every Skill, Work and Connector, before choosing an implementation. Use `runtime-inventory.json` for the complete explicitly declared OS and Python package lists and pinned versions. This is a Dockerfile-derived baseline captured on 2026-09-06, not an inspection of a deployed container.

## Evidence and scope

- The supplied Dockerfile declares contract `v1`; its embedded smoke script reports capability baseline `2026-08-28`. That string is not an image release or deployment date.
- A Dockerfile declaration does not prove a successful build, resolved transitive dependencies, or the deployed image's identity. Obtain the deployed image digest and run relevant checks in that sandbox when available. Do not treat the maker's host environment as target-runtime evidence.
- Node's base image is pinned by digest. Python packages are explicitly pinned, but apt packages and Python transitive dependencies are not fully locked. Python's exact version, npm's exact version and installed OS package versions require live inspection.
- The Dockerfile does not specify CPU, RAM, timeout, storage quota, network allowlists, writable mounts, GPU access or available Workbench Tools. Report these as deployment-dependent when the requested capability needs them.

## Declared environment

| Area | Declared baseline | Design consequence |
| --- | --- | --- |
| OS and Node | Debian Bookworm slim, Node.js 22.19.0; node and npm checked by smoke script | Use Linux-compatible commands; do not assume Windows COM, PowerShell, desktop Office or GUI automation |
| Python | `python3`, pip and venv; `/opt/sandbox-python/bin` prepended to PATH | Prefer `python` from that venv; inspect `sys.executable` and version when a constraint matters; system `/usr/bin/python3` may not see venv packages |
| Identity and workspace | Default `USER 1000:10001`, `WORKDIR /workspace`; deployment may override user | No root/sudo or arbitrary system installation assumptions; use runtime-approved writable output and temporary directories |
| Locale | `LANG=C.UTF-8`, `LC_ALL=C.UTF-8` | UTF-8 locale does not provide CJK fonts or OCR language data |
| Home and temporary state | `HOME=/workspace/resources/env/home`; D-Bus/keyring/XDG paths under `/tmp/workbench-runtime` | Home may hold sensitive persistent data; never use it for distributable artifacts, dump it, or assume `/tmp` persists |
| Lifecycle | Empty ENTRYPOINT; default CMD starts D-Bus/keyring and sleeps; Runtime overrides startup | Do not assume the default init runs, daemons exist, callbacks are reachable, or background jobs survive an invocation |

## Capability map

| Capability | Explicit packages/tools | Limits to check for the requested task |
| --- | --- | --- |
| Data and spreadsheets | numpy, pandas, openpyxl, xlsxwriter, sqlite3 | XLSX writing is not an Excel calculation engine; verify formulas/formatting through relevant acceptance checks |
| Word and slides | python-docx, python-pptx, pandoc | Office rendering/conversion is not supplied by these libraries; LibreOffice and TeX are not explicitly installed |
| PDF | pypdf, pdfplumber, pdfminer.six, pypdfium2, pdf2image, reportlab; Poppler, qpdf, Ghostscript | Validate fonts, extraction and rendered output separately; PDF generation does not prove CJK glyph coverage |
| Images and OCR | pillow, pytesseract; ImageMagick, tesseract-ocr | Check actual ImageMagick policy and Tesseract languages; `chi_sim`/`chi_tra` and CJK fonts are not explicitly installed |
| Media | ffmpeg | Inspect required codecs/filters; no AI transcription model or GPU stack is explicitly installed |
| HTML and structured text | beautifulsoup4, lxml, markdown, jinja2, pyyaml, pydantic; jq, xmlstarlet | HTML parsing is available; JavaScript browser rendering is not established |
| Network and mail clients | requests, httpx, aiohttp, websockets, aiosmtplib, dnspython, email-validator; curl, wget, SSH, OpenSSL, msmtp, dig, nc; Python stdlib SMTP/IMAP/POP | Clients do not grant network access, service accounts, OAuth configuration, or authorization to send |
| Databases | psycopg, pymysql, redis, sqlalchemy; PostgreSQL/MySQL/Redis clients, sqlite3 | Remote database servers and credentials are not provided; SQLite is local |
| Files and development | bash, coreutils, git, rg, rsync, patch, make, archive tools, py7zr | make alone does not establish a native build toolchain; gcc/g++, headers, Java, Rust and Docker are not explicitly installed |
| Secret-service compatibility | D-Bus, gnome-keyring, secret-tool, pass, gpg, keyctl | Tool presence is not a verified credential backend or a Workbench authentication contract |

No additional npm packages are explicitly installed by this Dockerfile. Treat `pptxgenjs`, `sharp`, `playwright`, `puppeteer` and similar packages as undeclared unless bundled correctly or verified in the target. Chromium/Chrome browser binaries, Playwright browser downloads, matplotlib, scipy, scikit-learn, torch, transformer/ASR models and service-specific SDKs are also not explicitly installed. These examples are not an exhaustive denylist: compare every actual requirement with the inventory. Dependencies supplied transitively or by the base image remain unverified until inspected.

## Runtime and authentication boundaries

Runtime controls network, capabilities, root filesystem, tmpfs, workspace mounts, credentials and resource limits. An installed `curl`, pip, npm, SSH or database client is not permission to use it against an external service or install packages during execution.

Skills and Works must continue to discover external services through `workbench_action_search` and invoke selected Connector Actions through `workbench_action_execute`. Connectors use their selected authentication reference. The Dockerfile neither implements nor proves availability of those Tools, secure password forms, environment injection, OAuth exchange/refresh or callback routing.

### OAuth2 capability evidence

An OAuth2 Connector requires target-platform evidence for managed authorization start, callback routing, `state`/PKCE handling, authorization-code exchange, encrypted connection storage, refresh, revocation/reauthorization, and the selected provider-call channel. The Dockerfile baseline alone is not evidence for any of these capabilities. Prefer a managed Connector Action whose gateway attaches the token; use foreground Runtime environment injection only when the target explicitly documents that OAuth2 injection contract. If a mandatory capability is unverified or unavailable, record the affected member and operation as blocked and do not add a local callback server, token file, or hand-written OAuth implementation as a workaround.

The default init unlocks a keyring using a blank login password for CLI Secret Service compatibility. The Dockerfile explicitly does not describe it as an independent encryption-at-rest boundary. Do not use the home directory, local JSON, `pass` or keyring as an API-Key credential fallback; retain the maker's managed password-form and environment-injection contract. Do not inspect credential contents as part of dependency detection.

Do not silently add startup `apt-get`, `pip install`, `npm install`, browser/model downloads, privileged containers, host paths or permanent background services. Prefer an installed equivalent, a compatible packaged dependency with its required resources, a Connector-backed service, or a platform image change. Bundled native dependencies must match target OS/architecture/ABI; a Windows build is not proof of Linux compatibility. Any installation proposal must identify network, write permission, size and lifecycle requirements instead of assuming deployment permits them.

## Dependency assessment before generation

1. Derive requirements from the actual workflow: Python distributions and import names, Node modules, CLI binaries, version constraints, fonts, OCR languages, browser/model files, native libraries, external Actions, authentication and relevant resource limits. Include Work members and their handoffs. For an instruction-only resource, state that no additional execution packages are required rather than inventing dependencies.
2. Compare with the inventory and any newer target evidence. Classify each requirement as `declared`, `verified`, `bundled`, `undeclared`, `missing`, `incompatible`, or `deployment-dependent`. Use `missing` only for a failed target presence check; lack of an explicit Dockerfile entry means `undeclared`, not proven absence. Record build/runtime failures separately from absence.
3. Before implementation, notify the user of material undeclared, missing, incompatible or deployment-dependent requirements, including the exact dependency/version or asset, affected function, mandatory/optional status, evidence and remedy. Do not wait until package delivery to reveal a blocker. Continue independent work; ask only when the choice changes the requested capability or requires unavailable deployment facts.
4. Resolve with an available equivalent where it preserves the requested behavior. Otherwise state the proposed bundle, platform image change or available Connector alternative. A requirements file by itself does not make a dependency installed. Never mark an unresolved mandatory dependency as ready to run.
5. Carry only task-relevant requirements into the generated member's runtime instructions, with a preflight before the dependent step and a precise error/remedy. Put detailed matrices in a packaged reference only when needed; do not copy the entire sandbox inventory into every output.

Use this report shape in requirement summaries and delivery evidence:

| Function/member | Dependency and constraint | Required/optional | Status and evidence | Impact and remedy |
| --- | --- | --- | --- | --- |
| Slide generation | python-pptx 1.0.2 | Required | declared in baseline; target not inspected | Generation supported by declaration; verify in target |
| HTML screenshot | playwright + matching browser binary/system libraries | Required | undeclared | Browser-based output is blocked until bundled/installed by platform or an available Connector supplies it |
| Chinese scanned PDF OCR | tesseract + chi_sim traineddata | Required | engine declared; language undeclared | Inspect languages, then supply language data or use an available OCR Connector |

## Bounded verification

Run only relevant checks through the target sandbox execution channel. Do not print environment dumps or read credential stores. Examples:

```sh
python -c 'import sys; print(sys.executable); print(sys.version)'
python -c 'from importlib.metadata import version; print(version("python-pptx"))'
python -c 'import pptx, docx, openpyxl; print("imports ok")'
node --version
command -v pandoc
tesseract --list-langs
```

For Node, test module loading using the generated script's actual ESM/CommonJS mode and resolution location; a global npm listing or a check from an unrelated directory is insufficient. For fonts, inspect and render the exact font required by the task; `fc-list` itself is not guaranteed by the explicit apt list. For libraries that depend on native binaries, imports alone are insufficient: execute a small relevant artifact operation.

The image includes `/usr/local/lib/workbench-sandbox/capability-smoke.py` and declares `pip check` plus a non-root build smoke run. The smoke script imports many libraries, checks command presence, exercises local artifacts and an SMTP loopback socket. Its reported categories do not prove remote database connectivity, real email delivery, keyring read/write or successful provider authentication. No execution log was supplied with this baseline. Run the full script only when a full baseline check is needed and target policy allows its loopback socket and temporary writes; policy denial is not automatically a missing dependency. Actual deployment with read-only root and real runtime parameters still needs verification.

Report static comparison, target preflight, functional artifact checks and external authentication/API checks separately. When target access is unavailable, explicitly say `Dockerfile baseline only; deployed runtime unverified`.
