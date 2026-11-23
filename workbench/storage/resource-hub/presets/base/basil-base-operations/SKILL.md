---
name: "basil-base-operations"
description: "Manage Basil Base multi-dimensional tables, including Bases, tables, fields, views, and records. Use when a request mentions Basil Base or multi-dimensional tables (including requests in other languages)."
---

# Basil Base CLI

This Skill is self-contained. Resolve packaged scripts and references from this folder and pass one JSON object on stdin, never as a command-line argument. Use the packaged capability scripts for API calls.

## Required first action

Immediately after loading this Skill for a business task, call `session_status({})`, then execute `scripts/auth/status.py` using the stdin example below. Do not run a business script with empty stdin or before checking authorization. A configured credential is reused; first use of this Skill does not necessarily mean the user has no stored authorization. If credentials are missing, continue the Bootstrap recovery proactively. Do not ask whether to check authorization or read the contract.

## Bootstrap

Before any business script, complete this sequence in the current Run/Attempt: `session_status({})` → `scripts/auth/status.py` via stdin → resolve missing credentials → read the selected capability reference → execute its operation. Do this proactively for the user's task; do not ask whether to check authorization. Loading this Skill is not an authorization check. After a personal-token form resumes execution, obtain the current domain again before checking status. Successful native OAuth authorization resumes the suspended task in a new Attempt with refreshed credentials; no extra user message is required.

At the start of each Run/Attempt, call Workbench `session_status` with `{}`. Pass its unchanged `domain` as top-level `_runtimeDomain` on every API script input, including status. Never reuse another Run/Attempt's domain, guess a host, accept a substitute URL, or store the domain in packaged configuration. If the tool or valid domain is missing, stop and report the missing Runtime context. Capability examples omit this shared control; add it when executing them.

Run `scripts/auth/status.py` with `{"_runtimeDomain":"<session_status.domain>"}` through foreground Runtime exec (`background=false`). Status checks local availability, not remote access. Both Apps share provider `basilos`: default `_authMode=auto` prefers injected `APP_OAUTH_BASILOS_ACCESS_TOKEN`, then reuses an already configured `APP_BASILOS_PERSONAL_TOKEN`. If neither is usable, or a business request returns HTTP 401, use the conversation OAuth2 authorization card below unless the user explicitly requests personal-token authorization. Reusing an existing personal token does not authorize collecting a replacement. Missing injection, OAuth2 unavailability or an authorization-card failure never authorizes personal-token collection.

### Connect Base in the conversation

When OAuth2 connection is required, actually invoke Workbench `request_user_input` with exactly:

```json
{"title":"连接 Base","description":"授权后继续访问你的 Base 数据。","authorization":{"type":"app_oauth","appKey":"multidimensional-table"},"fields":[]}
```

Workbench displays the native authorization card and handles the trusted OAuth page. Do not combine this request with credentialKey, resourceRefresh, password fields or ordinary fields. Do not use app.connection.ensure as the card operation, fabricate an authorization URL, or ask the user to send Continue.

On authorization.status=authorized, the suspended task resumes in a new Attempt with refreshed credentials. Obtain its current domain with session_status({}), rerun status, verify one small read-only request, and continue the original task. Before retrying a write with an unknown outcome, follow its capability recovery contract. On declined or outcome=skipped/timed_out, respect the decision and continue only independent work; on failed, report the connection failure. Do not automatically repeat authorization or treat skip/timeout as consent. If request_user_input or its authorization schema is unavailable, report the specific host capability issue and stop credential-dependent work; do not silently choose personal-token fallback.

Only when the user explicitly asks to use or fill in a personal token, follow `references/auth.md`: check status with `_authMode=personal_token` and reuse an available token without a form. If no usable personal token is available within this explicitly requested workflow, run `scripts/auth/personal_token.py` with `{}` (or reuse the same locally generated next_action from missing/rejected personal-token output), then actually invoke Workbench `request_user_input` with the returned fixed password-form arguments. Do not just display the JSON. Preserve its title, description and field arguments unchanged, including the instructions to open Library, sign in with the Library account, open the bottom-left profile panel, select “Personal token”, and paste the token into the secure field. The form uses `credentialKey=app.basilos.personal-token` and injects `APP_BASILOS_PERSONAL_TOKEN`. Never collect tokens in chat, stdin, arguments or files, or substitute an ordinary question tool for the Workbench password form. If the secure tool is unavailable or cancelled, stop credential-dependent work.

After successful personal-token submission, resume with newly injected credentials and the new Run/Attempt's domain, rerun status, and verify a small read-only request before continuing the original task. If injection is still missing, stop instead of reopening the form. After the user explicitly chooses personal-token authorization, pass `_authMode=personal_token` on status and every subsequent business call, including after resumption, so rejected OAuth2 still in the environment is not reselected. Scripts never store or refresh credentials or replay HTTP failures under another identity. Use `references/auth.md` for bounded recovery: successful native OAuth authorization resumes with refreshed credentials in a new Attempt; personal-token HTTP 401 allows at most one replacement form per task only when the user explicitly chose personal-token authorization; permission/rate-limit and network failures do not request new credentials.

Local helpers that make no API call do not need a domain. Normal authorized calls do not require reading auth.md, README.md, OAUTH_SETUP.md or source code.

## Passing script input

Runtime exec `arguments` supplies program argv; it does not supply Python stdin. Direct Python execution is valid only when the tool supplies the complete JSON to stdin. Without that facility, use the shell example below; executing only the script path with no input is not a valid call. Never put an operation name or JSON after the script path. If using an argv-only exec tool, explicitly launch a shell with a quoted here-document, for example:

