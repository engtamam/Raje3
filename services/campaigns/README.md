# campaigns

Goal-driven marketing campaigns for a Raje3 shop — the owner picks a GOAL (win-back an absent
customer, reward a loyal one, announce something, an offer on one service or package, a seasonal
awareness tip), never a mode. This service derives who fires it (manual/scheduled/standing), which
template it sends, and its regulatory class (marketing vs. awareness), then resolves the audience
and dispatches through reminders' own send gate — never a second, drifting copy of the WhatsApp
messaging limits/quiet-hours rules `reminders` already enforces.

A standing campaign (e.g. win-back) evaluates daily and fires itself; a manual one is sent once, on
the owner's own press. Every firing — automated or manual — writes its own `Run` record: matched,
sent, suppressed, failed, and why, so "why did nobody get it last Tuesday" always has a real answer.

Backend + endpoints only (no UI — the console renders it). See `app/core/models.py` for the full
goal/trigger/state design and `app/api/v1/campaigns.py` for the routes.

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
  core/models.py         # Campaign/Run — the goal-driven design, one record for three triggers
  core/audience.py        # who a campaign reaches, resolved fresh at every fire (never cached)
  core/dispatch.py         # fires a campaign through reminders' own send gate
  core/tick.py             # the daily pass that evaluates every standing campaign
  api/v1/campaigns.py       # the owner-facing routes (create, preview, list, runs)
  api/internal.py           # X-Internal-Token routes for peer services
tests/
```
