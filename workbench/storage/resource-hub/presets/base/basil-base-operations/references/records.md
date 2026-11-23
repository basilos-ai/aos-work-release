# Base record reads and writes

Use `scripts/base/records.py`. For `record_query` and its result view, read `record-query.md` instead; ordinary reads and mutations below do not create views.

## Read operations

| Operation | Endpoint | Required query | Permission |
| --- | --- | --- | --- |
| `record_get` | `GET /openapi/record/readRecord` | `tableId`, `recordId` | `auth.multi.dimensional.table.record.read` |
| `record_aggregate` | `GET /openapi/record/aggregation` | `tableId` | `auth.multi.dimensional.table.record.aggregation` |
| `record_enum_values` | `GET /openapi/record/fieldEnumValueList` | `tableId`, `fieldId` | `auth.multi.dimensional.table.record.field.enum.value.list` |


## Other read operations

`record_get` accepts `fieldKeyType`, `cellFormat`; `record_enum_values` accepts `fieldKeyType`, `limit` (default 50, maximum 1000). `record_aggregate` accepts `viewId`, `ignoreViewQuery`, `fieldKeyType`, `filter`, `orderBy`, `groupBy`, `collapsedGroupIds`, `search` (array of strings), `selectedRecordIds` and `aggregations` (JSON). Pass structured JSON or JSON strings for filter/orderBy/groupBy/collapsedGroupIds and aggregations; the execution layer encodes each once. search and selectedRecordIds arrays are sent as repeated parameters. Do not URL-encode them. A filter is a recursive object with conjunction (and/or), filterSet, isSymbol, fieldId, operator and value; orderBy/groupBy are arrays of fieldId/order objects. Use operators established by the API contract or a response, never guessed aliases. Keep field and record IDs as strings; integer table/view IDs may be decimal strings. fieldKeyType is ID, NAME or DB_FIELD_NAME; cellFormat is TEXT or JSON.

## Write operations

| Operation | Endpoint | Required body/query | Permission |
| --- | --- | --- | --- |
| `record_create` | `POST /openapi/record/saveRecord` | body record fields | `auth.multi.dimensional.table.record.save` |
| `record_batch_create` | `POST /openapi/record/batchSaveRecordList` | body `tableId`, `fieldKeyType`, non-empty `records` | `auth.multi.dimensional.table.record.batch.save` |
| `record_update` | `PUT /openapi/record/updateRecord` | body `tableId`, `recordId`, `fields` | `auth.multi.dimensional.table.record.update` |
| `record_batch_update` | `PUT /openapi/record/batchUpdateRecordList` | body `tableId`, non-empty `records` | `auth.multi.dimensional.table.record.batch.update` |
| `record_delete` | `DELETE /openapi/record/deleteRecord` | query `tableId`, `recordId` | `auth.multi.dimensional.table.record.delete` |
| `record_batch_delete` | `DELETE /openapi/record/deleteRecordList` | body `tableId`, non-empty `recordIds` | `auth.multi.dimensional.table.record.batch.delete` |

Single-create body fields are `tableId`, `fieldKeyType`, `typecast`, and `fields`. Batch-update records contain `recordId` and `fields`. `fieldKeyType` is `ID`, `NAME`, or `DB_FIELD_NAME`; prefer `ID` for stable automation. Use `typecast=true` only when the user wants server-side conversion.

## Library file references (`ASSETS_FILE`)

An `ASSETS_FILE` cell stores references to existing Library files. Use the ordinary record write operations with an object as the field value:

```json
{
  "assetsFileList": [{"id": "<Library file ID>"}],
  "mainAssetsFileList": []
}
```

`assetsFileList` contains the referenced files; `mainAssetsFileList` contains files selected as main images. For a PDF reference with no main image, pass an empty `mainAssetsFileList`. Keep file IDs as strings and obtain them from a Library query, an existing `ASSETS_FILE` cell, or an explicit user-provided ID. Do not invent IDs. A file reference only needs its `id`; file names, URLs and binary uploads are unnecessary. This object differs from the array used by `ATTACHMENT`; `record_attachment_upload` does not create a Library file reference.

First inspect the field metadata and read the target record with `fieldKeyType=ID` and `cellFormat=JSON`. For an append request, retain the current references and main-image selection when constructing the intended cell value; do not assume the update operation appends automatically.

Pass the following JSON on stdin to `scripts/base/records.py` after the Bootstrap and mutation policy in `SKILL.md`. Add the current `_runtimeDomain` and selected `_authMode` as described there; credentials remain host-injected.

```json
{
  "operation": "record_update",
  "_confirm": true,
  "body": {
    "tableId": "<table ID>",
    "recordId": "<record ID>",
    "fieldKeyType": "ID",
    "fields": {
      "<ASSETS_FILE field ID>": {
        "assetsFileList": [{"id": "<Library file ID>"}],
        "mainAssetsFileList": []
      }
    }
  }
}
```

