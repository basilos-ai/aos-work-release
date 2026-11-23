# sharing

For replacement writes, subject changes, or access revocation, preserve current state and check the impact scope using [workflows.md](workflows.md).

Use `scripts/admin_console/cli.py`; see [protocol.md](protocol.md) for shared input/output rules. Locate the required contract by operation; other capabilities need not be read.

- [share_page](#share-page): List direct resource grants
- [share_candidates](#share-candidates): Query eligible users/departments for direct sharing
- [share_create](#share-create): Grant direct sharing to a user/department
- [share_update](#share-update): Update direct sharing for a user/department
- [share_delete](#share-delete): Revoke direct sharing from a user/department

## Share-subject and permission selection

Follow [interaction.md](interaction.md). Read eligible candidates from the target resource's `share_candidates` and display users and departments separately. Do not combine them into one subject list or add excluded subjects from general user/department lists. Pagination limits and total cover both types together, with users before departments; no departments on page one does not mean none are available. Continue pagination or explicitly narrow the search scope.

Each share selects exactly one user or one department. Use two single-select fields with an exactly-one check, or host-supported conditional fields by subject type. If the user has specified a type, show only that type. Unlike ACLs, a single grant cannot bind both. If the user explicitly requests multiple subjects, create a separate grant per subject and report each result.

Offer only View VIEW, Download DOWNLOAD, Upload UPLOAD, and Edit EDIT, not other shared-enum presets. Map explicit permission requests directly. For updates, read the existing grant, subject, and version from `share_page`; collect only unresolved permission changes, without asking users to reselect subjects or enter versions.

<a id="share-page"></a>

## `share_page` — List direct resource grants

GET /typekey/api/v1/assets/share/page

Purpose: Manage direct shares granted to specific users or departments on a target file/folder

Scope: Resource sharing panel, not the Admin ACL configuration role list

Authorization: System permission 111000 / system.assets.management; checkTargetManagePermission requires all standard MANAGE actions (1..10) on the target. System-menu permission 111000 alone is insufficient.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|sortField|string|Not declared required|Sort field|
|query|sortDirection|SortDirectionEnum|Not declared required|Sort direction|
|query|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|query|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|
|query|targetType|AssetsType|Yes|Target type; NotNull|
|query|targetId|string\(integer\)|Yes|Target ID; folder 0 means Root; NotNull|

Response data: List\<AssetsShareVO\>. See the corresponding model in [models.md](models.md).

- targetType/targetId/page/size are required; targetId=0 is valid only for FOLDER Root; ordered by grantId ascending.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 400|biz\.error|Target missing/unshareable or current user lacks all standard MANAGE actions; message from assets.share.target.invalid/assets.share.manage.required; default errorKey remains biz.error|

<a id="share-candidates"></a>

## `share_candidates` — Query eligible users/departments for direct sharing

GET /typekey/api/v1/assets/share/user/page

Purpose: Unified pagination of subject candidates for new grants

Scope: Resource sharing panel, not Admin ACL role candidates

Authorization: System permission 111000 / system.assets.management; checkTargetManagePermission requires all standard MANAGE actions (1..10) on the target. System-menu permission 111000 alone is insufficient.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|sortField|string|Not declared required|Sort field|
|query|sortDirection|SortDirectionEnum|Not declared required|Sort direction|
|query|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|query|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|
|query|targetType|AssetsType|Yes|Target type; NotNull|
|query|targetId|string\(integer\)|Yes|Target ID; folder 0 means Root; NotNull|
|query|keyword|string|Not declared required|Username, nickname, or department-name keyword; case-insensitive and trimmed; blank disables filtering|

Response data: AssetsShareCandidateVO. See the corresponding model in [models.md](models.md).

- page starts at 1; 0 is equivalent to the first page. size 1..1000 caps both types combined; addition.total is also combined. Users precede departments, each ordered by ID ascending.

- Excludes yourself, disabled users, and users/departments already directly granted access on the target; keyword is case-insensitive and trimmed.

- AssetsShareCandidateVO.DepartmentVO defines nested department fields; the response exposes only the dedicated user VO.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 400|biz\.error|Target missing/unshareable or current user lacks all standard MANAGE actions; message from assets.share.target.invalid/assets.share.manage.required; default errorKey remains biz.error|

<a id="share-create"></a>

## `share_create` — Grant direct sharing to a user/department

POST /typekey/api/v1/assets/share

Purpose: Direct sharing for a specified subject on a target, not SystemRole ACL configuration

Scope: Resource sharing panel, not the Admin ACL configuration page

Authorization: System permission 111000 / system.assets.management; checkTargetManagePermission requires all standard MANAGE actions (1..10) on the target. System-menu permission 111000 alone is insufficient.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|targetType|AssetsType|Yes|Target type; NotNull|
|body|targetId|string\(integer\)|Yes|Target ID; NotNull|
|body|userId|string\(integer\)|Not declared required|Grantee user ID; 0 is the initialization user|
|body|departmentId|string\(integer\)|Not declared required|Grantee department ID; exactly one of this and user ID is required|
|body|presetType|AssetsPermissionPresetTypeEnum|Yes|Permission preset; NotNull|

Request body model: AssetsShareSaveVO; see [models.md](models.md) for all nested fields.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Requires all standard MANAGE actions on the target; personal-space roots, user containers, and UNKNOWN targets cannot be shared.

- Direct-share presets allow only VIEW/DOWNLOAD/UPLOAD/EDIT, not MANAGE/SYNC/CUSTOM/NONE/INHERIT.

- Exactly one of userId and departmentId is required. The target user must exist and be enabled and cannot be yourself; the department must exist.

- Deleting a direct share does not guarantee loss of effective access; resource ACLs, other user/department shares, and ownership may still grant permissions.

- The write transaction includes audit logs; permission-cache invalidation runs after commit.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1001|param\.parse\.failure|Invalid JSON or field deserialization failure|
|400 / 1002|param\.is\.invalid|Request-body Bean Validation failure|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 400|biz\.error|Target missing/unshareable, insufficient target management permissions, duplicate direct share, disabled/self user, or unsupported preset; message from assets.share.*; AssertUtils errorKey remains biz.error|
|400 / 400|validation\.subject\.exclusive|Exactly one of userId and departmentId is required|

<a id="share-update"></a>

## `share_update` — Update direct sharing for a user/department

PUT /typekey/api/v1/assets/share

Purpose: Direct sharing for a specified subject on a target, not SystemRole ACL configuration

Scope: Resource sharing panel, not the Admin ACL configuration page

Authorization: System permission 111000 / system.assets.management; checkTargetManagePermission requires all standard MANAGE actions (1..10) on the target. System-menu permission 111000 alone is insufficient.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|targetType|AssetsType|Yes|Target type; NotNull|
|body|targetId|string\(integer\)|Yes|Target ID; NotNull|
|body|userId|string\(integer\)|Not declared required|Grantee user ID; 0 is the initialization user|
|body|departmentId|string\(integer\)|Not declared required|Grantee department ID; exactly one of this and user ID is required|
|body|presetType|AssetsPermissionPresetTypeEnum|Yes|Permission preset; NotNull|
|body|grantId|string\(integer\)|Yes|Grant ID; NotNull|
|body|version|integer|Yes|Grant version; NotNull|

Request body model: AssetsShareUpdateVO; see [models.md](models.md) for all nested fields.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Requires all standard MANAGE actions on the target; personal-space roots, user containers, and UNKNOWN targets cannot be shared.

- Direct-share presets allow only VIEW/DOWNLOAD/UPLOAD/EDIT, not MANAGE/SYNC/CUSTOM/NONE/INHERIT.

- Exactly one of userId and departmentId is required. The target user must exist and be enabled and cannot be yourself; the department must exist.

- update requires grantId/version and inherited targetType/targetId/presetType/subject fields; the grant's subject cannot be changed.

- Deleting a direct share does not guarantee loss of effective access; resource ACLs, other user/department shares, and ownership may still grant permissions.

- The write transaction includes audit logs; permission-cache invalidation runs after commit.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1001|param\.parse\.failure|Invalid JSON or field deserialization failure|
|400 / 1002|param\.is\.invalid|Request-body Bean Validation failure|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 400|biz\.error|Target missing/unshareable, insufficient target management permissions, duplicate direct share, disabled/self user, or unsupported preset; message from assets.share.*; AssertUtils errorKey remains biz.error|
|400 / 400|validation\.subject\.exclusive|Exactly one of userId and departmentId is required|
|400 / 4001|version\.conflict|Grant version mismatch or concurrent update|

<a id="share-delete"></a>

## `share_delete` — Revoke direct sharing from a user/department

DELETE /typekey/api/v1/assets/share

Purpose: Direct sharing for a specified subject on a target, not SystemRole ACL configuration

Scope: Resource sharing panel, not the Admin ACL configuration page

Authorization: System permission 111000 / system.assets.management; checkTargetManagePermission requires all standard MANAGE actions (1..10) on the target. System-menu permission 111000 alone is insufficient.

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|body|targetType|AssetsType|Yes|Target type; NotNull|
|body|targetId|string\(integer\)|Yes|Target ID; NotNull|
|body|grantId|string\(integer\)|Yes|Grant ID; NotNull|
|body|version|integer|Yes|Grant version; NotNull|

Request body model: AssetsShareDeleteVO; see [models.md](models.md) for all nested fields.

Response data: Boolean. See the corresponding model in [models.md](models.md).

- Requires all standard MANAGE actions on the target; personal-space roots, user containers, and UNKNOWN targets cannot be shared.

- delete takes grantId/version in JSON body; they must match the resource target and existing version.

- Deleting a direct share does not guarantee loss of effective access; resource ACLs, other user/department shares, and ownership may still grant permissions.

- The write transaction includes audit logs; permission-cache invalidation runs after commit.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1001|param\.parse\.failure|Invalid JSON or field deserialization failure|
|400 / 1002|param\.is\.invalid|Request-body Bean Validation failure|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 400|biz\.error|Target missing/unshareable or insufficient target management permission; grantId belongs to another target or no longer exists. message from assets.share.*; AssertUtils default errorKey remains biz.error.|
|400 / 4001|version\.conflict|Grant version mismatch or concurrent update|
