# organization-roles

For replacement writes, subject changes, or access revocation, preserve current state and check the impact scope using [workflows.md](workflows.md).

Use `scripts/admin_console/cli.py`; see [protocol.md](protocol.md) for shared input/output rules. Locate the required contract by operation; other capabilities need not be read.

- [organization_role_page](#organization-role-page): List organization roles with pagination
- [organization_role_create](#organization-role-create): Create an organization role and its legacy permissions
- [organization_role_update](#organization-role-update): Update an organization role and replace its legacy permissions
- [organization_role_delete](#organization-role-delete): Delete an organization role
- [organization_role_detail](#organization-role-detail): Read organization-role details including legacy permission IDs
- [organization_role_all](#organization-role-all): List all roles in the shared organization
- [organization_role_default](#organization-role-default): Set the default organization role
- [organization_role_assign](#organization-role-assign): Replace a member's legacy organization roles

## Legacy organization-role selection boundaries

Follow [interaction.md](interaction.md). Use this capability only when the user explicitly requests legacy organization Role operations. Obtain candidates through its organization-role queries; do not mix them with SystemRoles.

`permissionIdList` carries both legacy RolePermissionEnum values and application IDs, not the closed SystemRolePermissionEnum. Collect legacy organization permissions and application permissions in separate selection fields, then merge them into the request array. First obtain authoritative candidates and names for each. This package does not provide a complete candidate directory; neither `organization_permissions` (current permissions) nor an existing role's permissions represents the full set. An ID not matching the system enum is not proof of a valid application. Explain candidate-discovery limitations, resolve explicitly named objects first, and ask only about unresolved information; do not claim to offer a complete list. Read role details before editing and preserve unchanged permissions.

<a id="organization-role-page"></a>

## `organization_role_page` — List organization roles with pagination

GET /typekey/api/v1/role/page

Scope: Independent legacy organization-role system; called by Studio RoleSettings source, with the current configuration entry commented out

Authorization: Unified credential and license checks; no CheckSystemPermission on the controller. Some services call checkTenantId (the current User.checkTenantId body is commented out).

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|keyword|string|Not declared required|LIKE substring match on organization Role.name, without SystemRole-style escaping/trimming.|
|query|page|int32|Yes|The frontend sends pageIndex + 1, starting at 1; neither controller nor business logic declares a page lower-bound check.|
|query|size|int32|Yes|Controller @Max(1000); recommended 1..1000; no @Min or business lower-bound check.|

Response data: RoleVO[]. See the corresponding model in [models.md](models.md).

- Not current Admin Console system roles; IDs cannot be interchanged with SystemRole IDs.

- Filters by the fixed SHARED_ORGANIZATION_ID returned by HeaderInterceptor.getTenantId; arbitrary tenant-id headers do not switch organizations.

- Computes userNumber in bulk; page results do not populate permissionIdList, usually null. The detail endpoint populates it.

- Default ordering: created_at DESC NULLS LAST; no separate sort field is accepted.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 1003|param\.not\.match|Missing page or size|
|400 / 1005|param\.cast\.failure|id/page/size cannot be converted to target numeric types|
|400 / 1002|param\.is\.invalid|query.size exceeds 1000, violating the controller parameter's Max(1000) constraint|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|

<a id="organization-role-create"></a>

## `organization_role_create` — Create an organization role and its legacy permissions

POST /typekey/api/v1/role

Scope: Independent organization-role endpoint, not the current Admin role menu

Authorization: Unified credential and license checks; no CheckSystemPermission on the controller. Some services call checkTenantId (the current User.checkTenantId body is commented out).

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|name|string|NotBlank; saveRole additionally limits String.length <= 20|Name|
|body|description|string|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Remarks|
|body|permissionIdList|string\(integer\)\[\]|NotNull; may be an empty array, but underlying batch SQL behavior for empty arrays requires runtime verification|Permission ID collection|

Request body model: RoleSaveVO; see [models.md](models.md) for all nested fields.

Response data: RoleVO. See the corresponding model in [models.md](models.md).

- name has @NotBlank and String.length <= 20 on creation; description is optional; permissionIdList has @NotNull.

- The service saves a different object from the controller's pre-copied response, so response ID/organization ID/timestamps/defaultIs may be null. Query the page for the new ID.

- Saves organizationId as the shared organization and defaultIs=false.

- Permission IDs matching RolePermissionEnum are SYSTEM; others are recorded as APPLICATION (application IDs). This is not the strict SystemRolePermissionEnum.

- permissionIdList=[] passes NotNull, but empty batch insertion has no explicit short-circuit. Runtime verification is required; empty-array creation is not guaranteed to succeed.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 1002|param\.is\.invalid|Missing/null/empty/whitespace-only body.name, or missing/null body.permissionIdList. description is optional and permits an empty string under its declared constraints.|
|400 / 1001|param\.parse\.failure|Missing body, invalid JSON syntax, or unparseable BigInteger/array field types|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|
|400 / 400|biz\.error|Role name duplicates another Role in the current shared organization|
|400 / 400|biz\.error|Role creation only: name.length > 20; SystemRole has no equivalent 20-character limit|

<a id="organization-role-update"></a>

## `organization_role_update` — Update an organization role and replace its legacy permissions

PUT /typekey/api/v1/role

Scope: Independent organization-role endpoint, not the current Admin role menu

Authorization: Unified credential and license checks; no CheckSystemPermission on the controller. Some services call checkTenantId (the current User.checkTenantId body is commented out).

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|id|string\(integer\)|NotNull; must reference an existing record, otherwise the current implementation encounters a null pointer|Primary key|
|body|name|string|NotBlank; update does not repeat the 20-character limit|Name|
|body|description|string|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Remarks|
|body|permissionIdList|string\(integer\)\[\]|NotNull; replaces the whole collection|Permission ID collection|

Request body model: RoleUpdateVO; see [models.md](models.md) for all nested fields.

Response data: RoleVO. See the corresponding model in [models.md](models.md).

- id@NotNull/name@NotBlank/permissionIdList@NotNull; update does not reuse the creation-only 20-character limit.

- Loads the existing role and validates its shared organization, deletes all old permissions, inserts the new list, then updates name and other fields. Service-level transaction applies.

- No SystemRole-style super-administrator/defaultIs edit protection.

- A nonexistent target causes NPE at savedRole.checkTenantId rather than an explicit 404/business not-found result.

- The response maps the submitted Role object and may omit organizationId/createdAt/defaultIs/userNumber.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 1002|param\.is\.invalid|Missing/null body.id; missing/null/empty/whitespace-only body.name; or missing/null body.permissionIdList. description is optional.|
|400 / 1001|param\.parse\.failure|Missing body, invalid JSON syntax, or unparseable BigInteger/array field types|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|
|400 / 400|biz\.error|Role name duplicates another Role in the current shared organization|
|400 / 400|biz\.error|Existing Role organizationId differs from the shared organization ID during read/update/delete|

<a id="organization-role-delete"></a>

## `organization_role_delete` — Delete an organization role

DELETE /typekey/api/v1/role/\{id\}

Scope: Independent organization-role endpoint, not the current Admin role menu

Authorization: Unified credential and license checks; no CheckSystemPermission on the controller. Some services call checkTenantId (the current User.checkTenantId body is commented out).

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|path|id|BigInteger decimal ID|Yes|Organization Role ID|

Response data: boolean. See the corresponding model in [models.md](models.md).

- Rejects existing UserRole associations; after checking the shared organization, deletes RolePermission associations and the Role record.

- Organization Role deletion checks membership associations and shared-organization ownership, without default-role or super-administrator-name deletion protection.

- A nonexistent role causes a null pointer at role.getId; repeated deletion is not guaranteed to succeed idempotently.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 1005|param\.cast\.failure|id/page/size cannot be converted to target numeric types|
|400 / 400|biz\.error|Deletion rejected because the organization role has UserRole member associations|
|400 / 400|biz\.error|Existing Role organizationId differs from the shared organization ID during read/update/delete|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|

<a id="organization-role-detail"></a>

## `organization_role_detail` — Read organization-role details including legacy permission IDs

GET /typekey/api/v1/role/\{id\}

Scope: Independent organization-role endpoint; legacy Studio RoleSettings reads edit details

Authorization: Unified credential and license checks; no CheckSystemPermission on the controller. Some services call checkTenantId (the current User.checkTenantId body is commented out).

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|path|id|BigInteger decimal ID|Yes|Organization Role ID|

Response data: RoleVO. See the corresponding model in [models.md](models.md).

- Calls fillPermissionIdList, then checkTenantId; the current implementation encounters a null pointer if the role is absent.

- permissionIdList comes from RolePermission, not SystemRolePermission; userNumber is not populated here.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 1005|param\.cast\.failure|id/page/size cannot be converted to target numeric types|
|400 / 400|biz\.error|Existing Role organizationId differs from the shared organization ID during read/update/delete|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|

<a id="organization-role-all"></a>

## `organization_role_all` — List all roles in the shared organization

GET /typekey/api/v1/role/readRoleAll

Scope: Organization-member role selection helper; called by legacy Studio MemberOverview source

Authorization: Unified credential and license checks; no CheckSystemPermission on the controller. Some services call checkTenantId (the current User.checkTenantId body is commented out).

Parameters: No additional path/query/body fields.

Response data: RoleVO[]. See the corresponding model in [models.md](models.md).

- Filters by the fixed shared-organization ID; no pagination; permissionIdList/userNumber are not populated.

- Not /systemRole/optional; cannot supply resource ACL role candidates.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|

<a id="organization-role-default"></a>

## `organization_role_default` — Set the default organization role

PUT /typekey/api/v1/role/updateDefaultRole/\{id\}

Scope: Independent organization-role endpoint; called by legacy Studio RoleSettings

Authorization: Unified credential and license checks; no CheckSystemPermission on the controller. Some services call checkTenantId (the current User.checkTenantId body is commented out).

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|path|id|BigInteger decimal ID|Yes|Existing organization Role ID|

Response data: boolean. See the corresponding model in [models.md](models.md).

- Finds the shared organization's defaultIs=true role and sets it false, then finds the target ID and sets it true. No target-organization validation or explicit target-not-found check.

- No SystemRole default-role setter exists; this endpoint cannot change SystemRole.defaultIs.

- Missing current-default or target roles may cause NPE and transaction rollback.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 1005|param\.cast\.failure|id/page/size cannot be converted to target numeric types|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|

<a id="organization-role-assign"></a>

## `organization_role_assign` — Replace a member's legacy organization roles

PUT /typekey/api/v1/organization/changeRole

Scope: Legacy organization-member UI helper; distinct from systemRoleIdList and resource ACLs

Authorization: Unified credential and license checks; no CheckSystemPermission on the controller. Some services call checkTenantId (the current User.checkTenantId body is commented out).

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|userId|string\(integer\)|NotNull; must not be the current user or organization owner|User ID|
|body|roleIdList|string\(integer\)\[\]|NotNull; service explicitly rejects empty arrays|Role ID collection|

Request body model: ChangeRoleVO; see [models.md](models.md) for all nested fields.

Response data: boolean. See the corresponding model in [models.md](models.md).

- userId and roleIdList have @NotNull; the service rejects []. Operations on yourself or the organization owner are prohibited.

- Deletes all the user's old role associations in the current shared organization and inserts the submitted list; not incremental addition.

- Does not validate that every roleIdList ID exists and belongs to the current organization; no explicit deduplication.

- Updates UserRole organization-member associations; resource ACL systemRoleIdList references SystemRole.id.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 1002|param\.is\.invalid|Missing/null body.userId or body.roleIdList; roleIdList=[] returns code400/biz.error through service validation|
|400 / 1001|param\.parse\.failure|Missing body, invalid JSON syntax, or unparseable BigInteger/array field types|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|
|400 / 400|biz\.error|organization/changeRole target is the current user|
|400 / 400|biz\.error|organization/changeRole\.roleIdList=\[\]|
