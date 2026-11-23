# system-roles

For replacement writes, subject changes, or access revocation, preserve current state and check the impact scope using [workflows.md](workflows.md).

Use `scripts/admin_console/cli.py`; see [protocol.md](protocol.md) for shared input/output rules. Locate the required contract by operation; other capabilities need not be read.

- [system_role_create](#system-role-create): Create a system role and bind system permissions
- [system_role_update](#system-role-update): Update a system role and fully replace system permissions
- [system_role_delete](#system-role-delete): Delete a system role
- [system_role_page](#system-role-page): List system roles with permission IDs for editing
- [system_role_options](#system-role-options): Query system-role dropdown options

## Permission selection workflow

Follow [interaction.md](interaction.md) when information is missing. Reuse the supplied name on creation, collecting only missing remarks and unresolved permissions. For editing, first obtain the complete target row with `system_role_page`, preserving fields and permissions not requested to change.

For creation, query `system_role_page` for the supplied name and check exact matches before collecting missing remarks or permissions. If this necessary read returns a permission denial, report the blocker without asking the user to fill out a form first.

Build permissionList multi-selects from the complete system-function permission table in [permissions.md](permissions.md), using display names for labels and original IDs for values. Do not substitute a role list, a role's permissionIdList, or `system_permissions` (current-user permissions) for the full set. Do not offer replacement bundles such as "default-role permissions / test-role permissions / same as admin". Read and copy another role's actual permissions only when the user explicitly requests that copy.

Example: for "Create role test", collect remarks as text and system-function permissions as a multi-select; name test is already known. Show every known permission enum and explain that submitting no selections creates a role with no permissions. Non-submission or no answer does not authorize empty permissions. If permissions are already explicit, resolve them without another selection form.

Native Workbench field mapping, subject to the current schema checks in interaction.md:

|Field name|Type|Options and result mapping|
|---|---|---|
|`description`|`text`, required|Free-form remarks -> `body.description`|
|`permissionList`|`multi_select`, optional|One option per row of permissions.md, display name -> label and original ID string -> value; submitted array -> `body.permissionList`|

Put the full permission list (currently 47 distinct IDs) inside this field's `options`. Do not ask users to copy names or IDs from a chat list, split permissions into module text boxes, or substitute role bundles. There is no package-defined need to split these 47 options; follow the evidence-based host-limit rule only if an actual limit applies. Do not set a positive minimum selection count, since an explicitly submitted empty selection is valid on creation. Verify candidate completeness by the ID set, not by count alone.

<a id="system-role-create"></a>

## `system_role_create` — Create a system role and bind system permissions

POST /typekey/api/v1/systemRole/save

Scope: Current Admin Console role menu

Authorization: Unified credential and license checks; system permission 135000/system.admin.roles

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|name|string|NotBlank: Must not be null, empty, or whitespace-only|Name|
|body|description|string|NotBlank: Must not be null, empty, or whitespace-only|Remarks|
|body|permissionList|string\(integer\)\[\]|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Permission list|

Request body model: SystemRoleSaveVO; see [models.md](models.md) for all nested fields.

Response data: boolean. See the corresponding model in [models.md](models.md).

- Server generates the ID; defaultIs is fixed false; creator/updater is the current user. Response is only true, without the new role ID.

- Omitted/null/empty permissionList creates a role with no permissions. The product UI's default full selection and locked 111000 are product behavior only, not conversational authorization or API requirements. Do not default to all permissions or forcibly add 111000 based on that UI behavior.

- permissionList must use known SystemRolePermissionEnum IDs; no deduplication or null-element validation.

- Global duplicate-name check without trim normalization or a declared maximum length; @NotBlank rejects only blank values.

- Repeated submission with the same name errors; this is not idempotent creation.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 403|user\.has\.no\.permission|User credentials lack 135000 (or 134000 for auxiliary user-write endpoints); the system-permission aspect throws BizException with HTTP400, unlike authentication-interceptor UnauthorizedException with HTTP403|
|400 / 1002|param\.is\.invalid|Missing/null/empty/whitespace-only body.name or body.description violates NotBlank|
|400 / 1001|param\.parse\.failure|Missing body, invalid JSON syntax, or unparseable BigInteger/array field types|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|
|400 / 400|biz\.error|Role name duplicates another existing global system role|
|500 / \-1|error|Unknown enum IDs or null in SystemRole permissionList may trigger NullPointerException in of(id), returning HTTP500, code=-1, errorKey=error|

<a id="system-role-update"></a>

## `system_role_update` — Update a system role and fully replace system permissions

PUT /typekey/api/v1/systemRole/update

Scope: Current Admin Console role menu

Authorization: Unified credential and license checks; system permission 135000/system.admin.roles

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|id|string\(integer\)|NotNull; must reference an existing system role|Primary key|
|body|name|string|NotBlank|Name|
|body|description|string|NotBlank|Remarks|
|body|permissionList|string\(integer\)\[\]|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Permission list|
|body|defaultIs|boolean|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Whether this is the default role|
|body|createdBy|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Created by|
|body|updatedBy|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Modified by|

Request body model: SystemRoleUpdateVO; see [models.md](models.md) for all nested fields.

Response data: boolean. See the corresponding model in [models.md](models.md).

- id/name/description are required; permissionList has no NotNull.

- Permissions use replacement semantics: delete all SystemRolePermission entries for the role, then insert the submitted list. Omission, null, and [] all clear permissions.

- Cannot edit a role whose current name is the protected super-administrator literal (Unicode U+8D85 U+7BA1). Default role id0/defaultIs=true is not thereby protected from editing; defaultIs retains its database value.

- UpdateVO declares defaultIs/createdBy/updatedBy, but the service ignores them; the current user determines the audit updater.

- Identical repeated PUTs leave the same permission set but change update timestamps and association IDs; replay still performs writes.

- Role permission changes affect users holding the role through SystemUserRole; membership associations are unchanged. No independent system-permission bind/unbind endpoint exists.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 403|user\.has\.no\.permission|User credentials lack 135000 (or 134000 for auxiliary user-write endpoints); the system-permission aspect throws BizException with HTTP400, unlike authentication-interceptor UnauthorizedException with HTTP403|
|400 / 1002|param\.is\.invalid|Missing/null body.id or missing/null/empty/whitespace-only body.name or body.description|
|400 / 1001|param\.parse\.failure|Missing body, invalid JSON syntax, or unparseable BigInteger/array field types|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|
|400 / 400|biz\.error|Role name duplicates another existing global system role|
|400 / 400|biz\.error|System-role update/delete target does not exist|
|400 / 400|biz\.error|Edit rejected because the target's current name is the protected super-administrator literal (Unicode U+8D85 U+7BA1)|
|500 / \-1|error|Unknown enum IDs or null in SystemRole permissionList may trigger NullPointerException in of(id), returning HTTP500, code=-1, errorKey=error|

Skill overwrite protection: Explicitly provide `permissionList`; read current state, merge changes, then submit the complete value. This is client protection, not an additional server requirement.

<a id="system-role-delete"></a>

## `system_role_delete` — Delete a system role

DELETE /typekey/api/v1/systemRole/delete/\{id\}

Scope: Current Admin Console role menu

Authorization: Unified credential and license checks; system permission 135000/system.admin.roles

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|path|id|BigInteger decimal ID|Yes|Existing system-role ID; no positive-only restriction; 0 is the protected default role|

Response data: boolean. See the corresponding model in [models.md](models.md).

- Nonexistent targets return generic biz.error for data.not.exist; repeated DELETE does not return idempotent success.

- Backend rejects deletion when id=0, defaultIs=true, or name equals the protected super-administrator literal (Unicode U+8D85 U+7BA1). The UI hides deletion based on defaultIs.

- Rejects any SystemUserRole user association; first remove the role through user updates.

- Deletes the role and its permission associations; does not proactively clean up resource ACL associations or other references.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 403|user\.has\.no\.permission|User credentials lack 135000 (or 134000 for auxiliary user-write endpoints); the system-permission aspect throws BizException with HTTP400, unlike authentication-interceptor UnauthorizedException with HTTP403|
|400 / 1005|param\.cast\.failure|id/page/size cannot be converted to target numeric types|
|400 / 400|biz\.error|System-role update/delete target does not exist|
|400 / 400|biz\.error|Deletion rejected: target id=0, defaultIs=true, or name equals the protected super-administrator literal (Unicode U+8D85 U+7BA1)|
|400 / 400|biz\.error|Deletion rejected because the system role has SystemUserRole member associations|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|

<a id="system-role-page"></a>

## `system_role_page` — List system roles with permission IDs for editing

GET /typekey/api/v1/systemRole/page

Scope: Current Admin Console role menu

Authorization: Unified credential and license checks; system permission 135000/system.admin.roles

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|keyword|string|Not declared required|System roles: nonblank keyword is trimmed for name substring matching with SQL LIKE wildcards escaped; blank disables filtering|
|query|page|int32|Yes|The frontend sends pageIndex + 1, starting at 1; neither controller nor business logic declares a page lower-bound check.|
|query|size|int32|Yes|Controller @Max(1000); recommended 1..1000; no @Min or business lower-bound check.|

Response data: SystemRoleVO[]. See the corresponding model in [models.md](models.md).

- No separate GET /systemRole/{id} or detail getter; the page directly reuses name/description/permissionIdList from the current paginated row.

- Name substring matching; creation time descending, NULLS LAST. The controller accepts keyword, page, and size query parameters.

- Loads permission IDs for all roles on this page in bulk; no association yields permissionIdList=[]. No member counts or lists are returned.

- SystemRole has no organizationId and the service does not filter by tenant; these are global system roles.

- An annotation example shows page 0, but the actual frontend sends 1-based pages. Code does not validate size/page lower bounds; invalid lower-bound behavior is not guaranteed.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|400 / 403|user\.has\.no\.permission|User credentials lack 135000 (or 134000 for auxiliary user-write endpoints); the system-permission aspect throws BizException with HTTP400, unlike authentication-interceptor UnauthorizedException with HTTP403|
|400 / 1003|param\.not\.match|Missing page or size|
|400 / 1005|param\.cast\.failure|id/page/size cannot be converted to target numeric types|
|400 / 1002|param\.is\.invalid|query.size exceeds 1000, violating the controller parameter's Max(1000) constraint|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|

<a id="system-role-options"></a>

## `system_role_options` — Query system-role dropdown options

GET /typekey/api/v1/systemRole/optional

Scope: Helper for user system-role selection and resource ACL role selection; not called by the role menu itself

Authorization: Unified credential and license checks; no system permission; explicit IgnoreCheckSystemPermission

Parameters: No additional path/query/body fields.

Response data: SystemRoleOptionalVO[]. See the corresponding model in [models.md](models.md).

- @IgnoreCheckSystemPermission skips the 135000 check; valid credentials and License are still required.

- Excludes name equal to the protected super-administrator literal (Unicode U+8D85 U+7BA1); ordered by createdAt descending. Returns only id/name, with no pagination or other parameters.

- No membership filter; not a list of roles assigned to a particular user.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|No usable credentials, credential conflict, expiration, or invalid credentials|
|500 / \-1|error|Unclassified database/null-pointer or other exception; static risk only, not verified with real requests|
