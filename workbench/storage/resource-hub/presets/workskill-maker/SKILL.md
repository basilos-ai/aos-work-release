---
name: "workskill-maker"
description: "Work Skill Maker — design, generate, and validate administrator-upload packages for ordinary Skills, multi-member Works, and API-Key or OAuth2 Connectors in Workbench. Use when a user wants to turn a task, workflow, or external service integration into a complete source package for publishing."
---

# Responsibilities

Turn a confirmed work scenario into exactly one Workbench administrator upload package:

- `skill`: one reusable capability with a root `SKILL.md`.
- `work`: a coordinated set of first-level member Skills. Treat a user request for a Workbench "worker" as `work`, unless they mean an Agent or background process.
- `connector`: one or more first-level member Skills plus the Connector publishing and authentication files required by the Resource Guide. Select exactly one authentication mode: `api_key` or `oauth2`.

The default output is the administrator's original upload package. It is not the filtered user resource or Runtime installation view. Preserve the user's requested capability and do not add unrelated Actions, commands, tests, or documentation.

# Execution

## Interaction rules

Use secure password forms only for static credentials such as API Keys or Tokens. OAuth2 user consent uses the Workbench-managed authorization entry, not a password form. Ask ordinary material gaps and necessary authorization questions in chat, never through a form. Reuse supplied facts and authorization covering the current operation, target and cost scope; ask again only for missing authorization or a material change. Do not add a human visual-review or visual-approval gate. Retain automatic structural/layout checks and report unavailable rendering honestly without blocking delivery solely for that limitation.

## Stage 1: Classify and collect requirements

Read `../workbench-resource-guide.md`, `references/publish-package.md`, `templates/interview.md`, and `references/runtime-environment.md`. Use `references/runtime-inventory.json` for exact declared packages and versions. Determine the resource type and the administrator upload package contents before designing files. Notify the user immediately of material dependency gaps with their affected function, evidence and remedy; distinguish undeclared dependencies from confirmed missing packages and deployment-dependent capabilities.

For a Connector, verify from current official provider documentation whether the requested authentication is a static Key/Token or an OAuth2 authorization-code flow. Do not relabel client credentials, signed requests, service accounts, or proprietary login flows as user OAuth2. Record the provider application owner, `connector.key`, `authProviderKey`, the selected execution channel, and the control-plane configuration owner.

Summarize the confirmed type, users, trigger, inputs, outputs, decision rules, approval points, external service, authentication mode, original package files, and validation criteria. Continue automatically unless a blocking ambiguity remains.

For a Skill or Work that depends on an external service, treat the service as a Connector-backed runtime dependency. Do not design direct API access, embedded credentials, or package-owned connection logic. The generated runtime instructions must discover a currently available Connector Action with `workbench_action_search` before selecting or invoking it.

## Stage 2: Model the workflow and members

Describe the entry point, input handling, decision points, human review, external calls, output production, errors, and validation.

- For a Skill, keep one primary responsibility.
- For a Work, split the workflow into cohesive first-level members with non-overlapping responsibilities.
- For a Connector, split by user capability or bounded service domain; do not create members merely to mirror individual endpoints.
- For a Skill or Work that uses an external service, place Connector discovery before the dependent operation. Search with `workbench_action_search`, select a suitable Connector Action from the visible results, and invoke it only through `workbench_action_execute` using the returned `actionKey`, `version`, `schemaHash`, and an input that satisfies the returned `inputSchema`. If no suitable Connector Action is available, report the missing dependency instead of adding a direct connection.

## Stage 3: Read the applicable standards

Always read:

- `../workbench-resource-guide.md` for the source package, Manifest, OAuth client control-plane file, and installation-filter contract;
- `references/publish-package.md` for the administrator-upload package profile;
- `references/runtime-environment.md` for sandbox capabilities, dependency assessment and execution boundaries;
- `references/output-structure.md` for the required package structure;
- `references/skill-standard.md` for every generated `SKILL.md`;
- `templates/skill-template.md` before assembling files.

Then read only the selected branch:

- `references/work-standard.md` for a Work;
- `references/api-key-connector.md` for an API-Key or Token Connector;
- `references/oauth2-connector.md` for an OAuth2 Connector;
- `templates/oauth2-setup-template.md` when generating an OAuth2 Connector;
- `templates/connector-manifest-template.yaml` when generating a Connector Manifest;
- `templates/oauth-clients-template.yaml` when generating the OAuth control-plane entry.

Do not mix the two Connector authentication contracts.

## Stage 4: Generate the administrator upload package

Include task-relevant dependency requirements and a bounded preflight in each affected member, following `references/runtime-environment.md`. Do not assume package installation, browser binaries, fonts, models, network access or platform Tools are available merely because Node/Python or network clients exist. Keep unresolved mandatory dependencies explicit; do not claim the package is ready to import or run.

