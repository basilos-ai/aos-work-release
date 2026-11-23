# Base databases

Use `scripts/base/databases.py`.

| Operation | Endpoint | Input | Permission |
| --- | --- | --- | --- |
| `base_list` | `GET /openapi/base/page` | query `keyword?`, `page?`, `size?` | `auth.database.base.page` |
| `base_get` | `GET /openapi/base/{id}` | `path.id` | `auth.database.base.read` |
| `base_create` | `POST /openapi/base` | body `name`, optional `description`, `icon` | `auth.database.base.save` |
| `base_update` | `PUT /openapi/base` | body `id`, `name`, optional `description`, `icon` | `auth.database.base.update` |
| `base_delete` | `DELETE /openapi/base/{id}` | `path.id` | `auth.database.base.delete` |

List defaults are `page=0,size=10`; size cannot exceed 1000. Follow the global mutation policy in SKILL.md.

The returned `currentUserPermission` contains effective `roleType` (`OWNER`, `ADMIN`, or `READER`) and permission codes. Treat server authorization as authoritative; do not infer write access from the role name alone.
