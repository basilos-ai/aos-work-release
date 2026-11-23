# Basil-admin-console maintenance

The member key remains `basil-admin_console-operation`; the Connector key is `basil-admin-console`, display name `Basil-admin-console`.

## File map

- `SKILL.md`: capability routing, bootstrap and operation boundaries.
- `user_preferences.md`: approved persistent preferences only.
- `references/auth.md`: dual selection, native card, personal-token form and recovery.
- `references/protocol.md`: transport/input/output/pagination conventions.
- `references/business-context.md`, `permissions.md`, `models.md`: business semantics, permission IDs and nested schemas.
- `references/users.md`, `departments.md`, `identity.md`, `system-roles.md`, `acl.md`, `resources.md`, `sharing.md`, `organizations.md`, `organization-roles.md`: domain contracts.
- `references/workflows.md`: bounded composition of existing operations.
- `scripts/runtime.py`: shared transport, credential selection, fixed form, status and verification.
- `scripts/config/service.json`: non-secret relative API prefix only; no user configuration or credential file.
- `scripts/auth/`: small stdin entry points for status, verify, personal-token form and recovery policy.
- `scripts/admin_console/contracts.json`: 61 documented routes, including one explicitly unsupported password-change route; 60 callable routes.
- `scripts/admin_console/contracts.py`: registry loader and strict endpoint allowlist.
- `scripts/admin_console/cli.py`: validation, serialization, mutation guards and bounded execution.
- `tests/`: offline request, authentication, recovery and standalone packaging tests.
- `../OAUTH_SETUP.md`: operator prerequisites and live-validation limitations.
- `../icon.svg`: supplied Connector icon; upload/display selection depends on the host's Connector metadata UI.

## Modification rules

Update the operation registry, affected capability reference and request-boundary tests together. Use provider contract evidence for method, parameter placement, null/empty semantics and permitted values. Preserve the distinction between system permissions and resource action IDs. Never add generic endpoint passthrough or side-effecting auth verification. Keep the entire member in English, including domain references, display labels, comments, and contract descriptions. Preserve API identifiers and exact business literals; describe non-English literals by Unicode code points when needed.

The package contains no App manifest or OAuth client file. Host registration, refresh, secure storage and injection are deployment dependencies. Never add local token storage or a refresh-token exchange to make an unconfigured host appear functional.

## Validation

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v` from this member. Tests use synthetic credentials and mocked HTTP only. Validate package structure with the maker's connector/dual validator and review the explicit special binding described in the root setup guide; do not silently treat default identity checks as runtime proof. Check all Markdown links and run the entire member in an isolated temporary directory without a parent App or another member.

The document's 61 inventory routes match the registry by exact method and endpoint. Deprecated folder routes and the misnamed deleteUserDepartment route are intentionally excluded. No deployment, live credentials, user accounts, role membership or real ACLs were changed during offline validation.
