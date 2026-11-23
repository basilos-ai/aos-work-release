# Parameter and response models

Locate the model named by the selected capability. A field not declared required may still need its current value preserved for replacement writes.

## UserSaveVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|nickname|string|Yes|Nickname; NotBlank(message = "{required.parameter.error}")|
|username|string|Yes|Username; NotBlank(message = "{required.parameter.error}")|
|departmentIdList|string\(integer\)\[\]|Not declared required|Department ID collection|
|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role ID collection|
|userPermissionIdList|string\(integer\)\[\]|Not declared required|User-level permission IDs; only 114001 (bulk read) and 114002 (bulk set)|
|jobTitle|string|Not declared required|Job title|
|leaderId|string\(integer\)|Not declared required|Direct supervisor ID|
|email|string|Not declared required|Email|
|tenantIdList|string\(integer\)\[\]|Not declared required|Space ID collection|
|personalAssets|UserPersonalAssetsConfigVO|Not declared required|Personal asset-space configuration; created by default when omitted; Valid|
|personalBase|UserPersonalBaseConfigVO|Not declared required|Personal multidimensional-table database configuration; omitted means no creation; Valid|

## UserUpdateVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key|
|username|string|Not declared required|Username|
|nickname|string|Not declared required|User display name|
|departmentIdList|string\(integer\)\[\]|Not declared required|Department ID collection|
|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role ID collection|
|jobTitle|string|Not declared required|Job title|
|leaderId|string\(integer\)|Not declared required|Direct supervisor ID|
|email|string|Not declared required|Email|
|ssoUserId|string|Not declared required|ssoUserId|

## SystemUserUpdateVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key|
|username|string|Not declared required|Username|
|nickname|string|Not declared required|User display name|
|departmentIdList|string\(integer\)\[\]|Not declared required|Department ID collection|
|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role ID collection|
|jobTitle|string|Not declared required|Job title|
|leaderId|string\(integer\)|Not declared required|Direct supervisor ID|
|email|string|Not declared required|Email|
|ssoUserId|string|Not declared required|ssoUserId|
|userPermissionIdList|string\(integer\)\[\]|Not declared required|User-level permission IDs; omission preserves, an empty array clears, and a nonempty array fully replaces|
|personalAssets|UserPersonalAssetsConfigVO|Not declared required|Personal asset-space configuration; omission creates it by default if not yet enabled; Valid|
|personalBase|UserPersonalBaseConfigVO|Not declared required|Personal multidimensional-table database configuration; omitted means no creation; Valid|

## UserVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key|
|registerWay|RegisterWayEnum|Not declared required|Registration method|
|wxOpenId|string|Not declared required|WeChat OpenId|
|wxUnionId|string|Not declared required|WeChat UnionId|
|phoneNumber|string|Not declared required|Phone number|
|createdAt|string\(date\-time\)|Not declared required|Creation time|
|updatedAt|string\(date\-time\)|Not declared required|Edit time|
|role|UserRoleEnum|Not declared required|Role|
|ssoUserId|string|Not declared required|SSO user ID|
|nickname|string|Not declared required|User display name|
|lastLoginAt|string\(date\-time\)|Not declared required|Last login time|
|organizationRole|OrganizationRoleEnum|Not declared required|Organization role|
|username|string|Not declared required|Username|
|jobTitle|string|Not declared required|Job title|
|leaderId|string\(integer\)|Not declared required|Direct supervisor ID|
|status|UserStatusEnum|Not declared required|User status|
|systemAdministratorIs|boolean|Not declared required|Whether the user is a platform administrator|
|shouldUpdatePassword|boolean|Not declared required|Whether a password update is required|
|departmentList|Department\[\]|Not declared required|Department collection|
|systemRoleList|SystemRole\[\]|Not declared required|System-role collection|
|userPermissionIdList|string\(integer\)\[\]|Not declared required|User-level permission IDs; 114001 means bulk read and 114002 means bulk set|
|leader|User|Not declared required|Direct supervisor|
|email|string|Not declared required|Email|
|assetId|string\(integer\)|Not declared required|Personal asset-space root folder ID|
|baseId|string\(integer\)|Not declared required|Personal multidimensional-table database ID|
|personalAssets|UserPersonalAssetsVO|Not declared required|Personal asset-space response information|
|personalBase|UserPersonalBaseVO|Not declared required|Personal multidimensional-table database response information|

## DepartmentSaveVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|name|string|Yes|Department name; NotBlank(message = "{required.parameter.error}")|
|parentId|string\(integer\)|Yes|Parent department ID; NotNull(message = "{required.parameter.error}")|
|leaderId|string\(integer\)|Not declared required|Department leader ID|

## DepartmentUpdateVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Yes|Primary key; NotNull(message = "{required.parameter.error}")|
|name|string|Not declared required|Department name|
|parentId|string\(integer\)|Not declared required|Parent department ID|
|leaderId|string\(integer\)|Not declared required|Department leader ID|

## DepartmentVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key|
|name|string|Not declared required|Department name|
|parentId|string\(integer\)|Not declared required|Parent department ID|
|leaderId|string\(integer\)|Not declared required|Department leader ID|
|rankIndex|integer|Not declared required|Department sort value|
|createdAt|string\(date\-time\)|Not declared required|Creation time|
|updatedAt|string\(date\-time\)|Not declared required|Edit time|
|children|DepartmentVO\[\]|Not declared required|Subdepartment collection|
|userList|UserVO\[\]|Not declared required|User collection|

## UserDepartmentSaveVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|userId|string\(integer\)|Yes|User ID; NotNull(message = "{required.parameter.error}")|
|departmentId|string\(integer\)|Yes|Department ID; NotNull(message = "{required.parameter.error}")|

## UserDepartmentVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key|
|userId|string\(integer\)|Not declared required|User ID|
|departmentId|string\(integer\)|Not declared required|Department ID|
|createdAt|string\(date\-time\)|Not declared required|Creation time|
|updatedAt|string\(date\-time\)|Not declared required|Edit time|

## UserResetPasswordResultVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|username|string|Not declared required|Username|
|nickname|string|Not declared required|Full name|
|resetPassword|string|Not declared required|Random plaintext password after reset|

## UserPersonalAssetsConfigVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|enabled|boolean|Yes|Whether to enable personal asset space; only enabling is supported; NotNull(message = "{required.parameter.error}")|

## UserPersonalBaseConfigVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|enabled|boolean|Yes|Whether to enable a personal multidimensional-table database; only enabling is supported; NotNull(message = "{required.parameter.error}")|
|name|string|Yes|Personal multidimensional-table database name; NotBlank(message = "{required.parameter.error}")|
|description|string|Not declared required|Personal multidimensional-table database description|
|icon|string|Not declared required|Personal multidimensional-table database icon|

## UserPersonalAssetsVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|enabled|boolean|Not declared required|Whether personal asset space is enabled|
|assetId|string\(integer\)|Not declared required|Personal asset-space root folder ID|
|path|string|Not declared required|Fixed personal asset-space path|

## UserPersonalBaseVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|enabled|boolean|Not declared required|Whether a personal multidimensional-table database is enabled|
|baseId|string\(integer\)|Not declared required|Personal multidimensional-table database ID|
|name|string|Not declared required|Personal multidimensional-table database name|
|description|string|Not declared required|Personal multidimensional-table database description|
|icon|string|Not declared required|Personal multidimensional-table database icon|

## LoginResultVO

- Global BigNumberJsonConfiguration serializes Long expiresIn/refreshExpiresIn as strings; examples use strings.

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|user|UserVO|Not declared required|Logged-in user.|
|accessToken|string|Not declared required|User access JWT.|
|tokenType|string|Not declared required|Token type.|
|expiresIn|string\(integer\)|Not declared required|JWT lifetime in seconds.|
|refreshExpiresIn|string\(integer\)|Not declared required|Refresh Token lifetime in seconds.|
|deviceBindFolder|DeviceBindFolderVO|Not declared required|Personal-space folder used by device-binding login; empty for other login methods.|

## JoinOrganizationVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|userId|string\(integer\)|Yes|User ID; NotNull(message = "{required.parameter.error}")|
|tenantIdList|string\(integer\)\[\]|Yes|Space ID collection; NotEmpty(message = "{required.parameter.error}"); Valid|

## OrganizationVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key|
|name|string|Not declared required|Name|
|createdAt|string\(date\-time\)|Not declared required|Creation time|
|updatedAt|string\(date\-time\)|Not declared required|Edit time|
|defaultOrganizationIs|boolean|Not declared required|Whether this is the default organization|
|description|string|Not declared required|Description|
|engineStatistic|EngineStatisticVO|Not declared required|Statistics|
|owner|UserVO|Not declared required|Organization owner|

## SsoUserBindingVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Binding ID.|
|ssoSystemId|string\(integer\)|Not declared required|SSO configuration ID.|
|systemName|string|Not declared required|Configuration name.|
|provider|string|Not declared required|Identity-provider application code.|
|protocol|string|Not declared required|SSO protocol code.|
|createdAt|string\(date\-time\)|Not declared required|Binding time.|

## UserEntity

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key.|
|registerWay|RegisterWayEnum|Not declared required|Registration method.|
|wxOpenId|string|Not declared required|WeChat OpenId.|
|wxUnionId|string|Not declared required|WeChat UnionId.|
|phoneNumber|string|Not declared required|Phone number.|
|createdAt|string\(date\-time\)|Not declared required|Creation time.|
|updatedAt|string\(date\-time\)|Not declared required|Edit time.|
|role|UserRoleEnum|Not declared required|Role (currently unused).|
|ssoUserId|string|Not declared required|SSO user ID.|
|nickname|string|Not declared required|User display name.|
|lastLoginAt|string\(date\-time\)|Not declared required|Last login time.|
|username|string|Not declared required|Username.|
|password|string|Not declared required|Password.|
|status|UserStatusEnum|Not declared required|User status.|
|salt|string|Not declared required|Salt.|
|jobTitle|string|Not declared required|Job title.|
|leaderId|string\(integer\)|Not declared required|Direct supervisor ID.|
|email|string|Not declared required|Email.|
|assetId|string\(integer\)|Not declared required|Personal asset-space root folder ID.|
|baseId|string\(integer\)|Not declared required|Personal multidimensional-table database ID.|
|tokenVersion|string\(integer\)|Not declared required|User Session and access JWT version.|
|userPermissionIdListJson|string|Not declared required|JSON list of user-level permission IDs.|
|personalAssets|UserPersonalAssetsVO|Not declared required|Personal asset-space response information.|
|personalBase|UserPersonalBaseVO|Not declared required|Personal multidimensional-table database response information.|
|departmentIdList|string\(integer\)\[\]|Not declared required|Department ID collection.|
|organizationRole|OrganizationRoleEnum|Not declared required|Organization role.|
|systemAdministratorIs|boolean|Not declared required|Whether the user is a platform administrator.|
|shouldUpdatePassword|boolean|Not declared required|Whether a password reset is required.|
|departmentList|Department\[\]|Not declared required|Department collection.|
|systemRoleList|SystemRole\[\]|Not declared required|System-role collection.|
|leader|User|Not declared required|Direct supervisor.|
|userGroupList|UserGroup\[\]|Not declared required|User-group collection.|
|planType|AssetsPlanEnum|Not declared required|Asset mode.|
|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role ID collection.|
|userPermissionIdList|string\(integer\)\[\]|Not declared required|User-level permission ID collection.|

## DepartmentEntity

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key.|
|name|string|Not declared required|Department name.|
|parentId|string\(integer\)|Not declared required|Parent department ID.|
|leaderId|string\(integer\)|Not declared required|Department leader ID.|
|rankIndex|integer|Not declared required|Department sort value.|
|createdAt|string\(date\-time\)|Not declared required|Creation time.|
|updatedAt|string\(date\-time\)|Not declared required|Edit time.|
|children|Department\[\]|Not declared required|Subdepartment collection.|
|userList|User\[\]|Not declared required|User collection.|

## SystemRoleEntity

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key.|
|name|string|Not declared required|Name.|
|description|string|Not declared required|Remarks.|
|defaultIs|boolean|Not declared required|Whether this is the default role.|
|createdBy|string\(integer\)|Not declared required|Created by.|
|updatedBy|string\(integer\)|Not declared required|Modified by.|
|createdAt|string\(date\-time\)|Not declared required|Creation time.|
|updatedAt|string\(date\-time\)|Not declared required|Edit time.|
|permissionList|SystemRolePermission\[\]|Not declared required|Permission list.|
|permissionIdList|string\(integer\)\[\]|Not declared required|Permission ID list.|

