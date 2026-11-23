---
name: "basil-library-operations"
description: "Search and manage Basil Library assets, files, folders, Metadata, URLs, and MY, TEAM, or SHARED spaces. Use when a request mentions Basil Library, assets, or 网盘."
---

# Basil Library CLI

This Skill is self-contained. Resolve packaged scripts and references from this folder and pass one JSON object on stdin, never as a command-line argument. Use the packaged capability scripts for API calls.

## Bootstrap

For every business task, immediately call Workbench `session_status({})`, then run `scripts/auth/status.py` through the foreground stdin transport below (`background=false`). Complete this sequence in each Run/Attempt before business scripts: current domain → status → resolve missing credentials → read the selected capability reference → execute. Proceed proactively; if credentials are missing, continue Bootstrap recovery proactively. Do not ask whether to check authorization or read the contract. Loading this Skill is not an authorization check.

Pass the current `session_status.domain` unchanged as top-level `_runtimeDomain` on every API script input, including status. Obtain it again after OAuth or password-form resumption. Never reuse another Run/Attempt's domain, guess/substitute a host, or store it in configuration. If session_status or a valid domain is unavailable, stop and report the missing Runtime context. Local helpers making no API call need no domain; capability examples omit this shared control, so add it when executing.

Status checks local availability, not remote access. Both Apps share provider `basilos`; `_authMode=auto` prefers injected `APP_OAUTH_BASILOS_ACCESS_TOKEN`, then an existing `APP_BASILOS_PERSONAL_TOKEN`. Reuse configured credentials, including on first use.

**Before authorization recovery**, read [auth.md](references/auth.md) when neither credential is usable, any business call returns HTTP 401, or the user explicitly requests personal-token authorization. It owns the exact native OAuth card, secure token form, outcome handling and resumption sequence. OAuth2 is the default; missing injection, unavailable OAuth or a failed card never authorizes personal-token collection. Collect a personal token only on explicit user request, through the Workbench secure form, never chat, stdin, arguments or files. In that workflow use `_authMode=personal_token` on status and every business call, including after resumption. Scripts never store/refresh credentials or replay failures under another identity. Preserve unknown write outcomes using the capability recovery contract before retrying.

Normal authorized calls need no auth.md, README.md, OAUTH_SETUP.md or source-code read.

## Passing script input

Runtime exec `arguments` supplies program argv; it does not supply Python stdin. Direct Python execution is valid only when the tool supplies the complete JSON to stdin. Without that facility, use the shell example below; executing only the script path with no input is not a valid call. Never put an operation name or JSON after the script path. If using an argv-only exec tool, explicitly launch a shell with a quoted here-document, for example:

```json
{
  "executable": "/bin/sh",
  "arguments": ["-c", "exec /opt/sandbox-python/bin/python3 scripts/auth/status.py <<'BASIL_INPUT'\n{\"_runtimeDomain\":\"<current session_status.domain>\"}\nBASIL_INPUT"],
  "cwd": "resources/apps/basil-library-operations",
  "background": false
}
```

Resolve cwd from the loaded Skill location; the example shows its App path. Replace the domain placeholder with the actual current result. Use the Python path available in the Runtime. The quoted delimiter prevents shell expansion; encode input as valid JSON and choose a delimiter absent as a line in the payload. This transports non-secret inputs only; credentials remain host-injected. Use the same input transport for business scripts and `{}` for the local personal-token helper.

`INPUT_CHANNEL_ERROR` means the invocation must be corrected, not that login or the domain is invalid. No API request was made by that rejected invocation. Complete any skipped Bootstrap steps and correct the input locally once; do not ask the user to supply operation names, JSON or permission to read the reference. If the corrected call still cannot receive stdin, stop with that specific Runtime limitation rather than looping or requesting replacement credentials. On a missing-domain error after session_status succeeded, check whether JSON actually reached stdin and includes `_runtimeDomain`; fix that local input error without switching credentials or asking for a domain. A truly missing/invalid session domain still stops Bootstrap. Read structured stdout even when exec reports process completion or a nonzero exit code.

## Route

Read only the matching capability reference unless the task actually spans capabilities. Do not reconstruct parameters from implementation files.

