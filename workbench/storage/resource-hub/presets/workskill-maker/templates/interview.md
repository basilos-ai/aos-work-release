# Resource Requirement Interview

Collect only information needed to classify and build the resource. Do not ask questions already answered by the user's request or inspectable files. Ask in ordinary chat, without a form or a fixed questionnaire. Human visual acceptance is not a default requirement.

## 1. Resource boundary

Determine:

```text
Requested term:
Resource type: skill | work | connector
Primary user:
Trigger:
Business outcome:
Administrator upload package or filtered Runtime resource: administrator upload package by default
```

If the user says `worker`, infer from the request whether they mean a Workbench `work`, an Agent, or a background process; ask in chat only if the distinction remains materially ambiguous. A single reusable capability is usually a Skill; a coordinated multi-capability workflow may be a Work; an external authenticated service integration is usually a Connector.

## 2. Workflow and members

Collect:

```text
Inputs and sources:
Main steps:
Decision points:
Human review or confirmation:
Outputs and consumers:
Failure handling:
Acceptance criteria:
Explicitly approved persistent preferences, or none:
Proposed members, if multi-member:
```

Ask follow-up questions only when a missing answer changes the architecture or makes validation impossible.

## 3. External integration

For a Connector, collect:

```text
Provider and official API:
Required capabilities:
Read-only actions:
Billable or side-effecting actions:
Pagination or asynchronous behavior:
Rate limits and important errors:
Target runtime or gateway:
Administrator upload requirements: manifest | icon | control-plane OAuth config | other
Connector key and authProviderKey:
```

Verify current provider facts from official sources before generation.

## 4. Authentication

Classify exactly one mode:

```text
Authentication mode: api_key | oauth2
Official evidence:
Credential placement or OAuth endpoints:
Tenant/account model:
Minimum scopes, if OAuth2:
Safe read-only verification endpoint:
```

For API-Key/Token, do not ask for the actual value during design. Write the packaged guidance and form text in English. Verify the official website, key-management entry and short acquisition steps; identify tenant-specific or multi-provider entry gaps. Plan a concise chat guide before the secure form, with no additional readiness confirmation. Confirm target Runtime support for secret password forms, Workbench storage and environment injection; define stable credential identity and environment names, separate ordinary preferences, identify a safe verification endpoint and any legacy migration needs. Platform storage precedes script verification.

For OAuth2, confirm all of the following before generation:

```text
OAuth flow evidence: authorization_code | not OAuth2
Application owner and environment:
Private/internal or public multi-tenant:
Provider authorization-server metadata or verified endpoints:
Approved redirect URI for each environment:
Minimum scopes and consent requirements:
PKCE and client-authentication requirements:
Workbench authorization-start and callback evidence:
Token exchange, refresh, expiry and revocation ownership:
Connection identity and account/tenant binding:
Execution channel: gateway_action | runtime_environment | unavailable
Safe read-only verification endpoint:
Client configuration and secret-management owner:
Administrator upload `oauth-clients.yaml` entry:
Control-plane key and `connector.authProviderKey` mapping:
Provider review/publication/test-user prerequisites:
Legacy OAuth files or scripts to remove:
```

Do not ask the user to paste a client secret, authorization code, access token, or refresh token into ordinary chat or a password form. If the target Runtime cannot prove authorization start, callback handling, code exchange/refresh, secure storage, and the selected injection channel, record the exact blocker. Do not invent an OAuth Tool name or replace the managed flow with a local callback/token implementation. The administrator upload source package may contain an `oauth-clients.yaml` control-plane template, but installed user resources and Runtime views must filter it.

## 5. Runtime dependency assessment

Read `references/runtime-environment.md` and compare the actual workflow with `references/runtime-inventory.json`. Derive requirements from supplied materials first; ask only for missing facts that change implementation or acceptance.

```text
Target runtime evidence or Dockerfile baseline only:
Per-function/member dependencies and constraints:
Required fonts, language data, browser/model files or native libraries:
Declared / verified / bundled dependencies:
Undeclared / missing / incompatible / deployment-dependent requirements:
Affected functions and mandatory/optional status:
Proposed remedy and unresolved blockers:
```

Disclose material gaps before implementation, not only in the final result. Continue independent work without treating unknown deployment facts as permission to install packages.

## 6. Requirement summary

Summarize:

```text
Resource type and key:
Objective and trigger:
Workflow and members:
Inputs and outputs:
External service and actions:
Authentication branch:
Approval boundaries:
Required references or setup guide:
Persistent preferences to record, or none:
Validation criteria:
Open blockers:
```

Pause only for a blocking ambiguity. Otherwise continue to architecture and generation.
