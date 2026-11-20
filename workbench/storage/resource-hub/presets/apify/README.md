# Apify Platform Declarative Integration

This package follows the current declarative integration specification for the Apify API. It stores the Apify API token in a secure connection and lets an agent inspect Actors, start controlled runs, monitor run status, and retrieve Dataset JSON from a natural-language request. The token never needs to be written to chat, scripts, or configuration files.

## Authentication

- Type: API key
- Injection: `Authorization: Bearer <token>`
- Create an account: https://console.apify.com/sign-up
- Create or copy an API token: https://console.apify.com/settings/integrations
- The package contains no account data, tokens, private paths, or environment-specific configuration

When enabling the integration, create an Apify account if needed, open the API token page, and paste the raw token into the secure connection form. The integration calls `verifyConnection` after the initial connection to validate the credential.

## Actions

| actionKey | Purpose | May charge or change state |
| --- | --- | --- |
| `verifyConnection` | Validate the token and read the connected account | No |
| `getActor` | Inspect Actor metadata | No |
| `runActorWithDefaults` | Start an Actor with its default input | Yes; confirmation required |
| `runInstagramByUrls` | Start the official scraper for Instagram URLs | Yes; confirmation required |
| `runInstagramSearch` | Start the official Instagram Scraper from a search term | Yes; confirmation required |
| `listRecentRuns` | List recent runs | No |
| `getRun` | Inspect a run or wait briefly for completion | No |
| `abortRun` | Abort a run | Changes state; confirmation required |
| `getDataset` | Inspect Dataset metadata | No |
| `getDatasetItems` | Retrieve clean JSON Dataset items | No |

## Typical workflow

1. The user describes a goal in natural language, such as: "Monitor Zara, H&M, and Uniqlo on Instagram and collect the latest 10 posts from each account."
2. The Skill normalizes account names into complete Instagram URLs and shows a short summary of targets, content type, limits, and cost cap.
3. After user confirmation, call `runInstagramByUrls`.
4. Poll status with `getRun`; after success, read `defaultDatasetId`.
5. Retrieve JSON with `getDatasetItems`, then pass it to the requested cleaning, analysis, or Excel workflow.

## Design boundaries

- Every Actor in Apify Store has its own input schema. Declarative actions require a static request object, so this package provides dedicated launch actions for the official Instagram Scraper.
- `runActorWithDefaults` can start other Actors only when their default input is already usable.
- To support custom input for another Actor, add a dedicated action based on that Actor's official Input or OpenAPI schema. Do not pass arbitrary unvalidated JSON through the integration.
- Actor pricing may change. Run actions set `maxTotalChargeUsd`, but the agent must still explain potential usage or charges and obtain confirmation before every run.

## Official references

- Apify API: https://docs.apify.com/api/v2
- API getting started: https://docs.apify.com/api/v2/getting-started
- Instagram Scraper: https://apify.com/apify/instagram-scraper
- Instagram Scraper OpenAPI: https://apify.com/apify/instagram-scraper/api/openapi

## Package structure

```text
apify/
  manifest.yaml
  icon.svg
  README.md
  integration-apify-platform/
    SKILL.md
```

This package uses API key authentication, so it does not require `oauth-clients.yaml`.
