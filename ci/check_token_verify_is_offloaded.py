"""A TokenVerifier's `.verify()` call must never run synchronously inside `async def`.

WHY THIS EXISTS. Every service in this codebase wires the identical port: `app/ports/
token_verifier.py` declares `TokenVerifier.verify(token) -> dict`, and the concrete adapter
selected by `TOKEN_VERIFIER_DRIVER` is a PLAIN (non-async) method — `HS256Verifier`/`RS256Verifier`
do local cryptographic work (cheap, but still a sync call), and `JWKSVerifier` (see
`app/adapters/token_verifier/jwks.py`'s own docstring, present verbatim in every service) can
additionally trigger a REAL network fetch of the remote key set. None of that is visible to a
plain "does this reach urlopen/subprocess" AST scan — the network call happens inside PyJWT's own
`PyJWKClient`, a third-party dependency, not in any line this codebase's own source shows. The only
place the risk is knowable at all is the port's own contract: `.verify()` may block, unconditionally,
by design.

FOUND LIVE, TWICE (see `jwks.py`'s own docstring): a slow JWKS fetch synchronously inside
`async def require_user`/`rate_limit` froze the whole pod's single-worker event loop for the
duration of the fetch — including that pod's own `/healthz`/`/readyz`, which timed out with no
crash and no log line naming why. This is not a per-request cost; it is every unauthenticated
request that reaches auth (or the rate limiter, which checks the token before deciding the bucket)
sharing one frozen event loop for as long as the slowest fetch takes.

FIXED IN insights (`app/api/auth.py::require_user`, `app/api/ratelimit.py::optional_principal`) —
both wrap the call in `await asyncio.to_thread(verifier.verify, token)`. A QA audit pass the same
day found the IDENTICAL unfixed call — `verifier.verify(token)` / `...token_verifier.verify(token)`
— still sitting, unoffloaded, in the other 10 services, each with the exact same file at the exact
same two call sites (`app/api/auth.py`, `app/api/ratelimit.py`) — a byte-for-byte-near-identical
copy that only ONE service's own audit pass happened to flag.

WHAT THIS CHECKS. Any `X.verify(...)` call — matched by attribute name `verify`, and by the
receiver expression's own source text containing the substring "verifier" (case-insensitive:
`verifier.verify(...)`, `token_verifier.verify(...)`, `self._verifier.verify(...)`, and their
`container.token_verifier.verify(...)` chained form all match; an unrelated `.verify()` on
something never named anything containing "verifier" does not, keeping this from firing on some
future, entirely different `.verify()` method this codebase might add) — appearing inside an
`async def` whose own body does NOT also call `asyncio.to_thread`/`run_in_threadpool` anywhere.
Deliberately narrow (name-and-substring, not a generic blocking-call scan): the danger here is not
"this reaches urlopen", it is "this is `TokenVerifier.verify()`, which the port's own contract
already admits may block" — a fact only this specific name pins down.

    python ci/check_token_verify_is_offloaded.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

_OFFLOAD_NAMES = {"to_thread", "run_in_threadpool"}
_EXCLUDED_DIRS = {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}


def _is_excluded(path: pathlib.Path) -> bool:
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def _calls_offload(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else (
        func.id if isinstance(func, ast.Name) else "")
    return name in _OFFLOAD_NAMES


def _is_unoffloaded_verify_call(node: ast.AST) -> str | None:
    """Returns the receiver's source text if `node` is a `<receiver>.verify(...)` call whose
    receiver's own source mentions "verifier" — the one shape this gate cares about — else None."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if not (isinstance(func, ast.Attribute) and func.attr == "verify"):
        return None
    try:
        receiver_src = ast.unparse(func.value)
    except Exception:                                                        # noqa: BLE001
        return None
    if "verifier" not in receiver_src.lower():
        return None
    return receiver_src


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(
        f for f in SERVICES.rglob("*.py")
        if not _is_excluded(f) and "test" not in f.parts and not f.name.startswith("test_")
    )

    violations: list[str] = []
    checked = 0

    for f in files:
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(f))
        except (SyntaxError, UnicodeDecodeError):
            continue

        for fn in ast.walk(tree):
            if not isinstance(fn, ast.AsyncFunctionDef):
                continue
            offloaded = False
            calls: list[tuple[int, str]] = []
            for node in ast.walk(fn):
                if node is fn:
                    continue
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue  # a nested def's own body is walked separately, on its own terms
                if _calls_offload(node):
                    offloaded = True
                receiver = _is_unoffloaded_verify_call(node)
                if receiver is not None:
                    checked += 1
                    calls.append((node.lineno, receiver))
            if not offloaded:
                for lineno, receiver in calls:
                    violations.append(
                        f"{f.relative_to(ROOT)}:{lineno}: `{receiver}.verify(...)` runs "
                        f"synchronously inside `async def {fn.name}` with no "
                        f"asyncio.to_thread/run_in_threadpool anywhere in the same function — a "
                        f"JWKSVerifier driver's real network fetch would freeze the whole pod")

    if violations:
        print(f"  ✘ {len(violations)} unoffloaded TokenVerifier.verify() call site(s):")
        for v in violations:
            print(f"      {v}")
        return 1

    print(f"  ✔ {checked} TokenVerifier.verify() call site(s) checked — none block the event "
          f"loop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
