# Base table views

Use `scripts/base/views.py`.

| Operation | Endpoint | Input | Permission |
| --- | --- | --- | --- |
| `view_list` | `GET /openapi/view/page` | query `tableId`, optional `keyword`, `page`, `size` | `auth.multi.dimensional.table.view.page` |
| `view_get` | `GET /openapi/view/read` | query `id`, `tableId` | `auth.multi.dimensional.table.view.read` |
| `view_create` | `POST /openapi/view` | body `tableId`, `type` | `auth.multi.dimensional.table.view.save` |
| `view_update` | `PUT /openapi/view` | body `id`, `tableId` | `auth.multi.dimensional.table.view.update` |
| `view_delete` | `DELETE /openapi/view/delete` | query `id`, `tableId` | `auth.multi.dimensional.table.view.delete` |

View create/update body fields include `name`, `description`, `type`, `options`, `sort`, `filter`, `groupMeta`, `columnMeta`, `enableShare`, `shareId`, `shareMeta`, `lockedIs`, and `publishToAssetsIs`; create also accepts `display` with default true. `tableId`, `id`, and `shareId` are JSON integers; scripts accept decimal strings and convert them exactly. `options` is optional. View type is `GRID`, `ASSETS_GRID`, `KANBAN`, `GALLERY`, `CALENDAR`, or `FORM`.

- `sort`: `{sortObjs:[{fieldId,order}], manualSort}`, order asc/desc.
- `filter`: recursive `{conjunction,filterSet,isSymbol,fieldId,operator,value}`.
- `groupMeta`: array of `{fieldId,order}`.
- `shareMeta`: `{allowCopy,includeHiddenField,password,includeRecords, submit:{allow,requireLogin}}`.

List defaults are `page=0,size=10`; size cannot exceed 1000. Treat share passwords as sensitive. Standalone mutations follow the global mutation policy in SKILL.md.

For accepted record queries, follow `record-query.md` and call `view_create_query_result` with the saved resultFile. Its scope, authorization exception, and recovery are defined there and in `SKILL.md`; do not manually assemble `view_create` or rerun the query to recover its link.
