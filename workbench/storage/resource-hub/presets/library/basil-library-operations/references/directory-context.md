# Library directory context

Read this shared context before every Library operation that searches, browses, resolves, creates, uploads to, renames, moves, or deletes a path or folder.

## Authoritative space model

Returned paths and IDs define the active user’s access boundary; never infer, probe, construct or display unavailable paths.

| `spaceType` | Meaning | Canonical path | Permission boundary |
| --- | --- | --- | --- |
| `MY` | Current user's own personal space | `/User/{currentUsername}[/relativePath]`; input may also use `/{currentUsername}[/relativePath]` | The current user owns this space directly; it does not use team ACL |
| `TEAM` | Team resources visible to the current user | `/Root[/relativePath]` | Team ACL and team sharing; administrator rights apply only here |
| `SHARED` | Resources another user directly shared with the current user | `/Shared/{grantId}[/relativePath]` | The specific direct-share grant and its allowed actions |

`TEAM` permanently excludes the `User` container and every personal space. `/Root/User/**` is not a public or team path. No user, including an administrator, may browse another user's personal space by default. A direct share exposes only the granted resource through `/Shared/{grantId}/...`; never reveal its owner's username or unshared ancestor directories.

## Resolve user language to a space

- “我的文件”, “我的目录”, “个人目录”, “个人空间”, or “my personal space” means `MY`. Call a tree operation with `spaceType=MY` and omit `folderPath` to resolve the current user's personal root without guessing a username.
- “团队目录” or “公共目录” means `TEAM`. Use only returned `/Root/...` paths.
- “共享目录”, “别人分享给我”, or “直接分享” means `SHARED`. Resolve a returned `/Shared/{grantId}/...` path; never substitute the owner's personal path.
- If “共享” is explicitly qualified as a team workspace rather than a direct resource share, use `TEAM` and keep the operation under `/Root/...`.

For personal-space uploads, use the resolved personal root unless a subfolder is named; resolve that subfolder when given. Ask only about ambiguity in visible results. Missing access or an empty tree is a lookup limitation, never grounds to guess a username, path, folder ID or alternative space.

## Locator and default rules

- When `spaceType` is omitted, the server may infer it from `folderId` or the path prefix. Structured search with no `spaceType` searches the visible union of `MY`, `TEAM`, and `SHARED`.
- With no directory locator, `MY` means the current user's personal root and `TEAM` means `/Root`. `SHARED` requires `/Shared/{grantId}`.
- If `spaceType` and `folderId` or `folderPath` are both supplied, they must identify the same space.
- If `folderId` and `folderPath` are both supplied, they must identify the same directory. Never rely on precedence or silent fallback.
- Verify explicit paths against the matching visible tree before using them for search, lookup, upload, create, move, rename, metadata work, or deletion.

File and folder moves must stay within one space, including the same personal space. Upload/copy requires a separately documented capability and confirmed user intent; never silently substitute it for a prohibited move.

If a target is outside the returned permission boundary, report that it is not visible or actionable for the current user. Do not claim it exists elsewhere or retry under another user's path.
