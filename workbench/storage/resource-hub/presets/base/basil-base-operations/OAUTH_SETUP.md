# Built-in App OAuth2 deployment

## Control-plane configuration

The App package root is one level above this document and contains `../manifest.yaml` and `../oauth-clients.yaml`. Both apps use `app.authProviderKey: basilos`; the client entry must have `key: basilos`, `authType: oauth2`, and non-empty provider-issued `clientId` and `clientSecret`. Keep client configuration at the App package root. Never copy it into a member Skill, documentation or scripts. Business scripts never read the client file; they use only credentials injected by Workbench.

The manifest supplies authorization, token, refresh, user-info and unbind URLs, the Workbench backend callback (`/basilcraw/api/apps/oauth2/callback`) and frontend result URL. Register the exact manifest callback with BasilOS. Use the manifest's `clientAuthMethod: basic`, form token request and PKCE settings. The requested scopes remain `id`, `username`, `nickname`, `email`; confirm business permissions with the provider.

The page flow reads standard OAuth response fields: required `access_token`, optional `refresh_token`, `token_type`, `scope`, `expires_in`. App manifest action declarations are not required for credential injection. Conversation authorization requires Workbench `request_user_input` with `authorization={"type":"app_oauth","appKey":"multidimensional-table"}` and `fields:[]`, the native authorization-card renderer, and automatic resumption of the suspended task in a new Attempt with refreshed credentials. The Agent must use this card contract, not call `app.connection.ensure` or `workbench_action_search` / `workbench_action_execute` to initiate authorization. Publishing this Skill does not deploy those host capabilities.

To verify this flow, start a Base conversation without injected credentials and confirm the Skill invokes the native request_user_input OAuth2 authorization card for multidimensional-table. Complete OAuth2 and verify the suspended task resumes automatically in a new Attempt with refreshed credentials, without an extra user message. The resumed Attempt must rerun status and verify an appropriate read-only request before business work. The resource-page OAuth entry remains available for administrator verification; an already running Attempt does not receive later credential updates.

The existing built-in `configure:builtin-apps` deployment process may supply `BASILOS_OAUTH_CLIENT_ID` and `BASILOS_OAUTH_CLIENT_SECRET`; generic YAML loading does not interpolate `${ENV_NAME}`. Confirm the target deployment actually runs its configured generation process. Do not put user Tokens in either YAML file.

## Runtime and deployment addresses

The host's session_status must return the current HTTPS origin exposing `/typekey/api/v1`. Agent bootstrap and domain lifetime are specified in SKILL.md; Agent recovery is specified in references/auth.md. The runtime owns URL validation and prefix assembly and never reads the parent manifest. Control-plane OAuth must authorize the backend exposed by that session origin; OAuth endpoint origins may differ. Never derive provider URLs by guessing or rewrite result-link origins.

Workbench injects `APP_OAUTH_BASILOS_*` at the start of each Runtime Attempt. Both apps share this App-provider prefix for the same user. A Connector with the same provider is a different authorization source. Confirm the environment injection implementation is deployed before distributing this package.

## Sandbox network access

Personal-token authorization uses the Runtime password form only when the user explicitly requests that method. OAuth2 or authorization-card unavailability does not permit automatic personal-token collection. Verify the injection contract below and the Agent recovery workflow in references/auth.md before enabling this optional host capability.

Before business verification, configure the Runtime's supported outbound-network policy for the confirmed BasilOS API destination and verify routing from the actual Sandbox. A resolved API URL and OAuth Token injection do not grant network access. Read the current destination from authorization status with the current `_runtimeDomain`; verify reachability from the deployed Sandbox network.

A platform `network_egress:not_declared` diagnostic requires checking Runtime network configuration. A TCP timeout can also result from routing, firewall, service or port issues. This package does not contain the Runtime policy schema; no unverified network fields are added to the App manifest. Apply the supported configuration at its documented deployment layer and verify that it takes effect for a new execution before testing OAuth-protected business requests.

## Git import and publication layout

`.workbench/apps.json` points to `apps/base`, which becomes the App snapshot root. Preserve the complete first-level `basil-base-operations/` member, including `basil-base-operations/SKILL.md`, and keep `manifest.yaml`, `oauth-clients.yaml`, and `icon.svg` at the App root. Do not add a `skills/` wrapper for Git import or copy only `SKILL.md`. The `skills/<member>/SKILL.md` layout is compatible with non-Git drafts and historical package publication, but does not satisfy Git discovery.

## Runtime layout

Workbench mounts only `basil-base-operations/`. Keep its scripts and references together, including `scripts/runtime/service.py`. The member does not depend on parent App files or the Sandbox's working directory. Deploy the member together to avoid mixing entrypoints and shared runtime modules from different versions.

If only a Refresh Token is injected, update authorization through Workbench. Sandbox scripts never refresh or persist Tokens; refresh rotation without a control-plane writeback can invalidate Workbench's stored refresh credential. An existing running Attempt never receives credentials from a later page update. Offline tests do not establish that the target deployment or live OAuth flow works.

## Credential injection contract

The runtime prefers APP_OAUTH_BASILOS_ACCESS_TOKEN; TOKEN_TYPE is optional and must be Bearer when present. EXPIRES_AT is optional and must be timezone-aware ISO 8601. SCOPE is optional metadata; REFRESH_TOKEN is inspected only for presence. These suffixes all use APP_OAUTH_BASILOS_. Workbench owns refresh and revocation. An already injected APP_BASILOS_PERSONAL_TOKEN is the fallback, selected only according to the runtime's auth mode and availability rules. Requests send exactly one authorization header: Authorization: Bearer for OAuth2 or auth-token for the personal token. Never place client secrets or user tokens inside the member.

The fixed personal-token form is generated by scripts/auth/personal_token.py; verify that the host supports its password fields and injects the submitted secret into the resumed Attempt. Authentication recovery decisions belong to references/auth.md; deployment documentation must not become a normal Agent execution prerequisite.
