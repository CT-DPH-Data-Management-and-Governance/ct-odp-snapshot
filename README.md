# ct-odp-snapshot

A daily, one-page snapshot of every asset published on
[data.ct.gov](https://data.ct.gov) — what is out there, who publishes it,
how fresh it is, and how complete its metadata is.

No agency filtering, no staff rosters. Whatever is on the domain is in
scope.

The app is a [marimo](https://marimo.io) notebook exported to WebAssembly
and served from GitHub Pages. It runs entirely in the browser — there is
no server and no database.

## How it works

```
Socrata /api/catalog  ──fetch.py──>  raw payload
                      ──flatten.py─>  tidy asset + tag frames
                      ──etl.py────>  app/public/{assets.csv,tags.csv,meta.json}
                                          │
                        marimo export html-wasm app/snapshot.py
                                          │
                                     GitHub Pages
```

The ETL is deliberately dumb: **load and replace**. Every run discards the
previous files and writes fresh ones. There is no history, no incremental
load, no database. The portal is the system of record.

GitHub Actions runs the whole chain daily at 09:00 UTC (and on every push
to `main`, and on demand).

## Layout

| Path | What it is |
| --- | --- |
| `src/ct_odp_snapshot/fetch.py` | One Socrata call for the whole catalog |
| `src/ct_odp_snapshot/flatten.py` | Nested payload → tidy polars frames |
| `src/ct_odp_snapshot/etl.py` | Derived columns, headline stats, file writes |
| `src/ct_odp_snapshot/settings.py` | Env-backed config (token, domain, stale threshold) |
| `app/snapshot.py` | The marimo app |
| `app/public/` | ETL output — generated, never committed |
| `.github/workflows/deploy.yml` | Daily ETL + build + Pages deploy |

## Running it locally

Needs [uv](https://docs.astral.sh/uv/) and a Socrata app token.

```bash
cp example.env .env          # then put your token in it
uv sync
uv run etl                   # writes app/public/
uv run marimo edit app/snapshot.py
```

To build exactly what Pages serves:

```bash
uv run marimo export html-wasm app/snapshot.py -o dist --mode run
python -m http.server -d dist 8000
```

The app reads its data over HTTP from `public/`, so opening `dist/index.html`
straight off the filesystem will not work — serve the directory.

## Configuration

| Env var | Default | Meaning |
| --- | --- | --- |
| `ODP_API_KEY` | *(required)* | Socrata app token |
| `ODP_DOMAIN` | `data.ct.gov` | Any Socrata portal works |
| `STALE_DAYS` | `365` | Age at which an asset counts as stale |

## Deploying

One-time setup on the GitHub repo:

1. `gh secret set ODP_API_KEY` — the workflow fails without it.
2. Settings → Pages → **Source: GitHub Actions**.

After that the daily run publishes itself.
