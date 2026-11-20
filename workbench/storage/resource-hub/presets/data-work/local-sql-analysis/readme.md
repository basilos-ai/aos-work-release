If the user asks to modify this skill, read this file before editing anything.

## Skill Structure

`SKILL.md` defines local SQL planning, execution boundaries, and validation. `user_preferences.md` contains optional output preferences.

## Modification Map

Change dialect or validation guidance in `SKILL.md`. Add scripts only when deterministic local execution materially improves reliability.

## Modification Rules

Keep remote credentials out, preserve read-only defaults, and distinguish generated from executed evidence. Do not silently install runtimes.

## Common Change Recipes

Add a dialect by documenting its quoting, date, cast, and file-access differences. Add a validation check that reconciles to an independent aggregate.

## Validation

Run the Workbench Skill validator and test with mixed data types, missing values, a many-to-many join risk, and an unavailable requested runtime.
