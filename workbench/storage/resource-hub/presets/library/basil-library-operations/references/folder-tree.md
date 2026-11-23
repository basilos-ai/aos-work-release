# Library folder tree

Use `scripts/library/folder_tree.py`, operation `folder_tree`: `GET /openapi/assets/folder/tree`. Returns the selected directory and all visible descendants as Markdown.

## Input

Pass one JSON object on standard input:

| Field | Type | Default | Constraint |
| --- | --- | --- | --- |
| `operation` | string | required | `folder_tree` |
| `query.spaceType` | string | inferred | `MY`, `TEAM`, or `SHARED` |
| `query.folderPath` | string | space default | `/Root/...`, `/User/{username}/...` (or `/{username}/...`), or `/Shared/{grantId}/...` |
| `_timeout` | number | `30` | Positive; removed before the request |

Omit `folderPath` with `spaceType=MY` to address the current user's root without guessing a username. `TEAM` defaults to `/Root`. `SHARED` always requires `/Shared/{grantId}[/relativePath]`. Read `directory-context.md` before resolving any path.

## Output

Return Markdown unchanged. Resolve folders and prepare mutations from explicit node attributes:

| Attribute | Meaning |
| --- | --- |
| `folder_id` | This folder's ID; keep it as an exact string in subsequent inputs |
| `parent_folder_id` | Parent ID in the returned tree; may be `null` after subtree trimming |
| `version` | This folder's optimistic-lock version (integer or `null`) |
| `parentVersion` | Its actual parent's optimistic-lock version (integer or `null`) |

Names may contain Markdown escapes; match space and hierarchy, not name alone. A trimmed subtree may start with `parent_folder_id=null` and its actual `parentVersion`; this does not establish a space root.

The virtual `Root` has `folder_id=0` and null parent ID and versions. Its direct children have `parentVersion=0`. Do not apply these virtual-root values to a personal root or convert a missing/null version to zero. Zero explicitly returned as a version is valid. For mutation field mapping and missing-version recovery, follow `folders.md`.

Successful responses are Markdown; errors are JSON (HTTP 400 for invalid input or missing paths, 401 for invalid credentials, 403 for missing scope or access). An error response is not a directory tree. The endpoint scope is `auth.library.folder.tree`.
