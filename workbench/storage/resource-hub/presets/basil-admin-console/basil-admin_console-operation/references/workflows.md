# Cross-capability workflows

These workflows compose existing operations without adding hidden remote calls. Check each business result; pause at the decision point if execution requires changing scope.

For missing inputs, follow [interaction.md](interaction.md) and the capability's candidate rules. Construct complete requests by reading and merging current state; do not make users re-enter existing information or reselect unchanged permissions. Forms handle only unresolved business decisions.

## Add a system role to an existing user

1. Query `user_page` by username and paginate to an exact match. Preserve id, username, nickname, jobTitle, leaderId, email, departmentList, systemRoleList, and user-level permissions. Do not write to the first fuzzy match.
2. Use `system_role_options` / `system_role_page` to verify the role is a SystemRole. Convert departmentList[].id and systemRoleList[].id to string lists and merge the target role; do not submit whole nested response objects.
3. Build `user_update` within user authorization, explicitly preserving all overwrite-prone fields. Use null only for genuinely empty or explicitly cleared information. The merged systemRoleIdList fully replaces roles; [] does not clear existing roles. Do not write if complete current values cannot be read.
4. Reread the user row to verify associations. To remove a role, subtract its ID using the same process; if the result would be empty, report that the public endpoint cannot clear all roles, without substituting the default role.

## Role and TEAM folder authorization

1. Establish the requested function permissions and resource actions. Query `system_role_page`, using `system_role_create` if necessary. Obtain permissionList from [permissions.md](permissions.md); creation returns only a boolean, so query the exact name for its ID.
2. Use `acl_form` for roleOptionList, departmentTree, folderTree, presetOptionList, and actionOptionList. Select real TEAM folders and valid subjects; departments include subdepartment members and must match user scope.
3. For existing configurations, read complete roles/departments/ruleList with `acl_detail`, then use `acl_form(permissionId)` to check folder candidates and existing values. Do not turn every inherited/effective computed value into an explicit rule. Query by name/ID after creation or update.
4. Merge SystemRoles into existing users using the preceding workflow; do not create demonstration users when only existing-subject authorization was requested.
5. `effective_permissions` must use the target user's own current authorization. Administrators can verify configuration but cannot prove another user's effective access. Without that user's own verification, state: "Configuration saved; target-user effective permissions have not been verified."

## Revoke access

First identify the source: SystemRole menu permissions, user-role membership, ACL configuration/rules, or direct user/department shares. Remove a rule or use INHERIT to remove this configuration's explicit folder rule; use NONE to block inheritance within this configuration branch. Other sources may still grant access; do not claim a global block.

ACL updates submit complete subjects and rules. Menu-permission changes convert the role row's permissionIdList to request permissionList for full replacement. For direct shares, query the grant with `share_page`, then update/delete using current grantId/version; updates must retain the original subject. Reread configuration/direct grants afterward; final access checks, if needed, must be performed by the corresponding user.

## Department moves, deletion, and leaders

First read `department_tree(withUser=true)`. Verify the target exists, the parent is real and outside the target subtree, and the root is not being moved. Select leaders from direct department members. For deletion, inspect the whole subtree and membership and explain the impact. Do not use the abnormal deleteUserDepartment route to remove members; remove department associations through user_update while preserving other data. Without another department, the server returns the user to root department 0.

## Sensitive account operations

Before administrator transfer, verify the current user is the platform administrator and the successor exists and is ENABLE. Before password reset, verify the target is not the platform administrator. For SSO unbinding, read the binding and verify ownership. Disabling invalidates existing sessions; reread status afterward. `data=true` does not prove an unknown userId was updated.
