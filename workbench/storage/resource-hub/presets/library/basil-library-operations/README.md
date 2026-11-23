# Basil Library Skill engineering

This built-in App member is self-contained: Runtime needs this entire directory, not the parent App manifest or OAuth client file. Resolve paths from SKILL.md. The host must supply Workbench-compatible session_status, credential injection, and request_user_input with the native app_oauth authorization-card schema and automatic task resumption in a new Attempt. Library uses appKey=library. Secure password-form capabilities are needed only when the user explicitly requests personal-token authorization. A generic terminal or same-named question tool is not a substitute. Authorization-card failures never trigger personal-token collection automatically. Missing host capabilities fail through the documented Runtime/auth path. See SKILL.md and references/auth.md for the execution and recovery rules.

## Responsibility and maintenance

| Source | Authority |
| --- | --- |
| SKILL.md | Agent bootstrap, routing, interaction policy and result presentation |
| references/ | Capability inputs, task-specific workflow and recovery; business-context.md owns optional business-object clarification; auth.md owns Agent authorization recovery |
| scripts/auth/ | Status and fixed authorization-helper entrypoints |
| scripts/runtime/ | Input controls, domain, credential selection, transport and response checks |
| scripts/library/ | Business contracts, validation and capability execution |
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

App identity is app.key=library, plugin.key=cloud.tyrion.workbench.library; Workbench page /library. These identities are not business script inputs.

Normal Agents follow references/search.md: metadata_catalog → Plan → structured_search with inspection → semantic review → FILE_ID refinement when required → final snapshotLink. Script Agents pass the Plan directly; `build_structured_search.py` is only an optional host function-call adapter. The default original route exposes server responses and has no session/receipt prerequisite. Runtime stdout truncation requires complete bounded file reading; it is not evidence that all candidates were reviewed.

Optional scripts/library/search_workflow.py callers use references/search-session.md. That mode retains catalog/read/ack/next/review/refine/deliver/close, identity-bound private temporary storage and its existing delivery guards. It is not automatically entered by the normal route; changing modes cannot legitimize incomplete review. Retain existing session callers and tests. The original route preserves live Metadata validation, review requirements and exact final query links. Existing structured_search.py callers retain operation=structured_search with exactly one of plan or body. Both paths retain live catalog validation. Native body uses the existing LITE fields, not Plan fields: tagConditionList enum values may be exact labels or integer option IDs belonging to that field. Numeric-looking strings are labels, never guessed IDs. Metadata uses tagConditionList, not generic METADATA_FIELD_TYPE/VALUE_TYPE filters or PRO condition groups. folderPath and folderIdList are mutually exclusive after empty fields are omitted.

The portable references/build-structured-search.function.json schema describes the optional build_structured_search host adapter. Its implementation emits a Plan; it is not automatically registered in the host and does not replace CLI validation. The adapter is not a required script step; script Agents pass the Plan directly to structured_search.py. The generated upstream generic string-value description must not override the LITE boundary's enum-option integer encoding. Low-level output compatibility is specified in references/search.md. folder_tree.py also retains its operation-less query input for existing callers; new calls use the standard operation envelope.

Source App integration tests in tests/test_app_package.py require parent manifest and client configuration and skip in member-only installations. All member runtime tests remain runnable without those App files. Never log client credentials.

## Business background maintenance

File Metadata name-only writes resolve one exact definition from the complete current-user LITE catalog before posting its ID. The CLI follows all catalog pages without a `name` filter. A missing/ambiguous definition or failed read blocks the write. Existing verified-ID calls and successful API output shapes are unchanged. Resolution is not a semantic alias matcher: Agents still inspect definitions and user intent using `references/metadata.md`.

`metadata_catalog` and `metadata_fields` accept an opt-in top-level `view=compact`. Full remains the default and returns raw server rows. Compact preserves field IDs, names, types, descriptions, group names/IDs and enum option IDs, values and descriptions, while removing audit, ordering and duplicated foreign-key fields; it is emitted as one-line JSON so a normal catalog no longer overflows stdout and triggers a second full pull. Compact is a projection only: pagination validation, live checks, identity binding and value resolution are unchanged, and nothing is persisted. Duplicate case-insensitive field names are reported in `addition.nameCollisions` so ambiguity is visible without another discovery call.

HTTP failures retain the existing error string and may add `details` with HTTP status and bounded scalar business error fields. Only JSON envelopes explicitly marked `success=false` are eligible; raw bodies, nested data and headers are not returned. Known credentials, credential-like text and URLs are redacted. Existing 401/403 recovery and no-replay behavior remain unchanged. Runtime diagnostics do not prove the cause of a historical failure without its response.

Metadata field creation is implemented by `metadata_field_create` in the existing metadata capability. Contract source: supplied `assets-metadata-field-save-and-openapi-page.md`. Creation uses `PUT /assets/metadata/field/save` with permission `system.assets.metadata.field.create`; the separate `GET /openapi/assets/metadata/field/page` remains LITE-only. Creation defaults `planType` to PRO, accepts LITE when it matches the user's real asset mode, and supports NUMBER, STRING and TIME in PRO alongside the existing types. Omitted grouping becomes null. Only boolean `data=true` means success; `data=false` or missing data exits nonzero as an unverified outcome that must not be replayed. The LITE paginated query can resolve LITE IDs but cannot resolve PRO creations. The workflow is maintained in `references/metadata.md`; field update/delete remain out of scope. Preserve existing credential selection and bounded auth recovery. No live deployment verification is implied by offline contract tests.

`references/business-context.md` contains the module-specific concepts confirmed for this Skill. Load it only for unclear business objects or intent, not as an extra bootstrap step. Existing capability contracts and execution policies retain their authority; background must not introduce a second workflow.

Source provenance below is for maintainers, relative to the development repository root. PRDs are not packaged runtime dependencies and Agents need not load them:

- `prd/B1.0.1/Basil Studio/用户文档/Library/Library 概览.md` and `标签与元数据.md`: file organization and field/value/tag concepts only; no PRO field types, UI workflows or historical navigation are imported as CLI support.
- `prd/V1.0.2/Library/Library_1.0.2_PRD.md`: asset discovery and Metadata filtering.
- Current `references/directory-context.md`: the executable space model; do not replace its scope or path rules with PRD UI descriptions.

Keep source versions separate: reuse only the stated concepts confirmed against the current contracts, not historical UI details or unimplemented plans. Business background excludes other platform modules and the added query-result presentation mechanisms. Existing query delivery remains in its current execution references. When updating concepts, check routing, supported inputs, mutation boundaries and failure handling together; examples must not become default fields or fixed calls.

## Asset Rule Group maintenance

The five AUTO_TAG endpoints form one domain in `references/rule-groups.md` and `scripts/library/rule_groups.py`. Technical authority: the supplied `assets-rule-group-api.md` (2026-09-23); it is not a runtime dependency. Business sources: `prd/B1.0.1/Basil Studio/用户文档/Library/自动标记规则.md`, `规则概览.md`, `标签与元数据.md`, `浏览与查找资源.md`, and section 3.9 of `prd/V1.0.2/Library/Library_1.0.2_PRD.md`. Keep search Advanced Filters, Metadata field groups and automatic tagging distinct. API limitations override broader PRD UI descriptions for executable requests; unresolved mappings are documented in the capability reference.

Transport retains the existing domain, credential, error and no-replay behavior. In addition to existing OpenAPI paths it permits only the five exact method/path patterns under `/assets/rule/group`; the Runtime prefix is added once. No other non-OpenAPI routes are enabled. No version contract is invented for these APIs.
