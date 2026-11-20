# Member Skill Writing Standard

Use this standard for an ordinary Skill and for every member Skill inside a Work or Connector.

## Core rules

- Give each Skill one clear, reusable responsibility.
- Use lowercase kebab-case for the directory and frontmatter `name`.
- Keep runtime instructions concise and executable.
- Do not create empty or speculative resources.
- Keep real credentials and environment-specific values outside member Skill files. An OAuth Connector's administrator root may contain the separate `oauth-clients.yaml` control-plane entry described by the publishing-package rules; it must never be copied into a member Skill, Runtime resource, report, or public archive.

Every `SKILL.md` starts with:

```yaml
---
name: "<skill-name>"
description: "<Capability>. Use when <trigger condition>."
---
```

The description states both capability and trigger. The body contains the real workflow, decision boundaries, relevant resource routing, external-effect confirmation points, error handling, and result requirements. Do not put maintenance instructions, long manuals, or user preferences in it.

## Required companion files

Every ordinary Skill and every member Skill inside a Work or Connector must contain:

- `readme.md`: exact lowercase maintenance guidance with the actual file map, modification rules, and validation checklist. Keep runtime instructions in `SKILL.md`; do not duplicate them here.
- `user_preferences.md`: exact lowercase persistent-preference storage. Record only preferences explicitly approved by the user. When none exist, use exactly:

```markdown
# User Preferences

No saved preferences yet.
```

Do not use uppercase `README.md` as an alternative.

## Optional resources

- `references/`: stable API documentation, schemas, business rules, and detailed procedures.
- `templates/`: reusable output structures.
- `scripts/`: deterministic parsing, conversion, validation, packaging, or bounded runtime operations.
- `config/`: non-secret endpoints and defaults only.
- `assets/`: static files used by the resource.

## Forbidden package content

- Do not create or retain provenance, author, attribution, or generator-source files, including `PROVENANCE.md`, `provenance.md`, `upstream-provenance.md`, `AUTHORS.md`, or `GENERATED_BY.md`.
- Do not present Codex, Claude, ChatGPT, another model, an assistant, a marketplace, or a creation tool as the author, writer, generator, or source of the resource.
- Apply this ban to filenames, frontmatter, prose, comments, examples, metadata, scripts, templates, archives, and generated output.
- Keep adaptation lineage outside the package in delivery records, validation reports, or version-control history.

Use relative links for packaged resources. Do not make a generated resource depend on creator-machine absolute paths.

## Runtime dependencies

For all output types, apply `runtime-environment.md` during design. State only the dependencies needed by this member: package/import or module names, relevant version constraints, commands and required assets such as fonts, browser binaries or OCR languages. Before the dependent step, check their availability in the target sandbox and report exact gaps and remedies. Distinguish declared, verified, bundled, undeclared, missing, incompatible and deployment-dependent requirements. Do not silently install packages or substitute creator-host checks for target verification. Unresolved mandatory dependencies prevent a ready-to-run claim; optional limitations must identify the affected function.

## Runtime writing

Use imperative language and state observable outcomes. Explain which execution channel performs an external call. Use secure password forms only for credentials. Ask ordinary material gaps and necessary authorization questions in chat, never through a form. Reuse supplied facts and authorization covering the current operation, target and cost scope; ask again only for missing authorization or a material change. Do not add a human visual-review or visual-approval gate. Retain automatic structural/layout checks and report unavailable rendering honestly without blocking delivery solely for that limitation. Require authorization for billable, create, send, update, delete, cancel, abort, or destructive operations; a required CLI flag is supplied by the Agent from that authorization, not a separate user submission.

For external APIs, document inputs, pagination or asynchronous follow-up, and relevant 401/403/429 recovery. Never claim live authentication or side-effecting behavior was validated unless it was actually authorized and observed.

### External services in Skills and Works

An ordinary Skill or a Work member must not implement or directly call an external service connection. This prohibition includes direct API requests, embedded service credentials, and any logic that bypasses a Connector.

When the capability depends on an external service, write the generated runtime instructions to:

1. call `workbench_action_search` before the dependent operation and select a suitable Connector Action from the results visible to the current user;
2. call `workbench_action_execute` only with the selected result's exact `actionKey`, `version`, and `schemaHash`, plus input that satisfies its `inputSchema`;
3. report that a suitable Connector is unavailable when search returns no match, rather than adding package-owned connection logic or assuming an Action exists.

Do not hard-code a current Action Catalog count or assume that administrator-only Actions are visible to ordinary users. These rules apply to Skills and Works that consume external services; they do not replace the separate Connector package standards.

## Validation

Before delivery, verify:

- frontmatter is valid and the name matches the containing directory;
- description is non-empty and discriminating;
- exact lowercase `readme.md` and `user_preferences.md` exist beside `SKILL.md` and are non-empty;
- no uppercase `README.md`, provenance/attribution file, or authoring-source attribution is packaged;
- required files and referenced resources exist;
- optional files have a concrete purpose;
- responsibilities are not duplicated across members or files;
- commands and scripts are executable in the target runtime;
- external-service dependencies in Skills and Works use `workbench_action_search` followed by Connector-backed `workbench_action_execute`;
- no Skill or Work directly requests an external API, embeds service credentials, or bypasses a Connector;
- no secret is present in ordinary Skill/Work files, logs, examples, reports, public archives, or Git; protected administrator control-plane values are checked separately;
- structural checks are not reported as live service validation.
