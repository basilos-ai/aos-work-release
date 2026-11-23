# Built-in App OAuth2 deployment

## Control-plane configuration

The App package root is one level above this document and contains `../manifest.yaml` and `../oauth-clients.yaml`. Both apps use `app.authProviderKey: basilos`; the client entry must have `key: basilos`, `authType: oauth2`, and non-empty provider-issued `clientId` and `clientSecret`. Keep client configuration at the App package root. Never copy it into a member Skill, documentation or scripts; Workbench excludes the root client file from Runtime materialization.

The manifest supplies authorization, token, refresh, user-info and unbind URLs, the Workbench backend callback (`/basilcraw/api/apps/oauth2/callback`) and frontend result URL. Register the exact manifest callback with BasilOS. Use the manifest's `clientAuthMethod: basic`, form token request and PKCE settings. The requested scopes remain `id`, `username`, `nickname`, `email`; confirm business permissions with the provider.

The page flow reads standard OAuth response fields: required `access_token`, optional `refresh_token`, `token_type`, `scope`, `expires_in`. App manifest action declarations are not required for credential injection. Conversation authorization requires Workbench `request_user_input` with `authorization={"type":"app_oauth","appKey":"library"}` and `fields:[]`, the native authorization-card renderer, and automatic resumption of the suspended task in a new Attempt with refreshed credentials. The Agent must use this card contract, not call `app.connection.ensure` or `workbench_action_search` / `workbench_action_execute` to initiate authorization. Publishing this Skill does not deploy those host capabilities.

The existing built-in `configure:builtin-apps` deployment process may supply `BASILOS_OAUTH_CLIENT_ID` and `BASILOS_OAUTH_CLIENT_SECRET`; generic YAML loading does not interpolate `${ENV_NAME}`. Confirm the target deployment actually runs its configured generation process. Do not put user Tokens in either YAML file.

## Runtime and deployment addresses

The host's session_status must return the current HTTPS origin exposing `/typekey/api/v1`. Agent bootstrap and domain lifetime are specified in SKILL.md; Agent recovery is specified in references/auth.md. The runtime owns URL validation and prefix assembly and never reads the parent manifest. Control-plane OAuth must authorize the backend exposed by that session origin; OAuth endpoint origins may differ. Never derive provider URLs by guessing or rewrite result-link origins.

Workbench injects `APP_OAUTH_BASILOS_*` at the start of each Runtime Attempt. Both apps share this App-provider prefix for the same user. A Connector with the same provider is a different authorization source. Confirm the environment injection implementation is deployed before distributing this package.

## Sandbox network access

Personal-token authorization uses the Runtime password form only when the user explicitly requests that method. OAuth2 or authorization-card unavailability does not permit automatic personal-token collection. Verify the injection contract below and the Agent recovery workflow in references/auth.md before enabling this optional host capability.

Before business verification, configure the Runtime's supported outbound-network policy for the confirmed BasilOS API destination and verify routing from the actual Sandbox. A resolved API URL and OAuth Token injection do not grant network access. Read the current destination from authorization status with the current `_runtimeDomain`; verify reachability from the deployed Sandbox network.

A platform `network_egress:not_declared` diagnostic requires checking Runtime network configuration. A TCP timeout can also result from routing, firewall, service or port issues. This package does not contain the Runtime policy schema; no unverified network fields are added to the App manifest. Apply the supported configuration at its documented deployment layer and verify that it takes effect for a new execution before testing OAuth-protected business requests.

## Publish and verify

1. Validate the manifest, provider/client key match, exact registered callback, and API base configuration. In this source tree the member is directly under the App root at `basil-library-operations/SKILL.md` (this document is inside that member). Git import and publication use the first-level member `basil-library-operations/SKILL.md`. Preserve the complete member directory and keep `manifest.yaml`, `oauth-clients.yaml`, and `icon.svg` at the App root (`apps/library` in this repository). Do not add a `skills/` wrapper, copy only `SKILL.md`, or place the client file inside the member. The `skills/<member>/SKILL.md` layout is supported for non-Git drafts and historical package publication only; it does not satisfy Git discovery.
2. Publish a new resource version and confirm the test user has that version.
3. Install/enable the App. In a conversation without injected credentials, verify that the Skill invokes the native request_user_input OAuth2 authorization card for library. Complete OAuth2 and confirm the suspended task resumes automatically in a new Attempt with refreshed credentials, without an extra user message. The existing resource-page OAuth entry remains available for administrator verification.
4. In the resumed Attempt, call `session_status({})`, then run the member's `scripts/auth/status.py` with `{"_runtimeDomain":"<session_status.domain>"}` via foreground `exec` (`background=false`), then make one read-only business call.
5. Confirm the intended account, scopes, data and absence of credentials in output. Verify refresh/revocation through Workbench, then use a new Attempt.

If only a Refresh Token is injected, update authorization through Workbench. Sandbox scripts never refresh or persist Tokens; refresh rotation without a control-plane writeback can invalidate Workbench's stored refresh credential. An existing running Attempt never receives credentials from a later page update. Offline tests do not establish that the target deployment or live OAuth flow works.

## Credential injection contract

The runtime prefers APP_OAUTH_BASILOS_ACCESS_TOKEN; TOKEN_TYPE is optional and must be Bearer when present. EXPIRES_AT is optional and must be timezone-aware ISO 8601. SCOPE is optional metadata; REFRESH_TOKEN is inspected only for presence. These suffixes all use APP_OAUTH_BASILOS_. Workbench owns refresh and revocation. An already injected APP_BASILOS_PERSONAL_TOKEN is the fallback, selected only according to the runtime's auth mode and availability rules. Requests send exactly one authorization header: Authorization: Bearer for OAuth2 or auth-token for the personal token. Never place client secrets or user tokens inside the member.

The fixed personal-token form is generated by scripts/auth/personal_token.py; verify that the host supports its password fields and injects the submitted secret into the resumed Attempt. Authentication recovery decisions belong to references/auth.md; deployment documentation must not become a normal Agent execution prerequisite.