## SystemRolePermissionEntity

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key.|
|roleId|string\(integer\)|Not declared required|Role ID.|
|permissionId|string\(integer\)|Not declared required|Permission ID.|
|permissionType|string|Not declared required|Permission type.|
|createdBy|string\(integer\)|Not declared required|Created by.|
|updatedBy|string\(integer\)|Not declared required|Updated by.|
|createdAt|string\(date\-time\)|Not declared required|Creation time.|
|updatedAt|string\(date\-time\)|Not declared required|Edit time.|

## SystemRoleSaveVO

- System-role name has no length-limit validation and is stored as TEXT; description uses unbounded VARCHAR.

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|name|string|NotBlank: Must not be null, empty, or whitespace-only|Name|
|description|string|NotBlank: Must not be null, empty, or whitespace-only|Remarks|
|permissionList|string\(integer\)\[\]|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Permission list|

## SystemRoleUpdateVO

- Although defaultIs, createdBy, and updatedBy are declared in the VO, SystemRoleServiceImpl.updateRole copies only id/name/description/permissionList; submitted values do not set defaults or audit users.

- Omitted/null/empty permissionList clears old permissions; this is not PATCH.

- System-role name has no length-limit validation and is stored as TEXT; description uses unbounded VARCHAR.

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|NotNull; must reference an existing system role|Primary key|
|name|string|NotBlank|Name|
|description|string|NotBlank|Remarks|
|permissionList|string\(integer\)\[\]|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Permission list|
|defaultIs|boolean|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Whether this is the default role|
|createdBy|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Created by|
|updatedBy|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Modified by|

## SystemRoleVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Primary key|
|name|string|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Name|
|description|string|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Remarks|
|defaultIs|boolean|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Whether this is the default role|
|createdBy|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Created by|
|updatedBy|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Modified by|
|createdAt|string\(date\-time\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Creation time|
|updatedAt|string\(date\-time\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Edit time|
|permissionIdList|string\(integer\)\[\]|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Permission ID list|

## SystemRoleOptionalVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Role ID|
|name|string|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Role name|

## RoleSaveVO

- Database tk_role.name is VARCHAR(20), description VARCHAR(500). Creation explicitly checks name length <= 20; updates and overlong descriptions have no dedicated business validation and may cause database exceptions.

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|name|string|NotBlank; saveRole additionally limits String.length <= 20|Name|
|description|string|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Remarks|
|permissionIdList|string\(integer\)\[\]|NotNull; may be an empty array, but underlying batch SQL behavior for empty arrays requires runtime verification|Permission ID collection|

## RoleUpdateVO

- Database tk_role.name is VARCHAR(20), description VARCHAR(500). Creation explicitly checks name length <= 20; updates and overlong descriptions have no dedicated business validation and may cause database exceptions.

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|NotNull; must reference an existing record, otherwise the current implementation encounters a null pointer|Primary key|
|name|string|NotBlank; update does not repeat the 20-character limit|Name|
|description|string|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Remarks|
|permissionIdList|string\(integer\)\[\]|NotNull; replaces the whole collection|Permission ID collection|

## RoleVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Primary key|
|name|string|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Name|
|organizationId|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Organization ID|
|createdAt|string\(date\-time\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Creation time|
|description|string|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Remarks|
|defaultIs|boolean|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Whether this is the default role|
|updatedAt|string\(date\-time\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Edit time|
|userNumber|integer|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Number of users with this permission|
|permissionIdList|string\(integer\)\[\]|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics|Permission ID collection|

## ChangeRoleVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|userId|string\(integer\)|NotNull; must not be the current user or organization owner|User ID|
|roleIdList|string\(integer\)\[\]|NotNull; service explicitly rejects empty arrays|Role ID collection|

## UserGroupEntity

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics||
|name|string|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics||
|createdAt|string\(date\-time\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics||
|updatedAt|string\(date\-time\)|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics||
|userIdList|string\(integer\)\[\]|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics||
|departmentIdList|string\(integer\)\[\]|No BeanValidation required constraint declared; see endpoint notes for defaults and update semantics||

## AssetsPermissionQueryVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|sortField|string|Not declared required|Sort field|
|sortDirection|SortDirectionEnum|Not declared required|Sort direction; nested model: SortDirectionEnum|
|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|
|keyword|string|Not declared required|Permission name keyword|

## CommonQueryVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|sortField|string|Not declared required|Sort field|
|sortDirection|SortDirectionEnum|Not declared required|Sort direction; nested model: SortDirectionEnum|
|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|

## SortDirectionEnum

Values used by this package are completed from the attachment's endpoint parameter descriptions; its model JSON excerpts are incomplete.

```json
[
  "ASC",
  "DESC"
]
```

## AssetsPermissionSaveVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|name|string|Yes|Permission name; NotBlank(message = "{required.parameter.error}")|
|description|string|Yes|Permission description; NotBlank(message = "{required.parameter.error}")|
|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role IDs; at least this list or the department ID list must be nonempty; both may be provided|
|departmentIdList|string\(integer\)\[\]|Not declared required|Department IDs; at least this list or the system-role ID list must be nonempty; includes users in all subdepartments of the selected departments|
|ruleList|AssetsPermissionRuleVO\[\]|Not declared required|Folder permission rule list; nested model: AssetsPermissionRuleVO|

## AssetsPermissionRuleVO

Note: Required annotations on rule items are not cascaded via @Valid in ACL save/update. Items missing folderId/presetType are currently skipped. Submit complete valid rules rather than relying on silent tolerance.

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|folderId|string\(integer\)|Yes|Folder ID; 0 means Root; NotNull(message = "{required.parameter.error}")|
|presetType|AssetsPermissionPresetTypeEnum|Yes|Permission preset type; NotNull(message = "{required.parameter.error}"); nested model: AssetsPermissionPresetTypeEnum|
|permissionIdList|string\(integer\)\[\]|Not declared required|Custom permission ID list; effective only for CUSTOM|

## AssetsPermissionPresetTypeEnum

```json
[
  "INHERIT",
  "NONE",
  "VIEW",
  "DOWNLOAD",
  "UPLOAD",
  "EDIT",
  "MANAGE",
  "SYNC",
  "CUSTOM"
]
```

## AssetsPermissionUpdateVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Yes|Primary key; NotNull(message = "{required.parameter.error}")|
|name|string|Yes|Permission name; NotBlank(message = "{required.parameter.error}")|
|description|string|Yes|Permission description; NotBlank(message = "{required.parameter.error}")|
|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role IDs; at least this list or the department ID list must be nonempty; both may be provided|
|departmentIdList|string\(integer\)\[\]|Not declared required|Department IDs; at least this list or the system-role ID list must be nonempty; includes users in all subdepartments of the selected departments|
|ruleList|AssetsPermissionRuleVO\[\]|Not declared required|Folder permission rule list; nested model: AssetsPermissionRuleVO|

## AssetsDirectoryChildrenQueryVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|spaceType|AssetsDirectorySpaceEnum|Yes|Space type: MY personal space, TEAM team space, SHARED shared entry; NotNull(message = "{required.parameter.error}"); nested model: AssetsDirectorySpaceEnum|
|entryRootId|string\(integer\)|Not declared required|Shared-folder entry ID; required for spaceType=SHARED|
|parentId|string\(integer\)|Not declared required|Parent folder ID; empty uses the current space's hidden root|
|includeFiles|boolean|Not declared required|Whether to also query files in the current folder; false|
|folderCursor|string\(integer\)|Not declared required|Last folder ID from the previous batch|
|fileCursor|string\(integer\)|Not declared required|Last file ID from the previous batch|
|folderSize|integer|Not declared required|Folder batch size, 1..100; 50; Min(value = 1, message = "{validation.min}"); Max(value = 100, message = "{validation.max}")|
|fileSize|integer|Not declared required|File batch size, 1..100; 50; Min(value = 1, message = "{validation.min}"); Max(value = 100, message = "{validation.max}")|

## AssetsDirectorySpaceEnum

Values used by this package are completed from the attachment's endpoint parameter descriptions; its model JSON excerpts are incomplete.

```json
[
  "MY",
  "TEAM",
  "SHARED"
]
```

## AssetsDirectorySearchQueryVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|spaceType|AssetsDirectorySpaceEnum|Yes|Space type: MY personal space, TEAM team space, SHARED shared entry; NotNull(message = "{required.parameter.error}"); nested model: AssetsDirectorySpaceEnum|
|entryRootId|string\(integer\)|Not declared required|Shared-folder entry ID; required for spaceType=SHARED|
|keyword|string|Yes|Folder/file name keyword; NotBlank(message = "{required.parameter.error}"); Size(max = 100, message = "{validation.size}")|
|folderCursor|string\(integer\)|Not declared required|Last examined folder ID from the previous batch|
|fileCursor|string\(integer\)|Not declared required|Last examined file ID from the previous batch|
|folderSize|integer|Not declared required|Folder result size, 1..100; 50; Min(value = 1, message = "{validation.min}"); Max(value = 100, message = "{validation.max}")|
|fileSize|integer|Not declared required|File result size, 1..100; 50; Min(value = 1, message = "{validation.min}"); Max(value = 100, message = "{validation.max}")|

## AssetsFolderNavigateVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|path|string|Not declared required|Folder path, for example /Root/Products/Designs; takes precedence for locating the target|
|targetId|string\(integer\)|Not declared required|Target resource ID; effective when path is empty|
|targetType|AssetsType|Not declared required|Target resource type, FILE or FOLDER; effective when path is empty and targetId is nonempty; nested model: AssetsType|
|folderOnly|boolean|Not declared required|Return folders only; default false returns folders and files; false|
|fileCursor|string\(integer\)|Not declared required|Last file ID from the current target folder's previous batch; omit on the first call|
|fileSize|integer|Not declared required|File batch size per trace node; default 30, range 1..1000; 30|

## AssetsType

Values used by this package are completed from the attachment's endpoint parameter descriptions; its model JSON excerpts are incomplete.

```json
[
  "FILE",
  "FOLDER"
]
```

## AssetsFolderChildrenPageVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|sortField|string|Not declared required|Sort field|
|sortDirection|SortDirectionEnum|Not declared required|Sort direction; nested model: SortDirectionEnum|
|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|
|keyword|string|Not declared required|Keyword|
|folderId|string\(integer\)|Yes|Folder ID; NotNull(message = "{required.parameter.error}")|
|type|string|Not declared required|Optional type filter: FOLDER for folders only, FILE for files only; omitted returns all|
|fileTypeFilter|AssetsSearchFileTypeEnum\[\]|Not declared required|File-type filters, such as ["IMAGE", "VIDEO", "DOC"]; ALL disables filtering; nested model: AssetsSearchFileTypeEnum|

## CommonPageVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|sortField|string|Not declared required|Sort field|
|sortDirection|SortDirectionEnum|Not declared required|Sort direction; nested model: SortDirectionEnum|
|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|

## AssetsSearchFileTypeEnum

```json
[
  "ALL",
  "IMAGE",
  "VIDEO",
  "DOC",
  "FOLDER",
  "PRODUCT"
]
```

## AssetsFolderMetadataFilterVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|metadataLogicType|AssetsRuleLogicTypeEnum|Not declared required|Metadata condition logic (AND/OR), default AND; AssetsRuleLogicTypeEnum.AND; nested model: AssetsRuleLogicTypeEnum|
|metadataFilterList|AssetsFolderMetadataFilterVO\.MetadataFilterVO\[\]|Not declared required|Metadata filter conditions; nested model: AssetsFolderMetadataFilterVO.MetadataFilterVO|

## AssetsRuleLogicTypeEnum

```json
[
  "OR",
  "AND",
  "IN",
  "NOT_IN",
  "EQUALS"
]
```

## AssetsFolderMetadataFilterVO\.MetadataFilterVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|fieldId|string\(integer\)|Not declared required||
|operator|AssetsSearchOperatorEnum|Not declared required||
|value|string\[\]|Not declared required||

## AssetsUserResourcePageQueryVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|size|integer|Not declared required|Records per batch, default 50, maximum 100; 50; Min(value = 1, message = "{validation.min}"); Max(value = 100, message = "{validation.max}")|
|cursor|string|Not declared required|Next-batch cursor returned by the previous batch; Size(max = 2048, message = "{validation.size}")|
|keyword|string|Not declared required|Resource-name or path keyword; Size(max = 100, message = "{validation.size}")|
|targetType|AssetsType|Not declared required|Resource type: FOLDER or FILE; nested model: AssetsType|

## AssetsShareQueryVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|sortField|string|Not declared required|Sort field|
|sortDirection|SortDirectionEnum|Not declared required|Sort direction; nested model: SortDirectionEnum|
|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|
|targetType|AssetsType|Yes|Target type; NotNull; nested model: AssetsType|
|targetId|string\(integer\)|Yes|Target ID; folder 0 means Root; NotNull|

## AssetsShareCandidateUserQueryVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|sortField|string|Not declared required|Sort field|
|sortDirection|SortDirectionEnum|Not declared required|Sort direction; nested model: SortDirectionEnum|
|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|
|targetType|AssetsType|Yes|Target type; NotNull; nested model: AssetsType|
|targetId|string\(integer\)|Yes|Target ID; folder 0 means Root; NotNull|
|keyword|string|Not declared required|Username, nickname, or department-name keyword; case-insensitive and trimmed; blank disables filtering|

## AssetsShareSaveVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|targetType|AssetsType|Yes|Target type; NotNull; nested model: AssetsType|
|targetId|string\(integer\)|Yes|Target ID; NotNull|
|userId|string\(integer\)|Not declared required|Grantee user ID; 0 is the initialization user|
|departmentId|string\(integer\)|Not declared required|Grantee department ID; exactly one of this and user ID is required|
|presetType|AssetsPermissionPresetTypeEnum|Yes|Permission preset; NotNull; nested model: AssetsPermissionPresetTypeEnum|

## AssetsShareUpdateVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|targetType|AssetsType|Yes|Target type; NotNull; nested model: AssetsType|
|targetId|string\(integer\)|Yes|Target ID; NotNull|
|userId|string\(integer\)|Not declared required|Grantee user ID; 0 is the initialization user|
|departmentId|string\(integer\)|Not declared required|Grantee department ID; exactly one of this and user ID is required|
|presetType|AssetsPermissionPresetTypeEnum|Yes|Permission preset; NotNull; nested model: AssetsPermissionPresetTypeEnum|
|grantId|string\(integer\)|Yes|Grant ID; NotNull|
|version|integer|Yes|Grant version; NotNull|

## AssetsShareDeleteVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|targetType|AssetsType|Yes|Target type; NotNull; nested model: AssetsType|
|targetId|string\(integer\)|Yes|Target ID; NotNull|
|grantId|string\(integer\)|Yes|Grant ID; NotNull|
|version|integer|Yes|Grant version; NotNull|

## AssetsPermissionPageVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Permission configuration ID|
|name|string|Not declared required|Permission name|
|description|string|Not declared required|Permission description|
|systemRoleList|SystemRoleOptionalVO\[\]|Not declared required|Associated system roles; nested model: SystemRoleOptionalVO|
|departmentList|Department\[\]|Not declared required|Associated departments; nested model: Department|
|createdBy|string\(integer\)|Not declared required|Created by|
|updatedBy|string\(integer\)|Not declared required|Updated by|
|createdAt|string\(date\-time\)|Not declared required|Creation time|
|updatedAt|string\(date\-time\)|Not declared required|Update time|

## Department

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key.|
|name|string|Not declared required|Department name.|
|parentId|string\(integer\)|Not declared required|Parent department ID.|
|leaderId|string\(integer\)|Not declared required|Department leader ID.|
|rankIndex|integer|Not declared required|Department sort value.|
|createdAt|string\(date\-time\)|Not declared required|Creation time.|
|updatedAt|string\(date\-time\)|Not declared required|Edit time.|
|children|Department\[\]|Not declared required|Subdepartment collection; nested model: Department|
|userList|User\[\]|Not declared required|User collection; nested model: User|

## User

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key.|
|registerWay|RegisterWayEnum|Not declared required|Registration method; nested model: RegisterWayEnum|
|wxOpenId|string|Not declared required|WeChat OpenId.|
|wxUnionId|string|Not declared required|WeChat UnionId.|
|phoneNumber|string|Not declared required|Phone number.|
|createdAt|string\(date\-time\)|Not declared required|Creation time.|
|updatedAt|string\(date\-time\)|Not declared required|Edit time.|
|role|UserRoleEnum|Not declared required|Role (currently unused); nested model: UserRoleEnum|
|ssoUserId|string|Not declared required|SSO user ID.|
|nickname|string|Not declared required|User display name.|
|lastLoginAt|string\(date\-time\)|Not declared required|Last login time.|
|username|string|Not declared required|Username.|
|password|string|Not declared required|Password.|
|status|UserStatusEnum|Not declared required|User status; nested model: UserStatusEnum|
|salt|string|Not declared required|Salt.|
|jobTitle|string|Not declared required|Job title.|
|leaderId|string\(integer\)|Not declared required|Direct supervisor ID.|
|email|string|Not declared required|Email.|
|assetId|string\(integer\)|Not declared required|Personal asset-space root folder ID.|
|baseId|string\(integer\)|Not declared required|Personal multidimensional-table database ID.|
|tokenVersion|string\(integer\)|Not declared required|User Session and access JWT version.|
|userPermissionIdListJson|string|Not declared required|JSON list of user-level permission IDs.|
|personalAssets|UserPersonalAssetsVO|Not declared required|Personal asset-space response information; nested model: UserPersonalAssetsVO|
|personalBase|UserPersonalBaseVO|Not declared required|Personal multidimensional-table database response information; nested model: UserPersonalBaseVO|
|departmentIdList|string\(integer\)\[\]|Not declared required|Department ID collection.|
|organizationRole|OrganizationRoleEnum|Not declared required|Organization role; nested model: OrganizationRoleEnum|
|systemAdministratorIs|boolean|Not declared required|Whether the user is a platform administrator.|
|shouldUpdatePassword|boolean|Not declared required|Whether a password reset is required.|
|departmentList|Department\[\]|Not declared required|Department collection; nested model: Department|
|systemRoleList|SystemRole\[\]|Not declared required|System-role collection; nested model: SystemRole|
|leader|User|Not declared required|Direct supervisor; nested model: User|
|userGroupList|UserGroup\[\]|Not declared required|User-group collection; nested model: UserGroup|
|planType|AssetsPlanEnum|Not declared required|Asset mode; nested model: AssetsPlanEnum|
|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role ID collection.|
|userPermissionIdList|string\(integer\)\[\]|Not declared required|User-level permission ID collection.|

## RegisterWayEnum

```json
[
  "PHONE",
  "EMAIL",
  "WEIXIN",
  "SSO",
  "USERNAME"
]
```

## UserRoleEnum

```json
[
  "ADMIN",
  "USER"
]
```

## UserStatusEnum

```json
[
  "ENABLE"
]
```

## OrganizationRoleEnum

```json
[
  "SUPER_ADMIN",
  "ADMIN",
  "DEVELOPER",
  "MEMBER"
]
```

## SystemRole

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key.|
|name|string|Not declared required|Name.|
|description|string|Not declared required|Remarks.|
|defaultIs|boolean|Not declared required|Whether this is the default role.|
|createdBy|string\(integer\)|Not declared required|Created by.|
|updatedBy|string\(integer\)|Not declared required|Modified by.|
|createdAt|string\(date\-time\)|Not declared required|Creation time.|
|updatedAt|string\(date\-time\)|Not declared required|Edit time.|
|permissionList|SystemRolePermission\[\]|Not declared required|Permission list; nested model: SystemRolePermission|
|permissionIdList|string\(integer\)\[\]|Not declared required|Permission ID list.|

## SystemRolePermission

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key.|
|roleId|string\(integer\)|Not declared required|Role ID.|
|permissionId|string\(integer\)|Not declared required|Permission ID.|
|permissionType|string|Not declared required|Permission type.|
|createdBy|string\(integer\)|Not declared required|Created by.|
|updatedBy|string\(integer\)|Not declared required|Updated by.|
|createdAt|string\(date\-time\)|Not declared required|Creation time.|
|updatedAt|string\(date\-time\)|Not declared required|Edit time.|

## UserGroup

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key.|
|name|string|Not declared required|Name.|
|createdAt|string\(date\-time\)|Not declared required|Creation time.|
|updatedAt|string\(date\-time\)|Not declared required|Edit time.|
|userIdList|string\(integer\)\[\]|Not declared required|User ID collection.|
|departmentIdList|string\(integer\)\[\]|Not declared required|Department ID collection.|

## AssetsPlanEnum

```json
[
  "LITE"
]
```

## AssetsPermissionFormInitVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Permission configuration ID; empty on creation|
|name|string|Not declared required|Permission configuration name|
|description|string|Not declared required|Permission configuration description|
|systemRoleIdList|string\(integer\)\[\]|Not declared required|Associated system-role IDs|
|selectedDepartmentList|AssetsPermissionDepartmentSelectionVO\[\]|Not declared required|Selected departments and full hierarchy paths; nested model: AssetsPermissionDepartmentSelectionVO|
|departmentTree|Department|Not declared required|Complete department tree for creation/edit selection; nested model: Department|
|roleOptionList|SystemRoleOptionalVO\[\]|Not declared required|System-role dropdown options; nested model: SystemRoleOptionalVO|
|presetOptionList|AssetsPermissionPresetOptionVO\[\]|Not declared required|Permission preset dropdown options; nested model: AssetsPermissionPresetOptionVO|
|actionOptionList|AssetsPermissionActionOptionVO\[\]|Not declared required|Custom permission action options; nested model: AssetsPermissionActionOptionVO|
|folderTree|AssetsPermissionFolderTreeNodeVO\[\]|Not declared required|Complete folder permission configuration tree; nested model: AssetsPermissionFolderTreeNodeVO|

## AssetsPermissionDepartmentSelectionVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Selected department ID|
|name|string|Not declared required|Selected department name|
|path|AssetsPermissionDepartmentSelectionVO\.DepartmentPathNodeVO\[\]|Not declared required|Full path from Root to the selected department; nested model: AssetsPermissionDepartmentSelectionVO.DepartmentPathNodeVO|

## AssetsPermissionDepartmentSelectionVO\.DepartmentPathNodeVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required||
|name|string|Not declared required||

## AssetsPermissionPresetOptionVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|presetType|AssetsPermissionPresetTypeEnum|Not declared required|Permission preset type; nested model: AssetsPermissionPresetTypeEnum|
|name|string|Not declared required|Permission preset name|
|permissionIdList|string\(integer\)\[\]|Not declared required|Permission IDs from the preset's default expansion|

## AssetsPermissionActionOptionVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Permission ID|
|name|string|Not declared required|Permission enum name|
|permission|string|Not declared required|Permission identifier|

## AssetsPermissionFolderTreeNodeVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|folderId|string\(integer\)|Not declared required|Folder ID|
|parentId|string\(integer\)|Not declared required|Parent folder ID|
|name|string|Not declared required|Folder name|
|children|AssetsPermissionFolderTreeNodeVO\[\]|Not declared required|Child folder list; nested model: AssetsPermissionFolderTreeNodeVO|
|permissionMode|AssetsPermissionModeEnum|Not declared required|Permission configuration mode: INHERIT inherits from the parent, CUSTOM indicates an explicit rule on this node; nested model: AssetsPermissionModeEnum|
|presetType|AssetsPermissionPresetTypeEnum|Not declared required|Explicit preset type on this node; meaningful when permissionMode=CUSTOM; nested model: AssetsPermissionPresetTypeEnum|
|permissionIdList|string\(integer\)\[\]|Not declared required|Explicit permission IDs on this node|
|explicitRule|boolean|Not declared required|Whether this node has an explicit rule|
|effectivePresetType|AssetsPermissionPresetTypeEnum|Not declared required|Final preset type after inheritance resolution; nested model: AssetsPermissionPresetTypeEnum|
|effectivePermissionIdList|string\(integer\)\[\]|Not declared required|Final permission IDs after inheritance resolution|
|inheritedFolderId|string\(integer\)|Not declared required|Nearest inheritance-source folder ID; null when this node is explicitly configured|
|inheritedFolderName|string|Not declared required|Nearest inheritance-source folder name; null when none exists|

## AssetsPermissionModeEnum

The attachment lists only INHERIT here, but response descriptions also use CUSTOM for explicit rules. This package does not use that incomplete response enum for input validation.

```json
[
  "INHERIT"
]
```

## AssetsPermissionVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Primary key|
|name|string|Not declared required|Permission name|
|description|string|Not declared required|Permission description|
|status|string|Not declared required|Permission status|
|systemRoleIdList|string\(integer\)\[\]|Not declared required|System-role ID list|
|departmentIdList|string\(integer\)\[\]|Not declared required|Department ID list|
|ruleList|AssetsPermissionRuleVO\[\]|Not declared required|Folder permission rule list; nested model: AssetsPermissionRuleVO|
|createdBy|string\(integer\)|Not declared required|Created by|
|updatedBy|string\(integer\)|Not declared required|Updated by|
|createdAt|string\(date\-time\)|Not declared required|Creation time|
|updatedAt|string\(date\-time\)|Not declared required|Update time|

## AssetsTargetPermissionVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|targetType|AssetsType|Not declared required|Target type, FILE or FOLDER; nested model: AssetsType|
|targetId|string\(integer\)|Not declared required|Target ID|
|targetName|string|Not declared required|Target name|
|parentId|string\(integer\)|Not declared required|Parent folder ID; Root returns null|
|folderId|string\(integer\)|Not declared required|Folder owning the permission context; the containing folder for files, the folder itself for folders|
|canOpen|boolean|Not declared required|Whether the current target can be opened|
|pathShell|boolean|Not declared required|Whether this is a path-shell folder|
|permissionIdList|string\(integer\)\[\]|Not declared required|Current user's final effective permission IDs for the target|
|childFolderPermissionList|AssetsTargetPermissionVO\[\]|Not declared required|Permission list for displayable direct child folders; new ArrayList<>(); nested model: AssetsTargetPermissionVO|
|children|AssetsTargetPermissionVO\[\]|Not declared required|Permission navigation children; the final folder-target node also returns directly viewable file permissions; new ArrayList<>(); nested model: AssetsTargetPermissionVO|
|filePage|AssetsCursorPageInfoVO|Not declared required|Cursor pagination for direct file-permission nodes; only returned on the final folder-target node; nested model: AssetsCursorPageInfoVO|

## AssetsCursorPageInfoVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|size|integer|Not declared required|Batch size for this request|
|hasMore|boolean|Not declared required|Whether another batch exists|
|nextCursor|string|Not declared required|Next-batch cursor; null when no next batch exists|

## AssetsDirectoryVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|spaceType|AssetsDirectorySpaceEnum|Not declared required|Current folder space type; nested model: AssetsDirectorySpaceEnum|
|available|boolean|Not declared required|Whether the current folder space is available; false if personal space is not enabled|
|rootId|string\(integer\)|Not declared required|Current space's hidden root folder ID; 0 for team space|
|rootVersion|string\(integer\)|Not declared required|Current space's hidden root folder version; 0 for team space|
|currentFolderId|string\(integer\)|Not declared required|Current browsed folder ID; equals the hidden root ID when parentId is omitted|
|currentFolderVersion|string\(integer\)|Not declared required|Current browsed folder version; used for upload, folder creation, and other optimistic-lock operations|
|entryRootId|string\(integer\)|Not declared required|Shared-folder entry ID; returned only for shared space|
|folderList|AssetsDirectoryNodeVO\[\]|Not declared required|Folder nodes; new ArrayList<>(); nested model: AssetsDirectoryNodeVO|
|fileList|AssetsDirectoryNodeVO\[\]|Not declared required|File nodes; new ArrayList<>(); nested model: AssetsDirectoryNodeVO|
|folderPage|AssetsCursorPageInfoVO|Not declared required|Folder cursor information; nested model: AssetsCursorPageInfoVO|
|filePage|AssetsCursorPageInfoVO|Not declared required|File cursor information; nested model: AssetsCursorPageInfoVO|

## AssetsDirectoryNodeVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Node ID.|
|parentId|string\(integer\)|Not declared required|Parent folder ID.|
|version|string\(integer\)|Not declared required|Resource version; used for optimistic locking on rename, move, and delete|
|name|string|Not declared required|Display name.|
|type|string|Not declared required|Node type: FOLDER or FILE.|
|hasChildren|boolean|Not declared required|Whether direct child folders exist.|
|pinIs|boolean|Not declared required|Whether pinned by the current user; Boolean.FALSE|
|favoriteIs|boolean|Not declared required|Whether favorited by the current user; Boolean.FALSE|
|path|string|Not declared required|Display path relative to the current space's hidden root.|
|ancestorIdList|string\(integer\)\[\]|Not declared required|Ancestor folder IDs relative to the current space's hidden root.|

## AssetsFolderTraceLevelVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|folderId|string\(integer\)|Not declared required|Folder ID|
|folderName|string|Not declared required|Folder name|
|parentId|string\(integer\)|Not declared required|Parent folder ID|
|folderList|AssetsFolderBrowseItemVO\[\]|Not declared required|Folder list; new ArrayList<>(); nested model: AssetsFolderBrowseItemVO|
|fileList|AssetsFileBrowseItemVO\[\]|Not declared required|File list; new ArrayList<>(); nested model: AssetsFileBrowseItemVO|
|filePage|AssetsCursorPageInfoVO|Not declared required|Current-node file cursor pagination; nested model: AssetsCursorPageInfoVO|
|children|AssetsFolderTraceLevelVO\[\]|Not declared required|Child nodes; new ArrayList<>(); nested model: AssetsFolderTraceLevelVO|

## AssetsFolderBrowseItemVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Folder ID|
|name|string|Not declared required|Folder name|
|type|string|Not declared required|Type|
|parentId|string\(integer\)|Not declared required|Parent folder ID|
|version|string\(integer\)|Not declared required|Current folder version|
|parentVersion|string\(integer\)|Not declared required|Parent folder version|
|pathShell|boolean|Not declared required|Whether this is a path shell leading to visible descendants or directly shared files|
|createdAt|string\(date\-time\)|Not declared required|Creation time|
|updatedAt|string\(date\-time\)|Not declared required|Update time|

## AssetsFileBrowseItemVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|File ID|
|type|string|Not declared required|File type|
|folderId|string\(integer\)|Not declared required|Folder ID|
|thumbnailWidth|integer|Not declared required|Thumbnail base-cover width in pixels; sizes scale proportionally; empty when unknown|
|thumbnailHeight|integer|Not declared required|Thumbnail base-cover height in pixels; sizes scale proportionally; empty when unknown|
|name|string|Not declared required|Display name|
|presignUrl|string|Not declared required|Presigned file URL|
|originalPresignedUrl|string|Not declared required|Presigned original-image URL|
|version|string\(integer\)|Not declared required|File version|
|folderVersion|string\(integer\)|Not declared required|Folder version|
|createdAt|string\(date\-time\)|Not declared required|Creation time|
|updatedAt|string\(date\-time\)|Not declared required|Update time|
|metadata|AssetsFileMetadataItemVO\[\]|Not declared required|Metadata list; nested model: AssetsFileMetadataItemVO|
|description|string|Not declared required|File description|
|recallSources|string\[\]|Not declared required|Keyword-search recall source|
|recallScore|string\(decimal\)|Not declared required|Keyword-search fusion score|

## AssetsFileMetadataItemVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|fieldId|string|Not declared required|Metadata field ID|
|fieldName|string|Not declared required|Metadata field name|
|fieldType|string|Not declared required|Metadata field type|
|fieldValue|object|Not declared required|Metadata field value|

## AssetsFolderChildrenVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|folderList|AssetsFolderBrowseItemVO\[\]|Not declared required|Folder list; new ArrayList<>(); nested model: AssetsFolderBrowseItemVO|
|fileList|AssetsFileBrowseItemVO\[\]|Not declared required|File list; new ArrayList<>(); nested model: AssetsFileBrowseItemVO|

## AssetsFolderOptionalVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|id|string\(integer\)|Not declared required|Folder ID|
|name|string|Not declared required|Folder name|
|parentId|string\(integer\)|Not declared required|Parent folder ID|
|pathShell|boolean|Not declared required|Whether this is a path shell leading to visible descendants or directly shared files|
|hasChildren|boolean|Not declared required|Whether child folders exist|
|children|AssetsFolderOptionalVO\[\]|Not declared required|Child folder list; nested model: AssetsFolderOptionalVO|

## AssetsTargetFileInfoVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|targetType|AssetsType|Not declared required|Target type, FILE or FOLDER; nested model: AssetsType|
|targetId|string\(integer\)|Not declared required|Target ID|
|folderId|string\(integer\)|Not declared required|Containing folder ID or target folder ID|
|pathShell|boolean|Not declared required|Whether the target folder is a path shell to visible descendants or directly shared files; always false for file targets|
|fileList|AssetsFileBrowseItemVO\[\]|Not declared required|Related file information; new ArrayList<>(); nested model: AssetsFileBrowseItemVO|

## AssetsCursorPageVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|recordList|T\[\]|Not declared required|Records in this batch|
|pageInfo|AssetsCursorPageInfoVO|Not declared required|Cursor pagination; nested model: AssetsCursorPageInfoVO|

## AssetsResourceSummaryVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|relationId|string\(integer\)|Not declared required|Recent-use, share, or favorite association ID|
|relationAt|string\(date\-time\)|Not declared required|Most recent access, share, or favorite time|
|id|string\(integer\)|Not declared required|Resource ID|
|targetType|AssetsType|Not declared required|Resource type: FOLDER or FILE; nested model: AssetsType|
|parentId|string\(integer\)|Not declared required|Parent folder ID|
|name|string|Not declared required|Live resource name|
|path|string|Not declared required|Live full path: /User/{ownerUsername}/... for personal space and its shared resources; /Root/... for team space|
|spaceType|AssetsDirectorySpaceEnum|Not declared required|Resource space: MY, TEAM, or SHARED; nested model: AssetsDirectorySpaceEnum|
|entryRootId|string\(integer\)|Not declared required|Shared-folder browsing entry ID; empty for non-shared folders|

## AssetsShareVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|grantId|string\(integer\)|Not declared required|Grant ID.|
|userId|string\(integer\)|Not declared required|Grantee user ID.|
|departmentId|string\(integer\)|Not declared required|Grantee department ID.|
|departmentName|string|Not declared required|Grantee department name.|
|displayName|string|Not declared required|User display name.|
|username|string|Not declared required|Username.|
|nickname|string|Not declared required|User nickname.|
|departmentList|Department\[\]|Not declared required|User departments; nested model: Department|
|presetType|AssetsPermissionPresetTypeEnum|Not declared required|Permission preset; nested model: AssetsPermissionPresetTypeEnum|
|version|integer|Not declared required|Grant version.|

## AssetsShareCandidateVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|userList|AssetsShareUserVO\[\]|Not declared required|Candidate users on this page, ordered by user ID ascending; empty array when none; new ArrayList<>(); nested model: AssetsShareUserVO|
|departmentList|AssetsShareCandidateVO\.DepartmentVO\[\]|Not declared required|Candidate departments on this page, ordered by department ID ascending; empty array when none; new ArrayList<>(); nested model: AssetsShareCandidateVO.DepartmentVO|

## AssetsShareUserVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|userId|string\(integer\)|Not declared required|Candidate user ID|
|displayName|string|Not declared required|User display name; nickname preferred, otherwise username|
|username|string|Not declared required|Username|

## AssetsShareCandidateVO\.DepartmentVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|departmentId|string\(integer\)|Not declared required||
|departmentName|string|Not declared required||

## DeviceBindFolderVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|folderId|string\(integer\)|Not declared required|Final device-binding folder ID|
|spaceType|AssetsDirectorySpaceEnum|Not declared required|Device-binding folder is always MY; server-side read-only constant|
|folderName|string|Not declared required|Actual folder name at successful login|
|folderPath|string|Not declared required|Snapshot of the personal-space logical path at successful login|

## EngineStatisticVO

|Field|JSON type / nested model|Declared constraints|Description and values|
|---|---|---|---|
|agentCount|integer|Not declared required|Agent count|
|flowCount|integer|Not declared required|Workflow count|
|skillCount|integer|Not declared required|Skill count|
|apiCount|integer|Not declared required|API count (source schema description reuses "Skill count")|
|variableCount|integer|Not declared required|Variable count|
|knowledgeBaseCount|integer|Not declared required|Knowledge-base count|

## AssetsSearchOperatorEnum

```json
{
  "IN": "Contains",
  "NOT_IN": "Does not contain",
  "EQUALS": "Equals",
  "NOT_EQUALS": "Does not equal",
  "GT": "Greater than",
  "LT": "Less than",
  "BETWEEN": "Between"
}
```
