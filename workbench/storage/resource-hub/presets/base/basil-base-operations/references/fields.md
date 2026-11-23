# Base table fields

Use `scripts/base/fields.py`.

| Operation | Endpoint | Input | Permission |
| --- | --- | --- | --- |
| `field_list` | `GET /openapi/field/page` | query `tableId`, optional `keyword`, `page`, `size` | `auth.multi.dimensional.table.field.page` |
| `field_get` | `GET /openapi/field/{id}` | `path.id` | `auth.multi.dimensional.table.field.read` |
| `field_create` | `POST /openapi/field` | body `name`, `type`, `tableId` | `auth.multi.dimensional.table.field.save` |
| `field_update` | `PUT /openapi/field` | body `id`, `name`, `type`, `dbFieldName`, `tableId` | `auth.multi.dimensional.table.field.update` |
| `field_delete` | `DELETE /openapi/field/{id}` | `path.id` | `auth.multi.dimensional.table.field.delete` |

Create/update also support `description`, `options`, `dbFieldName`, `notNull`, `uniqueIs`, and `primaryIs`. Field type is one of `SINGLE_LINE_TEXT`, `LONG_TEXT`, `NUMBER`, `CHECKBOX`, `SINGLE_SELECT`, `MULTIPLE_SELECT`, `DATE`, `RATING`, `ATTACHMENT`, `USER`, or `ASSETS_FILE`.

`ATTACHMENT` has no required field options. To upload a local file and obtain its record value, follow the attachment workflow in [records.md](records.md); do not place local paths or expiring URLs directly in a cell.

`ASSETS_FILE` stores references to existing Library files. For the `assetsFileList` / `mainAssetsFileList` cell structure, record update input and readback verification, follow [Library file references in records.md](records.md#library-file-references-assets_file).

List defaults are `page=0,size=10`; size cannot exceed 1000. Follow the global mutation policy in SKILL.md.
