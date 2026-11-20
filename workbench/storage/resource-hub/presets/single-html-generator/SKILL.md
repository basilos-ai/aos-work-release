---
name: "single-html-generator"
description: "Generate, revise, or transform supplied materials into a browser-ready single-file HTML page. Use when the user asks for an HTML page, report, catalog, dashboard, visual reference, proposal, or other standalone frontend artifact that must not become a multi-file project."
---

# Single HTML Generator

## Purpose

Create one polished HTML file from user-supplied text, Markdown, tables, data, images, links, or mixed materials.

Keep the skill small. Prefer direct reasoning and simple HTML over reusable machinery unless the user request truly requires more structure.

## Core Workflow

1. Read the exact materials named by the user.
2. Infer the page goal, audience, content hierarchy, and useful interactions.
3. Read `references/template-routing.md` and use the mandatory template for any routed page type.
4. Generate one standalone `.html` file.
5. Verify obvious syntax, rendering, and dependency risks when tools are available.
6. Report the output path and any meaningful assumptions.

If the input source is unclear, ask which file, text, image, or data source to use.

## Required Output

The output must be a single frontend HTML file that opens directly in a browser.

Hard rules:

- Do not create a React, Vue, Vite, Next, npm, or other project structure.
- Do not create adjacent CSS, JavaScript, image, JSON, or asset files required by the page.
- Put CSS inside `<style>`.
- Put page JavaScript inside `<script>`.
- Do not reference local files with relative paths in the final HTML.
- Convert local images needed by the page to `data:` URIs, or omit them if conversion is not practical.
- Preserve full image URLs and paths exactly, including query strings, signatures, tokens, fragments, percent-encoding, and other parameters.
- Use stable remote image URLs only when the source already provides them or the user asks for them; keep the complete URL unchanged.
- Do not expose API keys, tokens, secrets, debug dumps, raw Python reprs, or raw data structures.
- Do not render empty sections, fake placeholders, or "coming soon" content.
- Keep the page responsive for desktop and mobile.
- Include print-friendly CSS when the page is report-like or likely to be exported.

For detailed output constraints, read `references/html-output-rules.md`.

## Content Handling

Preserve user-provided facts, names, values, conclusions, labels, ordering, and source meaning.

Use inference only when it improves structure or readability. Do not invent product attributes, metrics, prices, dates, citations, claims, or source-backed facts.

Do not turn implementation requirements into visible page copy. Requirements such as "embed a video", "responsive on desktop and mobile", "muted autoplay", "MP4", "campaign banner", "official website first screen", or template/module behavior are build instructions, not marketing text. Unless the user supplies real publishable copy, keep the corresponding title, dek, note, or caption empty and omit unsupported sections.

When converting structured data:

- Keep source values intact.
- Use tables when exact comparison matters.
- Use charts only when they clarify a pattern and can be implemented safely in the single file.
- Keep chart source values visible nearby when possible.

When handling images:

- Prefer user-supplied images over decorative filler.
- When multiple images are provided for the same product from different angles, choose the best primary display, cover, hero, or card thumbnail by tag priority: images tagged with both `front_view` and `full_body` first, then `front_view`, then `full_body`, unless the user explicitly asks for another angle or crop.
- Avoid fake placeholders.
- Add useful alt text from available context.

## Design Guidance

Design the page for the task, not for a fixed template.

Use restrained, readable styling by default: clear hierarchy, adequate spacing, responsive layout, accessible contrast, stable containers, and predictable interactions. Add richer visual treatment only when the user request or materials call for it.

Future style or layout systems should live in `references/` and be loaded only when relevant. Do not expand this main file with detailed style catalogs.


## Mandatory Template Routing

Read `references/html-output-rules.md` for detailed single-file HTML constraints.

Read `references/template-routing.md` before generating any full HTML page. For routed page types, using the selected template is mandatory. Do not freestyle a replacement layout for these categories.

When a request matches any routed category below, read the selected file in `templates/`, preserve its core structure, class names, IDs, and interaction model, then replace its placeholders with user-derived content.

Available template references:

- `templates/homepage-template.html` for enterprise, corporate, brand, company, or official website homepages.
- `templates/scroll-balanced-template.html` for general mixed pages.
- `templates/scroll-analytics-template.html` for chart, KPI, competitor, and data reports.
- `templates/atelier-workbench-dashboard-template.html` for dashboards, operational workbenches, and internal KPI views.
- `templates/lookbook-showroom-template.html` for all product, fashion, catalog, and multi-item lookbook/showroom pages.

Mandatory routing:

- For enterprise, corporate, company, brand, official website, homepage, landing homepage, or homepage redesign requests, use `templates/homepage-template.html`.
- For product, fashion, catalog, asset collection, image collection, DAM assets, product JSON, multi-image JSON, multi-item visual data, or any request containing "lookbook", use `templates/lookbook-showroom-template.html`.
- For dashboard, operational dashboard, internal dashboard, executive dashboard, or KPI dashboard requests, use `templates/atelier-workbench-dashboard-template.html`.
- For KPI, metric, competitor analysis, comparison, chart, table-heavy, or data-forward report requests that are not dashboards, use `templates/scroll-analytics-template.html`.
- For mixed narrative pages, proposals, visual references, or general presentation pages that do not match the above categories, use `templates/scroll-balanced-template.html`.

Dashboard interaction requirements:

- The workbench dashboard sidebar must switch content panels, not merely update the active navigation style.
- Every retained `.nav-item[data-view]` must map to one `.dashboard-panel[data-panel]` with the same value, matching `aria-controls` / `id` values, and the generated HTML must preserve the template's `activateDashboardView` logic.
- Remove unsupported navigation items rather than leaving menu entries with no panel to display.
- Do not render buttons, filter chips, clickable cards, or other controls without a real implemented local interaction and data-backed result. Omit unsupported controls rather than presenting a non-functional interface.

Lookbook/showroom requirements:

- If the user asks for a lookbook, catalog, product image page, image collection page, asset lookbook, product JSON page, or DAM asset visual page, the final HTML must use the showroom template interaction model.
- The final HTML must preserve these showroom markers unless the user explicitly asks to remove the corresponding feature:
  - `LOOKBOOK_ITEMS`
  - `screenStage`
  - `screenDetail`
  - `looksRow`
  - `detail-track-inner`
  - `detail-slide`
  - `detailTrackInner`
  - `nav-pill`
  - `translateX(`
  - `shortlist`
- If a lookbook/catalog/product/image-collection output does not include these markers, treat it as incorrect and revise it using `templates/lookbook-showroom-template.html`.
- Do not replace the showroom template with a custom grid, filter gallery, masonry page, ordinary scrolling catalog, or report-style layout unless the user explicitly requests that different layout.

Template adaptation rules:

- Preserve the selected template's core layout and interactions.
- Replace placeholders with valid escaped HTML or JSON values.
- Remove only sections unsupported by real user content.
- Do not add chatbots, assistant iframes, typekey iframes, or floating chat widgets.
- Do not create a project folder or adjacent required assets.

## Revision Rules

When revising an existing generated HTML page, reuse the current source materials and output target unless the user asks for a new version or new inputs.

Prefer editing the HTML directly over rebuilding unrelated structure.




