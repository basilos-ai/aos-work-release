# Library file URLs

Use `scripts/library/file_urls.py`, operation `file_url_batch`: `POST /openapi/assets/file/url/batch`, permission `auth.library.file.url.batch`. On HTTP 403, check business permissions.

Pass `body` as a non-empty array. Each item supports:

| Field | Meaning |
| --- | --- |
| `id` | Asset file ID; use this or `path` |
| `path` | Asset file path; use this or `id` |
| `thumbnailTypeList` | Requested URL variants; include `ORIGINAL` for original file |
| `presigned` | `true` for a presigned URL, `false` for a public-bucket URL |

Each result contains `id`, `path`, and `urlMap`. URL-map keys may include `ORIGINAL`, `TINY`, `SMALL`, `MEDIUM`, `LARGE`, and `PREVIEW`. Presigned URLs expire; claim a lifetime only if returned.

The endpoint applies the same MY / TEAM / SHARED permission boundary. A direct share is addressed only through its returned `/Shared/{grantId}/...` path; never replace it with the owner's personal path or expose an unshared ancestor.
