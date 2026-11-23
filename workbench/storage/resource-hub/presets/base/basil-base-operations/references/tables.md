# Base data tables

Use `scripts/base/tables.py`.

| Operation | Endpoint | Input | Permission |
| --- | --- | --- | --- |
| `table_list` | `GET /openapi/tableMeta/page` | query `baseId`, optional `keyword`, `page`, `size` | `auth.multi.dimensional.table.meta.page` |
| `table_get` | `GET /openapi/tableMeta/{id}` | `path.id` | `auth.multi.dimensional.table.meta.read` |
| `table_create` | `POST /openapi/tableMeta` | body `baseId`, `name` | `auth.multi.dimensional.table.meta.save` |
| `table_update` | `PUT /openapi/tableMeta` | body `id`, `baseId`, `name`, `dbTableName` | `auth.multi.dimensional.table.meta.update` |
| `table_delete` | `DELETE /openapi/tableMeta/{id}` | `path.id` | `auth.multi.dimensional.table.meta.delete` |

Create also accepts `description`, `icon`, `dbTableName`, and `createDefaultRecordIs`. Update accepts optional `description` and `icon`. List defaults are `page=0,size=10`; size cannot exceed 1000.

Follow the global mutation policy in SKILL.md.
