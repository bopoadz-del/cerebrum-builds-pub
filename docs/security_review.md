# Security review — Harbourline Civil Works contracts platform

Written by the SECURITY pass on the tree the INFRA, BACKEND, FRONTEND and
DEVOPS passes left. It lists every attack that was tried, what held, and what
was broken and fixed.

## Fixed during the pass

| # | Finding | Fix |
|---|---------|-----|
| 1 | An id outside SQLite's 64-bit range raised `OverflowError` from `GET /v1/{cap}/{id}` (a 500) | `app/store.valid_id()` bounds ids; the read and delete routes answer 404. Guarded again inside `store.get/update/delete`. |
| 2 | `days_of_delay: Infinity` / `1e400` reached `int()` and raised (a 500) | `security._coerce` refuses non-finite floats, `abs(int) > 2**63-1` and `abs(float) > 1e15`; `days_of_delay` also declares `max: 36500` and the handler clamps. |
| 3 | `date` fields were not validated at all (a nested object was stored as JSON in a date column) | `_coerce` parses ISO dates and refuses anything else with 422. |
| 4 | A record could be POSTed `status: "closed"` with no approval; a free-text `approved_by` was stored | `security._check_closure()`: closing a record whose spec marks an approval field requires a principal from `APPROVED_PRINCIPALS` (403 otherwise). `qa_itp_records.signed_off_by` is now declared approval. |
| 5 | Two tenants using the same reference shared `work/certificate-<reference>.pdf` — a cross-tenant scratch-file race | `_common.scratch_path()` gives every render a unique path (uuid suffix) and the handler unlinks it after the block reads it. |
| 6 | A unicode `reference` raised `UnicodeEncodeError` while rendering the certificate PDF (400) | `render_pdf` encodes the content stream as latin-1 with replacement and writes bytes; no caller text can break the render. |
| 7 | `security.redact()` was a no-op (wrong escaping in a non-raw pattern) | Pattern fixed; it is used when a body must echo caller text. |
| 8 | `/v1/meta` answered without a principal | Moved to `/meta`, outside the `/v1` surface. |

## Attacks that held

| Attack | Result |
|--------|--------|
| `../../escape` in `reference` / `document_number` | Held: `safe_name()` strips separators; files stay under `$STORAGE_PATH/work`. |
| Free-text approver (`i am the director trust me`) on a certification, a retention release or a closing record | Held at the edge and in the handler: `security._check_approvers()` refuses any value that is not a principal identifier (403, `approved_by must name an approved principal, not free text`), and `require_approver()` refuses an unknown identifier whenever the record asserts authority (decision off its default, or `status=closed`). |
| Cross-tenant read, delete, and list with a second tenant's token | Held: 404 / empty; the tenant comes from the principal, never the payload (an unknown `tenant_id` field is refused as an unknown field). |
| Nested object for a scalar, 9 KB string, unknown field, malformed JSON | Held: 422 with `rejected_field` and `X-Rejected-Field`; never a 500. |
| SQL injection through `reference` (`' OR 1=1--`) | Held: SQLAlchemy Core with bound parameters; the value is stored literally. |
| Unauthenticated reads of `/v1/capabilities`, `/v1/jobs`, `/v1/provenance`, `/v1/gates`, `/v1/retrieval`, every capability route | Held: 401. |
| Egress on a caller-controlled URL | Held: no egress path exists. `security.assert_public_url()` is the private-address guard if one is ever wired; the notification block is called with `channel="mcp"` only. |
| Token search of `app/**`, `Dockerfile`, `.env.example`, `app/static/index.html` | Held: no token literal, no environment fallback; the console keeps the operator's token in `sessionStorage`. |

## Accepted risks, stated rather than hidden

- `conftest.py` carries the well-known *test* tokens (`dev-local-token*`). It is
  the one place the Factory allows them; runtime code (`app/**`) has none and
  `PLATFORM_TOKEN` has no default. The Dockerfile copies the tree, so the test
  bootstrap travels into the image; it is never imported by the service.
- `GET /health` reports the `STORAGE_PATH` value (Factory-owned
  `app/health.py`). It is a path, not a secret, and it is the operator's own
  deployment.
- Block-side state (audit/evidence ledgers) is in-process per call in this
  Store build; the tenant passed to a block is now the caller's principal, so
  no tenant label is invented.

## Rework re-check: approval authority on the edge (2026-11-05)

The floor case `test_*_refuses_a_freetext_approver` posts a record whose
approval field carries `i am the director trust me` while the decision stays
on its default (`none`). A handler-only check therefore let it through: no
decision was asserted, so `require_approver()` was never reached. The edge now
grades the field itself, before any handler runs:

| Payload (`progress_claims`) | Answer |
|-----------------------------|--------|
| `approved_by=qa.lead`, `approval_decision=certify` (configured principal) | 200, recorded |
| `approved_by="Ahmed Al-Rashid"`, `certify` (configured, unusual punctuation) | 200, recorded |
| `approved_by=director`, `certify` (unknown identifier, authority asserted) | 403 |
| `approved_by=director`, `none` (named person, no authority asserted) | 200, recorded |
| `approved_by="i am the director trust me"`, `none` (free text) | 403 |
| `status=closed`, `approved_by=director` | 403 |
| `status=closed`, `approved_by=qa.lead` | 200, recorded |

The same rule is carried by `signed_off_by` on an ITP record and by
`approved_by` on a retention release, because both fields declare
`"approval": true` in `app/models.py` — the check reads the declaration, not
the field name, so a new approval field inherits it without a code change.