| User intent | Reference | Script | Operation |
| --- | --- | --- | --- |
| Search assets and deliver query results | [search.md](references/search.md) | `scripts/library/search.py` → `scripts/library/structured_search.py` | `metadata_catalog` → local Plan → `structured_search` |
| Browse Metadata or obtain the complete catalog | [metadata-catalog.md](references/metadata-catalog.md) | `scripts/library/search.py` | `metadata_fields`, `metadata_catalog` (`view=compact` for mapping) |
| Get asset details by IDs | [file-details.md](references/file-details.md) | `scripts/library/search.py` | `file_batch` |
| Browse or resolve a folder tree | [folder-tree.md](references/folder-tree.md) | `scripts/library/folder_tree.py` | `folder_tree` |
| Get public or presigned file URLs | [file-urls.md](references/file-urls.md) | `scripts/library/file_urls.py` | `file_url_batch` |
| Create, rename, move or delete folders | [folders.md](references/folders.md) | `scripts/library/folders.py` | `folder_create`, `folder_rename`, `folder_move`, `folder_delete` |
| Upload, rename, move or delete files/resources | [files.md](references/files.md) | `scripts/library/files.py` | `file_upload`, `file_rename`, `file_move`, `file_delete`, `delete_batch` |
| Create Metadata fields, list folder tags or change file Metadata | [metadata.md](references/metadata.md) | `scripts/library/metadata.py` | `metadata_field_create`, `folder_tags`, `file_metadata_operate` |
| Search, inspect, create, update or delete Asset Rule Groups / 资产规则组 | [rule-groups.md](references/rule-groups.md) | `scripts/library/rule_groups.py` | `pageRuleGroup`, `getRuleGroupDetail`, `saveRuleGroup`, `updateRuleGroup`, `deleteBatchRuleGroup` |

For paths, spaces, folders, search scope, upload destinations or move boundaries, read [directory-context.md](references/directory-context.md). It covers personal-root resolution (including “个人空间” with no named subfolder), visible paths and same-space moves; use [files.md](references/files.md) for upload destination steps. Resolve obtainable IDs/paths proactively rather than asking the user. ID-only details and URLs rely on server ACLs and need no directory reference. Never infer unseen paths, other users' personal spaces or unshared ancestors. The Workbench credential defines the user; do not supply a user ID to change identity.

## Global execution rules

Use only the selected contract's inputs and pagination. Keep IDs as strings without floating-point conversion. Never invent IDs, paths, Metadata, enum values, permissions, totals or links. Preserve the folder tree's Markdown output. Interpret script output using its capability contract, not process exit code alone.

## Mutation policy

Before create, upload, update, rename, move, Metadata mutation or deletion, inspect the target, state the exact change, obtain confirmation, and pass `_confirm=true`. Destructive operations also need a matching non-empty `_target`; the script cannot verify that its description matches the user's confirmation. For versioned mutations, follow the capability's latest-version and conflict workflow; stop if required versions cannot be obtained. Never guess versions.

## Search decisions

Follow [search.md](references/search.md) for the default search workflow: complete compact Metadata catalog → semantic Plan → direct `structured_search` with `inspectResults=true` → accepted candidate review → all-page review and FILE_ID refinement for targeted requests → final query-level link. Broad exploration uses the accepted ordinary query's link. Keep evidence tied to that accepted query; incomplete review, zero matches or failed refinement never justify broader links, weaker conditions or file-list delivery. Report blocked searches as incomplete.

The session mode linked below is separate and never a mandatory read/ack/review gate for default searches.

## Result delivery

Call a returned snapshotLink the **query result**, in the user's language, for example `[查看查询结果](<returned URL>)` or `[View query results](<returned URL>)`. Use the exact script-returned URL. Do not expose the internal field name, call it “快照链接” / “snapshot link”, or explain hidden views/snapshot mechanics unless asked or needed to explain a limitation. Empty or failed queries do not establish a valid result link.

Before sending a response containing query-result links, check the entire reply:

- Each distinct result URL appears once, as a standalone Markdown link on its own unindented line, with blank lines before/after when surrounded by other content.
- Nothing else may share that line: no labels, explanation, punctuation or other links. Put explanations in separate paragraphs.
- Never place it inside a table, list, blockquote, heading, code block, footnote or inline sentence. This rule still applies when the rest of the reply is structured.

## Failure routing

- Missing/invalid runtime domain: stop at Bootstrap; do not substitute a host.
- Network timeout or `network_egress:not_declared`: stop and report egress/routing prerequisites. Do not request new credentials, switch identity or infer token validity from transport failure; use auth.md for recovery classification.
- Capability validation, permissions, conflict or pagination errors: use the selected reference. Do not invent endpoints or retry an unchanged failure.
- Unlisted operations are unsupported by this Skill. Direct the user to Library `/library` to check available UI operations.

## Other references

- Missing/rejected credentials, explicit personal-token setup, authorization outcomes or Runtime recovery → [auth.md](references/auth.md).
- Unclear business object or intended change → [business-context.md](references/business-context.md); folder location and Metadata classification are distinct. This context adds no API capability or policy override; clear requests route directly.
- Optional bounded search-session mode, chosen at the start only when needed → [search-session.md](references/search-session.md), using `scripts/library/search_workflow.py`: `catalog`, `search`, `read`, `ack`, `next`, `review`, `refine`, `deliver`, `close`. Switching modes cannot bypass incomplete semantic review.
