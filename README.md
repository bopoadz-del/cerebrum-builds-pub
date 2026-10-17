# Hotel Booking Platform

Cerebrum-builds session for **Hotel Booking Platform** — guests search, compare, and reserve rooms while hospitality operators manage inventory, pricing, reviews, and notifications.

Manufactured from vendored Store blocks (session `<SESSION_ID>`):

- `booking_management` — workflow, database, notification, queue
- `property_management` — database, storage, document_engine
- `dynamic_pricing` — formula_executor, analytics
- `review_management` — database, analytics, notification
- `analytics_dashboard` — dashboard, analytics, database
- `notification_system` — notification, queue, workflow
- `search_recommendation` — vector_search, recommendation_template, analytics

Offline platform. Channel `mcp` only. No HTTP store callbacks.

## Roles

- operator
- admin

Mutating routes require `OPERATOR_TOKEN` / `ADMIN_TOKEN`. CORS uses `CORS_ALLOWLIST` only (`*` is refused). Client `actor` / `user_id` is `claimed_actor` only.

## Run

```
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Render-ready (`Dockerfile` + `render.yaml`) is packaging, not a live deploy. Store gate = GHA docker + `scripts/acceptance.py`.
