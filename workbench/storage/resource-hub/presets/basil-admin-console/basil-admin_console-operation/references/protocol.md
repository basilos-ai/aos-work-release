# Invocation protocol

First follow Bootstrap in SKILL.md. Standard-library Python only, with no external or parent-manifest dependencies. The CLI accepts one object on stdin:

```json
{
  "_runtimeDomain": "<current session_status.domain>",
  "operation": "user_page",
  "query": {"page": 1, "size": 20, "username": "<user-specified username>"}
}
```

Run from this Skill's root:

```sh
python3 scripts/admin_console/cli.py <<'ADMIN_INPUT'
{"_runtimeDomain":"<current session_status.domain>","operation":"system_role_page","query":{"page":1,"size":20}}
ADMIN_INPUT
```

Placeholders are not executable environment values. Runtime `exec.arguments` is not stdin; argv-only hosts must use the SKILL shell-heredoc format with `background=false`. Every API input carries the current `_runtimeDomain`; use `_authMode=auto|oauth2|personal_token` as applicable. Other controls are positive `_timeout`, `_confirm=true` for writes, and `_target` for sensitive operations.

- `path`, `query`, and `body` are not interchangeable. Submit only business fields allowed by the selected contract; scripts reject unknown fields. Do not add tokens, headers, endpoints, or another user's identity.
- The two bulk endpoints `user_batch_create` / `department_members_append` require nonempty body arrays with documented fields in each item.
- `folder_page_post` pagination remains in query; body is the optional metadata-filter object itself, without a metadataFilterVO wrapper.
- `icon_upload` uses top-level `file_path` and optional `filename`, not JSON body; the script builds multipart and normalizes the raw URL to `{success:true,code:0,data:URL}`.
- page is 1-based, size 1..1000; both directory sizes and received-share size are capped at 100. Continue using server addition.total/page/size or pageInfo.hasMore/nextCursor. Advance folder/file cursors independently and reset them when filters change; do not parse or invent opaque share cursors. Set a reasonable call limit and clearly report incomplete results. Investigate repeated cursors/pages or changed totals rather than claiming completeness.
- Normal success requires success=true and code=0; preserve data/addition. Missing objects may return data=null, which does not prove existence. Output removes nested entity authentication fields while retaining the result of an explicitly requested password reset.
- Request IDs are decimal strings; page, size, and version are JSON integers. Query arrays use repeated parameters; booleans use lowercase true/false.
- Omission, null, and empty arrays are not universally equivalent; follow endpoint overwrite semantics. Scripts additionally require explicit overwritten fields for dangerous updates; do not claim these are server validations.
- No universal idempotency-key or rate-limit retry guarantee. After failure/timeout, read current target state before proceeding; do not automatically replay creation/grant/deletion. On share-grant version conflict, reread state, check user intent, then submit the newly read version; never increment a guessed version.

## Failure classification

Local input errors send no request. Script failures return success=false,error, possibly details.httpStatus/code/errorKey or authentication next_action, with exit code 1. Read structured stdout, not only the exit code.

- HTTP401: Restore the current user's authorization per auth.md; do not switch identities and automatically retry.
- HTTP400 + code403: Insufficient system permissions; permission checks may also be needed for HTTP403.
- HTTP403 + code4004: License error, not token expiration.
- code4001 / version.conflict: Reread version and state.
- code1001/1002/1003/1005: Check types, locations, and parameters; do not try writes with guessed replacements.
- 503 / authentication.state.unavailable: Identity-state service unavailable; verify write outcomes before proceeding, without automatic replay.
- Network timeout, redirect, or network_egress:not_declared: Report routing/egress issues; do not collect new tokens.

The full error catalog follows the attachment's common protocol; classify business errors by stable code/errorKey, not localized message text.
