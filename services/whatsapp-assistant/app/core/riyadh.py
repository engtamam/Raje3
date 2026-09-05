"""The single place this service constructs the product's clock.

WHY THIS FILE EXISTS. `config/product.json` declares `"timezone": "Asia/Riyadh"`, and a fixed
`timezone(timedelta(hours=3))` used to be typed out by hand in app/core/tools.py — twice, for the
slot times shown to a customer and the day-boundary that decides whether a booking reads as
"upcoming" or "history". Both were right, and both were a copy of a fact that already has a home
in every OTHER service (see services/operations/app/core/riyadh.py, the first one written).

NO DST, DELIBERATELY. Saudi Arabia does not observe it, so a fixed +03:00 is the whole truth here
and a tz database would add a dependency and a failure mode for a rule that does not change.
"""
from __future__ import annotations

import datetime as _dt

#: Riyadh is UTC+03:00 all year.
RIYADH = _dt.timezone(_dt.timedelta(hours=3))
