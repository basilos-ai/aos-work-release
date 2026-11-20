# Workbench Administrator Upload Package Template

Use only the skeleton for the selected resource type. The output is the administrator's original upload package; Workbench may later filter control-plane-only files from installed user resources.

## Ordinary Skill

```text
skills/
  <skill-key>/
    SKILL.md
    readme.md             required maintenance guide
    user_preferences.md   required; use the empty-preference template until the user approves a preference
    references/          optional
    templates/           optional
    scripts/             optional
    config/              optional, non-secret only
    assets/              optional
```

## Work

```text
works/
  <work-key>/
    <member-a>/
      SKILL.md
      readme.md
      user_preferences.md
      references/        optional
      scripts/           optional
    <member-b>/
      SKILL.md
      readme.md
      user_preferences.md
```

Do not create `works/<work-key>/SKILL.md`.

## Connector

```text
connectors/
  <connector-key>/
    manifest.yaml         required when authentication or HTTP Actions are declared
    icon.svg              required when the upload surface requests an icon
    oauth-clients.yaml    required for the OAuth control-plane entry
    OAUTH_SETUP.md        required for OAuth2
    <member-a>/
      SKILL.md
      readme.md
      user_preferences.md
      references/        optional
      scripts/           optional when bounded local runtime is needed
    <member-b>/           optional
      SKILL.md
      readme.md
      user_preferences.md
    readme.md             optional common maintenance guidance for multiple members only
```

Do not create `connectors/<connector-key>/SKILL.md`.
Do not create uppercase `README.md` or any provenance, attribution, author, or generator-source file.

`manifest.yaml` uses the Resource Guide fields `schemaVersion`, `plugin.name`, `connector.key`, `connector.authProviderKey`, `auth`, `actions`, and optional `errors`. `oauth-clients.yaml` is an administrator control-plane file. Its `oauthClients[].key` must match `connector.authProviderKey`; Workbench filters it from installed user resources and Runtime views.

### API-Key/Token branch

The member Skill follows `references/api-key-connector.md` and specifies:

- stable `credentialKey` (`connector.<connector-key>.<purpose>`), secret field names and injected environment variable names;
- English-only credential acquisition guidance and form titles, descriptions and labels;
- a packaged provider acquisition guide (official site, credential entry, short steps, verification source/date), shown in chat before opening a form; resolve tenant/provider-specific entries without guessing;
- one fixed password-form helper used by missing-credential and 401 responses;
- `status` -> actual secure Tool call when needed -> wait -> `status` -> separate read-only `verify` -> original task;
- stop on cancellation, unavailable secure Tool, failed injection or rejection after one replacement;
- environment-only credential reading, with no chat/stdin/file fallback or secret output;
- optional `configure` for allowlisted ordinary JSON preferences, per-call overrides and explicit legacy cleanup boundaries;
- provider-specific safe verification and errors, with static and live validation reported separately.

Use the form schema in the selected reference. Platform storage precedes script verification; never promise failed credentials were not persisted.

The original package also includes the Connector Manifest with the verified token/API-Key placement and declared Actions when that metadata is supported. Do not include OAuth client configuration in this branch.

### OAuth2 branch

Add the original-package provider and control-plane files at the Connector root, keeping them separate from member runtime instructions:

```text
connectors/<connector-key>/OAUTH_SETUP.md
connectors/<connector-key>/manifest.yaml
connectors/<connector-key>/oauth-clients.yaml
```

Start from `templates/oauth2-setup-template.md`. The guide covers application ownership, tenant model, exact redirect URI, scopes and consent, managed authorization start/resume, state/PKCE, token exchange and refresh, account verification/binding, provider review, rotation, revocation, and non-secret validation. It contains no real client secret, access token, refresh token, authorization code, connection ID, account data, or legacy OAuth file.

The member Skill follows `references/oauth2-connector.md` and specifies:

- the non-secret connection identity `connector.<connector-key>.oauth2` or the exact documented Runtime mapping;
- the verified Resource Guide `auth.type: oauth` metadata and endpoints, or the documented `oauth2` compatibility spelling;
- the `connector.authProviderKey` mapping to the root `oauth-clients.yaml` control-plane entry;
- the Workbench-managed authorization start, callback resume, status, and separate read-only verification flow;
- the selected execution channel: managed gateway Action, or short-lived Runtime environment injection only when explicitly supported;
- reauthorization and stop rules for revoked/expired connections;
- no `request_user_input` password form, client-secret collection, token input, local token persistence, callback server, or script-owned refresh.

