# Cerebrum Builds

The Fork (the-shovel) was built first, by hand, from block code; its blocks were extracted to create the Store (cerebrum-blocks); the Factory (CerebrumDev.ai) was built on the Store afterwards. The Fork is not a Factory product.

Its role: the certified-build store — the platform builds the CerebrumDev.ai Factory produces land here.

## What lands here

Each certified build is a complete vertical platform the Factory assembled from
certified Cerebrum-Blocks kernels. A build lands as a `build/plt_<id>` branch
carrying that platform's full tree — the FastAPI app, the vendored certified
blocks, the pinned `blocks.lock.json`, the `Dockerfile`, tests, and the build
receipt. The Factory's COLLECTOR surveys this repo so an already-built platform
is reused instead of rebuilt.

`main` holds the build gate and nothing else — no platform tree lives on
`main`; every build is its own `build/plt_*` branch.

## The gate

The gate runs in GitHub Actions: main's `.github/workflows/store-gate.yml` is
dispatched with `build_ref`, `docker build`s the build branch's artifact image,
and runs that build branch's own `scripts/acceptance.py` inside it. Acceptance is a **k/N contract** — N measured
checks, k of them passing — and a build is certified only at the required k/N;
below it the build is not certified. A build packages as a container
(`Dockerfile`) for the platform's own AWS deployment; the build itself is not a
live service.

## Auth convention

Generated platforms gate mutating routes behind token env vars (for example
`OPERATOR_TOKEN` and `ADMIN_TOKEN`), and restrict CORS to `CORS_ALLOWLIST` (a
wildcard is refused). A client-supplied `actor` / `user_id` is a claimed value
only.