Generate the smallest complete package at the user-selected output location:

- Skill package: `<skill-key>/SKILL.md`, `readme.md`, `user_preferences.md`, and only the required optional resources.
- Work package: every `<work-key>/<member>/` contains `SKILL.md`, `readme.md`, and `user_preferences.md`; never create `<work-key>/SKILL.md`.
- Connector package: the root contains the first-level member Skills plus the original-package publishing files required by the selected branch.

For every Connector with declared authentication or HTTP Actions, generate a root `manifest.yaml` using the Resource Guide field names: `schemaVersion`, `plugin.name`, `connector.key`, `connector.authProviderKey`, `auth`, `actions`, and optional `errors`. Use `auth.type: oauth` for the Resource Guide OAuth spelling; accept `oauth2` only when the target parser documents it as a compatibility value. Validate declared Action keys, URLs, methods, inputs, mappings and response paths.

Generate a root `icon.svg` when the target publishing surface requires the Connector icon. Use a supplied provider-approved asset when available; otherwise use the packaged neutral template and report that it is a fallback asset.

For an OAuth2 Connector, also generate:

- root `OAUTH_SETUP.md`;
- root `oauth-clients.yaml` as the administrator control-plane configuration entry, using placeholders when protected client configuration was not supplied.

The `oauthClients[].key` in that file must match `manifest.yaml`'s `connector.authProviderKey`. Workbench may filter this file from the installed user resource and Runtime view, but it remains part of the administrator upload source package. Never invent or print a real Client ID or Client Secret.

If the user supplies a surrounding `skills/`, `works/`, or `connectors/` directory, place the package under it without changing the package-internal definition rules.

Use exact lowercase filenames `readme.md` and `user_preferences.md`. `readme.md` contains maintenance guidance, the actual file map, modification rules, and validation checks without duplicating runtime instructions. `user_preferences.md` contains only explicitly approved persistent preferences; when none exist, write `# User Preferences` followed by `No saved preferences yet.`. Add references, scripts, templates, assets, or non-secret configuration only when they provide concrete value.

Do not create uppercase `README.md`. Do not create or retain provenance, attribution, author, or generator-source files such as `PROVENANCE.md`, `provenance.md`, `upstream-provenance.md`, `AUTHORS.md`, or `GENERATED_BY.md`. Do not identify Codex, Claude, ChatGPT, another model, an assistant, a marketplace, or a creation tool as the author, writer, generator, or source of the generated resource in filenames, frontmatter, documentation, comments, examples, metadata, or packaged content. When adapting an existing source, keep source lineage outside the resource package in the delivery record, validation report, or version-control history.

Every generated Skill, and every affected member Skill in a generated Work, must state that external service access begins with `workbench_action_search` and proceeds through the selected Connector Action with `workbench_action_execute`. It must forbid implementing or directly calling an external service connection inside the Skill or Work, including direct API requests, embedded service credentials, or logic that bypasses a Connector.

For an API-Key Connector, follow `references/api-key-connector.md`: generate the original-package Manifest with verified token/API-Key placement when declarative authentication is used; collect runtime secrets only through the Runtime password form; let Workbench encrypt them and Runtime inject them; and read them only from declared process environment variables. Write credential acquisition guidance and form text in English. Generate a stable credential identity, the actual form-call/resume workflow, separate status and remote verification, bounded credential recovery, and non-sensitive configuration/migration handling. Do not collect secrets in chat or stdin or store them in ordinary JSON.

For an OAuth2 Connector, follow `references/oauth2-connector.md`. Generate the original-package Manifest, `oauth-clients.yaml` control-plane entry, `OAUTH_SETUP.md`, and the selected publishing asset. Use the Workbench-managed authorization runtime for consent, callback, `state`, PKCE, code exchange, secure storage, refresh, revocation, and reauthorization. Prefer managed Connector Actions for provider calls; allow foreground environment injection only when the target Runtime explicitly documents that OAuth2 channel. Do not generate an API-Key password form, a user-facing Token file, a hand-written callback server, token parsing, or script-owned refresh logic. Do not put `redirectUri` or `resultBaseUrl` in the Manifest when the target backend derives callbacks from `APP_URL`; document the exact environment-specific requirement in `OAUTH_SETUP.md`. Missing client registration, control-plane configuration, redirect approval, or required Runtime capability is a reported blocker, not a reason to invent a fallback.

## Stage 5: Validate

Verify:

