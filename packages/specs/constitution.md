# Engineering constitution
1. Specifications and acceptance criteria are version-controlled.
2. No agent may claim a test passed without executable evidence.
3. All write operations require explicit approval and least privilege.
4. Never run arbitrary model-generated commands on the host.
5. An agent must have iteration and cost budgets before production. The current build enforces iteration/completion-token limits; financial quotas remain a gap.
6. Failed gates block release; never silently auto-approve.
7. All actions include trace identifiers, tenant boundaries, and audit logs before multi-tenant deployment.
