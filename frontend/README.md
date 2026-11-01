# Console source

The platform serves ONE console: `app/static/index.html` at `/`.

- `dist/index.html` is the self-contained page (HTML + CSS + vanilla JS) that
  is shipped. `frontend/build.py` validates it and renders the copy the image
  serves. The Dockerfile runs `python3 frontend/build.py` during the build, so
  the asset the image serves is produced by this tree, not copied by hand.
- `src/App.tsx` and `src/modules/*.tsx` are the readable React/TypeScript
  source of the same console, kept in step with `dist/index.html` by hand.
  They make the same calls: `GET /v1/capabilities`, `POST /v1/<capability>`,
  `GET /v1/<capability>`, `GET /health`, `GET /v1/authority`,
  `GET /v1/provenance`.

No JS toolchain runs at image build or run time: `npm run build` runs the
stdlib-only Python build script. Nothing is downloaded, and the console makes
no off-box request.
