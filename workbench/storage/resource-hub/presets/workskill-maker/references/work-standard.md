# Work Standard

A Work is a coordinated collection of first-level member Skills for one end-to-end business outcome.

## Design members

Split members at stable responsibility boundaries such as plan, execute, verify, or distinct domain capabilities. Do not split a simple single-purpose workflow merely to create a Work. Do not duplicate shared policy across every member; keep common detailed rules in a reference owned by the Work when useful.

Each member must be independently discoverable from its frontmatter description while remaining clear about its role in the wider Work. Document handoff inputs and outputs when one member feeds another. Do not imply that one member may perform another member's external side effect without the same authorization.

## Structure

```text
works/
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

The Work root has no `SKILL.md`. It has at least one exact first-level member, and every member contains `SKILL.md`, `readme.md`, and `user_preferences.md`.

## Validation

- Every member has a unique safe name and non-empty description.
- Every member has exact lowercase, non-empty `readme.md` and `user_preferences.md` files.
- Member responsibilities are cohesive and non-overlapping.
- Handoffs preserve required context and authorization boundaries.
- All member resource links resolve inside the Work or to an explicitly available runtime dependency.
- The Work root contains no `SKILL.md`.

## Interaction boundaries

Use secure password forms only for credentials. Ask ordinary material gaps and necessary authorization questions in chat, never through a form. Reuse supplied facts and authorization covering the current operation, target and cost scope; ask again only for missing authorization or a material change. Do not add a human visual-review or visual-approval gate. Retain automatic structural/layout checks and report unavailable rendering honestly without blocking delivery solely for that limitation. Content review, when required by the workflow, uses ordinary chat and reuses approval already covering the current content.
