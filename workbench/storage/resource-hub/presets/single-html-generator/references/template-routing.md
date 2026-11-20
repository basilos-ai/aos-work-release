# Template Routing

Use this file to choose the smallest useful HTML template. Templates are high-fidelity references; copy or adapt their structure into the final generated single HTML file, then replace placeholders with user-derived content.

## Available Templates

| Template | Use when |
|---|---|
| `templates/homepage-template.html` | Enterprise, corporate, brand, company, official website, landing homepage, or homepage redesign pages with hero media, navigation, feature stories, campaign sections, visual rails, and brand notes. |
| `templates/scroll-balanced-template.html` | General reports, proposals, product overviews, visual references, or mixed pages with narrative, images, tables, and light analysis. |
| `templates/scroll-analytics-template.html` | Data-forward reports, competitor analysis, KPI summaries, dashboards, chart/table-heavy pages, and trend analysis. |
| `templates/atelier-workbench-dashboard-template.html` | Operational, enterprise, and internal dashboards that need a light sidebar, Slate palette, compact KPI cards, data tables, and status-oriented charts. |
| `templates/lookbook-showroom-template.html` | Product, fashion, catalog, multi-item lookbook, and showroom experiences with a first-screen image stage, horizontal quick-switch detail pages, clickable top navigation, gallery, notes, shortlist, and keyboard navigation. |

## Selection Rules

- Choose `homepage-template.html` when the user asks for an enterprise website, company website, corporate website, official website, brand homepage, landing homepage, or homepage redesign.
- Choose `atelier-workbench-dashboard-template.html` when the user asks for a dashboard (including KPI, operational, executive, supply chain, or internal dashboards), unless they explicitly request a report, presentation, or an existing template.
- Choose `scroll-analytics-template.html` when metrics, comparisons, tables, charts, KPIs, or competitor analysis are central but the request is a report or analysis rather than a dashboard.
- Choose `lookbook-showroom-template.html` whenever images, products, fashion items, catalogs, or lookbooks are central, including when the user only says "lookbook" or "catalog".
- Choose `scroll-balanced-template.html` when the material mixes visuals, narrative, recommendations, and moderate structured data.
- If two templates are equally plausible and the user intent cannot be inferred, ask which direction they want.

## Required Placeholder Handling

For scroll templates, replace:

```text
{{page_title}}
{{extra_head}}
{{generated_date}}
{{source_notice}}
{{page_subtitle}}
{{content_body}}
{{extra_scripts}}
```

The scroll templates already include their style class and CSS. Do not reintroduce `{{style_css}}` or `{{body_style_class}}`.

For `atelier-workbench-dashboard-template.html`, replace:

```text
{{page_title}}
{{extra_head}}
{{generated_date}}
{{page_subtitle}}
{{content_body}}
{{extra_scripts}}
```

Compose `{{content_body}}` from the provided dashboard data. Start with `project-switcher` or `filter-bar` where the data has a selectable scope, then use `metrics` (or `metrics k6`), `dashboard-grid`, and `card` modules. For operational dashboards, use its `table-scroll`, `table`, `bar-row`, `distribution`, `worklist`, `work-row`, `mini-bar`, `status`, and `legend` classes when supported by real data. Keep the light sidebar, compact top bar, Slate palette, low-elevation surfaces, and responsive breakpoint unless the user explicitly asks to change them.

Dashboard navigation is functional, not decorative. Match each retained `.nav-item[data-view]` to one `.dashboard-panel[data-panel]` in `{{content_body}}`, using the same value. Each panel must also have the matching `id` (for example, `id="panel-overview"` and `data-panel="overview"`), `tabindex="-1"`, and an optional `data-title` for the compact top-bar title. Remove navigation items that do not have a supported data-backed panel. Do not use this template with only a static content body when the page displays more than one menu item.

Do not render decorative buttons. Add a `.button`, `.filter`, `filter-bar`, or clickable card only when it has a real local interaction that is implemented in `{{extra_scripts}}` and operates on supplied data. Otherwise, render the current state as plain text, a status tag, or omit the control. The template's only built-in action is the Print button, which calls `window.print()`.

For the showroom template, replace:

```text
{{page_title}}
{{brand_label}}
{{season_label}}
{{generated_date}}
{{lookbook_items_json}}
{{page_subtitle_json}}
```

`lookbook_items_json` must be valid JSON. Local image paths used in item images must be converted to `data:` URIs.

For the homepage template, replace:

```text
{{page_title}}
{{site_config_json}}
```

`site_config_json` must be valid JSON. Use this structure:

```json
{
  "pageTitle": "Company Name | Official Website",
  "brandName": "Company Name",
  "hero": { "eyebrow": "...", "title": "...", "dek": "...", "media": { "video": "", "poster": "", "image": "", "alt": "..." }, "actions": [{ "label": "...", "href": "#..." }] },
  "featureA": { "eyebrow": "...", "title": "...", "dek": "...", "media": { "video": "", "poster": "", "image": "", "alt": "..." }, "actions": [] },
  "featureB": { "eyebrow": "...", "title": "...", "dek": "...", "media": { "video": "", "poster": "", "image": "", "alt": "..." }, "actions": [] },
  "campaign": { "eyebrow": "...", "title": "...", "dek": "...", "media": { "video": "", "poster": "", "image": "", "alt": "..." }, "actions": [] },
  "explore": { "eyebrow": "...", "title": "...", "dek": "..." },
  "rail": [{ "eyebrow": "...", "title": "...", "cta": "...", "href": "#...", "media": { "video": "", "poster": "", "image": "", "alt": "..." } }],
  "notes": { "eyebrow": "...", "title": "...", "items": ["...", "..."] }
}
```

Homepage `site_config_json` content rules:

- Fill `eyebrow`, `title`, `dek`, `notes.items`, action labels, and rail labels only with user-supplied or clearly user-implied publishable website copy.
- Do not write visible explanatory copy about the template, implementation, layout, media mechanics, autoplay behavior, responsive behavior, file format, or module purpose. For example, do not write copy like "the page embeds a horizontal MP4 video", "desktop and mobile adaptive display", "muted autoplay", "suitable for official website first screen", or "Campaign Banner use case".
- If the user only asks for a technical capability, such as embedding a video, put the video URL/path in the relevant `media.video` field and keep unrelated copy fields empty.
- If a homepage module has no real user content except media, keep only the media and any user-supplied label. Do not invent a descriptive `dek` just to fill the module.
- If a section would depend on invented marketing claims or placeholder text, remove or hide that section instead of filling it with generic copy.

## Adaptation Rules

- The final artifact must still be one standalone HTML file.
- Inline any page-specific CSS and JavaScript directly in the final HTML.
- Keep only modules supported by real user content.
- Remove or hide optional sections that would be empty.
- Preserve null-safe JavaScript patterns from the templates.
- Do not create a project, dependency folder, external CSS file, or adjacent required asset.

## Final Check

Before finishing, verify:

- All required placeholders have been replaced.
- No unresolved template tokens remain unless they are intentionally shown as source content.
- Local images are converted or omitted.
- Preserve complete image URLs and paths, including signatures and query parameters.
- JavaScript strings are syntax-safe.
- Mobile and print rules still make sense after adaptation.


