If the user asks to modify this skill, read this file before editing anything.

## Skill Structure

| Path | Purpose |
|------|---------|
| `SKILL.md` | Skill definition: when to produce HTML artifacts vs. stay in markdown, the seven universal rules every artifact must satisfy, the category index table that routes requests to reference files, and output mechanics for Claude Code vs. Claude.ai. Do not change the `name` field. |
| `user_preferences.md` | Stores persistent user preferences (e.g., saved style tokens, default output behaviors). Read before running; write back after changes. |
| `references/exploration-and-planning.md` | Pattern for side-by-side option comparisons, visual design exploration grids, and implementation plans (milestones strip, data-flow diagram, risk table). |
| `references/code-review-and-pr.md` | Pattern for annotated diffs with margin annotations and severity tags, PR writeups, and module maps / "explain this code" artifacts. |
| `references/design-and-prototypes.md` | Pattern for living design systems, component variant sheets, animation/interaction prototypes, and clickable interaction flows. |
| `references/diagrams-and-illustrations.md` | Pattern for inline SVG figure sheets, annotated flowcharts, and SVG craftsmanship notes (viewBox, currentColor, grouped elements). |
| `references/reports-and-research.md` | Pattern for concept explainers with live demos, feature explainers, status reports, and incident post-mortems with visual timelines. |
| `references/decks.md` | Pattern for arrow-key navigable slide decks built from `<section>` tags plus ~20 lines of JavaScript. |
| `references/custom-editors.md` | Pattern for one-off throwaway editors (triage boards, flag toggles, prompt tuners) with the non-negotiable export button rule. |
| `references/matching-your-style.md` | Guidance on matching the user's existing design system, the safe default CSS palette, and what the "AI default look" to avoid is. |
| `LICENSE` | Apache License 2.0 covering the skill package. Do not edit. |
| `readme.md` | This file: the modification guide. |

## Modification Map

| Change Request | Primary File | Files Usually Updated Together | How to Validate |
|----------------|-------------|-------------------------------|-----------------|
| Add or remove an artifact category | `SKILL.md` (category index table) | A new `references/<category>.md` file (or deletion), `references/matching-your-style.md` if style rules need updating | Check the category index table: every row's `references/*.md` path exists on disk |
| Change the universal rules every artifact must satisfy | `SKILL.md` ("Universal rules" section) | `references/matching-your-style.md` (taste/typography rules), each category reference that demonstrates a rule | Re-read SKILL.md and confirm the rule list is still numbered 1–7 and no reference contradicts it |
| Adjust when to use HTML vs. markdown | `SKILL.md` ("When to reach for HTML" / "When to stay in markdown") | None typically | Re-read the two sections and confirm they are mutually consistent and still reference the category index |
| Change a single category's layout guidance, load-bearing elements, or mistakes | The specific `references/<category>.md` file | `SKILL.md` only if the category's name or routing description changes | Open the reference and confirm its three sections (Layout / What's load-bearing / Common mistakes) are still present |
| Update the safe default palette or typography | `references/matching-your-style.md` (CSS block) | `SKILL.md` if the "tasteful by default" universal rule changes | Generate a sample artifact and confirm it renders with the new tokens in both light and dark mode |
| Change output mechanics (file naming, Claude.ai rules) | `SKILL.md` ("Output mechanics" section) | `references/custom-editors.md` if persistence rules are affected | Re-read the section and confirm the Claude Code vs. Claude.ai branches are still clearly separated |
| Update license attribution or terms | `LICENSE` | None | No code change; verify the license text still parses as Apache 2.0 |

## Modification Rules

- Only modify files listed in the Modification Map.
- Do not change the `name` field in SKILL.md frontmatter.
- Keep file paths and references intact — they may be referenced by SKILL.md.
- Test after every change using the Validation section below.

## Common Change Recipes

**Recipe 1: Add a new artifact category (e.g., "interactive maps")**

1. Create `references/interactive-maps.md` following the existing reference structure: a `## Layout` section (with a concrete layout), a `## What's load-bearing` section, and a `## Common mistakes` section, plus an example sketch where helpful.
2. Register it in `SKILL.md` by adding a row to the category index table with a short "If the request is about…" description and the new `references/interactive-maps.md` path.
3. If the new category has style implications, add a note to `references/matching-your-style.md`.
4. Validate: open the category index in SKILL.md and confirm every row maps to a real file; skim the new reference to confirm all three sections are complete.

**Recipe 2: Tighten the universal rules (e.g., require an explicit accessible alt/label policy)**

1. Edit the "Universal rules" section in `SKILL.md`, updating the relevant numbered rule or adding a new one (renumbering the list 1–8 if added).
2. Grep the reference files for places that would now violate the rule (e.g., SVG figures in `references/diagrams-and-illustrations.md`) and update their example sketches.
3. Validate: re-read SKILL.md rules top to bottom, confirm the numbering is sequential, and confirm no example sketch in any reference contradicts the new rule.

**Recipe 3: Replace the safe default visual style**

1. Edit the CSS block in `references/matching-your-style.md` (the `:root` variables and dark-mode overrides).
2. Check the other references for hard-coded colors that would now clash (e.g., severity colors in `references/code-review-and-pr.md`) and align them with the new tokens.
3. Validate: build a sample HTML artifact using the new tokens, open it in a browser, and verify it renders readably in both light and dark `prefers-color-scheme`.

**Recipe 4: Refine the deck keyboard behavior (e.g., add presenter notes toggle)**

1. Edit `references/decks.md` — update the Layout section for the new key and adjust the example skeleton `<script>` block.
2. If the change conflicts with Claude.ai artifact constraints, update the "Output mechanics" note in `SKILL.md`.
3. Validate: copy the example skeleton into a local `.html` file, open it, and confirm the new key binding works and the slide counter still updates.

## Validation

Before finishing any change, verify all of these:

- [ ] The category index table in `SKILL.md` has one row per reference and every `references/*.md` path it lists exists in the package.
- [ ] The universal rules section in `SKILL.md` is sequentially numbered and every rule is reflected somewhere in the reference files.
- [ ] Every reference file still has its required sections (Layout / What's load-bearing / Common mistakes) after edits.
- [ ] `SKILL.md` mentions no file paths beyond the `references/` files and `user_preferences.md` that do not exist.
- [ ] The example HTML skeletons in the references are self-contained (inline `<style>`/`<script>`, no missing closing tags at a glance, use `viewBox` not fixed dimensions in SVG).
- [ ] The Claude.ai platform constraints noted in `SKILL.md` (no localStorage, allowed CDNs only) are not contradicted by any recipe or example.
- [ ] The `name` field in SKILL.md frontmatter is unchanged and `LICENSE` is untouched.
