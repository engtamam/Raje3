# Reports to base-services

`platform/` is read-only. When it lacks something generic or behaves wrongly, we report it, work
around it on our side, and delete the workaround when theirs lands. Every entry below states the
mechanism, the evidence, what a consumer can and cannot work around, and — most importantly — the
**guard** that would close the whole class rather than the single instance.

---

## OPEN — `rotate()` on a service account is a hard swap, with no overlap window

**Where:** `services/identity-service/app/core/service_accounts.py`, `ServiceAccount.rotate()`

**What it does:**

```python
async def rotate(self, account: ServiceAccount) -> str:
    secret = new_client_secret()
    account.secret_hash = self._hasher.hash(secret)
    await self._store.save(account)
    return secret
```

The old secret stops authenticating the instant the row is saved. There is exactly one live secret
per account, always.

**Why that is a problem for a consumer.** Our integration model puts a credential inside a
point-of-sale build that runs on hundreds of tills belonging to one partner. Rotating it — because
it leaked, because a contract renewed, or because an annual policy says so — currently means:

1. Press rotate.
2. Every till belonging to that partner fails authentication immediately.
3. Each one is repaired when its shop next takes a software update.

For a shop that opens three days a week, step 3 is a fortnight. During that fortnight the partner's
tills cannot post, and the shops believe their data is syncing.

The property that is missing is not "a second secret" — it is that **the overlap must expire on its
own**. An overlap an operator ends manually is an overlap nobody ends, and a credential still
working a year after it was rotated was not rotated.

**Proposed shape:** `rotate(account, overlap_seconds=...)` keeps `prev_secret_hash` and
`prev_secret_expires`; `authenticate()` checks the current hash first, then the previous one only
while its window is open, with the same constant-time comparison. A second rotation inside a window
drops the oldest hash rather than chaining — two live overlaps is a credential nobody can reason
about, and a second rotation is usually somebody reacting to a leak.

**What we can and cannot work around.** We CAN implement this for our own partner keys, and have —
`services/operations/app/core/partners.py`, `PartnerRegistry.rotate()`, six tests. We CANNOT do it
for service accounts, because that is the identity service's credential store and building a second
one is the thing the platform exists to prevent.

**The guard worth more than the fix:** a CI check that every credential-rotation path in the repo
accepts an overlap and expires it by timestamp. It would catch this instance and every future one —
including any rotation somebody adds to a different service next year without remembering this
conversation.

**Test that would have caught it:** rotate, then assert the OLD secret still authenticates; advance
the clock past the window; assert it does not.

---

## Reporting rules (from the playbook, §6)

1. Exact file and line.
2. The mechanism, not the symptom.
3. Evidence from a live system.
4. What a consumer can and cannot work around.
5. A proposed fix — **and the guard that closes the class.**

Expect the guard to find things we did not report. That is the point of it.
