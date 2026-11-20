# Administrator Upload Package Structure

The default output of Work Skill Maker is the complete administrator upload package described by `workbench-resource-guide.md`. It is not the filtered user resource or Runtime installation view.

## Ordinary Skill

An ordinary Skill has a root definition file:

```text
<skill-key>/
  SKILL.md
  readme.md
  user_preferences.md
  references/        optional
  templates/         optional
  scripts/           optional
  config/            optional, non-secret only
  assets/            optional
```

`SKILL.md` is required at the package root. The lowercase companion files are maintained by this maker and should be included when the Skill is delivered as a complete source package. A standalone Skill does not need `manifest.yaml` merely because it is uploaded.

## Work

A Work is a package of first-level member Skills:

```text
<work-key>/
  <member-a>/
    SKILL.md
    readme.md
    user_preferences.md
  <member-b>/
    SKILL.md
    readme.md
    user_preferences.md
```

The Work root must not contain `SKILL.md`. A Work has no dedicated Manifest contract in the Resource Guide. Add only the optional files required by the members and the publishing surface.

## Connector administrator upload package

A complete Connector source package for administrator upload is:

```text
<connector-key>/
  manifest.yaml                  required when auth or HTTP Actions are declared
  icon.svg                       required when the upload surface requests an icon
  oauth-clients.yaml             required for the OAuth control-plane entry
  OAUTH_SETUP.md                 required for OAuth2
  <member-a>/
    SKILL.md
    readme.md
    user_preferences.md
    references/                  optional
    scripts/                     optional when a bounded local runtime is needed
  <member-b>/                    optional
    SKILL.md
    readme.md
    user_preferences.md
```

The Connector root must not contain `SKILL.md`. At least one exact first-level member is required, and every member must contain `SKILL.md`, `readme.md`, and `user_preferences.md`.

`manifest.yaml` is the Workbench Connector declaration. It contains `schemaVersion`, `plugin.name`, `connector.key`, `connector.authProviderKey`, the selected `auth` branch, `actions`, and optional `errors`. Use the field names and limited parameter syntax in `workbench-resource-guide.md`.

`oauth-clients.yaml` belongs to the administrator upload source package for an OAuth Connector. It is read by the server-side control plane and filtered from the installed user resource and Runtime view. Its `oauthClients[].key` must match `manifest.yaml`'s `connector.authProviderKey`.

The maker may generate an `oauth-clients.yaml` template with placeholders when protected client configuration was not supplied. It must not invent a Client ID or Client Secret, and it must not print or copy real credentials into reports, public archives, Git, or ordinary user resources.

## Authentication branches

### API-Key or Token Connector

Include the Connector Manifest's verified token or API-Key placement when the Connector uses declarative authentication. Keep the Runtime password form, encrypted platform storage, environment injection, status/verify separation, and bounded recovery rules in the member Skill. Do not add OAuth client configuration.

### OAuth2 Connector

Include all of the following at the Connector root:

- `manifest.yaml` with the OAuth provider metadata and `connector.authProviderKey`;
- `oauth-clients.yaml` for the administrator control-plane configuration entry;
- `OAUTH_SETUP.md` for registration, callback, scopes, Runtime ownership, rotation, revocation, and open prerequisites;
- `icon.svg` when the target upload surface requires the publishing icon.

Use the Workbench-managed authorization lifecycle. Do not create a user-facing password form, local Token store, hand-written callback server, token parser, or script-owned refresh logic. Do not put `redirectUri` or `resultBaseUrl` in the Manifest when the target backend derives the callback from `APP_URL`; document the environment-specific callback requirement in `OAUTH_SETUP.md`.

## Definition requirements

Every generated `SKILL.md` must have parseable YAML frontmatter. Every Work or Connector member must have a non-empty `description` that states its capability and trigger. Member names must be safe, unique within the package, and consistent with their directory names.

Use exact lowercase `readme.md` and `user_preferences.md`. Do not substitute uppercase `README.md`. Do not include provenance, author, attribution, or generator-source files. Do not identify an assistant, model, marketplace, or creation tool as the author or source of packaged content.

## Installation filtering

The administrator upload package and the installed user resource are different views. Workbench may retain `manifest.yaml` and publishing metadata for Connector registration while filtering `oauth-clients.yaml` and other control-plane-only files from the user resource or Runtime. Static validation must check the administrator source package; it must not mistake an installation filter for a missing source file.
