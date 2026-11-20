# OAuth 2.0 Connector Standard

Use this branch only for a verified OAuth 2.0 authorization-code flow with user consent. Do not classify client credentials, signed service accounts, static tokens, API Keys, or proprietary login flows as user OAuth2.

This is the managed-runtime branch. The Connector describes capabilities and non-secret provider metadata; Workbench Runtime owns the user authorization lifecycle. Do not turn an OAuth2 Connector into a local authentication implementation.

## Responsibility boundary

| Layer | Owns | Must not do |
| --- | --- | --- |
| Provider or application owner | App registration, tenant policy, redirect URI, scopes, review/publication, client-secret rotation | Treat one customer's private client as a public default |
| Workbench administrator/control plane | The original-package `oauth-clients.yaml` entry, protected Client ID/Client Secret storage, and the mapping from `authProviderKey` to the provider application | Expose client secrets to users, Runtime scripts, public packages, logs, or chat |
| Workbench OAuth Runtime | Authorization UI/start, `state`, PKCE, callback routing, code exchange, encrypted token storage, refresh, revocation state, reauthorization, and connection status | Expose tokens or require the member Skill to implement the OAuth protocol |
| Connector member Skill | Capability routing, safe status/verification, user-facing outcomes, and confirmation boundaries | Collect or parse client secrets, authorization codes, access tokens, or refresh tokens |
| Gateway Connector Action or bounded Runtime script | Call the provider with the managed connection | Accept a token as an ordinary Action input or use a local token file |

The target Runtime must provide evidence for the capabilities required by the selected execution channel:

- an OAuth authorization start entry and a resumable callback path;
- `state` validation and PKCE when required by the provider;
- server-side authorization-code exchange and token refresh;
- encrypted connection storage with per-user, per-tenant, or per-connection binding;
- connection status, reauthorization, and revocation handling;
- either Connector Action token attachment or documented short-lived token injection for a foreground Runtime process.

The Dockerfile baseline does not prove these platform capabilities. If any mandatory capability is not available or cannot be evidenced, deliver the non-secret setup guide and a precise blocker, but do not claim that the Connector is ready to import or run.

## Authentication contract

Record the following non-secret contract before generation:

```text
Authentication mode: oauth2
OAuth flow: authorization_code
Connection identity: connector.<connector-key>.oauth2
Manifest authProviderKey: <must match oauthClients[].key in the administrator control plane>
Application owner: <provider, customer, or Workbench-managed owner>
Tenant model: <private/internal | public multi-tenant>
Authorization endpoint or metadata URL: <verified HTTPS URL>
Token endpoint or metadata URL: <verified HTTPS URL>
Minimum scopes: <verified provider scopes>
PKCE: <required | optional | not supported, with evidence>
Client authentication: <verified method>
Execution channel: gateway_action | runtime_environment
Safe read-only verification: <verified endpoint or documented limitation>
```

`connector.<connector-key>.oauth2` is a non-secret connection identity, not a token. If the target Runtime uses another field name, map this identity to that documented field and preserve it consistently across the Connector, setup guide, and validation report. Do not invent a platform field or put a real connection identifier in the package.

When declarative authentication metadata is supported, use the Resource Guide's `auth.type: oauth` spelling; accept `oauth2` only when the target parser documents it as a compatibility value. Include the original-package `manifest.yaml` with verified HTTPS endpoints and provider options. Include the administrator control-plane `oauth-clients.yaml` entry and make its `oauthClients[].key` exactly match `connector.authProviderKey`. The source package may contain placeholders when protected client configuration has not been supplied, but never invent a Client ID or Client Secret. Missing real client configuration, an unapproved redirect URI, or an unresolved provider review prerequisite blocks the final importable package.

When the target backend derives the callback from `APP_URL`, do not put `redirectUri` or `resultBaseUrl` in `manifest.yaml`; record the exact environment-specific callback requirement in `OAUTH_SETUP.md` and the administrator configuration checklist.

## Managed authorization flow

Generate member instructions around this sequence. Use the exact OAuth start/status hooks documented by the target Workbench; never invent a Tool name to fill a missing platform capability.

1. Run the member's bounded `status` or connection-status check. This reports whether the current Runtime has a usable managed connection; it does not print token fields.
2. If no usable connection exists, present the generated root-level `OAUTH_SETUP.md` guide in ordinary chat and start the Workbench-managed OAuth authorization entry. Do not open the API-Key password form, ask for a client secret, or ask the user to paste a token or authorization code.
3. The Runtime opens the provider consent page, creates and validates `state`, applies PKCE when required, receives the callback, exchanges the code, and stores the resulting connection securely. The member Skill waits for the authorization result rather than running a callback server or exchanging the code itself.
4. Rerun `status` after the authorization result. Confirm only non-sensitive metadata such as connected state, granted scope summary, provider account label, or expiry state when the Runtime exposes it safely.
5. Run a separate read-only `verify` through the managed connection. Prefer a documented identity/profile or equivalent safe endpoint. Do not use a paid, write, send, destructive, or otherwise side-effecting call as an implicit authentication test.
6. Continue the original task with the original non-sensitive inputs only after the connection is ready and any separate operation authorization is satisfied.