Do not add `redirectUri` or `resultBaseUrl` to the Manifest when the target backend derives callbacks from `APP_URL`; document the exact environment-specific callback in `OAUTH_SETUP.md`.

If client registration, redirect approval, or a required Runtime capability is unavailable, mark the package not import-ready and report the exact prerequisite.

## Member SKILL.md

```yaml
---
name: "<member-key>"
description: "<Capability>. Use when <trigger condition>."
---
```

Write the minimum runtime workflow, decision and confirmation boundaries, relevant resource routing, error handling, and result requirements.

## Runtime dependency contract

For every selected output type, include only the dependencies required by the member and tailor this skeleton using `references/runtime-environment.md`:

```markdown
## Runtime requirements

- Required packages/commands and version constraints: <actual requirements, or no additional packages>.
- Required runtime assets and platform capabilities: <actual requirements, or none>.
- Evidence and unresolved gaps: <baseline declaration, target verification or packaged dependency; disclose remaining gaps>.

Before the dependent operation, check the required packages, commands and assets in the target sandbox. If a mandatory requirement is unavailable or incompatible, report the exact dependency, affected operation and remedy; stop that operation and continue independent steps where useful. Do not silently install dependencies or claim readiness from creator-host checks. Report optional limitations without blocking unrelated output.
```

Replace placeholders with concrete requirements; do not copy unused categories or the whole baseline into each member.

## Required companion templates

Every ordinary Skill and every Work or Connector member includes exact lowercase `readme.md` and `user_preferences.md`.

`user_preferences.md` without approved preferences:

```markdown
# User Preferences

No saved preferences yet.
```

`readme.md` contains only maintained structure, modification rules, and validation checks. It does not repeat runtime instructions or identify an assistant, model, marketplace, or creation tool as the author or source.

For an ordinary Skill or Work member that depends on an external service, include this runtime contract in its `SKILL.md` and tailor the search criteria to the required capability:

```markdown
## External service access

Before using an external service, call `workbench_action_search` and select a suitable Connector Action from the results available to the current user. Invoke the selected Action only through `workbench_action_execute`, carrying forward its exact `actionKey`, `version`, and `schemaHash` and providing input that satisfies its `inputSchema`.

Do not implement or directly call an external service connection inside this Skill, including direct API requests, embedded service credentials, or logic that bypasses a Connector. If no suitable Connector Action is available, report the missing dependency and stop the external-service step.
```

Do not add this block to a Skill or Work member that has no external-service dependency. Connector packages follow their selected API-Key or OAuth2 branch instead.

## Final validation

- The selected type matches the required package structure.
- Every member name and description is valid and responsibilities do not overlap.
- Every ordinary Skill and every member has exact lowercase, non-empty `readme.md` and `user_preferences.md`.
- No uppercase `README.md`, provenance/attribution file, or authoring-source attribution appears in the package.
- All referenced files exist and optional resources are justified.
- Every external-service dependency in a Skill or Work is routed through `workbench_action_search` and Connector-backed `workbench_action_execute`.
- No Skill or Work directly calls an external API, embeds service credentials, or bypasses a Connector.
- No secret appears in files, examples, logs, archives, or Git.
- API-Key and OAuth2 rules are never combined in one Connector.
- Connector output uses the administrator source-package Manifest; OAuth2 output also includes the control-plane `oauth-clients.yaml` entry and root-level `OAUTH_SETUP.md`. It does not package user Token files, callback servers, or token lifecycle code.
- Structural checks and live-service validation are reported separately.

## Interaction boundaries

Use secure password forms only for static credentials such as API Keys or Tokens. OAuth2 user consent uses the Workbench-managed authorization entry; never ask for a client secret, authorization code, access token, or refresh token. Ask ordinary material gaps and necessary authorization questions in chat, never through a form. Reuse supplied facts and authorization covering the current operation, target and cost scope; ask again only for missing authorization or a material change. Do not add a human visual-review or visual-approval gate. Retain automatic structural/layout checks and report unavailable rendering honestly without blocking delivery solely for that limitation. Content review, when required by the workflow, uses ordinary chat and reuses approval already covering the current content.
