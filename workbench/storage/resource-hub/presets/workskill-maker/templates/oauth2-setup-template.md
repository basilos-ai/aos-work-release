# OAuth 2.0 Connection Setup

> Replace every `<...>` placeholder with verified, non-secret provider information before delivery. This guide is an admin/operator checklist, not a credential store.

## Scope and ownership

- Provider: `<provider name>`
- Connector key: `<connector-key>`
- Manifest `authProviderKey`: `<connector-key>`
- Connection identity: `connector.<connector-key>.oauth2`
- Application owner: `<provider | customer | Workbench-managed owner>`
- Environment: `<development | staging | production>`
- Tenant model: `<private/internal | public multi-tenant>`
- User/account binding: `<per-user | per-tenant | per-connection>`

## Verified provider metadata

- Official OAuth documentation: `<verified HTTPS URL>`
- Authorization-server metadata: `<verified HTTPS URL or not provided>`
- Authorization endpoint: `<verified HTTPS URL>`
- Token endpoint: `<verified HTTPS URL>`
- Revocation endpoint: `<verified HTTPS URL or documented limitation>`
- Minimum scopes: `<least-privilege scope list>`
- PKCE: `<required | optional | not supported, with provider evidence>`
- Client authentication: `<verified token-endpoint authentication method>`
- Source verification date: `<YYYY-MM-DD>`

## Administrator upload package and control-plane configuration

The original Connector package contains `manifest.yaml`, this setup guide, the member Skills, and the control-plane configuration entry below. Workbench may filter `oauth-clients.yaml` from the installed user resource and Runtime view, but it is part of the administrator upload source package.

```yaml
oauthClients:
  - key: <connector-key>
    authType: oauth
    clientId: "<configure through the approved administrator path>"
    clientSecret: "<configure through the approved secret-management path>"
```

The `key` above must match `manifest.yaml`'s `connector.authProviderKey`. Do not invent a Client ID or Client Secret. If protected client configuration was not supplied, keep the placeholders and report the package as blocked until the administrator configures them through the approved path. Do not place a real secret in this guide, a public archive, Git, chat, or an ordinary user resource.

## 1. Register the provider application

1. Open `<official application-registration URL>` using the approved application-owner account.
2. Select `<private/internal | public multi-tenant>` and record the provider's review, publication, test-user, and organization-consent requirements.
3. Register the exact redirect URI supplied by the target Workbench for `<environment>`:

   `<exact HTTPS redirect URI supplied by the target Workbench>`

   Do not put this environment-specific callback in `manifest.yaml` when the backend derives it from `APP_URL`; keep it in the administrator setup record instead.

4. Configure only the minimum scopes listed above and record the consent text shown to users.
5. Store the client configuration through the approved platform admin or secret-management path. Never put a client secret in this file, chat, source, archive, or ordinary Workbench input.

## 2. Configure the managed Runtime

- OAuth metadata/configuration owner: `<team or platform role>`
- Target Workbench OAuth authorization entry: `<documented UI/Tool/action name>`
- Callback evidence: `<documented callback path and environment>`
- Token exchange and refresh owner: `Workbench OAuth Runtime`
- Secure connection storage: `<documented platform mechanism>`
- Provider-call channel: `<managed Connector Action | Runtime environment injection>`
- Runtime capability evidence: `<link, test result, or explicit blocker>`

The Runtime must own authorization start, `state`, PKCE when required, callback handling, code exchange, refresh, revocation state, and per-user/tenant/connection binding. Do not add a callback server, token parser, token file, or script-owned refresh logic to the Connector.

## 3. Authorize a user

1. Open the Connector member's documented authorization entry in Workbench.
2. Follow the provider consent screen and grant only the listed scopes.
3. Wait for the managed callback and resume the original Attempt.
4. Confirm connection status using non-sensitive metadata only. Never paste or display a client secret, authorization code, access token, or refresh token.

## 4. Verify safely

- Read-only verification operation: `<provider endpoint/action>`
- Expected non-sensitive result: `<connected state, account label, or limited profile metadata>`
- Required operation authorization: `<none | exact user authorization boundary>`
- Expiry/refresh test status: `<not run | observed on YYYY-MM-DD | blocked>`
- Revocation/reauthorization test status: `<not run | observed on YYYY-MM-DD | blocked>`

Do not use a paid, write, send, destructive, or otherwise side-effecting operation as an implicit connection test.

## 5. Rotation, revocation, and recovery

- Client-secret rotation owner and approved procedure: `<team and official procedure URL>`
- User connection revocation procedure: `<provider/Workbench procedure URL>`
- Lost or compromised client response: `<disable, rotate, revoke, notify, and recover steps>`
- Scope or redirect change procedure: `<approval and reauthorization steps>`

## 6. Open prerequisites

| Prerequisite | Owner | Status | Evidence or remedy |
| --- | --- | --- | --- |
| Provider application registration | `<owner>` | `<complete | blocked>` | `<link or action>` |
| Client configuration in approved platform storage | `<owner>` | `<complete | blocked>` | `<non-secret evidence>` |
| Exact redirect URI approval | `<owner>` | `<complete | blocked>` | `<link or action>` |
| Minimum scopes and consent review | `<owner>` | `<complete | blocked>` | `<link or action>` |
| Workbench OAuth start/callback capability | `<owner>` | `<verified | unverified | unavailable>` | `<evidence or blocker>` |
| Selected provider-call injection channel | `<owner>` | `<verified | unverified | unavailable>` | `<evidence or blocker>` |

Do not label the Connector import-ready while a mandatory prerequisite remains unresolved.
