# acl

For replacement writes, subject changes, or access revocation, preserve current state and check the impact scope using [workflows.md](workflows.md).

Use `scripts/admin_console/cli.py`; see [protocol.md](protocol.md) for shared input/output rules. Locate the required contract by operation; other capabilities need not be read.

- [acl_page](#acl-page): List resource ACL configurations with pagination
- [acl_form](#acl-form): Initialize the resource permission configuration form
- [acl_create](#acl-create): Create a resource ACL configuration
- [acl_update](#acl-update): Update a resource ACL configuration
- [acl_delete](#acl-delete): Delete a resource ACL configuration
- [acl_detail](#acl-detail): Read resource ACL configuration details
- [effective_permissions](#effective-permissions): Read the current user's effective asset permissions

## Collecting configuration inputs

Follow [interaction.md](interaction.md). For creation, call `acl_form`; for editing, pass `permissionId` to load candidates and current configuration, preserving all unchanged subjects and explicit rules.

|Missing field|Control semantics|Authoritative candidate source|
|---|---|---|
|System roles: systemRoleIdList|`multi_select`; individually optional|All roleOptionList options; do not add the super-administrator role excluded by the endpoint|
|Departments: departmentIdList|`multi_select`; individually optional|The complete departmentTree; show full paths in labels|
|Rule target: folderId|`single_select` per rule, or a verified equivalent folder selector|Real TEAM folders from folderTree, including Root; do not substitute the employee-visible tree|
|Permission preset: presetType|`single_select`|presetOptionList; for edits restoring inheritance, follow the INHERIT semantics below|
|Custom actions: permissionIdList|`multi_select` only for CUSTOM|All valid actions from actionOptionList|

Use separate system-role and department fields. Explain: "Select at least one role or department; both are allowed. Departments include members of their subdepartments." Do not combine them into subjects, use an "other role/department names" field to compensate for arbitrarily omitted candidates, or require both fields. Before submission, check that they are not both empty; otherwise ask only for subjects and retain the other inputs.

Use the API field names as form names and apply the native bindings and host-schema checks in interaction.md. Each field must carry its own complete `options`: role names with role ID values; full department paths with department ID values; preset labels with presetType values; action labels with action ID values. Map the returned role and department arrays separately into the corresponding body arrays. Do not replace these fields with text even when cross-field validation is unavailable; perform the at-least-one check before the business call. The existing `acl_form` read supplies these candidates and must succeed before opening their selection form.

Example: the user provides name test, description test, and management access to all folders. Show only the system-role and department multi-selects. Describe the rule as "All team folders (Root, inherited by descendants) / Manage" and submit `{"folderId":"0","presetType":"MANAGE"}` from that explicit intent, without asking for the folder or preset again. Do not collect or attach permissionIdList for non-CUSTOM presets; expanded actions in presetOptionList only explain the preset.

<a id="acl-page"></a>

## `acl_page` — List resource ACL configurations with pagination

GET /typekey/api/v1/assets/permission/page

Purpose: Main resource-permission list, filtered by name keyword; returns lightweight fields rather than rule details

Scope: Used directly by Admin asset-ace; useAssetAceRequest.getPagePermission

Authorization: System permission 131000 / system.admin.assets.permission.management. Administrative ACL endpoints enforce system permissions; the configuration tree is not filtered by the administrator's own resource ACL. Uses the global CredentialAuthenticationInterceptor; the system-permission aspect has bypass branches for STUDIO/OAUTH_CLIENT. Menu visibility cannot replace endpoint authorization.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|sortField|string|Not declared required|Sort field|
|query|sortDirection|SortDirectionEnum|Not declared required|Sort direction|
|query|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|query|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|
|query|keyword|string|Not declared required|Permission name keyword|

Response data: List\<AssetsPermissionPageVO\>. See the corresponding model in [models.md](models.md).

- CommonQueryVO declares page/size required. size has only @Max(1000), no @Min; recommended page >= 1 and size 1..1000. Backend enforcement of lower bounds is not guaranteed.

- Trims keyword and escapes it for LIKE substring matching; orders by createdAt descending. Although inherited, sortField/sortDirection are ignored by this service's pageWithoutSort.

- systemRoleList excludes deleted system roles; the list does not return ruleList/status.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 403|user\.has\.no\.permission|Current user lacks system permission 131000; this aspect throws BizException, resulting in HTTP 400|

<a id="acl-form"></a>

## `acl_form` — Initialize the resource permission configuration form

GET /typekey/api/v1/assets/permission/form/init

Purpose: Return creation/edit details, the complete team folder tree, system-role options, department tree, presets, and action options in one call

Scope: Used directly by Admin asset-ace for both creation and editing; no separate employee browsing call is needed for the folder tree

Authorization: System permission 131000 / system.admin.assets.permission.management. Administrative ACL endpoints enforce system permissions; the configuration tree is not filtered by the administrator's own resource ACL. Uses the global CredentialAuthenticationInterceptor; the system-permission aspect has bypass branches for STUDIO/OAUTH_CLIENT. Menu visibility cannot replace endpoint authorization.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|permissionId|string\(BigInteger\)|Not declared required|Omit for creation; provide a value to edit an existing configuration|

Response data: AssetsPermissionFormInitVO. See the corresponding model in [models.md](models.md).

- For creation, id/name/description and the system-role selection are empty; a nonexistent editing permissionId is an error.

- roleOptionList comes from SystemRoleService.listRoleOptional and binds SystemRole IDs, excluding the role whose name is the protected super-administrator literal (Unicode U+8D85 U+7BA1). It is independent of the organization Role model.

- folderTree has a fixed Root(0) and contains only real team-space folders; it is not filtered by the administrator's resource visibility.

- permissionMode, explicitRule, effective*, and inheritedFolder* distinguish explicit rules from inheritance from the nearest ancestor.

- presetOptionList excludes INHERIT; name is an enum name, not localized display text.

- departmentTree contains the complete department tree; selectedDepartmentList includes full paths of selected departments.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 403|user\.has\.no\.permission|Current user lacks system permission 131000; this aspect throws BizException, resulting in HTTP 400|
|400 / 400|biz\.error|Permission configuration ID does not exist; message uses the data.not.exist localization, while errorKey remains biz.error|

<a id="acl-create"></a>

## `acl_create` — Create a resource ACL configuration

POST /typekey/api/v1/assets/savePermission

Purpose: Associate team-folder rules with system roles and/or departments; immediately invalidate the permission-scope cache after creation

Scope: Used directly by Admin asset-ace when submitting a new configuration

Authorization: System permission 131000 / system.admin.assets.permission.management. Administrative ACL endpoints enforce system permissions; the configuration tree is not filtered by the administrator's own resource ACL. Uses the global CredentialAuthenticationInterceptor; the system-permission aspect has bypass branches for STUDIO/OAUTH_CLIENT. Menu visibility cannot replace endpoint authorization.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|name|string|Yes|Permission name; NotBlank(message = "{required.parameter.error}")|
|body|description|string|Yes|Permission description; NotBlank(message = "{required.parameter.error}")|
|body|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role IDs; at least this list or the department ID list must be nonempty; both may be provided|
|body|departmentIdList|string\(integer\)\[\]|Not declared required|Department IDs; at least this list or the system-role ID list must be nonempty; includes users in all subdepartments of the selected departments|
|body|ruleList|AssetsPermissionRuleVO\[\]|Not declared required|Folder permission rule list|

Request body model: AssetsPermissionSaveVO; see [models.md](models.md) for all nested fields.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- name and description are required with @NotBlank; no @Size upper bound is declared. Do not invent length limits.

- At least one of systemRoleIdList and departmentIdList must be nonempty; both may be associated. Department associations cover the department and its subdepartments' users.

- ruleList may be omitted/empty. There is no cascading @Valid; buildList skips empty entries and entries missing folderId/presetType. INHERIT rules are not stored; the last entry wins for duplicate folderId values.

- permissionIdList applies only to CUSTOM; parseIdSet ignores unknown/null action IDs. This endpoint does not individually validate existence of systemRoleIdList entries.

- Returns only true, without the new configuration ID; query the page by name to retrieve it.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1001|param\.parse\.failure|Invalid JSON or field deserialization failure|
|400 / 1002|param\.is\.invalid|Request-body Bean Validation failure|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 403|user\.has\.no\.permission|Current user lacks system permission 131000; this aspect throws BizException, resulting in HTTP 400|
|400 / 400|validation\.permission\.subject|systemRoleIdList and departmentIdList are both empty|
|400 / 400|validation\.departments|Null department ID element or nonexistent department|
|400 / 400|validation\.permissions\.team|Explicit rule target is not a TEAM-space folder|
|400 / 400|biz\.error|Duplicate configuration name; message uses the data.repeat localization|

<a id="acl-update"></a>

## `acl_update` — Update a resource ACL configuration

PUT /typekey/api/v1/assets/updatePermission

Purpose: Fully replace associated system roles, departments, and folder rules, including grants and revocations

Scope: Used directly by Admin asset-ace when submitting edits

Authorization: System permission 131000 / system.admin.assets.permission.management. Administrative ACL endpoints enforce system permissions; the configuration tree is not filtered by the administrator's own resource ACL. Uses the global CredentialAuthenticationInterceptor; the system-permission aspect has bypass branches for STUDIO/OAUTH_CLIENT. Menu visibility cannot replace endpoint authorization.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|id|string\(integer\)|Yes|Primary key; NotNull(message = "{required.parameter.error}")|
|body|name|string|Yes|Permission name; NotBlank(message = "{required.parameter.error}")|
|body|description|string|Yes|Permission description; NotBlank(message = "{required.parameter.error}")|
|body|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role IDs; at least this list or the department ID list must be nonempty; both may be provided|
|body|departmentIdList|string\(integer\)\[\]|Not declared required|Department IDs; at least this list or the system-role ID list must be nonempty; includes users in all subdepartments of the selected departments|
|body|ruleList|AssetsPermissionRuleVO\[\]|Not declared required|Folder permission rule list|

Request body model: AssetsPermissionUpdateVO; see [models.md](models.md) for all nested fields.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- id, name, and description are required; this is not PATCH.

- Deletes old role/department/rule associations and writes the new collections. Omitted or empty collections clear that group, but at least one role or department must remain overall.

- To revoke an explicit folder grant, remove its rule from the complete ruleList or use INHERIT; both restore parent inheritance. NONE stores explicit empty actions and blocks inheritance only within that configuration branch; union grants from other configurations or shares may still apply.

- Cannot update status through this endpoint; the DTO has no status field.

- No version field or client optimistic-lock parameter is available.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1001|param\.parse\.failure|Invalid JSON or field deserialization failure|
|400 / 1002|param\.is\.invalid|Request-body Bean Validation failure|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 403|user\.has\.no\.permission|Current user lacks system permission 131000; this aspect throws BizException, resulting in HTTP 400|
|400 / 400|validation\.permission\.subject|systemRoleIdList and departmentIdList are both empty|
|400 / 400|validation\.departments|Null department ID element or nonexistent department|
|400 / 400|validation\.permissions\.team|Explicit rule target is not a TEAM-space folder|
|400 / 400|biz\.error|Duplicate configuration name; message uses the data.repeat localization|
|400 / 400|biz\.error|Permission configuration ID does not exist; message uses the data.not.exist localization, while errorKey remains biz.error|

Skill overwrite protection: Explicitly provide `systemRoleIdList`, `departmentIdList`, and `ruleList`; read current state, merge changes, then submit complete values. This is client protection, not an additional server requirement.

<a id="acl-delete"></a>

## `acl_delete` — Delete a resource ACL configuration

DELETE /typekey/api/v1/assets/deletePermission/\{id\}

Purpose: Delete the configuration and all role, department, and rule associations, and clear the permission cache

Scope: Used directly by Admin asset-ace row deletion and edit-drawer deletion

Authorization: System permission 131000 / system.admin.assets.permission.management. Administrative ACL endpoints enforce system permissions; the configuration tree is not filtered by the administrator's own resource ACL. Uses the global CredentialAuthenticationInterceptor; the system-permission aspect has bypass branches for STUDIO/OAUTH_CLIENT. Menu visibility cannot replace endpoint authorization.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|path|id|string\(BigInteger\)|Yes|Permission configuration ID|

Response data: Boolean. See the corresponding model in [models.md](models.md).

- No batch-delete endpoint; does not delete the actual files, folders, users, or roles.

- Removing this configuration does not guarantee loss of effective resource access; check other ACL configurations, personal ownership, and direct shares.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 403|user\.has\.no\.permission|Current user lacks system permission 131000; this aspect throws BizException, resulting in HTTP 400|
|400 / 400|biz\.error|Permission configuration ID does not exist; message uses the data.not.exist localization, while errorKey remains biz.error|

<a id="acl-detail"></a>

## `acl_detail` — Read resource ACL configuration details

GET /typekey/api/v1/assets/permission/\{id\}

Purpose: Return details and valid role/department/team-rule associations by configuration ID

Scope: Exposed by useAssetAceRequest; the current Admin page loads details through form/init instead of calling this directly

Authorization: System permission 131000 / system.admin.assets.permission.management. Administrative ACL endpoints enforce system permissions; the configuration tree is not filtered by the administrator's own resource ACL. Uses the global CredentialAuthenticationInterceptor; the system-permission aspect has bypass branches for STUDIO/OAUTH_CLIENT. Menu visibility cannot replace endpoint authorization.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|path|id|string\(BigInteger\)|Yes|Permission configuration ID|

Response data: AssetsPermissionVO. See the corresponding model in [models.md](models.md).

- Returns status, but no corresponding public status-update endpoint exists.

- Deleted system-role associations are not returned; historical non-TEAM folder rules are filtered on read.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 403|user\.has\.no\.permission|Current user lacks system permission 131000; this aspect throws BizException, resulting in HTTP 400|
|400 / 400|biz\.error|Permission configuration ID does not exist; message uses the data.not.exist localization, while errorKey remains biz.error|

<a id="effective-permissions"></a>

## `effective_permissions` — Read the current user's effective asset permissions

GET /typekey/api/v1/assets/access/permission

Purpose: Resolve and validate the current user's final file/folder actions and return navigation from Root to the target

Scope: Exposed by the Admin hook but not called by this Admin page; used by employee-side use-permission-request

Authorization: @IgnoreCheckSystemPermission skips system-menu permission checks but still requires global authentication and resource visibility/space-boundary checks

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|targetType|FILE\|FOLDER|Not declared required|Required when path is empty and targetId is nonempty|
|query|targetId|string\(BigInteger\)|Not declared required|Defaults to Root(0) when omitted; FILE must reference an existing file|
|query|path|string|Not declared required|When nonempty, takes precedence over targetType/targetId; Root-relative path, with a final segment containing an extension interpreted as a file|
|query|fileCursor|string\(BigInteger\)|Not declared required|Last file ID from the previous batch, >= 0|
|query|fileSize|integer|Not declared required|File-permission node batch size; 1..1000; 30|

Response data: AssetsTargetPermissionVO. See the corresponding model in [models.md](models.md).

- Not a simple true/false check: missing open access throws 2005. The response root usually starts a navigation chain from Root to the target; data itself is not necessarily the target.

- The final folder level includes directly viewable file-permission children and filePage; fileCursor applies only to the target folder's file batch.

- childFolderPermissionList contains displayable direct child folders; pathShell is a passage to visible descendants, not permission for all actions.

- Folder permissions inherit from the nearest explicit rule in each ACL configuration; actions across configurations are unioned, then combined with direct user/department grants. Direct file shares apply only to that file node.

- Validation must use the target user's own credentials, not administrator credentials on their behalf; no userId parameter exists.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 2005|user\.is\.not\.assets\.permission|Target cannot be opened; see I18nConstant/Result source for the actual key|
|400 / 400|validation\.range|fileSize out of range|
|400 / 400|validation\.nonnegative|Negative fileCursor|
|400 / 400|validation\.target\.type|targetId provided without a specified or applicable targetType|
|400 / 400|validation\.path\.empty\.segment|path is empty after normalization or contains invalid segments|
|400 / 400|biz\.error|File/folder for the path or ID does not exist; message assets.file.deleted|
