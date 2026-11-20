If the user asks to modify this skill, read this file before editing anything.

## Skill Structure

| Path | Purpose |
|------|---------|
| `manifest.yaml` | Connector definition: auth (API key in Authorization header), 5 Tavily actions (getUsage, searchWeb, extractUrls, mapSite, crawlSite), error mapping, rate limits, redaction rules. **Do not edit unless you understand the connector schema.** |
| `skills/integration-tavily/SKILL.md` | Runtime instructions: how the agent uses the Tavily actions, parameter guidance, usage scenarios. Primary entry point for the skill layer. |
| `user_preferences.md` | Stores user-approved persistent preferences (initially empty). |
| `readme.md` | This maintenance guide. |

## Modification Map

| Change Request | Primary File | Files Usually Updated Together | How to Validate |
|----------------|-------------|-------------------------------|-----------------|
| Add a new Tavily API action | `manifest.yaml` (actions list) | `skills/integration-tavily/SKILL.md` (document usage) | Inspect YAML parses, confirm the action matches Tavily API docs |
| Adjust an action's parameters or defaults | `manifest.yaml` (matching action block) | `skills/integration-tavily/SKILL.md` (parameter guidance) | Dry-run the action request body, confirm parameters map correctly |
| Change API endpoint URL | `manifest.yaml` (action `url` field) | — | Confirm the URL matches Tavily's published endpoints |
| Update auth placement or header | `manifest.yaml` (auth block) | `skills/integration-tavily/SKILL.md` if auth notes exist | Confirm Authorization header + Bearer prefix match Tavily docs |
| Adjust rate limit or redaction rules | `manifest.yaml` (rateLimit / redaction blocks) | — | Confirm YAML parses and redaction paths match request/response shapes |

## Modification Rules

- Only modify files listed in the Modification Map.
- Do not change the `name` field in the skill frontmatter or the connector `key` (`com.tavily.api-key`).
- Keep the `{{input.*}}` template syntax intact — the connector engine substitutes these at runtime.
- Keep `responseDataPath: "$"` semantics unless the API response shape changes.
- Redaction paths must cover any field carrying user text or the API key; never remove redaction for `Authorization`.
- Do not store API keys, tokens, or credentials anywhere in this package.
- Test after every change using the Validation section below.

## Common Change Recipes

**Recipe 1: Add a new Tavily action (e.g., a new API method)**

1. Add an action block to `manifest.yaml` following the existing pattern (`key`, `name`, `description`, `method`, `url`, `auth: true`, `input` fields, `body` with `{{input.*}}` placeholders).
2. Add the relevant error codes to the `errors` map if the endpoint returns distinct codes.
3. Document the new action's usage in `skills/integration-tavily/SKILL.md`.
4. Validate the YAML parses and the request body maps all inputs correctly.

**Recipe 2: Change the search endpoint's default maxResults**

1. Edit the `maxResults` `default` in `manifest.yaml` searchWeb action.
2. Update any matching guidance in `skills/integration-tavily/SKILL.md`.
3. Confirm the body maps `{{input.maxResults}}` to `max_results` unchanged.

**Recipe 3: Adjust rate limiting**

1. Edit the `rateLimit` block (`subject`, `limit`, `windowSeconds`) in `manifest.yaml`.
2. Confirm the values align with the user's Tavily plan to avoid false 429s.

## Validation

Before finishing any change, verify all of these:

- [ ] `manifest.yaml` parses as valid YAML (`python -c "import yaml; yaml.safe_load(open('manifest.yaml', encoding='utf-8'))"`)
- [ ] Every action's `body` values use only declared `{{input.*}}` placeholders
- [ ] Every declared input field appears in the action's `input` section
- [ ] Redaction paths cover `$.headers.Authorization` and all user-text body fields
- [ ] `skills/integration-tavily/SKILL.md` contains no Chinese characters and no author/version metadata
- [ ] No API keys or credentials are present in any file
- [ ] No `_meta.json` / `_skillhub_meta.json` / `.DS_Store` files exist in this package
- [ ] `user_preferences.md` contains the standard initial content
