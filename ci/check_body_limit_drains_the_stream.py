"""A body-size limit that only reads `Content-Length` is not a limit — it is a header a client can
omit.

WHY THIS EXISTS. `BodyLimitMiddleware` exists once per service (one near-identical copy per
`services/*/app/middleware/security.py`, not a shared module — this codebase's own convention for
small, deliberately-duplicated boilerplate). Its whole job is "refuse an oversized request body
before it reaches a route." A version that reads `request.headers.get("content-length")`, compares
it to the configured max, and otherwise falls straight through to `call_next(request)` refuses
exactly ONE shape of oversized request: one that is honest about its own size in a header. A
request sent with `Transfer-Encoding: chunked` (no `Content-Length` at all — httpx and every real
HTTP client produce this automatically for a streamed/generator body) or one that simply lies about
a small Content-Length sails straight through untouched, and the route (or Starlette's own
`Request.body()`/`.json()`) then buffers the WHOLE real body into memory regardless of the
configured cap.

FOUND AND FIXED, REPEATEDLY, BY HAND — a QA audit pass (2026-09-12) found and fixed this exact
defect in bookings, operations, error-collector and reminders, one service at a time, each with its
own regression test proving a chunked oversized body is now refused. A SECOND audit pass the same
day, run independently per-service, found the IDENTICAL unfixed defect still sitting in insights,
loyalty, campaigns, affiliate-service, portal, secrets-admin and whatsapp-assistant — services the
first pass's own per-service agents simply never happened to flag. That is precisely the failure
mode a hand-run audit cannot close and a mechanical gate can: this gate checks EVERY copy of the
class, not just the ones a reviewer's attention happened to land on.

THE CORRECT SHAPE (see bookings/operations/error-collector/reminders's own `security.py` for the
reference implementation): the header check stays as a cheap early rejection for an honest client,
but the middleware ALSO drains `request.stream()` itself, chunk by chunk, counting bytes as it
goes and refusing the instant the running total crosses `max_bytes` — regardless of what
`Content-Length` said or whether it was present at all — then caches the result on `request._body`
(Starlette's own caching attribute) so every downstream reader sees the same bytes exactly once.

WHAT THIS CHECKS. For every `services/*/app/middleware/security.py` (or any file — the path is not
hardcoded, in case a service ever splits it) that defines a class literally named
`BodyLimitMiddleware`, that class's `dispatch` method must contain an `async for` loop over a call
to `request.stream()` (the draining shape) — or, as an alternative deliberate whitelisted shape,
Starlette's own `await request.body()` called and its LENGTH checked (equally safe: `.body()`
buffers-then-returns, so the caller can measure it) before the route sees a payload larger than the
cap. A `BodyLimitMiddleware` whose `dispatch` reads and compares only `content-length` and never
calls `request.stream()` or `request.body()` at all is flagged — that is the exact bypassable
shape.

WHAT THIS CANNOT SEE, said plainly: a body-limit mechanism implemented under a different class
name, or one delegated entirely to an edge proxy in front of every service (this codebase's own
`deploy/edge/console.yaml` gateway is not itself scanned here) — this gate only follows the one
class name every service currently uses for this job.

    python ci/check_body_limit_drains_the_stream.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

_EXCLUDED_DIRS = {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}


def _is_excluded(path: pathlib.Path) -> bool:
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def _drains_the_body(fn: ast.AsyncFunctionDef) -> bool:
    """`dispatch`'s own body reaches EITHER an `async for` over `request.stream()` (any call
    literally named `.stream()`, not qualified to a specific variable name — different services
    name the middleware's own parameter differently) OR an awaited call to `.body()` — both force
    the real bytes to be read (and, for `.stream()`, counted) regardless of what `Content-Length`
    claimed or whether it was even sent."""
    for node in ast.walk(fn):
        if node is fn:
            continue
        if isinstance(node, ast.AsyncFor):
            call = node.iter
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                    and call.func.attr == "stream":
                return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "body":
            return True
    return False


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(
        f for f in SERVICES.rglob("*.py")
        if not _is_excluded(f) and "test" not in f.parts and not f.name.startswith("test_")
    )

    violations: list[str] = []
    classes_checked = 0

    for f in files:
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(f))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name != "BodyLimitMiddleware":
                continue
            classes_checked += 1
            dispatch = next(
                (m for m in node.body
                 if isinstance(m, ast.AsyncFunctionDef) and m.name == "dispatch"),
                None)
            if dispatch is None:
                violations.append(
                    f"{f.relative_to(ROOT)}: BodyLimitMiddleware has no async `dispatch` method "
                    f"at all — nothing here can be enforcing a body limit")
                continue
            if not _drains_the_body(dispatch):
                violations.append(
                    f"{f.relative_to(ROOT)}: BodyLimitMiddleware.dispatch only checks "
                    f"Content-Length and never drains request.stream()/request.body() — a "
                    f"chunked request (no Content-Length header at all) or one that understates "
                    f"its own size bypasses the limit entirely")

    if violations:
        print(f"  ✘ {len(violations)} of {classes_checked} BodyLimitMiddleware "
              f"implementation(s) can be bypassed by an honest-header-free (chunked) body:")
        for v in violations:
            print(f"      {v}")
        return 1

    print(f"  ✔ all {classes_checked} BodyLimitMiddleware implementation(s) drain the real body "
          f"— a chunked or Content-Length-free request cannot bypass the limit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
