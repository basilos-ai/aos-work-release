# Business input collection and selection

These rules cover ordinary business questions and forms; authorization cards and secret collection still follow [auth.md](auth.md). Capability references define candidate sources and specific constraints.

## When to ask

1. Reuse information explicitly provided in the current request and context; resolve names, entity types, and scope through current reads. Recent creation or identical names alone do not imply the user's selection.
2. Collect only missing or ambiguous information that affects the result. Do not turn every optional API parameter into a question; values such as "disable" or "folder" that map uniquely need no repeated selection. The Agent handles page sizes, cursors, versions, audit fields, and readable IDs.
3. Read current state before editing. Preserve other required fields when only part of the object changes; do not make the user re-enter them. For full editing, show existing selections. Distinguish unchanged, explicitly cleared, and unanswered fields; missing fields are not empty collections.
4. Collect independent missing inputs for the same stage together where possible. Split steps only when candidates depend on an earlier choice; retain other submitted values when correcting errors.
5. Follow the SKILL write-authorization boundary: form submission covers only the explicitly displayed target, scope, and entered values, not other operations. Do not request authorization again when already explicit. Cancellation, closure, non-submission, or tool failure is not a selection and cannot authorize dependent writes.

Before asking for input, complete the relevant read-only target/candidate checks that do not depend on that input. If those checks already establish an access denial or another blocking condition, report it before opening a form. Authentication verification alone does not establish business permission, and a successful read is not a guarantee that a later write will succeed. Do not add unrelated permission probes.

## Fields and candidates

- Enums: Offer the complete set allowed by the current operation; use single-select for one value and multi-select for collections. Filter shared enums by endpoint constraints, not Agent preferences. Do not replace enums with free text, existing objects' configuration bundles, or a few recommendations.
- Dynamic entities: Read the options endpoint or tree specified by the capability and cover all valid candidates, restricted to an explicitly requested scope when applicable. Do not offer only recent objects, the first page, or arbitrary candidates and ask users to type "other" values.
- Separate entity types into distinct fields, such as system roles and departments, users and departments, or legacy organization permissions and application permissions. A combined API response or array does not require a combined UI field. Collect separately, then construct the request according to its contract.
- Use readable business names in labels and full department/folder paths; add enough information to distinguish duplicate names. Values must be real IDs/enums, with IDs as decimal strings. Do not require users to understand or enter internal codes.
- Show only editable, effective fields for the operation. Do not create controls for server-ignored or generated fields, or offer unsupported states or functionality.
- Do not preselect permissions or grant subjects or expand scope without authorization, except for existing edit values and explicitly chosen values. Product UI defaults are not user authorization.

## Native field bindings

For Workbench `request_user_input`, use the following field bindings when exposed by the current tool schema. The schema received by the model for this Attempt is authoritative; do not substitute a different tool merely because it has the same name.

|Input semantics|Field arguments|Submitted value|
|---|---|---|
|Free-form remarks or a new object name|`type: "text"`|String|
|One enum value or one existing entity|`type: "single_select"`, complete `options`|One option value|
|A collection of enum values or existing entities|`type: "multi_select"`, complete `options`|Array of option values|

Each option has a readable `label` and its exact `value`; use decimal strings for IDs and original enum strings for enums. Use the corresponding API field name as the form field `name` where possible. For example, a permission option is `{"label":"Admin Console / Role management","value":"135000"}`; this illustrates one option's shape, not a complete candidate list. Build the actual `options` from every entry in the capability's authoritative source before invoking the tool. Do not send placeholders, ellipses, or this single example as the full list.

Listing all enum values in chat, a field label, or a description does not create a selection control. The actual tool arguments must contain the selection `type` and its `options`. Instructions to type names/IDs separated by commas are not multi-select behavior. In particular, do not replace `permissionList` with a text field named `permissions` or with module-specific text fields such as `perms_assets` and `perms_workflow`.

Use one complete selection field per logical collection by default. Grouping, when supported, stays within that field. Do not split a finite collection merely because it looks long or has several modules. A dropdown's visual presentation is controlled by the host; setting `multi_select` requests selection semantics, but the actual rendering must be verified in the host.

## Completeness and host capabilities

Use only fields and properties actually supported by the current host tool. Do not assume search, grouping, tree controls, default values, or cross-field validation are available.

Before reporting that a selection control is unsupported, identify the restriction in the current tool schema or an explicit tool rejection. An unavailable schema means capability is unverified, not that the host is text-only. Missing search/grouping/tree support does not imply missing basic single-select or multi-select support. Do not infer a field or option limit from a different environment, an earlier Attempt, or the size of the permission list.

If the current schema explicitly lacks selection fields, or the host explicitly rejects them as unsupported, explain the specific mismatch and leave dependent selection unresolved. Continue independent work, but do not silently downgrade to text, treat an unanswered selection as empty, or claim the requested form was delivered. If the schema uses a documented equivalent selection structure, follow that structure while preserving complete options and typed values. Do not invent unsupported arguments or repeatedly call a rejected form.

For large candidate sets, prefer supported in-field search/grouping. Only a documented capacity limit or explicit capacity error justifies splitting a finite collection into multiple selection steps. All such steps must still use selection controls, preserve selected values, and cover the complete collection before submission. Read dynamic pagination to completion within the protocol's call bounds; if a verified host limit prevents presenting the set, explain it and ask for a search scope, then offer all candidates within that scope. Never silently truncate or claim an incomplete set is complete. Paging or filtering must not discard selections.

Distinguish read failure, incomplete results, and genuinely empty lists. Do not invent candidates. If a complete candidate source is unavailable, state the limitation and retain unresolved items; existing object configurations are not the full candidate set.

## Submission and validation

- Before invoking `request_user_input`, inspect the actual outgoing arguments: every unresolved enum/entity field has a supported selection type and nonempty `options`; each option has a label and a unique value; the value set equals the complete operation-valid candidate set within the explicit scope. An empty candidate set must be reported as such rather than replaced with a text field. Check that free-form fields are genuinely free-form and that known inputs are not requested again.
- Check the actual returned selection values against the offered values and expected scalar/array shape before building the business request. Do not parse a comma-separated string as a successful multi-select response. If the host omits an optional empty selection, apply its documented submission semantics; without such semantics, omission is unresolved, not permission to clear or create empty permissions.
- Explain business constraints in the form. The Agent validates cross-field relationships before submission; the existing CLI retains deterministic validation. Lack of host cross-field validation does not justify changing field separation.
- Empty-array validity follows the endpoint contract. Explain the effect of an empty selection; only a successfully submitted, unambiguous empty selection maps to an empty array. Never clear existing edit values by default.
- Map selections to original API fields while preserving omitted/null/empty-array semantics. Expanded preset responses, inherited results, and computed fields must not be copied directly into write parameters.
- Do not impose selection-count limits absent from the contract. Describe scope in concise business language; understanding a form must not require reading request JSON or ID lists.

## Acceptance evidence

Review the actual tool-call arguments and host rendering, not just the Agent's prose. For role creation with only a name supplied, expect one remarks text field and one `permissionList` multi-select whose option values exactly match all system permission IDs (currently 47). For ACL creation with scope already supplied, expect separate complete role and department multi-selects with an at-least-one check. Exercise explicit empty selection, cancellation, unavailable selection support, and a verified capacity limit without text fallback or lost choices. Business CLI tests do not prove Agent form generation or host rendering; record these checks separately and do not claim live acceptance without a real host run.
