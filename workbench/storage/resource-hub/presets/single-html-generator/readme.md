If the user asks to modify this skill, read this file before editing anything.

## Skill Structure

| Path | Responsibility |
|---|---|
| `SKILL.md` | Generation workflow, template routing, output requirements, revision rules |
| `readme.md` | Modification guide and validation checklist |
| `references/html-output-rules.md` | Single-file HTML output constraints |
| `references/template-routing.md` | Template selection rules |
| `templates/` | Mandatory HTML templates for routed page types |

## Modification Map

| Change request | Primary file | Also update | Validation |
|---|---|---|---|
| Change generation workflow | `SKILL.md` | — | Walk through the complete generation flow |
| Change output constraints | `references/html-output-rules.md` | `SKILL.md` if workflow changes | Generate one HTML page and inspect the result |
| Change template routing | `references/template-routing.md` | `SKILL.md`; affected templates | Verify routing selects the expected template |
| Modify a template | `templates/...` | `references/template-routing.md` if routing changes | Generate a page using that template |
| Add a new template | `templates/` | `references/template-routing.md`; `readme.md` Skill Structure | Verify the new route is selected correctly |

## Modification Rules

- `SKILL.md` frontmatter `name` must match the skill folder name.
- `SKILL.md` `description` must describe both what the skill does and when it should be used.
- Keep all paths relative to the skill folder.
- Workflow belongs in `SKILL.md`.
- Output constraints belong in `references/html-output-rules.md`.
- Template routing belongs in `references/template-routing.md`.
- HTML implementations belong in `templates/`.
- Do not place large template code inside `SKILL.md`.
- Do not duplicate routing rules between multiple files.
- Every routed page type must map to exactly one template.

## Common Change Recipes

### Add a new page template

1. Add the HTML file under `templates/`.
2. Add routing rules in `references/template-routing.md`.
3. Update `readme.md` Skill Structure if needed.
4. Generate a matching page and verify the template is selected.

### Change output rules

1. Update `references/html-output-rules.md`.
2. Update `SKILL.md` if generation behavior changes.
3. Generate a real HTML page and verify the new rules.

### Change template routing

1. Update `references/template-routing.md`.
2. Verify every routed category still resolves to one template.
3. Test at least one request for the modified route.

## Validation

- [ ] `SKILL.md` frontmatter `name` matches the skill folder.
- [ ] `SKILL.md` `description` explains purpose and trigger.
- [ ] All referenced paths exist.
- [ ] Every routed category maps to a valid template.
- [ ] No duplicate routing definitions exist.
- [ ] Generated output is a single standalone HTML file.
- [ ] No external CSS or JavaScript files are required.
- [ ] No secrets or placeholder content appear in the output.
- [ ] Verify one normal generation request.
- [ ] Verify one revision request updates the existing HTML instead of rebuilding unrelated content.