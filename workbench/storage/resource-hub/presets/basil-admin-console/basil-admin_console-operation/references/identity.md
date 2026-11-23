# identity

Use `scripts/admin_console/cli.py`; see [protocol.md](protocol.md) for shared input/output rules. Locate the required contract by operation; other capabilities need not be read.

- [legacy_user_page](#legacy-user-page): Legacy administrative user pagination
- [current_user](#current-user): Read the current logged-in user
- [authenticated_user](#authenticated-user): Read the current user with Shiro authentication required
- [anonymous_user](#anonymous-user): Read the current user with anonymous compatibility
- [system_permissions](#system-permissions): Read current-user system permission IDs
- [organization_permissions](#organization-permissions): Read current organization permission IDs
- [profile_update](#profile-update): Update the current user's nickname
- [password_update](#password-update): Change the current user's password
- [icon_upload](#icon-upload): Upload a personal database icon (general upload helper)

<a id="legacy-user-page"></a>

## `legacy_user_page` — Legacy administrative user pagination

GET /typekey/api/v1/admin/user/page

Scope: Same-domain helper endpoint, not called by the current page

Authorization: Unified credentials; no additional system-menu permission on this method. Controller-level @RequiresRoles("ADMIN") checks legacy User.role ADMIN, not SYSTEM_ADMIN_USER(134000).

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|phoneNumber|string|Not declared required|Phone-number LIKE filter|
|query|page|integer|Yes|Page number|
|query|size|integer|Yes|Maximum 1000|

Response data: UserVO[]. See the corresponding model in [models.md](models.md).

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="current-user"></a>

## `current_user` — Read the current logged-in user

GET /typekey/api/v1/user/readCurrentUser

Scope: Current identity and permission helpers

Authorization: Unified credentials; no additional system-menu permission on this method. Returns the user represented by the credentials, not an arbitrary userId.

Parameters: No additional path/query/body fields.

Response data: UserVO. See the corresponding model in [models.md](models.md).

- Returns the user represented by the credentials, not an arbitrary userId.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="authenticated-user"></a>

## `authenticated_user` — Read the current user with Shiro authentication required

GET /typekey/api/v1/user/readAuthCurrentUser

Scope: Current identity and permission helpers

Authorization: Unified credentials; no additional system-menu permission on this method. Also requires @RequiresAuthentication; not equivalent to administrative user pagination.

Parameters: No additional path/query/body fields.

Response data: UserVO. See the corresponding model in [models.md](models.md).

- Also requires @RequiresAuthentication; not equivalent to administrative user pagination.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="anonymous-user"></a>

## `anonymous_user` — Read the current user with anonymous compatibility

GET /typekey/api/v1/user/readUnAuthCurrentUser

Scope: Current identity and permission helpers

Authorization: Anonymous-credential and license exemptions apply; response shape depends on whether the current identity can be recovered. See behavior notes.

Parameters: No additional path/query/body fields.

Response data: UserVO. See the corresponding model in [models.md](models.md).

- @AnonymousCredentialRoute/@LicenseExemptRoute; may return anonymous state and cannot replace protected user-management endpoints.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="system-permissions"></a>

## `system_permissions` — Read current-user system permission IDs

GET /typekey/api/v1/user/getSystemPermissionIdList

Scope: Current identity and permission helpers

Authorization: Unified credentials; no additional system-menu permission on this method. Common credential validation applies.

Parameters: No additional path/query/body fields.

Response data: string(integer)[]. See the corresponding model in [models.md](models.md).

- Permissions come from system roles; the super-administrator receives all permissions. STUDIO credentials explicitly receive an empty list.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="organization-permissions"></a>

## `organization_permissions` — Read current organization permission IDs

GET /typekey/api/v1/user/getPermissionIdList

Scope: Current identity and permission helpers

Authorization: Unified credentials; no additional system-menu permission on this method. Common credential validation applies.

Parameters: No additional path/query/body fields.

Response data: string(integer)[]. See the corresponding model in [models.md](models.md).

- Organization permissions differ from Admin system permissions and cannot replace getSystemPermissionIdList; STUDIO receives an empty list.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="profile-update"></a>

## `profile_update` — Update the current user's nickname

PUT /typekey/api/v1/user

Scope: Current identity and permission helpers

Authorization: Unified credentials; no additional system-menu permission on this method. Common credential validation applies.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|id|string\(integer\)|Not declared required|Ignored by the server; rejected by this Skill|
|body|username|string|Not declared required|Username|
|body|nickname|string|Not declared required|The only effective request field; current UserServiceImpl.updateUser calls only setNickname|
|body|departmentIdList|string\(integer\)\[\]|Not declared required|Department ID collection|
|body|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role ID collection|
|body|jobTitle|string|Not declared required|Job title|
|body|leaderId|string\(integer\)|Not declared required|Direct supervisor ID|
|body|email|string|Not declared required|Email|
|body|ssoUserId|string|Not declared required|ssoUserId|

Request body model: UserUpdateVO; see [models.md](models.md) for all nested fields.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Ignores request id, always reads the current user, and updates only nickname; cannot edit another user or assign departments/roles administratively.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

This Skill accepts only the effective `body.nickname` and rejects other fields ignored by the server.

<a id="password-update"></a>

## `password_update` — Change the current user's password

PUT /typekey/api/v1/user/updatePassword

Scope: Current identity and permission helpers

Authorization: Valid user Session or first-party user JWT only; CheckUserCredential rejects PERSON, STUDIO, and OAuth2 tokens. License validation still applies.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|oldPassword|string|Yes|Raw current password string, not a precomputed hash|
|query|newPassword|string|Yes|Raw new password; at least 8 characters, including uppercase/lowercase letters, digits, and special characters|

Response data: LoginResultVO. See the corresponding model in [models.md](models.md).

- Available only in SESSION or USER_JWT context. Passwords are query parameters; the server salts and hashes with PBKDF2WithHmacSHA256. Clients must not pre-apply MD5/AES.

- Changes the current user's password and increments token_version, then returns a new access token and HttpOnly Refresh Cookie; SESSION mode also binds the new session version.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|Incorrect old password (old.password.incorrect message)|
|400 / 400|biz\.error|Insufficient new-password strength (password.strength.insufficient message)|

This Connector does not expose this call: only Session or first-party USER_JWT is supported; its OAuth2/PERSON credentials are rejected. Change passwords in platform personal settings.

<a id="icon-upload"></a>

## `icon_upload` — Upload a personal database icon (general upload helper)

POST /typekey/api/v1/file/upload

Scope: General upload used by administrative pages

Authorization: Unified credentials; no additional system-menu permission on this method. Common credential validation applies.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|multipart|file|binary|Yes|Multipart file field; the UI accepts images <= 2 MiB|
|multipart|filename|string|Not declared required|Optional target filename; blank generates a random name while preserving the extension|

Response: Raw URL text, without a Response envelope or data field.

- FileController returns a String URL without a Response wrapper; this value supplies personalBase.icon.

- Image-type/2 MiB limits belong to the current UI; do not claim the general upload backend enforces only images/2 MiB. Global multipart configuration also applies.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

The CLI accepts top-level `file_path` for the local path and optional `filename` for the target name; the script constructs multipart. This endpoint is not declared in manifest actions because the Library action schema provides no multipart contract.
