# Library file management

Use `scripts/library/files.py`. Follow the global mutation policy in SKILL.md, including confirmation and delete guards.

| Operation | Endpoint | Input | Permission |
| --- | --- | --- | --- |
| `file_upload` | `POST /openapi/assets/file/upload` | `file_path`; query `folderId` or `folderPath`; optional `spaceType` | `auth.library.file.upload` |
| `file_rename` | `PUT /openapi/assets/file/rename` | body `fileId`, `newName`, `version` | `auth.library.file.rename` |
| `file_move` | `PUT /openapi/assets/file/move` | body `fileId`, `version`; optional `targetParentId` | `auth.library.file.move` |
| `file_delete` | `DELETE /openapi/assets/file` | body `folderId`, `fileId` | `auth.library.file.delete` |
| `delete_batch` | `PUT /openapi/assets/deleteBatch` | body file/folder lists | `auth.library.resource.batch.delete` |

## Resolve upload destination

Resolve spaces with [directory-context.md](directory-context.md) and destinations with [folder-tree.md](folder-tree.md). Obtain the API’s required `folderId` or `folderPath` through lookup; the user need not supply it.

For “上传到个人空间” / “upload to my personal space” with no named subfolder:

1. Complete SKILL.md Bootstrap. Call `scripts/library/folder_tree.py` via the documented stdin transport, adding the current domain and selected auth mode:

   ```json
   {"operation":"folder_tree","query":{"spaceType":"MY"},"_runtimeDomain":"<current session_status.domain>"}
   ```

2. Use the personal root identified by this unscoped MY response. Copy its explicit `folder_id` as an exact string; if only a verified canonical full path is available, use that path. A display name or parent_folder_id=null alone is not sufficient to construct a path or infer a root. Do not use session userId as folderId, guess a username, choose an arbitrary child or fall back to TEAM.
3. After the existing mutation confirmation, upload the available local image with `operation=file_upload`, `file_path`, `query.spaceType=MY` and the resolved `query.folderId` (or verified folderPath), plus `_confirm=true` and current Runtime controls. Do not request another destination merely because the user omitted an internal ID. Upload does not require parentVersion; do not import folder_create's version requirements into this operation.

If the user names a subfolder, resolve that intended subfolder instead. Ask for clarification only for genuinely ambiguous targets; a failed/empty lookup should report its actual limitation. Never ask for technical parameters before trying the supported lookup. Preserve the user's original upload and Metadata intent: use the returned Library file ID for subsequent operations in metadata.md, not the chat attachment ID. Clarify an unknown Metadata value separately; it does not make the meaning of “personal space” ambiguous.

Upload uses multipart data from the local file, never file bytes in JSON. `spaceType`: `MY`, `TEAM`, `SHARED`, or inferred from `folderId`/`folderPath` when omitted. Supplied locators must agree on directory and space; no precedence or silent fallback.

Before `file_move`, inspect both spaces. Moves across distinct spaces, including different personal spaces, are rejected; report the constraint without retrying or substituting upload/copy.

`delete_batch` accepts `fileItemList` entries shaped like `file_delete` bodies and `folderItemList` entries containing `folderId`, `version`, and `parentVersion`. At least one list must be non-empty. Present the complete batch to the user before confirmation.

Before versioned writes, read the latest file and required parent versions through supported operations (file_batch can inspect FILE or FOLDER resources). If a required version is unavailable, stop and explain what is missing; never guess, increment or silently overwrite it. On conflict, reread the current state and obtain confirmation of the updated change before proceeding. Version fields are passed through; the script does not establish that a supplied version is current.
