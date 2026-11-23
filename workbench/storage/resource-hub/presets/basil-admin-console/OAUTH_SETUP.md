# Basil-admin-console OAuth2 deployment

## Binding and evidence

Application owner: the existing Workbench/BasilOS operator. Tenant model: the configured internal deployment and current user. Authentication uses the user authorization-code flow, not client credentials. This Connector deliberately binds to the existing Library App authorization: `appKey=library`, provider `basilos`, native `app_oauth` card. Connection identity: that documented Library binding; no new Connector OAuth identity is registered. Static credentials retain `app.basilos.personal-token` and `APP_BASILOS_PERSONAL_TOKEN`. This package-specific exception is approved; do not generalize it to other resources.

The selected provider-call channel is foreground `runtime_environment`. Workbench injects credentials at Attempt start, and business calls use the current `session_status.domain` plus `/typekey/api/v1`. Scripts do not inspect Library's directory, manifest, client configuration or storage. The host must explicitly allow this Connector to receive the same declared injection names in its own sandbox; an App's working injection is not evidence that the Connector deployment is configured.

## Existing control-plane contract

The reference deployment uses these non-secret settings. They are operator evidence, not runtime fallback addresses. Confirm them against the target environment before enabling the Connector.

| Setting | Reference deployment |
| --- | --- |
| Authorization endpoint | `https://basilos.gateway.tyrion.cloud/typekey/api/v1/oauth2/authorize` |
| Token and refresh endpoint | `https://basilos.gateway.tyrion.cloud/typekey/api/v1/oauth2/token` |
| User-info endpoint | `https://basilos.gateway.tyrion.cloud/typekey/api/v1/oauth2/userinfo` |
| Revocation/unbind endpoint | `https://basilos.gateway.tyrion.cloud/typekey/api/v1/oauth2/bindings/current` |
| Redirect URI | `https://workbench.tyrion.cloud/basilcraw/api/apps/oauth2/callback` |
| Frontend result origin | `https://workbench.tyrion.cloud` |
| Minimum scopes declared by this integration | `id username nickname email` |
| Client authentication | HTTP Basic, form token request |
| PKCE | Enabled; verify deployed S256 behavior and state validation |
| Token response metadata | Standard access/refresh token fields, token type, expiry and scopes |

Managed Runtime owns the native authorization card, trusted provider page, callback, state validation, PKCE, token exchange, encrypted storage, silent refresh, rotation and revocation. No client secret or client registration is packaged. The operator must confirm the existing client registration, approved redirect URI, scope approval, test-user/organization access and account binding. Business system permissions remain separate from these identity scopes.

## Native card and fresh credential delivery

The native Tool is `request_user_input` with `authorization={"type":"app_oauth","appKey":"library"}` and `fields=[]`. The exact interaction and cancellation rules are in [authorization](basil-admin_console-operation/references/auth.md). The host must permit this special binding from a Connector and resume the suspended task automatically after callback.

Fresh credential delivery uses a new Attempt with `APP_OAUTH_BASILOS_ACCESS_TOKEN`, optional `TOKEN_TYPE`, `EXPIRES_AT`, `SCOPE`, and refresh-token presence under the same prefix. `EXPIRES_AT` must be timezone-aware ISO 8601. Never update a running process by exposing credentials to the Agent. After resume, reacquire the current session domain, status and read-only verification via `/user/readAuthCurrentUser`.

## Managed refresh contract and unresolved adapter

The reference configuration declares a refresh endpoint and platform ownership. It does not expose a verified callable managed-refresh Tool, automatic refresh trigger/status API, rotation transaction or concurrency implementation. Consequently `scripts/auth/recovery.py` is a local policy helper only, and status reports `managed_refresh_adapter_verified=false`. A returned refresh action has not been executed. This package is not verified ready for unattended long-lived OAuth use until the operator supplies and tests the following host behavior:

1. Read provider/host expiry metadata and refresh ahead of expiry (member margin: 60 seconds). Confirm whether and under what consent/scope conditions the provider issues refresh grants; do not add offline-access parameters without evidence.
2. Exchange at the verified HTTPS token endpoint using `grant_type=refresh_token` and the configured client authentication, without expanding scopes. The managed Runtime performs this, never a sandbox script.
3. Atomically save replacement access/expiry/refresh data. Retain the old refresh grant only when no replacement is returned and the provider permits it. Serialize or coordinate simultaneous refreshes so stale results cannot overwrite newer credentials.
4. On an unknown outcome, reconcile platform connection generation/state before reusing a previous refresh grant. Bound network/429/5xx retries; invalid grant or revocation requires bounded reauthorization rather than a loop.
5. Deliver the new access credential through documented new-Attempt resumption/injection. Verify it before continuing; no repeated business writes and no stale-process reruns as a refresh substitute.
6. Provide the concrete managed status/refresh/resume Tool schema or a documented automatic lifecycle. If absent, the Agent reports `MANAGED_REFRESH_UNVERIFIED`; it must not invent a Tool or implement local refresh persistence.

The policy helper covers refresh-first decisions, cancellation, unknown outcomes and budgets. It cannot prove token rotation, callback behavior or concurrent storage.

## Deployment validation

Dockerfile baseline only; deployed runtime unverified. Python 3.10+ and standard-library modules are sufficient for the packaged business client. Verify the actual sandbox version, HTTPS certificates/egress and current session origin. No extra Python/Node dependency or browser installation is required.

Before declaring the Connector operational, the operator must verify:

- registration permits the special Library authorization binding and exact personal-token identity;
- native card, callback, state/PKCE and automatic resume succeed for the intended current user;
- OAuth and personal-token credentials are separately injected and never logged;
- read-only verification and expected system permission checks work;
- expiry, refresh rotation, concurrent refresh, transient/unknown outcomes, revocation and fresh injection behave as specified;
- refusal, timeout, missing injection and rejected static credentials respect recovery budgets;
- the API is reachable from the actual sandbox through the current session origin.

No live OAuth, credential save, API read, write, import or publication was performed as part of package generation. Offline structure/tests do not establish these deployment properties.
