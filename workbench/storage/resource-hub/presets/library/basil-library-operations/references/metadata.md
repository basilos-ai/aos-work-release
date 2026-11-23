# Library metadata

Use `scripts/library/metadata.py`.

## `metadata_field_create`

Creates field definitions, not file values: `PUT /assets/metadata/field/save` under Runtime prefix `/typekey/api/v1`, permission `system.assets.metadata.field.create`. Use the existing selected credential. The request's `planType` must match the user's current asset mode; do not change mode, switch credentials, try another route/method or invent IDs. When the mode is not known from trusted context, the CLI defaults to `PRO`; a mode-conflict response requires determining the real mode, not blindly retrying with `LITE`.

Body parameters:

| Field | Required | Rules |
| --- | --- | --- |
| `name` | yes | Non-blank field name |
| `description` | yes | Non-blank description; derive from the user's stated purpose when clear |
| `type` | yes | `SINGLE_SELECT`, `MULTI_SELECT`, `NOT_ENUM`, `STRING`, `TIME`, or `NUMBER`; `LITE` allows only the first three |
| `planType` | no in CLI | Defaults to `PRO`; explicitly pass `LITE` for a verified LITE user; null and other values are rejected; the API always receives a value |
| `groupId` | no | Decimal ID string or null; defaults to null (ungrouped) |
| `enumOptionList` | no | For selection fields only: array of objects with non-blank `value` and optional string `description`; no duplicate values or supplied option IDs |

When no group is requested, use the default null. If a group is requested, use a verified group ID; do not infer an ID from its name. Single/multiple selection maps to `SINGLE_SELECT`/`MULTI_SELECT`; clarify only if the intended cardinality is unclear. Non-selection fields must omit options or use an empty list; non-empty options are rejected rather than silently discarded. Other body parameters are rejected.

### Create and resolve the field

1. If trusted context identifies the current asset mode, pass that `planType`; otherwise use the `PRO` default and stop on a mode conflict until the real mode is known. For LITE definitions, reuse `metadata_fields` in [metadata-catalog.md](metadata-catalog.md) to query the name and follow every matching page. Prefer `view=compact`. The name filter is fuzzy: compare returned names exactly, then inspect type, options and grouping. This read endpoint exposes only LITE fields; an empty result cannot establish that a PRO name is available.
2. Reuse a visible matching definition only if it satisfies the user's requested mode, type, options and grouping. If it conflicts, explain and ask for the intended resolution; do not rename automatically or convert an existing field's type. Field update/delete are not implemented by this capability.
3. Follow the global mutation policy, then call `metadata_field_create`. A successful response has `success=true`, `code=0`, `data=true` and no new ID. `data=false` or a missing `data` is a failed or unverified write, not success: report it and seek an applicable authoritative read before considering any retry. The packaged field-page read is LITE-only.
4. For LITE creation, query the name again, follow pagination and match the exact definition, including type, grouping and requested options. Obtain the real field ID and option IDs from that response. This endpoint cannot resolve a PRO field ID: report a successful create response without claiming readback verification or an ID. Do not create again or fabricate IDs.
5. If the user also requested file tagging, follow the separate `file_metadata_operate` contract and verify via `file_batch` where that LITE read path applies. PRO creation does not establish a usable field ID or PRO file-write/readback support through these LITE operations; report tagging as unresolved rather than guessing. This field-creation contract does not establish whether enum file writes take option IDs or text.

On timeout or another uncertain write result, query the LITE catalog when relevant, but remember it cannot establish the state of a PRO write. A match may be an existing/concurrently created field, not proof this request created it. An empty query is not permission to repeat the write. Report unresolved state instead of automatically replaying. Permission, name conflict and validation failures do not justify changing identity or guessing another mode.

Example CLI input (add current runtime controls from SKILL.md):

```json
{
  "operation": "metadata_field_create",
  "body": {
    "name": "色调",
    "description": "记录图片的主色调",
    "type": "SINGLE_SELECT",
    "enumOptionList": [
      {"value": "深蓝色"},
      {"value": "浅蓝色"},
      {"value": "牛仔蓝"},
      {"value": "黑色"}
    ]
  },
  "_confirm": true
}
```

