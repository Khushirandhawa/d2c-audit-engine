# Hyper A D2C Meta Ads Audit Engine — Vercel (Postgres) build

Cloud-hosted, Postgres-backed twin of the local SQLite app. Same UI, same
API, same 200-company dataset (`api/prospect_source.json`) — this build is
meant to be deployed to Vercel with a connected Postgres database so a team
can share one live link, separate from the local app's own hosting.

See **README_VERCEL.md** for the full non-technical deploy walkthrough
(create Vercel account → `npx vercel --prod` → add Postgres via the Storage
tab → Connect → redeploy → verify via `/api/health`).

## Structure
```
api/index.py       Flask app, Postgres via psycopg2, WSGI entrypoint for Vercel
api/seed_data.py    Segment / scoring / pipeline-stage static definitions
api/outreach_engine.py  Outreach draft generator (segment -> real-signal angle)
api/prospect_source.json  The 200 finalized company records (verbatim, not recomputed)
templates/index.html   Single-page frontend (same design system as the local app)
static/app.js, static/style.css
vercel.json         Build + routing config for @vercel/python
requirements.txt    Flask, psycopg2-binary
```

## Known Vercel gotcha already fixed here

Vercel's Python runtime does not add `api/`'s own directory to `sys.path`,
so a plain `from seed_data import (...)` fails with `ModuleNotFoundError` in
production even though the file sits right next to `index.py`. Fixed at the
top of `api/index.py`:

```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
```

## Testing

Real Postgres isn't available in most sandboxes used to build this, so the
Postgres-backed `api/index.py` was verified by running it **unmodified**
through Flask's `test_client()` with `psycopg2.connect` monkeypatched to a
SQLite-backed shim (translating `%s`→`?`, `ILIKE`→`LIKE`,
`SERIAL PRIMARY KEY`→`INTEGER PRIMARY KEY AUTOINCREMENT`, and intercepting
`RETURNING id` via `cursor.lastrowid`). All 27 end-to-end checks passed,
including `/api/health` returning `{"status":"ok","companies":200,...}` and
a same-process, second-independent-request check confirming writes persist
across requests.
