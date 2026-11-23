# departments

For replacement writes, subject changes, or access revocation, preserve current state and check the impact scope using [workflows.md](workflows.md).

Use `scripts/admin_console/cli.py`; see [protocol.md](protocol.md) for shared input/output rules. Locate the required contract by operation; other capabilities need not be read.

- [department_tree](#department-tree): Read the department tree
- [department_create](#department-create): Create a department/subdepartment
- [department_update](#department-update): Rename, move, or set a department leader
- [department_delete](#department-delete): Delete a department and its subdepartments
- [department_page](#department-page): List departments with pagination
- [department_detail](#department-detail): Read department details
- [department_members_append](#department-members-append): Append user-department associations in bulk

## Department selection

Follow [interaction.md](interaction.md). Resolve parent and target departments from the current `department_tree`; show full paths when selection is needed. Display the root as "Head Department" with value `0`. If the user already specifies the root, do not ask again. Exclude the department itself and its descendants as move destinations; the root cannot be moved. Do not arbitrarily restrict candidates to recent departments.

For an existing department's leader, select from its direct members using paginated `user_page(departmentId)` or the tree's direct userList; do not include subdepartment or company-wide users. Do not ask for a leader on creation unless requested; when explicitly specified, resolve the real user and check the applicable scope. For membership additions, keep user selection separate from the target department.

<a id="department-tree"></a>

## `department_tree` — Read the department tree

GET /typekey/api/v1/department/tree

Scope: Used directly by the current administrative page

Authorization: Unified credentials; no additional system-menu permission is declared on this method or controller. The service does not enable administrator-seat checks. Common credential validation applies.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|withUser|boolean|Not declared required|Only true includes each department's direct userList; omitted/false does not query members|

Response data: DepartmentVO. See the corresponding model in [models.md](models.md).

- Returns a single root object, not an array; the root ID is fixed at 0.

- children recursively describes the tree; withUser=true includes userList as UserVO[]; the page uses false.

- The frontend displays root as Head Department without changing the server-side name.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="department-create"></a>

## `department_create` — Create a department/subdepartment

POST /typekey/api/v1/department

Scope: Used directly by the current administrative page

Authorization: Unified credentials; no additional system-menu permission is declared on this method or controller. The service does not enable administrator-seat checks. Common credential validation applies.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|name|string|Yes|@NotBlank; must not be blank. No explicit backend length/duplicate-name validation; the UI also checks nonempty input. NotBlank(message = "{required.parameter.error}")|
|body|parentId|string\(integer\)|Yes|@NotNull; use 0 for the root department; parent existence is not explicitly validated. NotNull(message = "{required.parameter.error}")|
|body|leaderId|string\(integer\)|Not declared required|Optional BigInteger; user membership/existence is not explicitly validated|

Request body model: DepartmentSaveVO; see [models.md](models.md) for all nested fields.

Response data: DepartmentVO. See the corresponding model in [models.md](models.md).

- rankIndex is generated as the maximum sibling value + 1; ID and timestamps are generated automatically.

- Duplicate-name validation is commented out in Department.save.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="department-update"></a>

## `department_update` — Rename, move, or set a department leader

PUT /typekey/api/v1/department

Scope: Used directly by the current administrative page

Authorization: Unified credentials; no additional system-menu permission is declared on this method or controller. The service does not enable administrator-seat checks. Common credential validation applies.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|id|string\(integer\)|Yes|@NotNull target department ID; NotNull(message = "{required.parameter.error}")|
|body|name|string|Not declared required|Optional; writes non-null values; no explicit nonblank/length/duplicate validation|
|body|parentId|string\(integer\)|Not declared required|Optional destination parent ID for moves; the UI disallows self/descendants and moving root 0; the backend does not enforce these business checks|
|body|leaderId|string\(integer\)|Not declared required|Optional selected leader user ID; the UI selects from this department's paginated users; the backend does not verify membership|

Request body model: DepartmentUpdateVO; see [models.md](models.md) for all nested fields.

Response data: DepartmentVO. See the corresponding model in [models.md](models.md).

- One PUT supports renaming {id,name}, moving {id,parentId}, and setting the leader {id,leaderId}.

- MyBatis updateById updates non-null fields; returns a copy of the submitted partial Department object, not a freshly queried entity, so omitted fields may be null.

- Do not describe UI tree-cycle restrictions as backend-enforced constraints.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="department-delete"></a>

## `department_delete` — Delete a department and its subdepartments

DELETE /typekey/api/v1/department/\{id\}

Scope: Used directly by the current administrative page

Authorization: Unified credentials; no additional system-menu permission is declared on this method or controller. The service does not enable administrator-seat checks. Common credential validation applies.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|path|id|string(integer)|Yes|Department ID to delete|

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Deleting root department 0 is rejected.

- Reads the whole tree and targets the department and all descendants. Rejects if any has user associations; otherwise deletes the entire subtree in bulk.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|Attempt to delete root 0 (root.department.cannot.be.deleted message)|
|400 / 400|biz\.error|This department or a descendant still has users (department.with.users.cannot.be.deleted message)|

<a id="department-page"></a>

## `department_page` — List departments with pagination

GET /typekey/api/v1/department/page

Scope: Same-domain helper endpoint, not called by the current page

Authorization: Unified credentials; no additional system-menu permission is declared on this method or controller. The service does not enable administrator-seat checks. Common credential validation applies.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|keyword|string|Not declared required|Department-name LIKE keyword|
|query|page|integer|Yes|Page numbers start at 1; no @Min|
|query|size|integer|Yes|Maximum 1000; no @Min; <= 1000|

Response data: DepartmentVO[]. See the corresponding model in [models.md](models.md).

- The controller has no parentId parameter; although present in the VO, it is not a supported query parameter here.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="department-detail"></a>

## `department_detail` — Read department details

GET /typekey/api/v1/department/\{id\}

Scope: Same-domain helper endpoint, not called by the current page

Authorization: Unified credentials; no additional system-menu permission is declared on this method or controller. The service does not enable administrator-seat checks. Common credential validation applies.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|path|id|string(integer)|Yes|Department ID|

Response data: DepartmentVO. See the corresponding model in [models.md](models.md).

- Direct getById, usually without children/userList; unknown IDs return success with data=null, with no dedicated not-found validation.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="department-members-append"></a>

## `department_members_append` — Append user-department associations in bulk

POST /typekey/api/v1/department/batchSaveUserDepartment

Scope: Same-domain helper endpoint, not called by the current page

Authorization: Unified credentials; no additional system-menu permission is declared on this method or controller. The service does not enable administrator-seat checks. Common credential validation applies.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|userId|string\(integer\)|Yes|User ID; NotNull(message = "{required.parameter.error}")|
|body|departmentId|string\(integer\)|Yes|Department ID; NotNull(message = "{required.parameter.error}")|

Request body model: UserDepartmentSaveVO[]; see [models.md](models.md) for nested fields. The top-level body is an array.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Only inserts associations in bulk and generates IDs/timestamps; unlike updateUser, it does not fully replace departments.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.
