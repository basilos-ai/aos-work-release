
## System-function permission IDs

Use all candidates in the table below for system-role permission multi-selects. Display names do not change enums or IDs. Grouping is for presentation only, not automatic parent/child linkage; do not add parent or child selections without authorization. Keep candidates aligned with `system_permission_ids` in `scripts/admin_console/contracts.json` when updating the contract.

These values come from SystemRolePermissionEnum. Submit only known enum IDs in permissionList; some write paths do not fully guard against unknown IDs, which may cause technical errors. User-level 114001/114002 are managed through userPermissionIdList and must not be mixed into system roles.

|ID|Display name|Enum|Permission identifier|
|---|---|---|---|
|100000|Workbench|SYSTEM\_WORKBENCH|system\.workbench|
|110000|Assets / Entry|SYSTEM\_ASSETS|system\.assets|
|111000|Assets / Asset management|SYSTEM\_ASSETS\_MANAGEMENT|system\.assets\.management|
|112000|Assets / Rule-group management|SYSTEM\_ASSETS\_RULE\_GROUP\_MANAGEMENT|system\.assets\.rule\.group\.management|
|112100|Assets / Rule groups / Create|SYSTEM\_ASSETS\_RULE\_GROUP\_CREATE|system\.assets\.rule\.group\.create|
|112200|Assets / Rule groups / Edit|SYSTEM\_ASSETS\_RULE\_GROUP\_EDIT|system\.assets\.rule\.group\.edit|
|112300|Assets / Rule groups / Delete|SYSTEM\_ASSETS\_RULE\_GROUP\_DELETE|system\.assets\.rule\.group\.delete|
|113000|Assets / Metadata-field management|SYSTEM\_ASSETS\_METADATA\_FIELD\_MANAGEMENT|system\.assets\.metadata\.management|
|113100|Assets / Metadata fields / Create|SYSTEM\_ASSETS\_METADATA\_FIELD\_CREATE|system\.assets\.metadata\.field\.create|
|113200|Assets / Metadata fields / Edit|SYSTEM\_ASSETS\_METADATA\_FIELD\_EDIT|system\.assets\.metadata\.field\.edit|
|113300|Assets / Metadata fields / Delete|SYSTEM\_ASSETS\_METADATA\_FIELD\_DELETE|system\.assets\.metadata\.field\.delete|
|113400|Assets / Metadata fields / Import|SYSTEM\_ASSETS\_METADATA\_FIELD\_IMPORT|system\.assets\.metadata\.field\.import|
|113500|Assets / Metadata fields / Export|SYSTEM\_ASSETS\_METADATA\_FIELD\_EXPORT|system\.assets\.metadata\.field\.export|
|120000|Studio / Entry|SYSTEM\_STUDIO|system\.studio|
|121001|Studio / Workflows / Management tab|SYSTEM\_STUDIO\_WORKFLOW\_TAB\_MANAGEMENT|system\.studio\.workflow\.tab\.Management|
|121002|Studio / Workflows / Call records|SYSTEM\_STUDIO\_WORKFLOW\_TAB\_CALL\_RECORD|system\.studio\.workflow\.tab\.call\.record|
|121003|Studio / Workflows / Create|SYSTEM\_STUDIO\_WORKFLOW\_BUTTON\_CREATE|system\.studio\.workflow\.button\.create|
|121004|Studio / Workflows / Export|SYSTEM\_STUDIO\_WORKFLOW\_BUTTON\_EXPORT|system\.studio\.workflow\.button\.export|
|121005|Studio / Workflows / Copy|SYSTEM\_STUDIO\_WORKFLOW\_BUTTON\_COPY|system\.studio\.workflow\.button\.copy|
|121006|Studio / Workflows / Delete|SYSTEM\_STUDIO\_WORKFLOW\_BUTTON\_DELETE|system\.studio\.workflow\.button\.delete|
|121007|Studio / Workflows / View|SYSTEM\_STUDIO\_WORKFLOW\_BUTTON\_CHECK|system\.studio\.workflow\.button\.check|
|121008|Studio / Workflows / Edit|SYSTEM\_STUDIO\_WORKFLOW\_BUTTON\_EDIT|system\.studio\.workflow\.button\.edit|
|121009|Studio / Workflows / Version management|SYSTEM\_STUDIO\_WORKFLOW\_BUTTON\_VERSION\_MANAGEMENT|system\.studio\.workflow\.button\.version\.management|
|1210010|Studio / Workflows / Publish|SYSTEM\_STUDIO\_WORKFLOW\_BUTTON\_PUBLISH|system\.studio\.workflow\.button\.publish|
|121011|Studio / Workflows / Root node|SYSTEM\_STUDIO\_WORKFLOW\_ROOT\_NODE|system\.studio\.workflow\.root\.node|
|122001|Studio / Knowledge bases / Management tab|SYSTEM\_STUDIO\_KNOWLEDGEBASE\_TAB\_MANAGEMENT|system\.studio\.knowledgebase\.tab\.Management|
|122002|Studio / Knowledge bases / Create|SYSTEM\_STUDIO\_KNOWLEDGEBASE\_BUTTON\_CREATE|system\.studio\.knowledgebase\.button\.create|
|122003|Studio / Knowledge bases / Delete|SYSTEM\_STUDIO\_KNOWLEDGEBASE\_BUTTON\_DELETE|system\.studio\.knowledgebase\.button\.delete|
|122004|Studio / Knowledge bases / Edit|SYSTEM\_STUDIO\_KNOWLEDGEBASE\_BUTTON\_EDIT|system\.studio\.knowledgebase\.button\.edit|
|122005|Studio / Knowledge bases / View content|SYSTEM\_STUDIO\_KNOWLEDGEBASE\_BUTTON\_CHECK\_CONTENT|system\.studio\.knowledgebase\.button\.check\.content|
|122006|Studio / Knowledge bases / Export|SYSTEM\_STUDIO\_KNOWLEDGEBASE\_BUTTON\_EXPORT|system\.studio\.knowledgebase\.button\.export|
|122007|Studio / Knowledge bases / Test|SYSTEM\_STUDIO\_KNOWLEDGEBASE\_BUTTON\_TEST|system\.studio\.knowledgebase\.button\.test|
|123001|Studio / Authorization management tab|SYSTEM\_STUDIO\_AUTHORIZATION\_TAB\_MANAGEMENT|system\.studio\.authorization\.tab\.management|
|124001|Studio / Triggers / Entry|SYSTEM\_STUDIO\_TRIGGER|system\.studio\.trigger|
|124002|Studio / Triggers / Create|SYSTEM\_STUDIO\_TRIGGER\_BUTTON\_CREATE|system\.studio\.trigger\.button\.create|
|124003|Studio / Triggers / Delete|SYSTEM\_STUDIO\_TRIGGER\_BUTTON\_DELETE|system\.studio\.trigger\.button\.delete|
|124004|Studio / Triggers / Edit|SYSTEM\_STUDIO\_TRIGGER\_BUTTON\_EDIT|system\.studio\.trigger\.button\.edit|
|125001|Studio / Multidimensional tables / Entry|SYSTEM\_STUDIO\_MULTI\_DIM\_TABLE|system\.studio\.multi\.dim\.table|
|125008|Studio / Multidimensional tables / Create|SYSTEM\_STUDIO\_MULTI\_DIM\_TABLE\_BASE\_CREATE|system\.studio\.multi\.dim\.table\.base\.create|
|125009|Studio / Multidimensional tables / Edit|SYSTEM\_STUDIO\_MULTI\_DIM\_TABLE\_BASE\_EDIT|system\.studio\.multi\.dim\.table\.base\.edit|
|125010|Studio / Multidimensional tables / Delete|SYSTEM\_STUDIO\_MULTI\_DIM\_TABLE\_BASE\_DELETE|system\.studio\.multi\.dim\.table\.base\.delete|
|130000|Admin Console / Entry|SYSTEM\_ADMIN|system\.admin|
|131000|Admin Console / Resource permission management|SYSTEM\_ADMIN\_ASSETS\_PERMISSION\_MANAGEMENT|system\.admin\.assets\.permission\.management|
|132000|Admin Console / Connector management|SYSTEM\_ADMIN\_CONNECTOR\_MANAGEMENT|system\.admin\.connector\.management|
|133000|Admin Console / Model management|SYSTEM\_ADMIN\_MODEL\_MANAGEMENT|system\.admin\.model\.management|
|134000|Admin Console / User management|SYSTEM\_ADMIN\_USER|system\.admin\.user|
|135000|Admin Console / Role management|SYSTEM\_ADMIN\_ROLES|system\.admin\.roles|

## User and organization enums

|Enum|Values|
|---|---|
|UserStatusEnum|ENABLE；DISABLE|
|UserRoleEnum|ADMIN；USER|
|RegisterWayEnum|PHONE；EMAIL；WEIXIN；SSO；USERNAME；DEVICE\_BIND|
|OrganizationRoleEnum|SUPER\_ADMIN；ADMIN；DEVELOPER；MEMBER|
|UserPermissionEnum|114001 (bulk read); 114002 (bulk set)|

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


Preset labels: INHERIT Inherit, NONE No permissions, VIEW View, DOWNLOAD Download, UPLOAD Upload, EDIT Edit, MANAGE Manage, SYNC Synchronize, CUSTOM Custom. This is a shared enum; forms must use each endpoint's allowed subset. For ACLs, prefer `acl_form.presetOptionList`; direct sharing allows only VIEW/DOWNLOAD/UPLOAD/EDIT. See [acl.md](acl.md) for inheritance and revocation; NONE is not a global access denial.