The script adds `planType: "PRO"`, `groupId: null`. Verify the requested definition and confirmation before using the example; pass `planType: "LITE"` only when the user's current mode is known to be LITE.

## `folder_tags`

Calls `GET /openapi/assets/folder/tag/list`. Put optional `spaceType` (`MY`, `TEAM`, or `SHARED`), `folderId`, or `folderPath` in `query`. If `spaceType` is omitted, the server infers it from the directory locator. When both ID and path are supplied, they must identify the same directory; never rely on precedence. The endpoint's permission code is `auth.library.folder.tag.list`. The result contains metadata field definitions and enum options used within the selected folder level.

## `file_metadata_operate`

Calls `POST /openapi/assets/file/metadata/operate`. The endpoint's permission code is `auth.library.file.metadata.operate`.

### Resolve before writing

For file tagging, read [metadata-catalog.md](metadata-catalog.md) and use its `metadata_fields` contract before constructing a write. Reuse a definition already verified in the current task if there is no evidence it changed. Interpret the complete user request to identify candidate field names; do not treat prose, labels or punctuation as a literal API identifier without checking the catalog, and do not mechanically strip prefixes. Query candidates, follow pagination and match the intended definition. Use `metadata_catalog` when the intent requires broader discovery. `folder_tags` only shows used tags and is not a substitute for field discovery. Zero/multiple matches require resolving the ambiguity, not a speculative write or automatic field creation.

Inspect the definition's type, description and options to determine the value. Do not invent codes or translate values without evidence. If necessary ask only for the unresolved business value, not internal IDs or JSON. Do not infer a person's gender identity from appearance. Once resolved, prefer the real `fieldId`. Name-only inputs remain supported: the CLI reads the complete current-user LITE catalog, follows all pages, and requires one exact name match before substituting its ID; zero or multiple matches block the write. ID inputs avoid this extra read.

Inspect the file using [file-details.md](file-details.md), or reuse sufficient current file evidence such as the upload result. Follow the global mutation policy in SKILL.md. Preserve prior authorization for the same exact change; read-only lookup and correction of a rejected local input do not need a new confirmation. Body fields:

- required `operationType`: `ADD`, `UPDATE`, or `DELETE`;
- required `fileId`;
- `fieldId` or exact `fieldName`; `fieldId` takes precedence;
- required `value` for ADD/UPDATE: a **string containing a JSON array**; DELETE ignores it.

Encode the values array once with `json.dumps(values, ensure_ascii=False)` and assign that string to `body.value`. The CLI preserves it when serializing the outer request. Even one value must use this encoding: `"[\"nike\"]"`. Do not pass plain `"nike"` or a raw JSON array `["nike"]`. The CLI rejects these formats before making a request. The response's `metadata[].fieldValue` array is not the write input format.

Example script input (replace both IDs with verified values):

```json
{
  "operation": "file_metadata_operate",
  "body": {
    "operationType": "ADD",
    "fileId": "<fileId>",
    "fieldId": "<verifiedFieldId>",
    "value": "[\"nike\"]"
  },
  "_confirm": true
}
```

### Verify and recover

After writing, use `file_batch` from `file-details.md` with `body: {"idList": ["<fileId>"], "assetsType": "FILE"}`. Locate the requested file and check its `metadata` against the target field and intended value, using the response name/option maps where applicable. API success or an increased file version alone does not verify the stored value.

- Local validation error: read the named contract, correct the input once and continue without asking whether to investigate. Do not guess alternative keys.
- HTTP rejection: inspect sanitized `details` when returned. For field/value errors, refresh the relevant definition and compare the submitted request. Do not replay unchanged writes, change identity, or guess ADD/UPDATE semantics.
- Successful write but empty/mismatching readback: perform at most one further read-only check of the same file and relevant definition, then report the observed mismatch if unresolved. Do not call this “likely saved”, infer a mode mismatch without evidence, or repeat the write to prove it worked.
- Network/auth failures: follow SKILL.md failure routing. Missing error details mean the backend cause is unknown, not that the field/value is invalid.

If tagging fails, retain the upload result/file ID; never re-upload. Report upload, write-request and verified-value status separately. Unresolved readback means incomplete tagging: identify missing service evidence rather than asking permission for routine read-only diagnostics.
