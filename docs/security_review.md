# Security review — coffee-compost factory platform

Written by the WRITER role's SECURITY pass (`codewhale exec`). It records what
was attacked, and what held, against the tree that ships. Every claim below is
observable in this checkout and reproducible with the commands it names.

## 1. Authentication and authorisation

**Tried.** Every `/v1/...` route was called with no `Authorization` header, an
empty bearer, a wrong bearer, a non-ASCII bearer, and a bearer bound to another
tenant.

**Held.**
- Every `/v1` route answers `401` without a valid token — the check is a
  FastAPI dependency (`_require_identity`) solved *before* body validation, so
  an anonymous caller cannot tell a well-formed payload from a malformed one.
- The tenant is resolved only from the presented bearer (`app/tenancy.py`,
  constant-time comparison over the token map). `tenant_id`, `org_id`,
  `entity`, `block_id` and `action` in a payload are refused as reserved keys.
- Authorisation is not just authentication: a record belonging to another
  tenant reads as `404` on GET, PUT and DELETE (never `403`, never the
  record), and a PUT re-checks the resulting record's approval fields.
- Ten tokens per client per window after repeated failures answer `429`
  (`app/observability.py`), so token guessing is throttled. The limiter is
  in-process and resets on restart — see residual risks.

## 2. Secrets

**Tried.** Scanned `app/**` for a bearer-token literal and for an
environment fallback (`os.getenv(...) or "literal"`); started the process with
no `PLATFORM_TOKEN`; forced a handler to raise and read the error body.

**Held.**
- No token literal and no fallback in runtime code (`no_token_literal` PASS).
  `PLATFORM_TOKEN` is read at boot and its absence fails by name.
- `.env.example` ships examples only, and the tenancy module refuses the
  placeholder value `set-at-deploy` as a credential.
- `app/security.sanitise_error` masks `bearer|token|api-key|password|secret`
  values and URL credentials before any text reaches an error body or log;
  the 500 handler answers with the exception class only.
- The image carries no `.env`, no key, and no dev dependency.

## 3. Edge validation

**Tried.** Posted each capability with: a missing required field, an
out-of-vocabulary enum, a wrong JSON type, `NaN`/`Infinity`, a nested object
where a string is declared, a reserved key, and a free-text approver.

**Held.** All refused with 4xx naming the field; the checks are driven by the
model declaration (`app/edge.py`, `app/auth.py`), not by per-field branches, so
a newly declared field is validated the moment it is declared. Approval fields
are checked against `APPROVED_PRINCIPALS`; `"i am the director trust me"` is
refused.

## 4. Egress

**Tried.** Imported the app with every store/LLM variable stripped and outbound
sockets blocked; searched `app/**` for HTTP clients; supplied `http://127.0.0.1`,
`http://10.0.0.5`, `http://[::1]`, `http://localhost`, `file://` and
credential-bearing URLs as delivery destinations.

**Held.** There is no outbound call in the runtime path: blocks are dispatched
in-process from `vendor/`, the LLM surface is extractive and local, and Stripe
is only touched when a `stripe_key` is configured (it is not). Caller-supplied
delivery URLs pass `app.block_inputs.public_delivery_url`, which refuses any
non-http(s) scheme, URL credentials, loopback/private/link-local/reserved
addresses and `localhost`-style names, degrading to the in-platform channel.

## 5. Persistence

**Tried.** Cross-tenant read/write, SQL-ish strings in filters, 40 concurrent
creates per capability, a bare `store.connect()` on an empty directory.

**Held.** Statements are SQLAlchemy Core over declared tables with bound
parameters; table and column names come from the model declaration, not the
caller. `connect()` creates no table (schema is Alembic's). Writes hold under
concurrency (WAL, busy timeout matched to the sync threadpool), and the
cross-tenant cases answer 404.

## 6. Container and deployment

**Tried.** Read the Dockerfile against what the app loads at runtime; checked
the health probe path; checked the user the service runs as.

**Held.** The image installs runtime requirements against `constraints.txt`
only, `COPY . .` carries `vendor/`, `kits/`, `alembic/`, `docs/` and `deploy/`,
the entrypoint migrates before serving, the healthcheck fails closed, and the
process runs as the unprivileged `platform` user with `STORAGE_PATH=/data`
owned by it before the switch.

## Residual risks (stated, not hidden)

- The failed-auth limiter and the retrieval/in-memory stores are per-process;
  a restart clears them. A multi-replica deployment needs a shared limiter.
- TLS is terminated by the platform in front of this service; the app speaks
  plain HTTP on the private network.
- `SENTRY_DSN` is the one optional outbound path and is unset by default.
- RAG is not owed by this brief (no capability binds a retrieval block), so the
  retrieval index ships empty and tenant-scoped.
