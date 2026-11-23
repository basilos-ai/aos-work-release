# users

For replacement writes, subject changes, or access revocation, preserve current state and check the impact scope using [workflows.md](workflows.md).

Use `scripts/admin_console/cli.py`; see [protocol.md](protocol.md) for shared input/output rules. Locate the required contract by operation; other capabilities need not be read.

- [user_page](#user-page): List accounts with pagination
- [user_create](#user-create): Create an account
- [user_batch_create](#user-batch-create): Create accounts in bulk
- [user_update](#user-update): Update an account and its department/system-role associations
- [user_status](#user-status): Enable/disable an account
- [user_reset_password](#user-reset-password): Administratively reset a regular account's password
- [administrator_transfer](#administrator-transfer): Transfer the platform administrator role
- [user_sso_list](#user-sso-list): Read user SSO bindings
- [user_sso_unbind](#user-sso-unbind): Unbind a user's SSO identity

## Collecting user information

Follow [interaction.md](interaction.md); ask only for missing information that affects the operation. Use separate multi-selects for departments from `department_tree` and system roles from `system_role_options`. Resolve organization membership through `organization_page` only when needed; do not mix it with system roles. Resolve supervisors through user queries, distinguishing duplicate names with usernames or other details. User-level permissions have a separate multi-select limited to "Bulk read (114001)" and "Bulk set (114002)"; system-role permissions cannot substitute for them.

Read and merge all fields that user updates must preserve from the current user row; do not ask users to re-enter them because the script needs complete parameters. For creation, handle unspecified optional fields according to endpoint defaults and explain relevant results, without a questionnaire for every option. If bulk creation specifies non-root departments, use individual `user_create` calls that support that intent rather than offering department choices ignored by the bulk endpoint.

Map explicit enable/disable requests directly to ENABLE/DISABLE. Administrator successors must be real ENABLE accounts. For SSO unbinding, resolve ambiguity only among the target user's `user_sso_list` bindings; do not ask for bindingId.

<a id="user-page"></a>

## `user_page` — List accounts with pagination

GET /typekey/api/v1/system/user/page

Scope: Used directly by the current administrative page

Authorization: Unified credentials; no additional system-menu permission on this method. @IgnoreCheckSystemPermission applies; the old @CheckSystemPermission is commented out. Globally valid credentials are still required.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|keyword|string|Not declared required|Fuzzy nickname/username keyword|
|query|phoneNumber|string|Not declared required|Fuzzy phone-number search|
|query|nickname|string|Not declared required|Fuzzy nickname search|
|query|username|string|Not declared required|Fuzzy username search|
|query|departmentId|string(integer)|Not declared required|Direct-department filter, without descendant recursion. Omit for all; 0 queries only direct members of the root department.|
|query|page|integer|Yes|Page number; examples start at 1; frontend pageIndex+1; no @Min in source|
|query|size|integer|Yes|Records per page; @Max(1000), no @Min declared; <=1000|

Response data: UserVO[]. See the corresponding model in [models.md](models.md).

- The administrator user is prioritized using the dynamically configured ID; others are ordered by creation time descending.

- page/size are required query parameters; pagination total/page/size are in addition, not data.

- keyword combines nickname LIKE OR username LIKE, followed by additional filters. Compound conditions follow current SQL; no additional grouping semantics are guaranteed.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="user-create"></a>

## `user_create` — Create an account

POST /typekey/api/v1/system/saveUser

Scope: Used directly by the current administrative page

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|nickname|string|Yes|Bean @NotBlank; no backend @Size; UI trims and enforces 1..100; NotBlank(message = "{required.parameter.error}")|
|body|username|string|Yes|Bean @NotBlank; business maximum 100 characters; disallows path-reserved characters (backslash, slash, colon, asterisk, question mark, double quote, angle brackets, vertical bar) and duplicate usernames; NotBlank(message = "{required.parameter.error}")|
|body|departmentIdList|string\(integer\)\[\]|Not declared required|Optional; null/[] defaults to root department 0; deduplicated; department existence is not explicitly checked here|
|body|systemRoleIdList|string\(integer\)\[\]|Not declared required|Optional; null/[] or all-null defaults to system role 0; filters nulls and deduplicates; effective roles must exist|
|body|userPermissionIdList|string\(integer\)\[\]|Not declared required|Optional; omitted/null saves []; elements must be 114001/114002, with null/invalid elements rejected; valid entries are deduplicated|
|body|jobTitle|string|Not declared required|Optional string; no explicit length validation|
|body|leaderId|string\(integer\)|Not declared required|Optional BigInteger; no explicit existence check in this endpoint|
|body|email|string|Not declared required|Optional; nonempty values require regex-valid email and length <=320|
|body|tenantIdList|string\(integer\)\[\]|Not declared required|Optional; always adds shared organization 0, then appends requested organizations with deduplication; organization-space membership, not system roles|
|body|personalAssets|UserPersonalAssetsConfigVO|Not declared required|Optional; created by default even when omitted; if provided, enabled must be true; Valid|
|body|personalBase|UserPersonalBaseConfigVO|Not declared required|Optional; omission does not create it; if provided, enabled=true and name@NotBlank. At creation, request tenant-id must be an organization containing this user; Valid|

Request body model: UserSaveVO; see [models.md](models.md) for all nested fields.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- No password/phoneNumber input fields; the server sets the password using its built-in initial policy, with status ENABLE, registration USERNAME, and asset mode PRO.

- Success returns data=true without a new user ID or initial password; query user pagination by username to retrieve the ID.

- User, department/system-role associations, and personal asset space are created in one business transaction.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|Duplicate username, illegal path characters, excessive length, invalid email, nonexistent system-role/user-level permission ID, or rejected personal-resource state|

<a id="user-batch-create"></a>

## `user_batch_create` — Create accounts in bulk

POST /typekey/api/v1/system/batchSaveUser

Scope: Same-domain helper endpoint, not called by the current page

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|nickname|string|Yes|Nickname; NotBlank(message = "{required.parameter.error}")|
|body|username|string|Yes|Username; NotBlank(message = "{required.parameter.error}")|
|body|departmentIdList|string\(integer\)\[\]|Not declared required|Department ID collection|
|body|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role ID collection|
|body|userPermissionIdList|string\(integer\)\[\]|Not declared required|User-level permission IDs; only 114001 (bulk read) and 114002 (bulk set)|
|body|jobTitle|string|Not declared required|Job title|
|body|leaderId|string\(integer\)|Not declared required|Direct supervisor ID|
|body|email|string|Not declared required|Email|
|body|tenantIdList|string\(integer\)\[\]|Not declared required|Space ID collection|
|body|personalAssets|UserPersonalAssetsConfigVO|Not declared required|Personal asset-space configuration; created by default when omitted; Valid|
|body|personalBase|UserPersonalBaseConfigVO|Not declared required|Personal multidimensional-table database configuration; omitted means no creation; Valid|

Request body model: UserSaveVO[]; see [models.md](models.md) for nested fields. The top-level body is an array.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- The hook exports batchCreateUser, but the current User page does not call it.

- All users join root department 0; this bulk endpoint does not use each user's departmentIdList. Personal-resource configuration applies per user.

- Do not submit an empty list: the current helper returns null for it and the later stream fails. No maximum batch size is declared.

- Rejects duplicate usernames within the array or database; validates role existence and user-level permissions.

- Unlike single creation, the bulk endpoint does not first call per-user checkEmail/checkUserName; format constraints differ.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|Duplicate usernames in the array or existing username|
|400 / 400|biz\.error|Invalid system-role or user-level permission ID|

<a id="user-update"></a>

## `user_update` — Update an account and its department/system-role associations

PUT /typekey/api/v1/system/updateUser

Scope: Used directly by the current administrative page

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|id|string\(integer\)|Not declared required|Target user is required by business semantics; VO lacks @NotNull, but callers must provide a valid ID rather than assume omission is safe|
|body|username|string|Not declared required|null preserves the original; nonempty values use creation validation. Blank checks may be skipped and blank values written; external callers must supply valid usernames.|
|body|nickname|string|Not declared required|Missing/null writes null; UI enforces 1..100|
|body|departmentIdList|string\(integer\)\[\]|Not declared required|Each update deletes old associations; missing/null/[] returns to root department 0; nonempty values fully replace with deduplication|
|body|systemRoleIdList|string\(integer\)\[\]|Not declared required|Only nonempty arrays trigger full replacement; omitted/null/[] preserves old roles. This endpoint does not reuse creation's role-existence validation.|
|body|jobTitle|string|Not declared required|Missing/null writes null|
|body|leaderId|string\(integer\)|Not declared required|Missing/null writes null|
|body|email|string|Not declared required|Missing/null writes null; nonempty values must be valid email <=320 characters|
|body|ssoUserId|string|Not declared required|Writes and checks duplicates only for nonblank values; legacy field, not independent SSO-binding management|
|body|userPermissionIdList|string\(integer\)\[\]|Not declared required|Omitted/null preserves; [] clears; nonempty validates 114001/114002 then replaces|
|body|personalAssets|UserPersonalAssetsConfigVO|Not declared required|Omission still creates personal space automatically for users without it; Valid|
|body|personalBase|UserPersonalBaseConfigVO|Not declared required|Omission does not enable it; already enabled resources are not recreated; false cannot disable it; Valid|

Request body model: SystemUserUpdateVO extends UserUpdateVO; see [models.md](models.md) for all nested fields.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Not a general PATCH. Missing nickname, job title, supervisor, or email becomes null; preserve required current values when calling.

- A regular administrator cannot act on the platform administrator; the platform administrator may act on themselves.

- Success returns data=true.

- The request example preserves complete editable information; for existing users, replace job title, supervisor, department, role, and user-level permission arrays with the actual current values to retain.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|Unauthorized platform-administrator operation, duplicate username/legacy SSO ID, invalid email/username/user-level permissions, or nonexistent target user|

Skill overwrite protection: Explicitly provide `nickname`, `username`, `departmentIdList`, `systemRoleIdList`, `jobTitle`, `leaderId`, and `email`; read current state, merge changes, then submit complete values. This is client protection, not an additional server requirement.

<a id="user-status"></a>

## `user_status` — Enable/disable an account

PUT /typekey/api/v1/system/updateStatus

Scope: Used directly by the current administrative page

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|userId|string(integer)|Yes|Target account ID|
|query|userStatus|enum|Yes|ENABLE or DISABLE; ENABLE; DISABLE|

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Parameters are in query; no request body.

- DISABLE increments token_version, invalidating existing sessions/JWTs on subsequent validation.

- Acting on the platform administrator requires the current user to be that administrator.

- The current implementation does not check affected-row count; an unknown regular user ID may still return data=true.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|Unauthorized operation on the platform administrator|

<a id="user-reset-password"></a>

## `user_reset_password` — Administratively reset a regular account's password

PUT /typekey/api/v1/system/resetPassword

Scope: Used directly by the current administrative page

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|userId|string(integer)|Yes|Target account ID; platform administrator accounts cannot be reset|

Response data: UserResetPasswordResultVO. See the corresponding model in [models.md](models.md).

- Parameters are in query. Generates a random 10-character plaintext password as resetPassword; the frontend displays/copies it only in the result dialog.

- Server stores a salted PBKDF2WithHmacSHA256 hash and increments token_version.

- Platform administrator accounts are always rejected, even when requested by that administrator.

- Does not accept a custom new password.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|Target user does not exist|
|400 / 400|biz\.error|Target is the platform administrator, or platform-administrator configuration is missing/invalid|

<a id="administrator-transfer"></a>

## `administrator_transfer` — Transfer the platform administrator role

PUT /typekey/api/v1/system/updateSystemAdministrator

Scope: Used directly by the current administrative page

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|userId|string(integer)|Yes|Successor account ID|

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Parameters are in query; first verifies the current user is the current platform administrator, then changes SYSTEM_ADMINISTRATOR_ID configuration.

- Not an ordinary role grant; the controller requires 134000 and the service additionally requires platform-administrator identity.

- Does not explicitly validate successor existence/enabled status; callers must select a real enabled account from user pagination.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|Current operator is not the platform administrator|

<a id="user-sso-list"></a>

## `user_sso_list` — Read user SSO bindings

GET /typekey/api/v1/system/user/\{userId\}/sso\-bindings

Scope: Used directly by the current administrative page

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|path|userId|string(integer)|Yes|User ID|

Response data: SsoUserBindingVO[]. See the corresponding model in [models.md](models.md).

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|User does not exist (sso.user.missing message)|

<a id="user-sso-unbind"></a>

## `user_sso_unbind` — Unbind a user's SSO identity

DELETE /typekey/api/v1/system/user/\{userId\}/sso\-bindings/\{bindingId\}

Scope: Used directly by the current administrative page

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|path|userId|string(integer)|Yes|Target user ID|
|path|bindingId|string(integer)|Yes|This user's SSO binding ID|

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Binding must exist, still be bound to an SSO system, and belong to the path userId.

- Locks the external identity for the same provider and checks identity mapping. Clears ssoSystemId while retaining historical identity mappings rather than hard-deleting all history rows.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|User missing, binding missing/not owned by user/already unbound, or ownership conflict for the same external identity|
