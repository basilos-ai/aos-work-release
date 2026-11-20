# HTML Output Rules

Use these rules when generating or revising a single-file HTML artifact.

## Single-File Contract

A valid output is one `.html` file that can be opened directly in a browser.

Required:

- Inline CSS in `<style>`.
- Inline page JavaScript in `<script>`.
- Avoid required adjacent files.
- Avoid local relative paths in `src`, `href`, CSS `url()`, fetch calls, workers, imports, or modules.
- Convert necessary local images to `data:` URIs.

Allowed when useful:

- Remote URLs that already exist in the user's source materials.
- CDN scripts only for small, clearly justified runtime dependencies such as chart libraries, unless the user requires offline operation.

Avoid:

- Build steps.
- Package manifests.
- Framework scaffolds.
- External CSS frameworks.
- Placeholder modules.

## Image Path Integrity

Signed or parameterized image URLs must be preserved exactly as supplied.

Do not truncate, normalize, decode, re-encode, sort, or remove any part of an image path or URL, including:

- Query strings such as `?x-oss-signature=...` or `?Expires=...`.
- Access tokens, signatures, policy parameters, and cache-busting values.
- URL fragments.
- Percent-encoded characters.
- Long filenames or nested path segments.

When embedding an image in HTML or JavaScript, escape it for the target context without changing the underlying URL string. If converting a local image to a `data:` URI, use the converted data URI in full.

## HTML Safety

Escape user content correctly for the context where it appears:

- Text nodes: HTML-escape `<`, `>`, and `&`.
- Attributes: also escape quotes.
- JavaScript strings: JSON-encode values instead of manual quoting when possible.
- CSS strings and URLs: avoid injecting untrusted raw text.

Do not include secrets, access tokens, API keys, private headers, or debug logs.

## JavaScript Reliability

Keep scripts null-safe. One missing optional element must not break the page.

When creating JavaScript strings, escape line breaks as `\n`. Do not place literal newlines inside quoted strings.

Prefer simple event listeners and small helper functions. Avoid large app frameworks unless the user explicitly asks and the output can still remain a single HTML file.

## Layout And Responsiveness

Use semantic HTML where practical.

Ensure:

- Text does not overlap or overflow containers on common mobile and desktop widths.
- Fixed-format areas such as cards, tables, charts, toolbars, and image grids have stable dimensions or responsive constraints.
- Images use `max-width: 100%` and sensible object fitting.
- Tables remain readable with horizontal scrolling when needed.
- Interactive controls have visible focus states.
- Motion respects `prefers-reduced-motion: reduce` when animation is used.

## Print And Export

For report-like pages, include `@media print` rules that:

- Hide nonessential controls.
- Preserve readable colors when reasonable.
- Avoid cutting important cards, tables, and charts awkwardly.

A browser print button using `window.print()` is optional unless the user asks for PDF/export behavior.

## Charts And Data

Use charts only when they make the data easier to understand.

Keep exact values visible in a nearby table or labels when precision matters.

Do not alter source values while formatting.

Choose simple chart types:

- Bar charts for category comparison.
- Line charts for time or ordered trends.
- Pie or doughnut charts only for a small number of parts-of-whole categories.
- Tables when exact values are the main point.

## Final Check

Before finishing, check for:

- Missing closing tags in edited areas.
- Unescaped user content in HTML, attributes, or scripts.
- Relative local paths that would break outside the workspace.
- Empty sections or placeholder text.
- JavaScript syntax risks from quotes or line breaks.
- Mobile layout problems that are obvious from the CSS.


