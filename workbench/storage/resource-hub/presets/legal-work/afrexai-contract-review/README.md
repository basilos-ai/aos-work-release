If the user asks to modify this skill, read this file before editing anything.

## Skill Structure

| Path | Responsibility |
|---|---|
| `SKILL.md` | Runtime capability, workflow, boundaries, and results. |
| `readme.md` | Maintenance map and validation checklist. |
| `user_preferences.md` | User-approved durable output preferences. |
| `_icon.png` | Supporting runtime or reference material preserved for this member. |
| `_meta.json` | Supporting runtime or reference material preserved for this member. |
| `README.md` | Supporting runtime or reference material preserved for this member. |

## Modification Map

| Change request | Primary file | Also inspect | Validation |
|---|---|---|---|
| Change runtime behavior or trigger | `SKILL.md` | Referenced resources | Validate frontmatter, paths, and a representative scenario. |
| Change a helper or reference | The relevant supporting file | `SKILL.md` routing | Run the helper or verify the referenced guidance remains reachable. |

## Modification Rules

- Preserve the member's capability, safety boundaries, and relative resource paths.
- Keep the folder name and frontmatter `name` identical.
- Do not add credentials, machine-specific paths, or unverified external actions.

## Common Change Recipes

Update a reusable rule in its supporting resource when one exists; otherwise make the smallest change in `SKILL.md`, then test the affected workflow.

## Validation

- [ ] Frontmatter contains a matching name and a discriminating description.
- [ ] Referenced files exist and scripts compile or run where applicable.
- [ ] No sensitive sign-in data, machine-specific path, or unintended external write was added.
- [ ] Structural checks are not reported as live functional validation.
