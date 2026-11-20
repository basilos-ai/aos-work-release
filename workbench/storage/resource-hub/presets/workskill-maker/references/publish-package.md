# Administrator Upload Package Standard

Work Skill Maker generates the administrator upload package by default. Do not confuse this package with the filtered user resource or Runtime installation view.

## Package layers

The administrator upload package is the source package that Workbench receives and processes:

```text
connectors/<connector-key>/
  manifest.yaml
  icon.svg                         # when the upload surface requires an icon
  oauth-clients.yaml               # OAuth Connector control-plane entry
  OAUTH_SETUP.md                   # OAuth2 Connector only
  <member>/SKILL.md
  <member>/readme.md
  <member>/user_preferences.md
```

Workbench may filter `oauth-clients.yaml` from the installed user resource and Runtime view. That filtering does not remove the file from the administrator upload source package.

## Ordinary Skill and Work

An ordinary Skill has a root `SKILL.md`. A Work has first-level member Skills and no root `SKILL.md`. `manifest.yaml` is not required for either type unless a separate publishing surface explicitly requests additional metadata.

Keep the maintained companion files and optional references, scripts, templates, assets, and non-secret configuration that are needed by the resource. Do not add a Connector Manifest to an ordinary Skill or Work merely because the output is being uploaded.

## Connector package

For a complete administrator-upload Connector package:

- include a root `manifest.yaml` when the Connector declares authentication or HTTP Actions;
- include `connector.key` and `connector.authProviderKey` in the Manifest;
- use the Resource Guide Manifest fields: `schemaVersion`, `plugin.name`, `connector`, `auth`, `actions`, and optional `errors`;
- include a root `icon.svg` when the target publishing surface requires the Connector icon;
- include a root `oauth-clients.yaml` for the OAuth control-plane configuration entry;
- include a root `OAUTH_SETUP.md` for an OAuth2 Connector;
- keep all members at the first directory level and include their exact lowercase companion files.

The `oauth-clients.yaml` file is a control-plane configuration file, not a user credential form and not a Runtime token store. Its `oauthClients[].key` must match `manifest.yaml`'s `connector.authProviderKey`. If the administrator has not supplied protected client configuration, generate a clearly marked placeholder template and report that the source package is not import-ready until the platform configuration is completed.

Never invent a Client ID or Client Secret. Never copy a real secret into a public ZIP, chat message, Git repository, validation output, or ordinary user resource. The administrator may populate the control-plane file through the approved protected upload or secret-management path.

## Manifest and OAuth rules

Use `manifest.yaml`, not `main.yaml`. For OAuth metadata, prefer the Resource Guide spelling `auth.type: oauth`; accept `oauth2` only where the target parser explicitly documents it as a compatibility value. Keep the internal Work Skill Maker branch name `oauth2` for routing and validation.

The Manifest declares the provider metadata that the Workbench UI and backend need to identify the authorization branch. The control-plane file supplies the server-side OAuth client configuration. Do not put `redirectUri` or `resultBaseUrl` in the Manifest when the target Workbench generates the callback from `APP_URL`; record the exact environment-specific callback requirement in `OAUTH_SETUP.md` instead.

For declared HTTP Actions, validate each action's key, URL, method, authentication flag, input mapping, query/header/body mapping, and supported `responseDataPath`. Do not treat the limited input and response-path syntax as a full JSON Schema or JSONPath implementation.

## Validation states

Report these states separately:

1. **Source package structure:** required files, first-level members, Manifest, control-plane file, icon, and setup guide.
2. **Static contract:** YAML shape, key matching, authentication branch, Action declarations, secret-safety checks, and forbidden legacy files.
3. **Runtime capability:** authorization UI, callback, state/PKCE, code exchange, secure storage, refresh, revocation, injection, and provider Actions.
4. **Live provider verification:** user consent, account binding, safe read-only verification, and provider API results.

Passing the first two states does not prove the last two. A generated source package may be structurally valid while remaining blocked on administrator configuration or target Runtime capabilities.
