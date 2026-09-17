# pkg — Core Packages

How to read (bottom-up):

1. `model/` — shared nouns (no imports)
2. `graph/` — routing (imports `model`)
3. `store/` — in-memory store (imports `model`)
4. `server/` — HTTP + WebSocket (imports `model`+`graph`+`store`)
5. `client/` — typed HTTP client (standalone)

See `diagram.mmd`.
