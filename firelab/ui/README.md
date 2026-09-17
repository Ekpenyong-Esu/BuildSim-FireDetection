# ui — Svelte Frontend

Part 7 of [READING_ORDER.md](../READING_ORDER.md). Previous: #58 `app/main.py`.

How to read (numbers are global across firelab):

- **#59** `src/main.js` — mounts the app
- **#60** `src/lib/store.svelte.js` — single store: SSE `/api/events` + REST calls
- **#61** `src/App.svelte` — 3-column layout
- **#62–76** `src/lib/` — panels — see [src/lib/README.md](src/lib/README.md)

Build plumbing, skim only: `index.html`, `vite.config.js`, `package.json`. `dist/` is the build output served by `app/main.py`.

Next → #77 [`tests/helpers.py`](../tests/README.md).

See `diagram.mmd`.
