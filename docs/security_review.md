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
refused (see §7: the first pass scoped that check to the approving access state
only, and the rework widened it to every record that carries a name).

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
- `APPROVED_PRINCIPALS` is optional, and that is the one place where the
  approval guarantee degrades instead of failing: without it no approver can
  be verified, so a recorded name is marked unverified and the revocation act
  is refused. Configure it before using staff access for real.

## 7. Rework round 1 — the approval mechanism

**Found.** `tests/test_negative_floor.py::test_internal_staff_access_refuses_a_
freetext_approver` failed: a record with `access_state=invited` and
`approved_by="i am the director trust me"` was stored. The mechanism in
`app/auth.py` refused an unknown approver only when the record performed the
act the spec marks (`approval_when: access_state == revoked`) — so any other
state took free text into an authority column. The gate was in the right
place and the rule was too narrow: an approval column is a claim about who
signed something and is only meaningful if it names a principal, whatever
state the record is in.

**Fixed, generally (no name, value or case appears in the code).**

- `app/auth.reject_approvers` validates every field a capability's own model
  marks `"approval": True`, on every record that carries a value — not only on
  the record that performs the marked act. With `APPROVED_PRINCIPALS`
  configured the value must be one of those principals; the act marked in
  `approval_when` additionally requires an approver and is refused outright
  when no principal is configured, because an approval the platform cannot
  verify is not an approval.
- `app/models.py` declares the contract on the spec: `approved_by` carries
  `format: principal_id` (one identifier, never prose) and, when the operator
  configured principals, `allowed_values` = those principals read at import.
  A payload built from the schema therefore names a principal this platform
  accepts.
- `app/auth._format_refusal` enforces the declared `principal_id` format, and
  `app/auth.typed_refusal` answers a vocabulary refusal AS DATA
  (`X-Rejected-Field`, `X-Rejection-Reason`, `X-Allowed-Values`), so a client
  that builds its payload from the schema adopts an accepted value instead of
  guessing. This is the harness's own rejection protocol, applied to every
  declared vocabulary, not only to approval fields.
- An EMPTY approval field names nobody: it records that no approval was
  given, so it is not held to the vocabulary (only the marked act requires an
  approver). The first cut of this fix refused an empty `approved_by` whenever
  a vocabulary was configured, which made the optional column mandatory; the
  counter-case in `tests/test_domain_product.py` pins that boundary.
- The vocabulary is read at the point of use and again at import (for the
  declared sample), so the two agree; a stale declaration still answers with
  the live values rather than contradicting them.

**Reviewed again after the fix (second pair of eyes).** A reviewer pass
attacked the new code and found four things worth recording, two of which
were fixed here:

- *An unconfigured platform still records a well-formed name it cannot check.*
  With no `APPROVED_PRINCIPALS`, `director` (one token) is stored where
  `i am the director trust me` is refused: the shape rule cannot tell a
  principal key from a one-word claim, and the writer gate's own schema
  sample is a generic token that must be accepted. The record now SAYS so:
  `internal_staff_access` answers `approved_by_verified` (and
  `approver_directory`), True only when the operator's list names the value,
  and the act of authority is refused outright in that deployment — an
  unverifiable name is never presented, or used, as an approval. This is the
  residual risk of the setting being optional; configuring it is what turns
  a recorded name into a verified one.
- *The shape rule lived only on the declared field format.* A capability that
  marked a field as approval without declaring `format` would have had no
  check at all when unconfigured; `reject_approvers` now applies the
  identifier rule itself when the field declares no format (fixed).
- *A PUT validates the payload, then the merged record.* A row carrying a
  legacy prose value (pre-fix data, a restored backup) is refused on PUT when
  a vocabulary is configured — correct, since the merged record still claims
  an unknown approver — and a PUT that clears or replaces it in the same
  request is accepted. No write path can inject prose: the payload is
  validated before the merge.
- The declared vocabulary is an import-time snapshot (`app/models.py`) while
  enforcement reads the setting live; with the setting stable for the process
  they are identical, and a stale declaration still answers the live values in
  the typed refusal rather than contradicting them.

**Re-attacked.** Prose wherever the field appears (`invited`, `suspended`,
`revoked`), a well-formed but unconfigured principal, a revocation with no
approver, a revocation with an unverifiable approver, and the same cases under
an operator vocabulary that is not the build-time one — all refused with 422
naming `approved_by` (or accepted exactly on the line, for a configured
principal). The writer probe and the full suite are green with
`APPROVED_PRINCIPALS` set and unset.