The script sends `body` to `PUT /openapi/record/updateRecord`. The complete API path is `<current runtime origin>/typekey/api/v1/openapi/record/updateRecord`; the runtime adds `/typekey/api/v1` automatically. The operation and shared controls are script inputs, not HTTP body fields.

After a successful write, use the same script to read back the cell (add the shared runtime/auth controls):

```json
{
  "operation": "record_get",
  "query": {
    "tableId": "<table ID>",
    "recordId": "<record ID>",
    "fieldKeyType": "ID",
    "cellFormat": "JSON"
  }
}
```

Check that `data.fields["<ASSETS_FILE field ID>"].assetsFileList` contains the intended file ID. JSON reads return an object with `assetsFileList`, `mainAssetsFileList` and `groupBy`; the server may expand each reference with file metadata such as `originalName`, `extension` and `mimeType`. Do not depend on temporary file URLs as identifiers.

Validation evidence (2026-09-27): a direct HTTP update of an initially null `ASSETS_FILE` cell using one PDF file ID and `mainAssetsFileList: []` returned `success=true`, `code=0`. A subsequent JSON read returned that file ID with expanded PDF metadata. This verified the HTTP payload and readback; the packaged script, main-image selection, clearing, and create/batch variants were not exercised in that live test.

## Attachment upload

`record_attachment_upload` uploads one local non-empty file through the existing Base attachment multipart protocol. It requires the Base ID, not the table ID, and follows the global mutation confirmation policy. Add the current `_runtimeDomain` and selected `_authMode` required by `SKILL.md`:

```json
{
  "operation": "record_attachment_upload",
  "baseId": "<Base ID>",
  "file_path": "/absolute/path/report.pdf",
  "_confirm": true
}
```

The script initializes the upload, sends the server-sized chunks in order, completes the upload and returns a record-ready attachment object in `data`:

```json
{
  "id": "actXXXXXXXXXXXXXXXX",
  "name": "report.pdf",
  "token": "<server token>",
  "path": "multi-dim-table/attachments/<Base ID>/<server token>.pdf",
  "size": 1024,
  "mimetype": "application/pdf",
  "presignedUrl": "<temporary URL>"
}
```

Write attachment cells as a non-empty array of these objects through `record_create`, `record_update` or their batch variants. For an existing record, first use `record_get` with `cellFormat=JSON`, retain its current attachment array, append the new object in memory, then update the field. Sending only the new object replaces the existing cell value. Preserve `id`, `name`, `token`, `path`, `size` and `mimetype`; `presignedUrl`, thumbnail URLs and upload-session fields are temporary and the server does not persist them. Record reads refresh temporary URLs from the stable `path`.

If a chunk fails before completion begins, the script makes one best-effort abort call and does not write a record. It does not retry writes. If the completion request has been sent but its outcome is unknown, report the ambiguity and do not write attachment metadata; retry only with fresh confirmation because the first upload may have completed and become an orphan.

### Batch-create field keys

For `record_batch_create`, `body.fieldKeyType` determines how the keys in every `body.records[].fields` object are parsed:

| Value | Keys represent |
| --- | --- |
| `ID` | Field IDs obtained from metadata |
| `NAME` | Field names |
| `DB_FIELD_NAME` | Database column names |

The API default is `NAME`. The CLI requires an explicit `body.fieldKeyType` for every batch, alongside `body.tableId` and `body.records`, to avoid silent fallback. When field keys are IDs, explicitly pass `body.fieldKeyType="ID"`. Do not put this setting at the CLI input root, in `query`, or only inside `records[]`. The backend overwrites each record's `fieldKeyType` with the batch-level value. Without that value, IDs are interpreted as names and can cause “参数校验失败”. One batch must use one key type throughout.

The CLI stops before sending if the top-level setting is missing (including when it appears only inside records), invalid, or conflicts with any record's setting. An identical record-level setting is accepted but redundant; omit it. It does not infer key types or promote a record-level setting automatically.

Example CLI stdin for field ID keys (add `_runtimeDomain` as described in `SKILL.md`; use `_confirm=true` after the mutation confirmation):

```json
{
  "operation": "record_batch_create",
  "_confirm": true,
  "body": {
    "tableId": "<table ID>",
    "fieldKeyType": "ID",
    "records": [
      {"fields": {"<field ID>": "First value"}},
      {"fields": {"<field ID>": "Second value"}}
    ]
  }
}
```

For name keys, use `"fieldKeyType": "NAME"` at the same body level and `"fields": {"<field name>": "First value"}`. For database column keys, use `"fieldKeyType": "DB_FIELD_NAME"` and `"fields": {"<database column name>": "First value"}`.

Present every ID before batch-delete confirmation; use the global mutation policy in SKILL.md.

Apply the Result delivery rules in `SKILL.md` when a result link is returned.
