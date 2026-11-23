# Basil-admin-console

A dual-auth Connector for Basil account, department, system-role and resource-permission administration. The single member is [basil-admin_console-operation](basil-admin_console-operation/SKILL.md). It contains 60 callable documented routes and explicitly rejects the password-change route that requires another credential class. The supplied image is preserved as `icon.svg`.

The package intentionally retains Library's native OAuth card, personal-token identity and injection names under the approved special binding. See [OAuth setup](OAUTH_SETUP.md) for target prerequisites and the unverified managed-refresh adapter. No App YAML or client secret is included. Runtime and maintenance instructions are English; capability references retain detailed bilingual interface facts.

See [member maintenance](basil-admin_console-operation/readme.md) for file ownership and offline tests. Registry key: `basil-admin-console`; display name: `Basil-admin-console`.

The generic maker's default identity checks expect a `connector.*` credential and OAuth identity. This package uses the approved `app.basilos.personal-token` / Library mapping instead. Report those exact deviations explicitly; do not add unused Connector identities just to satisfy static string checks. All other structural and dual-auth checks still apply.

## Offline validation result

On 2026-10-27, 56 tests passed both in the repository and with the entire member copied into an isolated temporary directory. Package structure, local references, entry JSON examples, exact source icon bytes, registry-key uniqueness and Python syntax passed. The 61 documented inventory routes match the registry (60 callable; password change explicitly unsupported).

The generic dual-auth validator reports exactly two approved binding deviations: `missing stable connector credential identity` and `missing non-secret connector.<connector-key>.oauth2 identity`. Both are expected because the package intentionally uses the Library binding and personal-token identifier; all remaining generic checks pass. The generic maker and its validator were not changed for this exception.

Live authorization, token injection, managed refresh, network access and business API behavior remain unverified. In particular, a callable host refresh contract must be supplied or a documented automatic lifecycle verified before unattended OAuth recovery can be claimed.