- the directory and frontmatter names are consistent;
- every `SKILL.md` has valid YAML frontmatter and a non-empty capability-and-trigger description;
- the package structure matches the selected type and administrator upload profile;
- Work and Connector roots have no `SKILL.md` and have at least one first-level member `SKILL.md`;
- every ordinary Skill and every Work or Connector member contains exact lowercase `readme.md` and `user_preferences.md` files;
- Connector packages have the required original-package Manifest, and OAuth2 packages have `oauth-clients.yaml`, `OAUTH_SETUP.md`, and the required publishing asset;
- `manifest.yaml` uses the Resource Guide schema and its `connector.authProviderKey` matches `oauthClients[].key`;
- OAuth Manifest metadata does not contain a hard-coded `redirectUri` or `resultBaseUrl` when the backend derives callbacks;
- every declared Action has a valid key, URL, method, mapping and supported response path;
- no uppercase `README.md`, provenance/attribution file, or authoring-source attribution appears anywhere in the package;
- every reference and command points to a packaged file or a documented runtime dependency;
- the dependency assessment covers every affected member, required version and non-package asset; material gaps have been disclosed before implementation, and target preflight evidence is separated from Dockerfile declarations and host-only checks;
- every Skill or Work that depends on an external service searches for a suitable Connector Action before use and invokes it only through `workbench_action_execute`;
- no Skill or Work implements direct external API requests, embeds service credentials, or bypasses Connector-backed execution;
- risky, billable, create, send, update, or destructive operations require authorization covering the current operation and scope; reuse that authorization and ask in chat only when it is missing or the scope changes;
- no real credential appears in source, docs, examples, logs, tool output, public ZIP files, or Git; control-plane placeholders are explicit and protected values are handled only through the approved administrator path;
- API-Key runtimes use only injected environment credentials, with a fixed password form, separate verification, no file fallback, and JSON reserved for allowlisted ordinary preferences;
- OAuth2 output includes the original-package Manifest, control-plane client entry, root-level `OAUTH_SETUP.md`, managed authorization flow, consistent non-secret connection identity, and no user/runtime Token store or local OAuth lifecycle implementation.

If validation fails, correct the earliest invalid design or generation stage before delivery.

# Resource Routing

| Resource | Read when | Purpose |
| --- | --- | --- |
| `../workbench-resource-guide.md` | Every task | Authoritative source-package, Manifest, control-plane and installation-filter rules |
| `references/publish-package.md` | Every task | Administrator upload package profile and package-layer boundaries |
| `templates/interview.md` | Collecting requirements | Type, workflow, integration, authentication and source-package discovery |
| `references/runtime-environment.md` | Every type, during requirement analysis | Sandbox capabilities, boundaries, early dependency-gap reporting and target verification |
| `references/runtime-inventory.json` | Comparing required packages and versions | Complete explicit Dockerfile dependency inventory |
| `references/output-structure.md` | Planning package files | Required Skill, Work and Connector source package structures |
| `references/skill-standard.md` | Writing any member Skill | Frontmatter, writing, resources and validation |
| `references/work-standard.md` | Building a Work | Member boundaries and Work validation |
| `references/api-key-connector.md` | Building an API-Key/Token Connector | Secure forms, original-package Manifest and Runtime injection |
| `references/oauth2-connector.md` | Building an OAuth2 Connector | Managed authorization, original-package control-plane config and provider setup requirements |
| `templates/connector-manifest-template.yaml` | Generating a Connector Manifest | Resource Guide Manifest skeleton |
| `templates/oauth-clients-template.yaml` | Generating an OAuth2 Connector | Administrator control-plane client configuration skeleton |
| `templates/oauth2-setup-template.md` | Generating an OAuth2 Connector | Non-secret provider/admin setup checklist |
| `templates/skill-template.md` | Assembling output | Type-specific source-package file skeletons |
| `readme.md` | Modifying this maker | Maintenance map and validation checklist |

# Result Requirements

Report the confirmed resource type, workflow and member architecture, generated original-package files, validation results, installation-filter behavior, and remaining live-test limitations. Include dependency readiness, unresolved mandatory/optional gaps, affected functions and remedies. When no target sandbox was inspected, say `Dockerfile baseline only; deployed runtime unverified`. For API-Key Connectors, report the non-secret credential identity, injection status, verification evidence and the control-plane configuration requirement, never the credential. Platform storage precedes script verification; do not claim failed credentials were never stored. For OAuth2 Connectors, report the Manifest path, `authProviderKey`, `oauth-clients.yaml` control-plane entry path, non-secret connection identity, setup-guide path, selected execution channel, target Runtime capability evidence, and unmet provider or client-registration prerequisites; never report OAuth material.

Do not upload, publish, deploy, start OAuth authorization, save a credential, or perform paid or side-effecting API calls unless the user separately authorizes that action. Generating the administrator source package is separate from completing platform registration and live provider verification.
