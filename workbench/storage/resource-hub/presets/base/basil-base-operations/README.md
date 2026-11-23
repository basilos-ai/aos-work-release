# Basil Base Skill engineering

This built-in App member is self-contained: Runtime needs this entire directory, not the parent App manifest or OAuth client file. Resolve paths from SKILL.md. The host must supply Workbench-compatible session_status, credential injection, and request_user_input with the native app_oauth authorization-card schema and automatic task resumption in a new Attempt. Base uses appKey=multidimensional-table. Secure password-form capabilities are needed only when the user explicitly requests personal-token authorization. A generic terminal or same-named question tool is not a substitute. Authorization-card failures never trigger personal-token collection automatically. Missing host capabilities fail through the documented Runtime/auth path. See SKILL.md and references/auth.md for the execution and recovery rules.

## Responsibility and maintenance

| Source | Authority |
| --- | --- |
| SKILL.md | Agent bootstrap, routing, interaction policy and result presentation |
| references/ | Capability inputs, task-specific workflow and recovery; business-context.md owns optional business-object clarification; auth.md owns Agent authorization recovery |
| scripts/auth/ | Status and fixed authorization-helper entrypoints |
| scripts/runtime/ | Input controls, domain, credential selection, transport and response checks |
| scripts/base/ | Business contracts, validation and capability execution |
| OAUTH_SETUP.md | Developer/deployer OAuth, host injection, egress and packaging configuration |
| tests/ | Offline invariants and wire-contract regressions |

Keep each complete workflow in its capability reference. Other documents link to it rather than repeat it. Agent semantics and user confirmation are not proved by runtime flags or unit tests. Both members must remain independently materializable; shared maintenance must not introduce a runtime dependency on another Skill.

## Verification

From this directory run:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -v
```

Tests use offline fixtures. They do not verify live OAuth, server ACLs, deployment reachability or browser access. Retain exact API inputs/outputs and existing CLI entrypoints when refactoring internals. Reject unsupported input only where the capability contract establishes the constraint; do not guess server operator enums.

## Compatibility

Retired scripts/auth/configure.py and oauth_login.py intentionally reject local credential configuration without consuming secret input. Keep these fail-closed entrypoints and their tests while old callers can still invoke them.

Normal query delivery follows references/record-query.md. The core lives in scripts/base/query_workflow.py; query_results.py owns private workspace persistence and output budgeting. operations.py owns operation definitions and deterministic business validation; cli.py re-exports existing definitions for compatibility.

scripts/base/query_snapshot.py / record_query_snapshot remains the one-shot compatibility entrypoint and delegates to the same query core. Normal Agents retain the query → acceptance → create sequence. Keep its existing output envelope; both entrypoints validate result URL format and preserve the complete provider URL as defined in references/record-query.md. Do not turn the compatibility path into the default workflow.

## Business background maintenance

`references/business-context.md` contains the module-specific concepts confirmed for this Skill. Load it only for unclear business objects or intent, not as an extra bootstrap step. Existing capability contracts and execution policies retain their authority; background must not introduce a second workflow.

Source provenance below is for maintainers, relative to the development repository root. PRDs are not packaged runtime dependencies and Agents need not load them:

- `prd/V1.0.2/Basil CLI/basil-cli接口清单.md`, Table section: Base/table/field/ record/view relationships and distinct operation purposes. Its inventory is not an API contract or a promise that every listed operation is implemented.
- Current capability references define supported field types, operation inputs and effective permission handling; no tenant-specific table schema is assumed.

Keep source versions separate: reuse only the stated concepts confirmed against the current contracts, not historical UI details or unimplemented plans. Business background excludes other platform modules and the added query-result presentation mechanisms. Existing query delivery remains in its current execution references. When updating concepts, check routing, supported inputs, mutation boundaries and failure handling together; examples must not become default fields or fixed calls.