For a gateway Action, the managed gateway attaches the access token to the provider request; the token is not an Action input. For a bounded foreground script, use a Runtime environment injection only when the target platform explicitly documents it for OAuth2. The script may read the designated short-lived environment value for the current Attempt, but must never persist, echo, log, pass it through standard input/arguments, or use a file fallback. Prefer the gateway channel when both are available.

If the Runtime reports an expired or revoked connection, allow the documented reauthorization path at most once for the current task, then stop on a second failure. Do not reauthorize for 403, 429, network errors, or an insufficient-scope response unless the provider/Runtime explicitly classifies it as a consent or scope change. Credential or connection setup does not authorize business operations.

## Separate provider setup guide

Deliver a separate root-level `OAUTH_SETUP.md` in addition to the Connector member files. Use `templates/oauth2-setup-template.md` as the starting structure. The guide is an admin/operator checklist, not a credential store, and must explain:

- provider application creation and ownership;
- private/internal versus public multi-tenant selection;
- exact redirect URI registration and environment separation;
- minimum scopes, consent text, and least-privilege review;
- how the Workbench-managed authorization is started and resumed;
- authorization-code exchange, PKCE, expiry, refresh, and revocation behavior;
- account verification and user/tenant/connection binding;
- provider review, publication, test-user, or organization-approval requirements;
- client-secret storage, rotation, recovery, and incident response through the approved platform path;
- safe status and read-only verification without exposing tokens;
- unresolved prerequisites and the owner of each action.

Use verified official links and explicit placeholders. Never include a real client secret, access token, refresh token, authorization code, connection ID, account data, or copied token response. Replace every placeholder before calling the package import-ready; unresolved placeholders remain blockers.

The administrator upload source package includes the following control-plane template when the Connector uses OAuth2:

```yaml
oauthClients:
  - key: <connector-key>
    authType: oauth
    clientId: "<configure through the approved administrator path>"
    clientSecret: "<configure through the approved secret-management path>"
```

Workbench reads this configuration on the server side and may filter the file from the installed user resource and Runtime view. The file is not a user-facing Token store. The package must report the configuration owner and the key mapping even when the actual protected values are supplied outside the generated artifact.

## Legacy migration boundary

The new Connector contract does not package local token files, hand-written callback servers, token parsers, or script-owned refresh logic. The administrator upload source package may contain the control-plane `oauth-clients.yaml` entry described above; it is filtered from installed user resources and Runtime views. Move app-registration facts into `OAUTH_SETUP.md` and platform configuration, then route user consent and token lifecycle through Workbench Runtime. Do not automatically import legacy OAuth material or historical user tokens into the new package or read historical credential files into model context.

## Validation

Report these states separately:

1. **Structural:** package layout, frontmatter, companion files, setup-guide presence, reference paths, and absence of forbidden secret material.
2. **Runtime capability:** target evidence for authorization start, callback/state/PKCE, exchange, refresh, secure storage, status, revocation, and the selected injection channel.
3. **Live authorization:** user consent, account binding, granted scopes, read-only verification, expiry/refresh, and revocation behavior observed in the target environment.

Structural checks do not prove consent, exchange, refresh, revocation, or API access. Report each untested item honestly. Require separate authorization before starting OAuth, accessing a user's data, or performing remote side effects.

Before delivery, verify that:

- exactly one Connector authentication branch is selected;
- the stable connection identity is non-secret and consistent;
- the original-package `manifest.yaml` exists when the Connector declares OAuth metadata or HTTP Actions;
- `manifest.connector.authProviderKey` matches the administrator control-plane `oauthClients[].key`;
- the Manifest uses the target Resource Guide auth spelling and does not hard-code a backend-derived `redirectUri` or `resultBaseUrl`;
- the original package contains the control-plane `oauth-clients.yaml` entry without exposing protected values in reports or public archives;
- the member Skill references `OAUTH_SETUP.md` and the managed authorization flow;
- no API-Key password form or ordinary chat credential collection is used for OAuth2;
- no package-owned user Token store, authorization code, connection ID, account data, legacy OAuth lifecycle file, or local token fallback exists; the separate admin control-plane client entry is allowed only at the original-package layer;
- the setup guide names unresolved provider, client-registration, redirect, scope, Runtime, and review prerequisites;
- the safe verification endpoint and operation-authorization boundary are explicit.
