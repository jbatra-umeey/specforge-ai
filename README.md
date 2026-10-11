# SpecForge AI

Specification-driven engineering with a Next.js dashboard, FastAPI, bounded ReAct/LangGraph planning, approval-controlled integrations, and persistent run history.

**Status: implemented and locally tested reference platform, not a verified production deployment.** v0.2 adds real provider adapters; credentials are required. There is no fallback that presents fixtures as live model or external-system results.

## What works

- **Live planning:** OpenAI-compatible Chat Completions requests inside a bounded LangGraph read/observe/plan loop. Validated JSON plans, token usage, explicit model selection, timeouts and step budgets.
- **GitHub:** read allowlisted issues, create issues, and create draft pull requests from existing branches.
- **Jira Cloud:** read issues and create issues using REST v3 and Atlassian Document Format.
- **Human approval:** writes are stored as proposals. An authenticated approver reviews the exact payload; its digest must match. Atomic claiming prevents duplicate execution. Ambiguous outcomes require manual reconciliation.
- **Persistence:** PostgreSQL in Compose; SQLite for local development/tests. Tenant-scoped runs, proposed actions, audit events, request idempotency, and a versioned baseline schema migration.
- **Authentication:** browser OIDC authorization code + PKCE; backend RS256/JWKS signature, issuer, audience, expiration, subject and tenant validation; viewer/operator/approver roles. Production rejects shared-key authentication and SQLite.
- **SDD foundations:** versioned requirements, acceptance criteria, evidence evaluator, bounded local tool executor, and legacy workflow gates.
- **Five fixture demos:** feature delivery, regression, drift, incident and release. These remain deterministic examples, separate from live planning.

## Local start

```bash
cp .env.example .env
# Replace the development key and PostgreSQL password. Use an alphanumeric DB password,
# or supply a correctly URL-encoded DATABASE_URL when configuring the API directly.
docker compose up --build
```

Open `http://localhost:3000`. Enter your development API key in the sign-in field. The frontend does **not** attach a shared server credential to anonymous requests. Run a fixture, or configure a live model and create a plan. Live planning fails explicitly when model credentials are absent.

Without Docker:

```bash
cd apps/api
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
export SPECFORGE_API_KEY='your-long-random-local-key'
python -m app.migrate
uvicorn app.main:app --host 127.0.0.1 --port 8000
# In another shell:
cd apps/web
npm ci
npm run build
npm start
```

Set environment variables in each shell or use your process manager; `.env` is automatically read by Compose, not by a standalone Python process.

## Configure live providers and identity

See [configuration and operations](docs/operations.md) for credentials, OIDC claims, tenant binding, approval roles, migration and recovery. Never commit `.env` or provider secrets.

## Validate

```bash
cd apps/api && python -m pytest -q
cd ../web && npm ci && npm run lint && npm run build
# From repository root, after creating .env:
docker compose config --quiet
docker compose up -d --build --wait
```

GitHub Actions includes backend tests, frontend checks, and a PostgreSQL/container smoke job. See the actual Actions result for the current commit. [Validation evidence](docs/validation.md) separates local checks from unverified live environments.

## Limits before production

This platform plans and manages reviewed issue/PR proposals. It does **not** autonomously implement code, create branches, run untrusted code, or deploy software. Runs are synchronous; persisted events are not durable resumable LangGraph checkpoints. Integration credentials serve one explicitly configured tenant per deployment. More production work and live environment verification remain; see [readiness gaps](docs/production-readiness.md).
