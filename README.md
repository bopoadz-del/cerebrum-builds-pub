# Cerebrum Builds

The certified-build store of the Cerebrum platform. Each build is a complete
vertical platform that the **CerebrumDev.ai Factory** assembled from certified
**Cerebrum-Blocks** kernels and put through the build gate.

## What lands here

A certified build lands as a `build/plt_<id>` branch carrying that platform's
full tree — the FastAPI app, the vendored certified blocks, the pinned
`blocks.lock.json`, the `Dockerfile`, tests, and the build receipt. The
Factory's COLLECTOR surveys this repo so an already-built platform is reused
instead of rebuilt.

## Lineage

- **The Store — Cerebrum-Blocks:** the certified capability inventory.
- **The Factory — CerebrumDev.ai:** assembles blocks into a governed,
  deployable platform.
- **The Builds — this repo:** the certified platform builds the Factory ships.

## Deploy and gate

A build packages as a container (`Dockerfile`) for the platform's own AWS
deployment; the build itself is not a live service. The build gate runs in
GitHub Actions (Docker build + `scripts/acceptance.py`) and must pass before a
build is certified.

## Run a build locally

```
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```
