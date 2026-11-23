# Library folder management

Use `scripts/library/folders.py` under SKILL.md’s mutation policy. Resolve visible targets, IDs and current versions from explicit `folder_tree` attributes in `folder-tree.md`; space/path boundaries are in `directory-context.md`. Never guess or increment versions.

| Operation | Endpoint | Required body | Permission |
| --- | --- | --- | --- |
| `folder_create` | `PUT /openapi/assets/folder/save` | `parentId`, `name`, `parentVersion` | `auth.library.folder.save` |
| `folder_rename` | `PUT /openapi/assets/folder/rename` | `folderId`, `newName`, `version`, `parentVersion` | `auth.library.folder.rename` |
| `folder_move` | `PUT /openapi/assets/folder/move` | `folderId`, `version`, `parentVersion`, `targetParentVersion`; optional `targetParentId` | `auth.library.folder.move` |
| `folder_delete` | `DELETE /openapi/assets/folder` | `folderId`, `version`, `parentVersion` | `auth.library.folder.delete` |

## Version handoff and execution

Select the intended node in the current response. In the table below, F is the folder being changed and P is the destination parent. Keep IDs as strings and copy versions exactly, including an explicit integer zero.

| Operation | Mapping from tree attributes to request body |
| --- | --- |
| `folder_create` | `parentId=P.folder_id`, `parentVersion=P.version` |
| `folder_rename`, `folder_delete` | `folderId=F.folder_id`, `version=F.version`, `parentVersion=F.parentVersion` |
| `folder_move` | Source fields as above, plus `targetParentId=P.folder_id`, `targetParentVersion=P.version` |

Creation uses P’s `version`, not its `parentVersion`: P with `version=3`, `parentVersion=0` requires request `parentVersion=3`. Never substitute a child’s version or another folder’s file `folderVersion`.

1. Read the relevant tree(s) and resolve the target within the visible space. For the current personal root, use `spaceType=MY` without `folderPath`. Verify the returned node belongs to that space; never fall back to TEAM.
2. Obtain every required version using the mapping above. If a required field is absent or null, stop before writing and report which folder/version is unavailable. Older tree responses may have IDs without versions; report the missing server capability rather than guessing zero, probing with a write, or repeatedly calling `file_batch` after an empty `folderList`.
3. State the exact change and obtain confirmation as required by SKILL.md, then call the mutation with `_confirm=true` (and `_target` for deletion).
4. Interpret the response before reporting success. On a version conflict, re-read the relevant tree(s), inspect the updated state, and ask the user to confirm again. Do not assume an error contains a usable current version; never automatically retry or overwrite a version. A timeout leaves the outcome uncertain: inspect before any further write, do not replay creation.

`targetParentId=0` means virtual root. **Unresolved ambiguity:** the tree contract returns null versions for virtual Root but does not specify the write-version value for creating or moving directly into it. Do not turn null into zero or infer the write convention from a child's `parentVersion`; report the missing contract when this case blocks execution. This is distinct from a personal root with a real ID and an explicitly returned version.

## Personal-root creation example

Resolve scripts from the loaded Skill directory, not the workspace root. Follow SKILL.md Bootstrap per Run/Attempt and its stdin transport with unchanged `session_status.domain`; never execute Python source as shell commands.

For example, if the loaded Skill is `/workspace/resources/apps/basil-library-operations`, run `resources/apps/basil-library-operations/scripts/library/folder_tree.py` with:

```json
{
  "_runtimeDomain": "<session_status.domain>",
  "operation": "folder_tree",
  "query": {"spaceType": "MY"}
}
```

Suppose the actual response identifies the intended personal root as `folder_id=2089982124722622490`, `version=7`, `parentVersion=2`. After confirmation, run `resources/apps/basil-library-operations/scripts/library/folders.py` with:

```json
{
  "_runtimeDomain": "<session_status.domain>",
  "operation": "folder_create",
  "body": {
    "parentId": "2089982124722622490",
    "name": "0923-14:57",
    "parentVersion": 7
  },
  "_confirm": true
}
```

The ID and versions above are illustrative, not defaults or evidence about the current user. Replace them only with values from the current tree response.

## Move boundaries

Before `folder_move`, inspect source and target under `directory-context.md`: moves stay within the same `MY`, `TEAM` or `SHARED` space, never across personal spaces. Do not retry cross-space errors; copy requires a separately documented capability and explicit intent. Administrator access does not expose others’ personal spaces.
