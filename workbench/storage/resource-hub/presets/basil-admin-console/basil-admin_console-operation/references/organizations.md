# organizations

Use `scripts/admin_console/cli.py`; see [protocol.md](protocol.md) for shared input/output rules. Locate the required contract by operation; other capabilities need not be read.

- [organization_page](#organization-page): Query associated organization spaces (hook helper)
- [organization_join](#organization-join): Add a user to organization spaces (hook helper)
- [organization_leave](#organization-leave): Remove organization-space membership (hook helper)

<a id="organization-page"></a>

## `organization_page` — Query associated organization spaces (hook helper)

GET /typekey/api/v1/system/organization/page

Scope: Organization-space helper retained in the request hook

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|keyword|string|Not declared required|Fuzzy organization-name search|
|query|userId|string(integer)|Not declared required|Filter by the user's existing organization associations|
|query|page|integer|Not declared required|Page starts at 1; omitting page or size queries all results|
|query|size|integer|Not declared required|Per-page maximum 1000; omitting page or size queries all results|

Response data: OrganizationVO[]. See the corresponding model in [models.md](models.md).

- useSystemUserRequest exports getPageOrganization, but the current User page does not consume it.

- This is organization-space membership, not system roles; optional userId restricts results to that user's organizations.

Failures: Common authentication, parameter, and technical errors apply; no additional stable business-error keys are declared for this endpoint.

<a id="organization-join"></a>

## `organization_join` — Add a user to organization spaces (hook helper)

POST /typekey/api/v1/system/joinOrganizationList

Scope: Organization-space helper retained in the request hook

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|userId|string\(integer\)|Yes|VO has @NotNull, but the controller parameter has no @Valid, so HTTP Bean Validation is not guaranteed; required by business semantics; NotNull(message = "{required.parameter.error}")|
|body|tenantIdList|string\(integer\)\[\]|Yes|VO has @NotEmpty, but the controller has no @Valid; pass a nonempty array of real organization IDs; NotEmpty(message = "{required.parameter.error}"); Valid|

Request body model: JoinOrganizationVO; see [models.md](models.md) for all nested fields.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Appends user-organization associations in bulk and assigns the default tenant role MEMBER in each organization.

- Not a system-role grant endpoint; unused by the current User page. Acting on a platform administrator requires the current user to be that platform administrator.

- No explicit duplicate-association protection; assumes each organization has a default role. Repeated requests may add associations; idempotent full replacement is not guaranteed.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|A regular administrator is rejected when acting on the platform administrator|

<a id="organization-leave"></a>

## `organization_leave` — Remove organization-space membership (hook helper)

DELETE /typekey/api/v1/system/deleteOrganizationMember

Scope: Organization-space helper retained in the request hook

Authorization: System permission 134000 / system.admin.user; page route permission ADMIN_USER_PAGE. Backend CheckSystemPermission checks effective system permissions; arbitrary tenant roles cannot replace system roles.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|userId|string(integer)|Yes|Target user ID|
|query|tenantId|string(integer)|Yes|Target organization ID|

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Succeeds immediately if membership does not exist; otherwise removes organization membership and associated tenant roles.

- Acting on the platform administrator requires the current user to be that administrator; unused by the current User page.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|400 / 400|biz\.error|A regular administrator is rejected when acting on the platform administrator|
