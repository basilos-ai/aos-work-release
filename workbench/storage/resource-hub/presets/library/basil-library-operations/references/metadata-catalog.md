# Library Metadata discovery

Use `scripts/library/search.py` to browse Metadata definitions/catalogs; semantic asset search follows `search.md`. For large catalogs start with compact output, then use `search.md`’s private-file bounded reads or `search-session.md`’s bounded handoff if needed. Truncated stdout is incomplete.

## `metadata_catalog`

Input: `{"operation":"metadata_catalog","view":"compact"}`, with the runtime controls in `SKILL.md` and optional `_timeout`. `view` is optional and defaults to `full`; it is an output projection, not an API filter. Filters are not accepted. The script reads all current-user LITE fields, follows `addition` pagination, and rejects incomplete, duplicated or changing pagination. It returns the combined `data` array and `addition.total`. No catalog is persisted. A filtered `metadata_fields` result cannot replace it for search mapping.

Use `view=compact` for search mapping and ordinary Agent work. It is information-complete for choosing fields/values and constructing writes, but omits server audit, ordering and duplicated foreign-key fields:

- field: `id`, `name`, `type`, optional `description`, `groupId`, `groupName`, `enumOptionList`;
- option: `id`, `value`, optional `description`.

`full` returns the original server rows unchanged for audit/debug callers. Compact output is emitted as one-line JSON to avoid truncation; `addition` includes `{"total", "view": "compact"}` and, when case-insensitive duplicate names exist, `nameCollisions` as an array of original-name groups. Collisions are reported, never resolved automatically; inspect both definitions before choosing one.

## `metadata_fields`

Calls `GET /openapi/assets/metadata/field/page`. For permission troubleshooting, the endpoint's permission code is `auth.library.metadata.field.page`. The server always returns LITE fields (`SINGLE_SELECT`, `MULTI_SELECT`, `NOT_ENUM`), even for users currently in PRO mode, without checking or changing their asset mode. It cannot discover or verify a field created in PRO mode through `metadata_field_create`.

Put these fields in `query`:

| Field | Required | Rules |
| --- | --- | --- |
| `page` | yes | Integer starting at 1 |
| `size` | yes | Integer from 1 through 1000 |
| `name` | no | Metadata field-name fuzzy match |
| `fieldType` | no | `SINGLE_SELECT`, `MULTI_SELECT`, `NOT_ENUM`, `STRING`, `TIME`, or `NUMBER`; only the first three types are returned; the other types produce an empty page |
| `groupName` | no | String, at most 100 characters; exact match ignoring surrounding whitespace and case; blank means no group filter; unknown name returns an empty page; non-blank name is incompatible with `ungrouped=true` |
| `ungrouped` | no | Boolean; `true` selects only ungrouped fields; omitted or `false` disables this filter |
| `sortField` | no | `name`, `type`, `createdAt`, or `updatedAt`; omitted means creation time descending |
| `sortDirection` | no | `ASC` or `DESC`; defaults to `DESC` when sorting |

Only the query fields above are supported. Use `groupName` for group filtering; `planType` and request `groupId` are rejected. A top-level `view` (`full`, the default, or `compact`) applies the same projection as `metadata_catalog`; it controls local output and is not sent to the server. For example, pass to `scripts/library/search.py`:

```json
{"operation":"metadata_fields","query":{"page":1,"size":50,"groupName":"Campaign","fieldType":"SINGLE_SELECT"}}
```

There is no request body. Unknown groups or conditions with no LITE matches return successful `data: []` and `addition.total: 0`, retaining page and size. Invalid parameters and authentication failures use the unified error wrapper; business `code` is not the HTTP status.

Response `data` is a field array using the projection above. Full enum items include `id`, `fieldId`, `value`, `description`; compact omits redundant `fieldId` and audit fields. Paginate using `addition.total`, `addition.page`, `addition.size` until `page * size >= total`.
