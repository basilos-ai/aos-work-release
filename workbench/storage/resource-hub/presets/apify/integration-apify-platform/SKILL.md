---
name: "integration-apify-platform"
description: "Use the Apify Platform integration to collect public web and social-media data from a natural-language brief, run supported Actors with explicit cost confirmation, monitor runs, and retrieve Dataset items as JSON. Trigger when users mention Apify, Actors, web scraping, Instagram monitoring, competitor monitoring, social listening, public social data, run IDs, or Dataset IDs."
---

# Apify Platform Integration Skill

Use the declarative Apify plugin through the gateway at `http://workbench:3000/plugins/invoke`.

Every invocation includes:

- `agentId`: current agent ID
- `pluginKey`: `com.apify.platform`
- `actionKey`: one of the actions below
- `connectionKey`: optional; default is `default`
- `params`: action input parameters

## Primary behavior

Translate the user's natural-language goal into the smallest supported Apify workflow. Do not ask whether the user already has a Dataset or JSON file when their intent is to start monitoring or collection. Existing run or Dataset IDs are useful shortcuts only when the user voluntarily provides them.

Prefer API actions over browser instructions. Browser interaction is limited to actions that cannot be completed through this integration, chiefly creating an Apify account and copying the API Token during first-time connection setup.

Never mention internal runtime or container product names to the user. Never ask the user to paste an API Token into ordinary chat. If the connection is missing, direct them to enable the Apify integration and paste the Token into its secure credential form; the manifest will store and inject it automatically.

## Available actions

1. `verifyConnection` - validate the configured Token and identify the connected Apify account.
2. `getActor` - inspect an Actor by ID or `username~actor-name`.
3. `runActorWithDefaults` - run any Actor whose default input is already usable.
4. `runInstagramByUrls` - run `apify~instagram-scraper` for explicit Instagram URLs.
5. `runInstagramSearch` - run `apify~instagram-scraper` from a search term.
6. `listRecentRuns` - list recent runs for the connected account.
7. `getRun` - get status and storage IDs for a run; may wait up to 60 seconds.
8. `abortRun` - stop a running Actor.
9. `getDataset` - inspect Dataset metadata and item counts.
10. `getDatasetItems` - retrieve clean Dataset items in JSON.

## First-time connection

When an action reports a missing connection or invalid credential:

1. Tell the user that Apify requires an account and API Token.
2. If the user does not have an account, provide the direct registration URL: `https://console.apify.com/sign-up`.
3. Provide the direct API Token URL: `https://console.apify.com/settings/integrations`.
4. Ask them to enable this integration and paste the Token into the secure connection form, not the chat.
5. After connection, call `verifyConnection` automatically.
6. Resume the original task without asking the user to restate it.

Do not create `.env`, config, JSON, YAML, or script files containing the Token.

## Safety and cost rules

Read-only actions (`verifyConnection`, `getActor`, `listRecentRuns`, `getRun`, `getDataset`, `getDatasetItems`) may run without extra confirmation when they directly support the user's request.

Before `runActorWithDefaults`, `runInstagramByUrls`, or `runInstagramSearch`:

1. Show a compact summary of the Actor, targets, result type, result limits, and `maxTotalChargeUsd`.
2. Explain that the run can consume Apify usage or create a charge under the user's plan.
3. Obtain explicit confirmation in the current conversation.

Before `abortRun`, state the run ID and obtain explicit confirmation.

Default `maxTotalChargeUsd` to `1` unless the user provides a lower cap. Never increase a user-provided cap without a new confirmation. Keep result limits small for trials.

Collect only public data requested by the user. Do not use this integration to bypass authentication, access private accounts, collect secrets, or evade platform restrictions. Respect applicable laws, platform terms, and data-minimization requirements.

## Instagram monitoring workflow

For a request such as "monitor these Instagram brand accounts":

1. Extract the usernames, content type, count per account, market/language context, and whether the run is one-time or recurring.
2. Convert usernames to canonical URLs: `https://www.instagram.com/<username>/`.
3. Use `runInstagramByUrls`; do not substitute public web search for the Apify API.
4. Poll with `getRun`. Use `waitForFinish` up to 60 seconds per call; do not assume success until `status` is `SUCCEEDED`.
5. Read `defaultDatasetId` from the successful run.
6. Call `getDatasetItems` with the requested data limit.
7. Return or pass the JSON to the requested downstream analysis/export capability.

The action's `resultsLimit` is per URL. For three URLs with a limit of 10, expect up to roughly 30 items, subject to source availability, pinned posts, duplicates, Actor behavior, and plan limits.

## Run status handling

- Transitional: `READY`, `RUNNING` - poll again.
- Success: `SUCCEEDED` - retrieve `defaultDatasetId` and then items.
- Failure: `FAILED`, `TIMED-OUT`, `ABORTED` - report `statusMessage` and relevant error details; do not silently fall back to another collection method.

Run cost and aggregate statistics can be eventually consistent. If exact finalized cost is requested, fetch the run again after completion rather than presenting preliminary values as final.

## Minimal examples

### Verify the connection

```json
{
  "agentId": "CURRENT_AGENT_ID",
  "pluginKey": "com.apify.platform",
  "actionKey": "verifyConnection",
  "connectionKey": "default",
  "params": {}
}
```

### Start a confirmed Instagram URL run

```json
{
  "agentId": "CURRENT_AGENT_ID",
  "pluginKey": "com.apify.platform",
  "actionKey": "runInstagramByUrls",
  "connectionKey": "default",
  "params": {
    "directUrls": [
      "https://www.instagram.com/zara/",
      "https://www.instagram.com/hm/",
      "https://www.instagram.com/uniqlo/"
    ],
    "resultsType": "posts",
    "resultsLimit": 10,
    "addParentData": true,
    "maxTotalChargeUsd": 1
  }
}
```

### Retrieve JSON after success

```json
{
  "agentId": "CURRENT_AGENT_ID",
  "pluginKey": "com.apify.platform",
  "actionKey": "getDatasetItems",
  "connectionKey": "default",
  "params": {
    "datasetId": "DATASET_ID_FROM_RUN",
    "offset": 0,
    "limit": 100,
    "desc": false
  }
}
```

## Error guidance

- `INVALID_OR_MISSING_TOKEN`: reconnect with a valid Apify API Token through the secure form.
- `PAYMENT_OR_USAGE_LIMIT`: explain that the account's plan, credit, or run cap prevented execution; do not retry with a higher cap automatically.
- `RESOURCE_NOT_FOUND`: verify the Actor, run, or Dataset ID and the connected account's access.
- `THIRD_PARTY_RATE_LIMITED`: wait and retry with backoff; do not create a rapid retry loop.
- `THIRD_PARTY_UNAVAILABLE`: preserve the user's brief and offer to retry later.

Do not claim that data collection succeeded until the Actor run succeeded and Dataset items were actually retrieved.
