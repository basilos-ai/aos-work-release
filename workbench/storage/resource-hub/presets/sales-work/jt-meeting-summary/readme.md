If the user asks to modify this skill, read this file before editing anything.

## Skill Structure

| Path | Responsibility |
|---|---|
| `SKILL.md` | TODO: describe runtime responsibility |
| `readme.md` | Maintenance guide and validation checklist |
| `user_preferences.md` | User-approved persistent preferences |

## Modification Map

| Change request | Primary file | Also update | Validation |
|---|---|---|---|
| TODO: fill based on actual files | | | |

## Modification Rules

- `SKILL.md` frontmatter `name` must match the skill folder name.
- `SKILL.md` `description` must describe both what the skill does and when it should be used.
- Keep all relative paths relative to the skill folder.
- Never place API keys, secrets, or environment-specific values in documentation.

## Common Change Recipes

### Change Runtime Behavior

1. Update `SKILL.md`.
2. Update this file only if file responsibilities change.
3. Walk through the full flow once and verify output is consistent.

## Validation

- [ ] `SKILL.md` frontmatter `name` matches the skill folder.
- [ ] `SKILL.md` `description` explains both purpose and trigger.
- [ ] All referenced paths exist.
- [ ] No API keys or secrets appear in documentation.
- [ ] No duplicate ownership exists for the same rule.