```json
{
  "executable": "/bin/sh",
  "arguments": ["-c", "exec /opt/sandbox-python/bin/python3 scripts/auth/status.py <<'BASIL_INPUT'\n{\"_runtimeDomain\":\"<current session_status.domain>\"}\nBASIL_INPUT"],
  "cwd": "resources/apps/basil-base-operations",
  "background": false
}
```

Resolve cwd from the loaded Skill location; the example shows its App path. Replace the domain placeholder with the actual current result. Use the Python path available in the Runtime. The quoted delimiter prevents shell expansion; encode input as valid JSON and choose a delimiter absent as a line in the payload. This transports non-secret inputs only; credentials remain host-injected. Use the same input transport for business scripts and `{}` for the local personal-token helper.

`INPUT_CHANNEL_ERROR` means the invocation must be corrected, not that login or the domain is invalid. No API request was made by that rejected invocation. Complete any skipped Bootstrap steps and correct the input locally once; do not ask the user to supply operation names, JSON or permission to read the reference. If the corrected call still cannot receive stdin, stop with that specific Runtime limitation rather than looping or requesting replacement credentials. On a missing-domain error after session_status succeeded, check whether JSON actually reached stdin and includes `_runtimeDomain`; fix that local input error without switching credentials or asking for a domain. A truly missing/invalid session domain still stops Bootstrap. Read structured stdout even when exec reports process completion or a nonzero exit code.

## Business context

Base organizes structured business data into Bases, tables, fields, records and views. Field definitions, record values and view settings are distinct objects. Read [business-context.md](references/business-context.md) only when the user's wording leaves the business object or intended change unclear. After Bootstrap, clear capability requests use the Route below directly; this background adds no API capability and does not replace the selected contract or execution policies.

## Route

Read only the matching capability reference unless the task actually spans capabilities. Do not reconstruct parameters from implementation files.

| User intent | Reference | Script | Operation |
| --- | --- | --- | --- |
| List, inspect or manage Bases | `references/databases.md` | `scripts/base/databases.py` | `base_*` |
| Work with data tables | `references/tables.md` | `scripts/base/tables.py` | `table_*` |
| Work with field definitions | `references/fields.md` | `scripts/base/fields.py` | `field_*` |
| Manage standalone views | `references/views.md` | `scripts/base/views.py` | `view_list`, `view_get`, `view_create`, `view_update`, `view_delete` |
| Query records and deliver the matching result view | `references/record-query.md` | `scripts/base/records.py`, then `scripts/base/views.py` | `record_query`, then `view_create_query_result` |
| Upload a local file for an attachment field | `references/records.md` | `scripts/base/records.py` | `record_attachment_upload` |
| Read, aggregate, create, update or delete records | `references/records.md` | `scripts/base/records.py` | other `record_*` operations |

Resolve missing parent IDs before child capabilities: Base → table → field/view/record. Reuse verified IDs; do not rediscover known parents unnecessarily.

## Global execution rules

Use only the selected contract's parameters and pagination. Preserve exact ID strings without floating-point conversion. Do not invent IDs, operators, permissions, totals or links. Correct errors only with contract/response evidence; never remove requested conditions to force success. Interpret script output using its capability contract, not process exit code alone.

## Mutation policy

For standalone create, upload, update or delete, inspect the target, state the exact change, obtain confirmation and pass `_confirm=true`. Destructive operations also require a matching non-empty `_target`; the script cannot verify that its description matches the user's confirmation.

A query request authorizes `view_create_query_result` for that query's matching `display=false` result view without separate confirmation or `_confirm`. This exception does not authorize standalone view mutations, sharing, publishing or record edits.

## Query decisions

Follow `references/record-query.md`: query first, inspect the result, and create its view from resultFile only after accepting that query as answering the request. Exploratory queries do not need views. For a non-empty accepted query, delivery is incomplete until its valid result link is returned. Inspect workflow status; query success is not view/link success. Recover from the saved result rather than rerunning queries or blindly repeating creation after an ambiguous failure. If faithful delivery is blocked, explain the blocker; a summary or guessed URL cannot substitute for the required link.

## Result delivery

For an accepted non-empty record query, run view_create_query_result using the saved resultFile and deliver its returned snapshotLink. Returning records alone is incomplete; do not ask whether the user wants the link or silently skip creation.

Call a returned snapshotLink the **query result**, in the user's language, for example `[查看查询结果](<returned URL>)` or `[View query results](<returned URL>)`. Use the exact script-returned URL. Do not expose the internal field name, call it “快照链接” / “snapshot link”, or explain hidden views/snapshot mechanics unless asked or needed to explain a limitation. Empty or failed queries do not establish a valid result link.

Before sending a response containing query-result links, check the entire reply:

- Each distinct result URL appears once, as a standalone Markdown link on its own unindented line, with blank lines before/after when surrounded by other content.
- Nothing else may share that line: no labels, explanation, punctuation or other links. Put explanations in separate paragraphs.
- Never place it inside a table, list, blockquote, heading, code block, footnote or inline sentence. This rule still applies when the rest of the reply is structured.

## Failure routing

- Missing/rejected authorization or credential injection: `references/auth.md`.
- Missing/invalid runtime domain: stop at Bootstrap; do not substitute a host.
- Network timeout or `network_egress:not_declared`: stop and report egress/routing prerequisites. Do not request new credentials, switch identity or infer token validity from transport failure; use auth.md for recovery classification.
- Capability validation, permissions, conflict or pagination errors: use the selected reference. Do not invent endpoints or retry an unchanged failure.
- Unlisted operations are unsupported by this Skill. Report the capability gap.
