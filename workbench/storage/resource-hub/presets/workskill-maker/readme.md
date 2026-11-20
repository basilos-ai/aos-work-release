If the user asks to modify this skill, read this file before editing anything.

## Skill Structure

| Path | Responsibility |
| --- | --- |
| `SKILL.md` | Resource classification, workflow, branch routing, generation, and validation |
| `references/output-structure.md` | Required package structure for Skill, Work, and Connector outputs |
| `references/publish-package.md` | Administrator upload package, Manifest, control-plane file, icon, and installation-filter contract |
| `references/runtime-environment.md` | Dockerfile-derived capabilities, boundaries and dependency-gap workflow |
| `references/runtime-inventory.json` | Explicit OS/Python package inventory, pins and baseline identity |
| `references/skill-standard.md` | Writing standard for ordinary and member Skills |
| `references/work-standard.md` | Work member design and validation |
| `references/api-key-connector.md` | API-Key/Token secure forms, managed storage and Runtime injection |
| `references/oauth2-connector.md` | OAuth2 managed authorization lifecycle, runtime boundary, migration rules, and provider setup requirements |
| `templates/connector-manifest-template.yaml` | Resource Guide Connector Manifest skeleton |
| `templates/oauth-clients-template.yaml` | Administrator OAuth control-plane configuration skeleton |
| `templates/connector-icon.svg` | Neutral fallback publishing icon when the upload surface requires one |
| `templates/interview.md` | Minimal cross-type requirement interview |
| `templates/skill-template.md` | Type-specific output skeletons |
| `templates/oauth2-setup-template.md` | Non-secret OAuth2 provider/admin setup guide template |
| `scripts/validate_output.py` | Companion-file, attribution, API-Key Runtime, and OAuth2 setup-contract checks |
| `user_preferences.md` | Explicitly approved persistent user preferences |
| `readme.md` | This maintenance guide |

## Modification Map

| Change request | Primary file | Also update | Validation |
| --- | --- | --- | --- |
| Change type routing | `SKILL.md` | `templates/interview.md`, `templates/skill-template.md` | Walk through Skill, Work, and both Connector branches |
| Change package structure | `references/output-structure.md`, `references/publish-package.md` | `SKILL.md`, output template, validator | Validate original upload files, installation filtering, and all three types |
| Change member Skill rules | `references/skill-standard.md` | Output template, validator | Validate one ordinary Skill and one member Skill |
| Change Work behavior | `references/work-standard.md` | `SKILL.md`, interview, template | Confirm root/member layout and handoffs |
| Change API-Key onboarding | `references/api-key-connector.md` | `SKILL.md`, interview, template | Check secure form, environment injection, separate verification and no secret echo |
| Change Connector publishing | `references/publish-package.md`, `references/output-structure.md` | `SKILL.md`, connector templates, validator | Check Manifest, icon, control-plane file, member structure, and installation filtering |
| Change OAuth2 delivery | `references/oauth2-connector.md` | `SKILL.md`, interview, output structure, templates, validator | Check managed authorization lifecycle, Manifest mapping, `oauth-clients.yaml`, setup guide, migration boundary, and selected execution channel |
| Save a persistent preference | `user_preferences.md` | None unless runtime routing changes | Confirm the user explicitly approved persistence |

## Modification Rules

- Keep the folder and frontmatter name `workskill-maker` unless the user explicitly requests a rename.
- Treat `skill`, `work`, and `connector` as output package types; `worker` is only a user-language alias for `work` after ambiguity is removed.
- Keep API-Key and OAuth2 requirements in separate references and load only the selected branch at runtime.
- Use `workbench-resource-guide.md` and `references/publish-package.md` as the source-package and administrator-upload contract. Keep platform-specific deployment facts in the setup guide rather than inventing them.
- Do not force ordinary Skills to use Connector packaging or credential rules.
- Require exact lowercase `readme.md` and `user_preferences.md` for every ordinary Skill and every Work or Connector member.
- Do not create uppercase `README.md`, provenance/attribution files, or packaged authoring-source statements.
- Keep source lineage outside generated packages in delivery evidence or version-control history.
- Never invent or expose secrets, tokens, authorization codes, or real client credentials in this Skill, generated reports, commands, logs, or public examples. The administrator upload package may contain the control-plane `oauth-clients.yaml` entry, but generated output uses placeholders unless protected values were explicitly supplied through an approved administrator path.

## Runtime baseline maintenance

When a newer sandbox Dockerfile is supplied, update `references/runtime-inventory.json` from its explicit declarations, including the SHA256 and capture date, then align `references/runtime-environment.md`. Inventory all explicit apt packages and Python pins, including packaging tools; do not invent transitive packages or exact OS/Python/npm versions. The empty additional npm list means no explicit npm install, not that the base image contains no modules. Keep deployment facts and live verification separate from build declarations. Recheck authentication boundaries against the selected Connector references.

Validate early dependency assessment and generated preflight instructions across ordinary Skill, multi-member Work, API-Key Connector and OAuth2 Connector scenarios. Include an undeclared browser/module case and an undeclared CJK font/OCR-language case. Confirm gaps identify function, dependency, evidence and remedy; unknown or missing mandatory requirements must not become a ready-to-run claim. Do not add installation or human approval gates merely to report an optional dependency limitation.

## Common Change Recipes

### Change a resource type

