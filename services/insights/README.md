# insights

A nightly-computed dashboard and association engine for a Raje3 shop — never an indicator computed
on the request path. `core/tick.py` runs once a day, reads visits/balances/campaign runs from their
OWNING services (never a mirrored copy), and writes one `Snapshot` per tenant (and per branch); the
owner-facing route only ever reads what tick already stored, with an honest `computed_at`/`partial`
flag so a number never looks more current or more complete than it actually is.

The association engine (`core/associations.py`) finds which two services tend to go together, judged
on BOTH axes — same-basket (careful about a family's one receipt looking like a relationship) and
same-customer-repeatedly (a habit, not a coincidence) — feeding the bundle-suggestion feature and
the AI assistant's own cross-sell prompt.

Backend + endpoints only (no UI — the console renders it). See `app/core/models.py` for what is
stored (and the much longer list of what deliberately is not) and `app/core/tick.py` for the nightly
compute pass.

## Run it

Requires **Python 3.12**.

```bash
py -3.12 -m venv .venv
. .venv/Scripts/activate          # PowerShell: .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
pytest -q
```

## Layout

```
app/
  core/models.py         # Snapshot/CustomerSequence/Pair — what is stored, and why so little is
  core/tick.py             # the nightly pass: computes every indicator, writes one snapshot
  core/indicators.py        # the individual number-crunching functions tick.py calls
  core/associations.py      # the two-axis "goes together" engine behind bundle suggestions
  core/rollup.py            # the cross-tenant platform summary, for the admin panel
  api/v1/insights.py         # the owner-facing dashboard route (reads a snapshot, never computes)
  api/internal.py            # X-Internal-Token routes for peer services
tests/
```
