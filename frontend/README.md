# Console source

`src/App.tsx` is the React source of the operator console the platform serves.
The shipped console is the committed build at `app/static/index.html` (the same
screen: capability discovery from `/v1/capabilities`, a form per capability,
the answer with its authority label, and the tenant-scoped record list). The
image serves that file at `/`; it needs no node build at image time.

If you change the console, rebuild it into `app/static/index.html`:

```sh
cd frontend && npm ci && npm run build   # vite, build.outDir -> ../app/static
```
