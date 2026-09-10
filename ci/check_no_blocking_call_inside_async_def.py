"""A blocking `urllib` call inside `async def` freezes the whole pod, not just that request.

FOUND LIVE, TWICE, IN THE SAME PRODUCT. `adapters/token_verifier/jwks.py`'s own docstring
documents the first incident on notification-service: a slow JWKS fetch, called synchronously
inside an `async def` route, held the event loop for the whole fetch — including that pod's own
`/healthz`/`/readyz`, which timed out with no crash and no log line naming why. That one call site
was found and fixed (wrapped in `asyncio.to_thread`); the other 30+ blocking calls already fixed
the same way elsewhere in notification-service prove the pattern is known and correct here.

`services/whatsapp-assistant` never got the fix: a deep architectural review (2026-09-10) found
24 more sites — including the LLM call itself — each an `async def` whose entire body was a
synchronous `urllib.request.urlopen`, no `asyncio.to_thread` anywhere. Effective platform-wide LLM
concurrency was exactly one: not by a semaphore, by an accident of every call sharing one frozen
event loop. This gate is what stops a 25th site from landing the same way, in this service or the
next one this product adds — asyncio is the right concurrency model for I/O-bound work like this;
the defect was never using it.

THE RULE: inside an `async def`, a call to `urllib.request.urlopen` (however imported) is fine only
if that SAME function's body also calls `asyncio.to_thread` or Starlette's `run_in_threadpool` —
the two offload mechanisms already used correctly elsewhere in this codebase (notification-service's
`core/notifier.py`, `services/operations`'s `adapters/whatsapp_admin.py` and
`adapters/renewal_provider.py`). A nested SYNCHRONOUS helper (a plain `def`, not `async def`) that
calls `urlopen` is exactly the correct shape — the offload happens at the `async def` call site that
invokes it via `asyncio.to_thread`, not inside the sync helper itself, so sync helpers are never
flagged; only an `async def` whose OWN body reaches `urlopen` directly is.

SCOPE. `services/*/app/**/*.py` — this product's own services, never `platform/` (vendored,
read-only, and already holds the correct pattern throughout). Test files are excluded: a test's own
`urlopen`-shaped mock inside an `async def` is fixture plumbing, not a live request path.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

_OFFLOAD_NAMES = {"to_thread", "run_in_threadpool"}


def _calls_urlopen(node: ast.AST) -> bool:
    """Does this Call node invoke `urlopen`, however it was imported (`urllib.request.urlopen`,
    `from urllib.request import urlopen` -> bare `urlopen`, an aliased import)?"""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "urlopen"
    if isinstance(func, ast.Attribute):
        return func.attr == "urlopen"
    return False


def _calls_offload(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.id if isinstance(func, ast.Name) else (
        func.attr if isinstance(func, ast.Attribute) else "")
    return name in _OFFLOAD_NAMES


def _scan_async_function(fn: ast.AsyncFunctionDef) -> tuple[bool, bool]:
    """(reaches urlopen directly, offloads somewhere) over THIS function's own body — a nested
    `def`/`async def`'s body belongs to that nested function, not this one, so it is walked
    separately (or, for a nested sync `def`, never flagged at all — see the module docstring)."""
    reaches_urlopen = False
    offloads = False
    for node in ast.walk(fn):
        if node is fn:
            continue
        # A nested function's body is a DIFFERENT scope — skip its subtree here; ast.walk over the
        # module still visits it independently as its own FunctionDef/AsyncFunctionDef.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _calls_urlopen(node):
            reaches_urlopen = True
        if _calls_offload(node):
            offloads = True
    return reaches_urlopen, offloads


def _walk_functions(tree: ast.Module):
    """Every FunctionDef/AsyncFunctionDef in the tree, at any nesting depth — a plain `ast.walk`
    already reaches nested ones; this just filters to the two node types once."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(
        p for p in SERVICES.rglob("*.py")
        if "/tests/" not in p.as_posix() and not p.name.startswith("test_")
        and "__pycache__" not in p.parts)
    if not files:
        print("no service .py files found — this gate needs re-pointing")
        return 1

    hits: list[str] = []
    checked = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {f.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        if "urlopen" not in text:
            continue
        try:
            tree = ast.parse(text, filename=str(f))
        except SyntaxError as exc:
            print(f"cannot parse {f.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        for fn in _walk_functions(tree):
            if not isinstance(fn, ast.AsyncFunctionDef):
                continue
            checked += 1
            reaches_urlopen, offloads = _scan_async_function(fn)
            if reaches_urlopen and not offloads:
                hits.append(f"{f.relative_to(ROOT).as_posix()}:{fn.lineno}: "
                            f"async def {fn.name}() calls urlopen() directly, "
                            f"with no asyncio.to_thread/run_in_threadpool in the same function")

    if hits:
        print(f"{len(hits)} async function(s) block the event loop on a direct urlopen() call:")
        for line in hits:
            print("  " + line)
        print("\nA blocking call inside `async def` freezes the WHOLE pod for its duration — its "
              "own /healthz/readyz included, every other tenant's request on the same pod, all of "
              "it — not just the slow call. Fix: move the urllib call into a plain (non-async) "
              "helper method, then call that helper via `await asyncio.to_thread(self._helper, "
              "...)` from the async def — see services/operations/app/adapters/renewal_provider.py "
              "or platform's notification-service/app/core/notifier.py for the established pattern.")
        return 1
    print(f"{checked} async function(s) reaching urlopen() across services/: every one offloads it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
