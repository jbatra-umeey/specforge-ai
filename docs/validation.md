# Validation evidence — 2026-10-11

Source: v0.2 expansion of the supplied SpecForge monorepo. Python 3.12.14; Node 24.19.0; Next.js 15.5.27. CI/containers target Node 22 and Python 3.12.

| Check | Observed result |
|---|---|
| Backend `python -m pytest -q` | 32 passed, no skips |
| Frontend `npm run lint` | Passed (TypeScript type check) |
| Frontend `npm run build` | Passed; optimized Next.js build generated |
| Local HTTP integration | Passed: built Next server to FastAPI; all five fixtures; anonymous proxy requests rejected; missing-provider failure persisted and retrievable |
| Database restart persistence | Passed with a fresh SQLAlchemy Store connection to SQLite |
| OIDC security | Signed test JWTs; expired/wrong issuer/wrong audience/forged/HMAC tokens rejected; roles and tenant filtering tested |
| Provider flow | HTTP mock-transport contracts: model -> issue read -> structured plan -> reviewed approval -> external write result |
| Duplicate execution | Concurrent action claims allow one execution; repeated idempotency key returns original run |
| Docker locally | Not run: `docker` executable/engine unavailable; Compose YAML/build-context static checks pass |
| PostgreSQL locally | Not executed; Compose/CI job configured to exercise PostgreSQL |
| Live provider/IdP accounts | Not verified: no live credentials supplied or used |
| Browser-level user journey | Not executed; HTTP integration is not full browser E2E |
| Cloud deployment | Not performed |

The original `pytest -q` command failed to import `app` in this environment. README and CI now use the passing `python -m pytest -q` invocation. Python and npm lockfiles capture dependencies used for checks.

GitHub Actions has backend, frontend and Docker/PostgreSQL smoke jobs. Refer to the Actions result for the final published commit; this document records local validation rather than predicting CI results. Local successful build output does not prove a successful container image build or a production deployment.

See production-readiness.md for remaining limitations and operations.md for configuration and recovery.
