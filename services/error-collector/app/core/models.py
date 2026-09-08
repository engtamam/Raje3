"""The collections this service writes, named in one place.

One name per collection, imported everywhere rather than re-typed — a collection written under
`"signals"` in one module and `"signal"` in another is two stores that both look correct and never
see each other's rows, and nothing in the platform would report it.
"""
from __future__ import annotations

#: Every signal, from every source, in ONE collection.
#
# NOT SPLIT BY SOURCE, deliberately. A browser error and a pod's stack trace are the same question
# asked from two places — "what broke, when, and for whom" — and the moment they live in two
# collections every reader has to remember to ask twice. The `source` field is what separates them,
# and it is a plain indexed string precisely so a third source (a mobile app, a webhook peer) is a
# new VALUE and not a new table, a new migration and a new screen.
SIGNALS = "signals"

#: The constant partition every signal row carries.
#
# `DataStore.find()` refuses an empty `where` on purpose (a cross-tenant leak one typo away), and
# this store is deliberately NOT tenant-partitioned — a platform operator reads across the whole
# fleet, which is the entire point of the screen. So every row carries one constant field, and the
# browse/reap queries filter on it. It is the smallest honest way to say "all of them" to a port
# whose contract is "never all of them by accident".
SIGNAL_KIND = "signal"
