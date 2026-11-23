# Library asset details

Use `scripts/library/search.py`. ID-only lookup relies on server ACLs; read `directory-context.md` for path/space interpretation.

## `file_batch`

Calls `POST /openapi/assets/file/batch?planType=LITE`. The endpoint's permission code is `auth.library.file.batch.query`; HTTP 403 requires checking business permissions.

Body: required `idList`, optional `assetsType` (`FILE` or `FOLDER`); LITE only. Results may contain `fileList`, `folderList`, folder paths, metadata names/options, and page information. IDs do not bypass the MY / TEAM / SHARED permission boundary; inaccessible personal or unshared resources must not be inferred from missing results.

If a query-result link is returned, apply the Result delivery rules in `SKILL.md`. This detail lookup does not replace the accepted/refined structured-search link.
