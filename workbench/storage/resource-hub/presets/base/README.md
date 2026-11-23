# Base

Base is a built-in Workbench app for managing structured data and collaborative workflows in flexible tables.

## Package contents

- `manifest.yaml`: app identity, entry path, and OAuth2 page-authorization endpoints
- `oauth-clients.yaml`: the OAuth client used by this app package
- `basil-base-operations/SKILL.md`: runtime guidance for using the app
- `icon.svg`: the app icon

The member lives directly under this App directory. Run member scripts from `basil-base-operations/` or use absolute script paths. For Git import and publication, preserve `basil-base-operations/SKILL.md` as a first-level member and keep the complete member directory together. The repository manifest `.workbench/apps.json` points to `apps/base`; that directory becomes the App snapshot root. Do not add a `skills/` wrapper for Git import. See `basil-base-operations/OAUTH_SETUP.md` for deployment guidance.

## Authorization

Base declares the `basilos` OAuth provider. Workbench starts OAuth for the current user, stores that user's tokens in the encrypted App OAuth connection, and reuses the connection only for apps that declare the same provider key.

At startup, `configure:builtin-apps` writes the OAuth client credentials from `BASILOS_OAUTH_CLIENT_ID` and `BASILOS_OAUTH_CLIENT_SECRET` into this server-only package when both variables are configured. If either variable is missing, both fields stay empty, OAuth remains unavailable, and this built-in App is hidden from Client Explore APIs. Access tokens and refresh tokens are never stored in the package or exposed to the client.

The checked-in OAuth client fields are currently empty deployment placeholders. Supply both provider-issued values through the deployment configuration before publishing; this package alone cannot complete live authorization.

## Agent / CLI authorization

The `basil-base-operations` member reads `APP_OAUTH_BASILOS_ACCESS_TOKEN` inside Python from the current Runtime Attempt. Use foreground `exec` with `background=false`; run `scripts/auth/status.py` with `{}` before a small read-only business request. Both built-in Apps share `app:oauth:basilos` for the same user. Scripts do not use App-key or Connector credential prefixes.

API addresses come from `basil-base-operations/scripts/runtime/service.json`. This non-secret configuration must match the BasilOS deployment in the manifest. The current package uses the HTTPS destination recorded in both configuration files.

Missing/expired Tokens and HTTP 401 require updating authorization in Workbench and starting a new execution. HTTP 403 requires checking scopes and business permissions. Scripts never refresh Tokens, persist credentials, perform local OAuth login, or automatically retry with a different credential. Personal-token authorization is available through the Workbench password form when OAuth2 is unavailable; see the member's `basil-base-operations/references/auth.md`. They reject automatic redirects. See `basil-base-operations/OAUTH_SETUP.md` for publishing and live validation steps. Changes to a local package require publishing and installation of the updated version.