1. Update the selected type reference.
2. Update routing and validation in `SKILL.md`.
3. Update the interview and output skeleton only where the changed requirement affects them.
4. Validate a realistic package for that type.

### Change API-Key onboarding

1. Update `references/api-key-connector.md`.
2. Align `SKILL.md`, interview and template with stable credential identity, actual password Tool invocation, environment-only loading, separate verification and ordinary configuration.
3. Check retry/stop rules and migration boundaries. Platform storage happens before remote verification; do not promise automatic rollback. Run the optional API-Key static profile and mock-based runtime checks; report target-platform validation separately.

### Change OAuth2 requirements

1. Update `references/oauth2-connector.md`.
2. Align `SKILL.md`, interview, output structure, `templates/skill-template.md`, and `templates/oauth2-setup-template.md` with managed authorization start/resume, Runtime ownership, and the selected injection channel.
3. Align `references/publish-package.md`, `templates/connector-manifest-template.yaml`, `templates/oauth-clients-template.yaml`, `templates/oauth2-setup-template.md`, and `scripts/validate_output.py` with the administrator source package and installation-filter boundary.
4. Verify the `authProviderKey` / `oauthClients[].key` mapping, no hard-coded backend-derived callback fields, no user Token store, and no hand-written callback implementation. Allow the documented control-plane configuration entry at the original-package layer.

## Validation

- [ ] `SKILL.md` frontmatter name matches the folder and its description covers Skill, Work, and both Connector modes.
- [ ] All references routed from `SKILL.md` exist.
- [ ] Connector original packages contain the Resource Guide Manifest when authentication or Actions are declared.
- [ ] OAuth2 original packages contain `oauth-clients.yaml`, and its key matches `manifest.connector.authProviderKey`.
- [ ] `oauth-clients.yaml` is documented as control-plane configuration and is filtered from installed user resources and Runtime views.
- [ ] Manifest OAuth metadata does not hard-code `redirectUri` or `resultBaseUrl` when the backend derives callbacks from `APP_URL`.
- [ ] Declared Manifest Actions use the supported field and response-path syntax.
- [ ] Skill output uses a root `SKILL.md`.
- [ ] Work and Connector output forbid a root `SKILL.md` and require first-level member `SKILL.md` files.
- [ ] Skill output has a root `SKILL.md`; Work and Connector outputs do not.
- [ ] Every ordinary Skill and every Work or Connector member contains exact lowercase `readme.md` and `user_preferences.md`.
- [ ] No uppercase `README.md`, provenance/attribution file, or authoring-source attribution appears in generated output.
- [ ] API-Key onboarding uses only the supported password Tool, with stable identity and bounded resume/recovery.
- [ ] API-Key secrets come only from injected environment variables; fixed JSON contains ordinary preferences only.
- [ ] API-Key status and remote verification are separate; failed verification does not imply platform deletion or rollback.
- [ ] OAuth2 delivery requires the original-package Manifest, control-plane `oauth-clients.yaml`, root-level `OAUTH_SETUP.md`, managed Runtime authorization, an explicit execution channel, and no user Token store or legacy OAuth lifecycle files.
- [ ] One realistic scenario for each of Skill, Work, API-Key Connector, and OAuth2 Connector passes a structural walkthrough.

Run `python3 scripts/validate_output.py <package> --resource-type connector --package-profile admin_upload --auth-mode api_key` for an API-Key original package, or use `--auth-mode oauth2` for the OAuth2 original-package contract. Add `--require-icon` when the target publishing surface requires `icon.svg`. Static checks cover common legacy patterns and declared structure; they do not prove secret data flow, platform injection, user consent, token exchange/refresh, or provider access.

## OAuth2 validation checks

- Check that the member Skill uses authorization-code language, a stable non-secret connection identity, the managed Runtime lifecycle, and a separate read-only verification step.
- Check that the root-level `OAUTH_SETUP.md` records provider ownership, tenant model, exact redirect URI, scopes, PKCE, endpoints, client-configuration owner, execution channel, review prerequisites, and open blockers.
- Ensure OAuth2 does not use the API-Key password form, ordinary chat secret collection, user-facing Token files, callback servers, token parsers, or script-owned refresh logic. The administrator original package may contain the documented control-plane `oauth-clients.yaml` entry.
- Keep structural checks, target Runtime capability evidence, and live consent/API verification as separate results.

## Interaction validation

- Static API-Key/Token credentials use the fixed secure password form; OAuth2 user consent uses the managed authorization entry; ordinary parameters and authorizations use chat.
- Reuse facts and authorization already covering the target, operation and cost scope, including billable and write operations; no redundant confirmation loop.
- Generated Skills and Works must not require human visual review or form-based visual acceptance. Keep automatic checks and honest rendering limitations.
- Review entrypoints, branch references and templates together for contradictory interaction rules.

## API-Key credential onboarding guidance checks

- Check that credential guidance and form text are written in English, without Chinese onboarding copy.

- Verify each provider guide includes an official site, credential entry or documented tenant-specific fallback, short steps and source/date.
- Ensure SKILL.md requires a visible chat guide before the actual password-form call, without asking whether to open it.
- Ensure the fixed form description contains acquisition help; missing and replacement forms share it and preserve secret field/identity/environment contracts.
- Usable credentials skip onboarding; missing non-secret provider/login details are asked only in ordinary chat.
