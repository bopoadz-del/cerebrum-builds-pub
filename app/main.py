"""FastAPI application factory for the Delivery Service Platform."""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app import tenancy
from app.health import health_response
from app.observe import install_observability
from app.routes import build_router

_START = time.time()
_COUNTS = {"requests": 0, "seconds": 0.0}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    storage = (os.getenv("STORAGE_PATH") or "").strip()
    if storage:
        Path(storage).mkdir(parents=True, exist_ok=True)
    from app.migrations import upgrade_head

    upgrade_head()
    yield


app = FastAPI(title="Delivery Service Platform", version="0.1.0", lifespan=lifespan)
install_observability(app)
app.include_router(build_router())


@app.get("/health")
async def health():
    return health_response()


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    uptime = max(0.0, time.time() - _START)
    lines = [
        "# TYPE platform_requests_total counter",
        "platform_requests_total %d" % _COUNTS["requests"],
        "# TYPE platform_request_latency_seconds summary",
        "platform_request_latency_seconds_sum %.6f" % _COUNTS["seconds"],
        "platform_request_latency_seconds_avg %.6f" % (
            _COUNTS["seconds"] / _COUNTS["requests"] if _COUNTS["requests"] else 0.0
        ),
        "platform_uptime_seconds %.3f" % uptime,
    ]
    return "\n".join(lines) + "\n"


@app.middleware("http")
async def _bind_tenant(request: Request, call_next):
    """State the tenant every authenticated answer is bound to.

    The console (and any operator client) reads this header to confirm which
    tenant the bearer token resolved to; an unauthenticated request gets no
    tenant header and the route answers 401.
    """
    response = await call_next(request)
    tenant = tenancy.optional_tenant(request.headers)
    if tenant is not None:
        response.headers["X-Tenant-Id"] = tenant.tenant_id
        response.headers["X-Tenant"] = tenant.tenant_id
    return response


@app.middleware("http")
async def _count_requests(request: Request, call_next):
    started = time.time()
    response = await call_next(request)
    _COUNTS["requests"] += 1
    _COUNTS["seconds"] += max(0.0, time.time() - started)
    return response



# The Factory console binds every screen to the authenticated principal.  The
# bound tenant is fetched from the product's own /v1/tenant route as soon as
# the operator supplies a token, and is stated on the page so an operator can
# see which tenant the session resolved to before touching a record.
TENANT_BINDING_SCRIPT = """
<script>
(function () {
  var tenant = "";
  function token() {
    var input = document.getElementById("tok");
    return input ? (input.value || "").trim() : "";
  }
  function bind() {
    var value = token();
    if (!value) { return; }
    fetch("/v1/tenant", { headers: { "Authorization": "Bearer " + value } })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (body) {
        if (!body) { return; }
        tenant = body.tenant_id || (body.tenant && body.tenant.id) || "";
        if (!tenant) { return; }
        document.body.setAttribute("data-tenant", tenant);
        document.title = "Delivery Service Platform \u2014 tenant " + tenant;
        paint();
      })
      .catch(function () {});
  }
  function paint() {
    var who = document.getElementById("who");
    if (who && tenant && (who.textContent || "").indexOf(tenant) === -1) {
      who.textContent = (who.textContent || "") + " \u2014 tenant " + tenant;
    }
  }
  document.addEventListener("change", function (event) {
    if (event.target && event.target.id === "tok") { bind(); }
  });
  document.addEventListener("click", function (event) {
    if (event.target && event.target.tagName === "BUTTON") { setTimeout(bind, 30); }
  });
  document.addEventListener("input", function (event) {
    if (event.target && event.target.id === "tok") { clearTimeout(window.__tenantBind); window.__tenantBind = setTimeout(bind, 250); }
  });
  var who = document.getElementById("who");
  if (who) { new MutationObserver(paint).observe(who, { childList: true, characterData: true, subtree: true }); }
})();
</script>
"""

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.is_dir():
    @app.get("/", include_in_schema=False)
    async def console():
        index = STATIC_DIR / "index.html"
        try:
            html = index.read_text(encoding="utf-8")
        except OSError:
            return PlainTextResponse("console unavailable", status_code=503)
        if "</body>" in html:
            html = html.replace("</body>", TENANT_BINDING_SCRIPT + "</body>", 1)
        return HTMLResponse(html)

    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="ui")
