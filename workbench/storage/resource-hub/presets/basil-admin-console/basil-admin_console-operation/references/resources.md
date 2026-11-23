# resources

Use `scripts/admin_console/cli.py`; see [protocol.md](protocol.md) for shared input/output rules. Locate the required contract by operation; other capabilities need not be read.

- [directory_children](#directory-children): Query direct folders/files by space
- [directory_search](#directory-search): Search folders/files by space
- [folder_navigate](#folder-navigate): Query folder navigation by path or ID
- [folder_page_post](#folder-page-post): List folder resources with pagination
- [folder_page](#folder-page): List folder resources with pagination
- [folder_files](#folder-files): List folder files with pagination
- [resource_files](#resource-files): Query files associated with a resource target
- [shares_received](#shares-received): Query received shares using a cursor

<a id="directory-children"></a>

## `directory_children` — Query direct folders/files by space

GET /typekey/api/v1/assets/access/directory/children

Purpose: Browse one level of visible resources in MY/TEAM/SHARED space and obtain target IDs for later authorization

Scope: Employee-side directory-tree helper, not called directly by Admin asset-ace

Authorization: @IgnoreCheckSystemPermission skips system-menu permission checks but still requires global authentication and resource visibility/space-boundary checks

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|spaceType|AssetsDirectorySpaceEnum|Yes|Space type: MY personal space, TEAM team space, SHARED shared entry; NotNull(message = "{required.parameter.error}")|
|query|entryRootId|string\(integer\)|Not declared required|Shared-folder entry ID; required for spaceType=SHARED|
|query|parentId|string\(integer\)|Not declared required|Parent folder ID; empty uses the current space's hidden root|
|query|includeFiles|boolean|Not declared required|Whether to also query files in the current folder; false|
|query|folderCursor|string\(integer\)|Not declared required|Last folder ID from the previous batch|
|query|fileCursor|string\(integer\)|Not declared required|Last file ID from the previous batch|
|query|folderSize|integer|Not declared required|Folder batch size, 1..100; 50; Min(value = 1, message = "{validation.min}"); Max(value = 100, message = "{validation.max}")|
|query|fileSize|integer|Not declared required|File batch size, 1..100; 50; Min(value = 1, message = "{validation.min}"); Max(value = 100, message = "{validation.max}")|

Response data: AssetsDirectoryVO. See the corresponding model in [models.md](models.md).

- Required spaceType is MY/TEAM/SHARED; SHARED requires entryRootId to be a directory entry actually shared with the current user.

- folderSize/fileSize default to 50, range 1..100; cursors are nonnegative IDs, not page numbers. Advance each cursor independently.

- Unavailable MY personal space returns available=false and empty resources, not an authentication failure.

- Returns only nodes visible/traversable by the current user; cannot replace the complete TEAM configuration tree from Admin form/init.

- DirectoryNodeVO does not include final permissionIdList; query assets/access/permission for effective actions.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 400|validation\.nonnegative|Negative cursor|
|400 / 400|validation\.positive|Missing or nonpositive SHARED entryRootId|
|400 / 400|biz\.error|Space boundary violation, deleted folder, invalid shared entry, or invisible resource|

<a id="directory-search"></a>

## `directory_search` — Search folders/files by space

GET /typekey/api/v1/assets/access/directory/search

Purpose: Search visible folders and files by name within the specified space

Scope: Employee-side directory-tree helper, not called directly by Admin asset-ace

Authorization: @IgnoreCheckSystemPermission skips system-menu permission checks but still requires global authentication and resource visibility/space-boundary checks

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|spaceType|AssetsDirectorySpaceEnum|Yes|Space type: MY personal space, TEAM team space, SHARED shared entry; NotNull(message = "{required.parameter.error}")|
|query|entryRootId|string\(integer\)|Not declared required|Shared-folder entry ID; required for spaceType=SHARED|
|query|keyword|string|Yes|Folder/file name keyword; NotBlank(message = "{required.parameter.error}"); Size(max = 100, message = "{validation.size}")|
|query|folderCursor|string\(integer\)|Not declared required|Last examined folder ID from the previous batch|
|query|fileCursor|string\(integer\)|Not declared required|Last examined file ID from the previous batch|
|query|folderSize|integer|Not declared required|Folder result size, 1..100; 50; Min(value = 1, message = "{validation.min}"); Max(value = 100, message = "{validation.max}")|
|query|fileSize|integer|Not declared required|File result size, 1..100; 50; Min(value = 1, message = "{validation.min}"); Max(value = 100, message = "{validation.max}")|

Response data: AssetsDirectoryVO. See the corresponding model in [models.md](models.md).

- Required spaceType is MY/TEAM/SHARED; SHARED requires entryRootId to be a directory entry actually shared with the current user.

- folderSize/fileSize default to 50, range 1..100; cursors are nonnegative IDs, not page numbers. Advance each cursor independently.

- Unavailable MY personal space returns available=false and empty resources, not an authentication failure.

- Returns only nodes visible/traversable by the current user; cannot replace the complete TEAM configuration tree from Admin form/init.

- DirectoryNodeVO does not include final permissionIdList; query assets/access/permission for effective actions.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
|400 / 400|validation\.nonnegative|Negative cursor|
|400 / 400|validation\.positive|Missing or nonpositive SHARED entryRootId|
|400 / 400|validation\.required|Empty search keyword|
|400 / 400|biz\.error|Space boundary violation, deleted folder, invalid shared entry, or invisible resource|

<a id="folder-navigate"></a>

## `folder_navigate` — Query folder navigation by path or ID

GET /typekey/api/v1/assets/folder/navigate

Purpose: Build a trace navigation chain for a target and return bounded file batches

Scope: Asset navigation hook helper, not called directly by Admin asset-ace

Authorization: System permission 111000 / system.assets.management plus target visibility/action checks; see endpoint notes

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|path|string|Not declared required|Folder path, for example /Root/Products/Designs; takes precedence for locating the target|
|query|targetId|string\(integer\)|Not declared required|Target resource ID; effective when path is empty|
|query|targetType|AssetsType|Not declared required|Target resource type, FILE or FOLDER; effective when path is empty and targetId is nonempty|
|query|folderOnly|boolean|Not declared required|Return folders only; default false returns folders and files; false|
|query|fileCursor|string\(integer\)|Not declared required|Last file ID from the current target folder's previous batch; omit on the first call|
|query|fileSize|integer|Not declared required|File batch size per trace node; default 30, range 1..1000; 30|

Response data: AssetsFolderTraceLevelVO. See the corresponding model in [models.md](models.md).

- path takes precedence; absent path and targetId use service defaults. fileSize defaults to 30, range 1..1000; fileCursor >= 0; folderOnly=true skips file queries.

- See models.md for actual response fields; models were checked against source, not sampled from a live service.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|

<a id="folder-page-post"></a>

## `folder_page_post` — List folder resources with pagination

POST /typekey/api/v1/assets/folder/page

Purpose: Read child resources by folderId, subject to resource visibility

Scope: Resource browsing helper, not called directly by Admin asset-ace

Authorization: System permission 111000 / system.assets.management plus target visibility/action checks; see endpoint notes

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|sortField|string|Not declared required|Sort field|
|query|sortDirection|SortDirectionEnum|Not declared required|Sort direction|
|query|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|query|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|
|query|keyword|string|Not declared required|Keyword|
|query|folderId|string\(integer\)|Yes|Folder ID; NotNull(message = "{required.parameter.error}")|
|query|type|string|Not declared required|Optional type filter: FOLDER for folders only, FILE for files only; omitted returns all|
|query|fileTypeFilter|AssetsSearchFileTypeEnum\[\]|Not declared required|File-type filters, such as ["IMAGE", "VIDEO", "DOC"]; ALL disables filtering|
|body|metadataFilterVO|AssetsFolderMetadataFilterVO|Not declared required||

Request body model: AssetsFolderMetadataFilterVO; see [models.md](models.md) for all nested fields.

Response data: AssetsFolderChildrenVO. See the corresponding model in [models.md](models.md).

- folderId/page/size are required; size maximum 1000. type FILE/FOLDER filters results; file/page forces FILE.

- POST query parameters remain in the URL; only the optional metadata-filter object is JSON body. GET is retained for compatibility/synchronization helpers.

- See models for sort/file-type/metadata-filter fields and constraints; do not guess parameters from frontend types.

- Pagination remains in query; optional JSON body is the AssetsFolderMetadataFilterVO object directly, without a metadataFilterVO wrapper.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1001|param\.parse\.failure|Invalid JSON or field deserialization failure|
|400 / 1002|param\.is\.invalid|Request-body Bean Validation failure|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|

<a id="folder-page"></a>

## `folder_page` — List folder resources with pagination

GET /typekey/api/v1/assets/folder/page

Purpose: Read child resources by folderId, subject to resource visibility

Scope: Resource browsing helper, not called directly by Admin asset-ace

Authorization: System permission 111000 / system.assets.management plus target visibility/action checks; see endpoint notes

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|sortField|string|Not declared required|Sort field|
|query|sortDirection|SortDirectionEnum|Not declared required|Sort direction|
|query|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|query|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|
|query|keyword|string|Not declared required|Keyword|
|query|folderId|string\(integer\)|Yes|Folder ID; NotNull(message = "{required.parameter.error}")|
|query|type|string|Not declared required|Optional type filter: FOLDER for folders only, FILE for files only; omitted returns all|
|query|fileTypeFilter|AssetsSearchFileTypeEnum\[\]|Not declared required|File-type filters, such as ["IMAGE", "VIDEO", "DOC"]; ALL disables filtering|

Response data: AssetsFolderChildrenVO. See the corresponding model in [models.md](models.md).

- folderId/page/size are required; size maximum 1000. type FILE/FOLDER filters results; file/page forces FILE.

- POST query parameters remain in the URL; only the optional metadata-filter object is JSON body. GET is retained for compatibility/synchronization helpers.

- See models for sort/file-type/metadata-filter fields and constraints; do not guess parameters from frontend types.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|

<a id="folder-files"></a>

## `folder_files` — List folder files with pagination

GET /typekey/api/v1/assets/folder/file/page

Purpose: Read child resources by folderId, subject to resource visibility

Scope: Resource browsing helper, not called directly by Admin asset-ace

Authorization: System permission 111000 / system.assets.management plus target visibility/action checks; see endpoint notes

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|sortField|string|Not declared required|Sort field|
|query|sortDirection|SortDirectionEnum|Not declared required|Sort direction|
|query|page|integer|Yes|Page number; NotNull(message = "{required.parameter.error}")|
|query|size|integer|Yes|Records per page, maximum 1000; NotNull(message = "{required.parameter.error}"); Max(value = CommonConstant.PAGING_LIMIT_MAX)|
|query|keyword|string|Not declared required|Keyword|
|query|folderId|string\(integer\)|Yes|Folder ID; NotNull(message = "{required.parameter.error}")|
|query|type|string|Not declared required|Optional type filter: FOLDER for folders only, FILE for files only; omitted returns all|
|query|fileTypeFilter|AssetsSearchFileTypeEnum\[\]|Not declared required|File-type filters, such as ["IMAGE", "VIDEO", "DOC"]; ALL disables filtering|

Response data: List\<AssetsFileBrowseItemVO\>. See the corresponding model in [models.md](models.md).

- folderId/page/size are required; size maximum 1000. type FILE/FOLDER filters results; file/page forces FILE.

- POST query parameters remain in the URL; only the optional metadata-filter object is JSON body. GET is retained for compatibility/synchronization helpers.

- See models for sort/file-type/metadata-filter fields and constraints; do not guess parameters from frontend types.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|

<a id="resource-files"></a>

## `resource_files` — Query files associated with a resource target

GET /typekey/api/v1/assets/file/access/file/info

Purpose: FILE returns itself; FOLDER returns directly visible files; path shells return only permitted directly shared files

Scope: Resource-information helper, not called directly by Admin asset-ace

Authorization: @IgnoreCheckSystemPermission skips system-menu permission checks but still requires global authentication and resource visibility/space-boundary checks

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|targetType|FILE\|FOLDER|Not declared required|Required when path is empty and targetId is nonempty|
|query|targetId|string\(BigInteger\)|Not declared required|Defaults to Root(0) when omitted; FILE must reference an existing file|
|query|path|string|Not declared required|When nonempty, takes precedence over targetType/targetId; Root-relative path, with a final segment containing an extension interpreted as a file|

Response data: AssetsTargetFileInfoVO. See the corresponding model in [models.md](models.md).

- This path has the /assets/file prefix, not /assets/access/file/info.

- Not a permission-action endpoint; fileList does not authorize UI actions.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|

<a id="shares-received"></a>

## `shares_received` — Query received shares using a cursor

GET /typekey/api/v1/assets/share/received/page

Purpose: List resources directly shared with the current user or their departments

Scope: Shared-entry helper, not the Admin ACL page

Authorization: @IgnoreCheckSystemPermission skips system-menu permission checks but still requires global authentication and resource visibility/space-boundary checks

|Parameter location|Name|JSON/transport type|Required/declared constraints|Description, values, and update semantics|
|---|---|---|---|---|
|query|size|integer|Not declared required|Records per batch, default 50, maximum 100; 50; Min(value = 1, message = "{validation.min}"); Max(value = 100, message = "{validation.max}")|
|query|cursor|string|Not declared required|Next-batch cursor returned by the previous batch; Size(max = 2048, message = "{validation.size}")|
|query|keyword|string|Not declared required|Resource-name or path keyword; Size(max = 100, message = "{validation.size}")|
|query|targetType|AssetsType|Not declared required|Resource type: FOLDER or FILE|

Response data: AssetsCursorPageVO\<AssetsResourceSummaryVO\>. See the corresponding model in [models.md](models.md).

- size defaults to 50, range 1..100; cursor is an opaque string <= 2048 characters; keyword <= 100; optional targetType FILE/FOLDER.

- Results are direct-share entries, not all assets visible through ACLs.

- Opaque cursor is bound to keyword/targetType filters; discard it and restart when filters change.

|HTTP / business code|errorKey|Common failure conditions|
|---|---|---|
|401 / 2001|user\.not\.login|Missing, invalid, or expired login credentials|
|400 / 1003|param\.not\.match|Missing query parameters or binding validation failure|
|400 / 1005|param\.cast\.failure|path/query values cannot be converted to their declared types|
