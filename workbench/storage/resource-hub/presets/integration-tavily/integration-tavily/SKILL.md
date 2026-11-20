---
name: integration-tavily
description: Use a configured Tavily API connection to inspect usage and perform credit-consuming web search, extraction, mapping, or crawling with explicit confirmation.
---

# Tavily Web Intelligence API

This skill is intended for use exclusively with the `com.tavily.api-key` integration connection.

## Action reference

| Action key | Purpose | Inputs and confirmation |
| --- | --- | --- |
| `getUsage` | Return API key and account usage and limits. | Optional `projectId`. This read does not consume search or extraction credits, but the usage endpoint has a strict rate limit. |
| `searchWeb` | Search the web and optionally return an answer, raw content, or images. | Required `query`; optional depth, topic, date, domain, country, and response controls. Explicit confirmation is required immediately before every call because it consumes credits. |
| `extractUrls` | Extract and optionally rerank content from supplied URLs. | Required `urls`; optional query, depth, format, image, favicon, chunk, and timeout controls. Explicit confirmation is required immediately before every call because it consumes credits. |
| `mapSite` | Discover URLs in a website graph without full extraction. | Required `url`; optional instructions, graph limits, path filters, external-domain behavior, and timeout. Explicit confirmation is required immediately before every call because it consumes credits. |
| `crawlSite` | Discover pages and extract their content. | Required `url`; optional instructions, graph limits, extraction depth, path filters, format, and timeout. Explicit confirmation is required immediately before every call because it consumes credits. |

## General workflow

1. Clarify the exact information need and the allowed public-web scope.
2. Use `getUsage` when remaining credits or plan limits are uncertain.
3. Select the least expensive action and conservative parameters that can answer the request.
4. Show a concise request and credit-impact preview.
5. Ask for explicit confirmation for that exact call.
6. Invoke the credit-consuming action only after confirmation in the current interaction.
7. Report the returned `usage.credits` and `request_id` when available.

## Credit confirmation rules

Every `searchWeb`, `extractUrls`, `mapSite`, and `crawlSite` call is billable in credits. A general request to research a topic is not sufficient run-time confirmation. Immediately before the call, show:

- The selected action.
- The query, URL list, or root site.
- Search or extraction depth.
- Result count, crawl limit, map limit, and graph depth as applicable.
- Whether generated answers, raw content, images, instructions, or external domains are enabled.
- The known credit cost or a clear statement that the final cost depends on successful pages.

Ask the user to confirm that exact scope and cost. Obtain confirmation again if any parameter that can increase scope or cost changes.

## Search guidance

Use `searchWeb` for open-web discovery. Keep `searchDepth` at `basic` unless the user needs higher relevance and confirms the advanced cost. Basic, fast, and ultra-fast search currently cost one credit; advanced search currently costs two credits.

Use `topic: news` for current mainstream news and `topic: finance` for financial content. Use date filters only when they reflect the user's intended time window. Domain allowlists are preferred when authoritative sources are known. Avoid requesting raw content or images unless the downstream task needs them.

## Extraction guidance

Use `extractUrls` when the URLs are already known. Accept no more than 20 public URLs in one request. Prefer `extractDepth: basic`; use `advanced` only for complex pages after confirming the higher credit rate. Provide `query` only when reranking content against a clear intent is useful.

Show the complete URL list before confirmation. Do not send private, signed, intranet, localhost, or credential-bearing URLs.

## Map and crawl guidance

Use `mapSite` to discover page URLs. Use `crawlSite` only when page content is required. Start with `maxDepth: 1`, `limit: 10`, and `allowExternal: false`. Increase breadth, depth, page limit, or external-domain scope only when necessary and reconfirm the larger scope.

Path filters are regular expressions. Review them carefully so an intended narrow pattern does not become a broad crawl. Natural-language `instructions` can change credit use and should be included in the confirmation preview.

## Usage and rate limits

Use `getUsage` no more than once per minute in routine workflows. Tavily currently applies a 100-request-per-minute limit to development keys, a higher general limit to production keys, and a separate 100-request-per-minute crawl limit. Respect a `429` response and its `retry-after` header; do not immediately retry.

Stop and report plan-limit errors instead of attempting alternative keys, increased limits, or billing changes.

## Limits

- Do not create, rotate, reveal, or delete API keys.
- Do not change plans, pay-as-you-go limits, billing, or projects.
- Do not use the package for private-network or authenticated-page extraction.
- Do not bypass robots restrictions, access controls, paywalls, or service policies.
- Do not run live API calls solely to validate this package.
- Do not start asynchronous Research tasks; they are outside this release.
