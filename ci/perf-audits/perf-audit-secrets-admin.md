# Perf audit — services/secrets-admin/ (read-only)

Scope covered: app/ (all subpackages), ci/ (check_licenses.py, security_gate.py),
tests/ (integration, unit, security). platform/ and repo-root ci/ excluded per instructions.

## Method
Grepped for the defect classes named in the task (rglob/os.walk/glob, per-char loops,
repeated file reads, N+1 calls, O(n^2)/list-membership-in-hot-path, blocking sleep in
async, full-scan-instead-of-indexed-lookup), then read every file that matched or that
handles request-time / CI-time work: app/security/{checks,cwe_guard,catalog,step_map}.py,
app/manifest.py, app/api/{authz,v1/secrets}.py, app/adapters/k8s_client.py,
app/adapters/rate_limiter/sliding_window.py, app/core/secret_registry.py,
ci/check_licenses.py, ci/security_gate.py.

## Findings

**Nothing significant found.** This service does not have the class of defect found in
ci/check_deploy_wiring.py, for concrete reasons:

1. **No filesystem tree walks at all.** `grep -rn "rglob\|os.walk\|glob("` across app/,
   tests/, ci/ returned zero hits. check_licenses.py and security_gate.py (the only two
   CI scripts specific to this service) work entirely off `importlib.metadata.distributions()`
   and `subprocess.run` calls to external tools (bandit, detect-secrets, pip-audit,
   cyclonedx, trivy) — no directory traversal of this service's own source tree happens
   in Python at all, so there's no node_modules/.venv/platform-submodule walk to prune.

2. **No per-character loops over arbitrary-length text.** The only per-character-ish
   constructs are:
   - `app/adapters/telemetry/stdout.py:26`: `"".join(c if c.isalnum() else "_" for c in name)`
     — `name` is a metric/event name, always a short fixed literal from this codebase
     (tens of characters), never file-sized input. Not a hot path over large text.
   - `ci/check_licenses.py:34` `classify_one()`: runs a handful of `in` checks against a
     license string per installed **package** (`importlib.metadata.distributions()`),
     not per file or per character of a large corpus. A Python venv has on the order of
     50-150 distributions; this is ~150 * ~20 substring checks = a few thousand ops,
     sub-millisecond. Not comparable to a 137M-ord()-call full-repo-text scan.

3. **No repeated re-reads of the same file across functions.** `_own_package_name()` in
   check_licenses.py reads pyproject.toml once per process; nothing else in this service
   reads a file more than once for the same purpose. K8s tokens are intentionally
   re-read per call (app/adapters/k8s_client.py:107-114) but that's correctness (token
   rotation), not redundant work — same file, but required freshness, and it's a single
   small in-cluster file read over a local named pipe/tmpfs, not a large-file re-parse.

4. **No N+1 pattern** — in fact `app/api/v1/secrets.py:100-116` (`list_secrets`)
   explicitly guards against N+1: it keys a `seen` dict on `(namespace, secret_object)`
   and only calls `k8s.read_secret_annotations()` once per distinct k8s Secret object,
   collapsing what would be 9 calls (one per `SecretEntry` in the registry) down to 3
   (one per distinct Secret object) — already the optimization this audit would have
   recommended.

5. **No O(n^2) or list-as-set hot path.** `app/api/authz.py:25,37` does
   `all(c in held for c in caps)` / `any(c in held for c in caps)`, but `held` is
   `principal.caps`, typed and constructed as a `frozenset[str]` (see
   `app/api/authz.py:16 effective_caps() -> frozenset[str]`), and `caps` (the required
   capability list per route) is a handful of literal strings (1-3 items) declared at
   router-definition time. `c in held` against a frozenset is O(1); the whole check is
   O(caps) with caps bounded by a small compile-time constant, not by any user- or
   tenant-scaled collection.

6. **`app/core/secret_registry.py`**: `SECRETS` is a fixed tuple of 9 hardcoded
   `SecretEntry` literals (a closed allowlist by design — see the module docstring); the
   `BY_KEY` dict comprehension at line 194 builds an O(1) key->entry lookup once at
   import time. No scan of this ever happens per-request beyond iterating those 9 items
   in `list_secrets`.

7. **No blocking I/O inside async code.** `grep -n "time.sleep|asyncio.sleep"` across
   app/ returned zero hits. The only `time.sleep` in the whole service is in
   `ci/security_gate.py:118`, inside a **synchronous** CI retry loop for pip-audit
   (`1s, 2s` backoff, 3 attempts max) — not inside an async request handler, so it's not
   the defect class described (blocking the event loop). It's a deliberate, bounded,
   off-request-path retry.

8. **Rate limiter (`app/adapters/rate_limiter/sliding_window.py`)** is GCRA: O(1) per
   check, one stored float (TAT) per key, no loop, no collection scan at all. This is
   already the "cheap enough for the hot path" design the file's own docstring argues
   for, and it holds up on inspection.

9. **k8s_client.py** SSL context is built once and cached (`_context()`, line 70-75,
   with an explicit comment about avoiding a per-request CA-bundle reload) — the same
   shape of fix as the regex-compile-once pattern in the audited example, already
   applied here.

## Conclusion
services/secrets-admin/ is a small, request-scoped CRUD-over-k8s-Secrets service with a
hardcoded 9-entry credential registry and thin CI gates that mostly shell out to external
scanners. There is no large corpus this service walks or scans (no repo-wide text
scanning, no big collections, no per-tenant fan-out), so the defect class from
check_deploy_wiring.py (accidentally-quadratic scans over large trees/text) has no
equivalent surface here to exhibit on. No changes recommended.
