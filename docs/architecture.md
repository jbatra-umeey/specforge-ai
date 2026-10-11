# Architecture

The Next.js client supports two explicit modes: an in-memory development key or an OIDC public-client authorization code/PKCE sign-in. Same-origin route handlers forward the caller's credential to FastAPI; they never supply a server key to an anonymous caller.

FastAPI verifies the principal and roles. A run request is inserted with a tenant/subject/idempotency-key uniqueness constraint. The live LangGraph alternates a model decision node and an allowlisted external issue-read node, with a bounded step budget. Final plans are validated against a typed schema. Proposed external actions are stored, not executed by the model.

An approver reviews an immutable action payload and submits its SHA-256 digest. An atomic database update transitions pending to executing and records the actor before an adapter sends the request. The result is persisted as succeeded, failed or unknown. Claims are never blindly replayed. This is at-most-once application dispatch, not an exactly-once guarantee across external systems.

SQLAlchemy supports SQLite for local development and PostgreSQL in Compose. Every run/action/event read and write is scoped to the verified tenant. This is application-level isolation, not PostgreSQL row-level security. Integration credentials are bound to one configured tenant and target allowlists.

The original specification/evidence evaluator, bounded local file tool, boolean workflow example and five deterministic fixture scenarios remain available. The live planner does not claim that a proposed implementation was built or tested. Audit events retain operational decisions and usage, not hidden model reasoning.

Production controls and unverified assumptions are tracked in production-readiness.md.
