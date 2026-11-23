# Base record queries and result delivery

Use `scripts/base/records.py` / `record_query`, then `scripts/base/views.py` / `view_create_query_result` after accepting the query. This document contains both calls; normal query delivery does not require loading `views.md` or the implementation. Querying uses `GET /openapi/record/queryRecord`, permission `auth.multi.dimensional.table.record.query`; field references also require `auth.multi.dimensional.table.field.page`. Creating its result view uses `POST /openapi/view`, permission `auth.multi.dimensional.table.view.save`.

## Query parameters

`query` follows `queryRecord`: required `tableId`; optional `viewId`, `ignoreViewQuery`, `fieldKeyType`, `cellFormat`, `projection`, `filter`, `orderBy`, `groupBy`, `collapsedGroupIds`, `search`, `selectedRecordIds`, `skip`, `take`. IDs must come from API metadata. When filter/orderBy/groupBy contain field references, the script loads this table's field metadata (including pagination), validates existing IDs, and resolves exact names or physical column names to IDs. Queries without such references do not load field metadata. Ambiguous or unknown references stop before querying or creating a view. `fieldKeyType` remains unchanged; it does not authorize storing names in a view's `fieldId`. The saved effective query and the created view share the normalized IDs. Integer IDs may be supplied as exact decimal strings; scripts convert them without floating-point rounding. `fieldId` and `recordId` remain strings. `fieldKeyType` is `ID`, `NAME`, or `DB_FIELD_NAME`; `cellFormat` is `TEXT` or `JSON`. This workflow defaults to skip=0, take=100 (the API default is 10); take cannot exceed 1000.

The execution layer serializes `filter`, `orderBy`, `groupBy`, and `collapsedGroupIds` to one JSON string each for GET requests. Callers may pass structured JSON or JSON-encoded strings. `projection` and `selectedRecordIds` are arrays of strings sent as repeated parameters. `search` is a string, `ignoreViewQuery` is boolean. Do not manually URL-encode values.

- `filter` follows ViewFilterVO: recursive `conjunction` (and/or), `filterSet`, `isSymbol`, `fieldId`, `operator`, `value`. Conjunction case is normalized. The reference does not enumerate operators or per-operator value types; do not infer aliases from another product. Numeric `>` with scalar `50` was verified in this deployment. It is an example, not the only allowed operator.
- `orderBy` and `groupBy` use arrays of `{fieldId, order}`; order is asc/desc (uppercase input is normalized). `collapsedGroupIds` is an array of strings.

Example (replace both IDs with values obtained from metadata):

```json
{
  "operation": "record_query",
  "query": {
    "tableId": "<table ID>",
    "fieldKeyType": "NAME",
    "cellFormat": "TEXT",
    "filter": {
      "conjunction": "and",
      "filterSet": [{"fieldId": "<price field ID>", "operator": ">", "value": 50}]
    },
    "take": 100
  }
}
```

## Query-result workflow

1. Run `record_query` through `scripts/base/records.py`. It resolves field metadata when needed, calls `queryRecord` once, saves the full response and effective query, and returns a bounded preview with `resultFile`, `returnedCount`, `previewComplete`, total when supplied, and `workflow.viewStatus`. `pending` means a result view can be created; it does not mean one exists.
2. Check that this query answers the user's question. For the matching query, run `scripts/base/views.py` with the exact returned `resultFile`:

```json
{
  "operation": "view_create_query_result",
  "resultFile": "<returned resultFile>",
  "viewName": "Materials with unit price above 50"
}
```

3. Deliver `data.snapshotLink` as the query result when `workflow.viewStatus` is `created` and the link is present. A row summary may accompany the link, but does not replace it. Do not stop after step 1, offer to fetch the link later, or request separate confirmation for this internal view.

The second call uses the saved query without querying again or accepting a replacement filter. It calls only `POST /openapi/view`, generates a `display=false` GRID view, and returns link/status independently of records. `filter` maps directly, `orderBy` maps to `sort.sortObjs` (manualSort=false), and `groupBy` maps to `groupMeta`. The live view covers all matching records; it is not an immutable snapshot or limited to the returned page. Sharing and publishing are not enabled. Exploratory queries need no result view until they answer the user's question. Supply a descriptive viewName; the script uses its first 80 characters plus a UUID suffix for the actual name. This avoids collisions between independent queries with the same label. The actual name is retained as `workflow.viewName` before creation and reused for the saved outcome.

### Output and recovery

Previews contain at most five records and fit an 8,000-byte stdout budget; large values are omitted as whole values, not truncated into invalid JSON. `previewComplete=false` means omitted fields or rows, not an empty query. Complete data remains in `resultFile` under `.basil-query-results` in the current workspace, including the exact effective query and, after creation, its link and status. Both calls must run in the same workspace and API environment. Files contain business data, use private permissions, and last for that workspace's lifetime. Do not use the local file path as the user-facing result link.

For additional fields, use Runtime `read` on the returned file with bounded chunks (remove `/workspace/` for workspace-relative tools), or use foreground `exec` to parse that file and print only requested fields. Do not print the whole file or rerun the query just to recover hidden output. Do not change the API projection merely to shorten the preview.

Local credential or timeout validation failures before creation leave the saved result pending. Follow `auth.md` for credential recovery; resume with the same resultFile only in the same workspace and API environment. Once creation starts, the persisted no-retry rules below apply, including after authorization changes.

Repeating `view_create_query_result` with the same resultFile returns the saved outcome without creating another view. An in-progress/ambiguous attempt is also retained and must not be retried as a new creation. `failedStage=view_create` means creation failed or is unknown; `failedStage=result_link` means the view was created but a usable link was not returned. Keep the view ID for diagnosis. The create call's top-level `success` is true and `code=0` only when a valid result link is ready. Otherwise it returns `success=false` and the local code `QUERY_RESULT_UNAVAILABLE`; inspect `workflow` for the provider failure or scope blocker. The saved query retains its own success status. Neither query success nor process exit code proves link success. A duplicate-data error is not grounds for automatic retries: it may concern a constraint other than the name. Previously failed result files keep their saved failure; deployment does not reset or retry those attempts.

### Scope and link limitations

An empty page creates no view. With nonzero skip, it does not prove zero total matches: query the appropriate page before deciding there are no matches. Non-empty `search`, `projection`, `selectedRecordIds`, `collapsedGroupIds`, or an inherited `viewId` scope (ignoreViewQuery is not true) have no faithful mapping in the documented ViewSaveVO. They return `not_created_unsupported_scope`. Preserve requested conditions; report the delivery blocker instead of creating a broader view or declaring the linked-result task complete.

`snapshotLink` is a deployment extension absent from the supplied ViewVO reference. If absent or invalid, report the link-stage failure; do not fabricate a URL or create another view. The Base frontend and Workbench are separate platforms: a result link need not share the session/API origin. The script validates HTTP(S) URL format and preserves the complete service-returned URL, including its origin, path, query and fragment; do not add `/basilos` or substitute the Workbench domain. API-domain validation, authenticated redirect restrictions and saved-result environment binding still apply. A returned link does not establish public sharing or verify browser access.

Apply the mutation exception and Result delivery policy in `SKILL.md`.
