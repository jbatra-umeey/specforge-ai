# Configuration and operations

## Live model

Set `LLM_API_KEY`, `LLM_MODEL` (a model enabled for your provider/account), and optionally `LLM_BASE_URL` (default `https://api.openai.com/v1`). The provider must support `/chat/completions`, JSON object response format and `max_completion_tokens`. Calls use 30-second HTTP timeouts, up to six model turns, and 2,400 completion tokens per turn. Usage is recorded; dollar budgets and quotas are not yet enforced. Goals and selected issue content are sent to the configured model provider.

## GitHub and Jira

- Set `INTEGRATION_TENANT_ID` to the authenticated tenant claim (`local` in development).
- GitHub: `GITHUB_TOKEN` with minimum issue/PR permissions and `GITHUB_ALLOWED_REPOS=owner/repo,owner/another`. Read issue tools and write proposals can access only exact allowlisted repositories. Draft PRs require existing head/base branches; this service does not push source code.
- Jira: `JIRA_BASE_URL=https://your-site.atlassian.net`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_ALLOWED_PROJECTS=PROJ,OTHER`; optionally `JIRA_ISSUE_TYPE=Task`. Custom required project fields are not handled yet.
- Credentials stay server-side and are never placed in prompts. Integration issue data is untrusted; write proposals need an approver regardless of model output. Configure isolated, least-privilege service credentials and an outbound network policy.

## OIDC setup

Register a public SPA client with authorization code + PKCE, no browser client secret, exact redirect URI `PUBLIC_APP_URL/`, and the same post-logout URI. Configure identity-provider CORS for your frontend origin. Issue **RS256 JWT access tokens for the API**, not opaque tokens or ID tokens. Set:

| Variable | Meaning |
|---|---|
| `AUTH_MODE=oidc` | Disable development shared keys |
| `SPECFORGE_ENV=production` | Require OIDC, PostgreSQL and HTTPS CORS |
| `OIDC_ISSUER` | Exact token issuer, HTTPS; preserve any issuer trailing slash |
| `OIDC_JWKS_URL` | Trusted issuer's HTTPS JWKS endpoint |
| `OIDC_AUDIENCE` | Dedicated API audience, distinct from SPA client ID |
| `OIDC_CLIENT_ID` | Public SPA client ID |
| `OIDC_SCOPE` | `openid profile` plus provider-specific API scopes |
| `PUBLIC_APP_URL` | External HTTPS frontend origin, without trailing slash |
| `CORS_ORIGINS` | Comma-separated explicit HTTPS browser origins |

Access tokens must include `sub`, `iss`, `aud`, `iat`, `exp`, `tenant_id` and a string-array `roles`. Claim names for tenant/roles are configurable. Assign `viewer` for read access, `operator` for planning, and `approver` for external writes; users who operate the dashboard also need viewer. No role is inferred from email. Backend verification fixes the algorithm to RS256, caches JWKS for 300 seconds and allows 15 seconds of clock skew. Use short-lived access tokens and accurate server clocks. Browser tokens are stored in session storage; automatic silent renewal is disabled, so sign in again on expiration.

OIDC code paths and cryptographic validation are tested, but a real identity-provider login/logout, key rotation, tenant provisioning and access-token audience configuration still need environment-specific verification. No provider is preconfigured.

## Persistence and migrations

Compose runs PostgreSQL on its private network with named volume `postgres_data`; it does not publish a database port. A one-shot migration service creates schema v1 before API startup. For direct deployment set `DATABASE_URL=postgresql+psycopg://...` and run `python -m app.migrate` as a migration job. Production startup checks schema v1 without creating tables. Development defaults to a local SQLite file.

The baseline migration is repeatable, but later schema upgrades and rollbacks require new explicit versioned migrations; do not change existing table definitions and expect create_all to migrate columns. Use separate migration/runtime database roles, managed TLS, encrypted storage, backups and tested restores for production.

## APIs and recovery

`POST /api/runs` accepts `{ "goal": "..." }`, requires operator, and requires an `Idempotency-Key` (8–128 characters). Reusing it with the same tenant, subject and goal returns the original run; changing the goal returns 409. `GET /api/runs` returns the newest 50 runs in the caller's tenant. `GET /api/runs/{id}` includes plans, action payloads and audit events.

`POST /api/runs/{id}/actions/{action_id}/execute` requires approver and `{ "digest": "<reviewed action digest>" }`. It atomically records approval and claims the action before making the external request. A repeated request is rejected. The actor may currently approve their own proposal; configure roles accordingly until a separate four-eyes policy is implemented.

No automatic retry occurs on writes. If the worker dies after claiming, or a provider response is ambiguous, inspect the provider and reconcile the `executing`/`unknown` operation manually. Do not reset it blindly: the provider might already have committed the action. Crashed `running` plans similarly need operator reconciliation; there is no durable job runner or resume endpoint yet.

## Sources for integration contracts

- OpenAI: https://developers.openai.com/api/reference/resources/chat
- GitHub: https://docs.github.com/en/rest/pulls/pulls
- Jira: https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/
- OIDC browser client: https://authts.github.io/oidc-client-ts/classes/UserManager.html
- JWT verification: https://pyjwt.readthedocs.io/en/stable/usage.html
