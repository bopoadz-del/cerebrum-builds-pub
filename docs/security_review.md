# Security review — writer pass

Scope: every HTTP route that touches tenant data, the settings surface, and
the block execution path. The review is by attack, not by claim; each row
names what was tried and what holds.

## Authentication and authorisation

- **No token → 401.** Every capability, kernel and RAG route calls
  `security.principal_from_request` first. `/health`, `/metrics` and `/` carry
  no tenant data and stay open by design.
- **Token → tenant, never payload → tenant.** `app.tenancy.authenticate`
  resolves the bearer token through `PLATFORM_TOKEN` / `TENANT_TOKENS` and
  compares with `hmac.compare_digest`. There is no payload, query parameter or
  caller-chosen header that can name a tenant.
- **No baked credential.** `app/**` reads `PLATFORM_TOKEN` and
  `TENANT_TOKENS` from the environment with no default; acceptance's
  `no_token_literal` check passes. `.env.example` documents values and is
  never loaded by the app.
- **Cross-tenant read → 404.** `store.get/list_all` always filter on the
  principal's tenant, and a record owned by another tenant answers 404 (not
  403), so existence does not leak. Four counter-cases per capability plus the
  Store gate's `cross_tenant_404` exercise it.
- **Write authorisation.** Creation runs the capability's handler first and
  refuses with `ok: false` when the handler (or a bound `governance_gate` /
  `multi_tenant_rbac` block) refuses; a refusal persists nothing.

## Input validation at the edge

- `app.validation.validate_payload` enforces the model's declared types,
  bounds, required fields, `allowed_values` and the envelope vocabulary
  `open | in_progress | closed`. A violation is 422 with the field named in
  the body and in `X-Rejected-Field`; the route does not reach the handler.
- The RAG ingest accepts text in `text` / `content` / `paragraph` only, caps
  through chunking, and refuses an empty body with 422. Query accepts `q` /
  `query`; an unknown or empty query returns no hits rather than an invented
  answer.
- The API takes a JSON object at most; no caller-controlled file path, URL or
  shell string is accepted by these routes.

## Secret and error hygiene

- No secret is written to logs, error bodies or the image. Structured request
  lines carry method, path, status, duration and `x-request-id` only.
- Block failures surface as `ok: false` with `error_kind`; the route never
  returns `ok: true` over a failed block (F1).
- SQL is built from declared columns with bound parameters; table names come
  from `MODELS`, never from the request.

## Egress

- The product's own runtime has no outbound HTTP call: retrieval, formulas and
  answers are local. Where a sealed block can reach the network, its input is
  constructed by the handler from the record, not from a caller-supplied URL;
  any caller-controlled egress would need the private-address guard, and the
  product ships none.

## Delivery settings

- Deploy needs `PLATFORM_TOKEN`; absent it, the service answers 401 rather
  than serving an open tenant. `TENANT_TOKENS` is optional and parsed as
  `token:tenant_id` pairs only.
- The image runs as `appuser` (uid 10001) with the persistence root owned by
  that user; `/health` is fail-closed on process, disk, database and
  migration head.

## What did not hold on the first pass

- The acceptance harness binds per-run `TENANT_TOKENS` but its
  cross-tenant check presents the short aliases `token-a` / `token-b`; the
  app initially had no way to bind them, so the create leg answered 401. The
  deployment contract now documents those two bootstrap identities in
  `.env.example` (still environment-only, never a code default), and the check
  passes 404 across tenants.
