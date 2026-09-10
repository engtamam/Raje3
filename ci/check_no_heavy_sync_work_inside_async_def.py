"""File reads and deliberately-slow hashing inside `async def` freeze the pod the same way a
blocking network call does — a separate gate from `check_no_blocking_call_inside_async_def.py`
because these two are NOT syntactically detectable as "urlopen vs. offload": most `open()` calls
and most hashing are cheap and harmless, so a gate here has to name specific, precise, known-heavy
operations rather than every call to a common builtin.

WHY THIS IS SEPARATE FROM THE OTHER GATE, ON PURPOSE. `check_no_blocking_call_inside_async_def.py`
flags urlopen/subprocess/requests unconditionally when unoffloaded, because ANY network round trip
is worth moving off the loop. `open()` is not that: reading three bytes off local disk and reading
a 40MB export are the same syntax. This gate does NOT try to guess file size — it only flags the
one case this codebase actually has, verified by grep before writing this: `adapters/object_store/
local.py` already correctly wraps its own file I/O in `asyncio.to_thread` (the established
pattern), so a NEW site that reaches the bare `open(...)` builtin directly inside `async def` is
either a second file adapter that forgot the wrapper, or file I/O that snuck into request-path code
that was never meant to touch disk at all — both worth a human look, so `open()` itself is flagged
here, same offload-or-flag rule as the other gate's network calls.

DELIBERATELY-SLOW HASHING is the second, more precise case: `hashlib.pbkdf2_hmac`/`hashlib.scrypt`
and `bcrypt.hashpw`/`bcrypt.checkpw` are designed to be CPU-expensive — that is the whole point of a
password/PII-hashing KDF, tunable to take real milliseconds on purpose (`secret_store.py`'s own
`hashlib.scrypt` call, verified read: it runs once at construction, not per-request, which is why it
is not flagged — this gate only reaches into `async def` bodies). Unlike a plain hash (`sha256` etc,
sub-microsecond, never flagged), a KDF call reached directly from a live `async def` request path
blocks the event loop for its own tuned cost, every time. `asyncio.to_thread` is the correct fix
here too (CPU-bound work under the GIL does not gain true parallelism from a thread, but it DOES
stop blocking the loop that is scheduling everyone else's I/O — the loop was never doing this
service's own computation in parallel anyway, only interleaving I/O waits).

SCOPE. `services/*/app/**/*.py` — never `platform/` (vendored, read-only). Test files excluded.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

_OFFLOAD_NAMES = {"to_thread", "run_in_threadpool"}
#: The builtin file-open — flagged as a bare name only (never `self.open`/`store.open`, which are
#: unrelated methods that merely share the word).
_FILE_OPEN_BARE_NAMES = {"open"}
#: Deliberately-expensive KDF/hash calls, matched ONLY when qualified on their real module/library
#: name — the same false-positive reasoning as the sibling gate's `subprocess.run`: `hashpw`/
#: `pbkdf2_hmac` are specific enough as bare names too (nothing else in this codebase is named
#: that), but kept qualified here for symmetry and because `hashlib`/`bcrypt` might not always be
#: imported that way.
_HEAVY_HASH_QUALIFIED = {("hashlib", "pbkdf2_hmac"), ("hashlib", "scrypt"),
                        ("bcrypt", "hashpw"), ("bcrypt", "checkpw")}


def _call_name(node: ast.AST) -> str:
    if not isinstance(node, ast.Call):
        return ""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_file_open(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node) in _FILE_OPEN_BARE_NAMES \
        and isinstance(node.func, ast.Name)


def _is_heavy_hash(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return (func.value.id, func.attr) in _HEAVY_HASH_QUALIFIED
    return False


def _calls_offload(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node) in _OFFLOAD_NAMES


def _scan_async_function(fn: ast.AsyncFunctionDef) -> tuple[bool, bool, bool]:
    """(reaches open() directly, reaches a heavy KDF directly, offloads somewhere) over THIS
    function's own body — a nested `def`/`async def` is a different scope, walked separately."""
    reaches_open = False
    reaches_hash = False
    offloads = False
    for node in ast.walk(fn):
        if node is fn:
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_file_open(node):
            reaches_open = True
        if _is_heavy_hash(node):
            reaches_hash = True
        if _calls_offload(node):
            offloads = True
    return reaches_open, reaches_hash, offloads


def _walk_functions(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    excluded_dirs = {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}
    files = sorted(
        p for p in SERVICES.rglob("*.py")
        if "/tests/" not in p.as_posix() and not p.name.startswith("test_")
        and not (excluded_dirs & set(p.parts)))
    if not files:
        print("no service .py files found — this gate needs re-pointing")
        return 1

    open_hits: list[str] = []
    hash_hits: list[str] = []
    checked = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {f.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        if not any(name in text for name in ("open(", "pbkdf2_hmac", "scrypt", "hashpw", "checkpw")):
            continue
        try:
            tree = ast.parse(text, filename=str(f))
        except SyntaxError as exc:
            print(f"cannot parse {f.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        rel = f.relative_to(ROOT).as_posix()
        for fn in _walk_functions(tree):
            if not isinstance(fn, ast.AsyncFunctionDef):
                continue
            checked += 1
            reaches_open, reaches_hash, offloads = _scan_async_function(fn)
            if reaches_open and not offloads:
                open_hits.append(f"{rel}:{fn.lineno}: async def {fn.name}() calls open() "
                                 f"directly, with no asyncio.to_thread/run_in_threadpool in the "
                                 f"same function")
            if reaches_hash and not offloads:
                hash_hits.append(f"{rel}:{fn.lineno}: async def {fn.name}() calls a "
                                 f"deliberately-slow hash/KDF directly, with no asyncio.to_thread/"
                                 f"run_in_threadpool in the same function")

    hits = open_hits + hash_hits
    if hits:
        if open_hits:
            print(f"{len(open_hits)} async function(s) reach open() directly, unoffloaded:")
            for line in open_hits:
                print("  " + line)
            print("\nadapters/object_store/local.py already wraps its own file I/O in "
                  "asyncio.to_thread — a NEW site reaching open() directly inside async def is "
                  "either a second file adapter that forgot the wrapper, or disk I/O that should "
                  "never have been on the request path. Fix: extract the read/write into a plain "
                  "helper, call it via `await asyncio.to_thread(self._helper, ...)`.")
        if hash_hits:
            print(f"\n{len(hash_hits)} async function(s) reach a slow KDF/hash directly, "
                  f"unoffloaded:")
            for line in hash_hits:
                print("  " + line)
            print("\nhashlib.pbkdf2_hmac/scrypt and bcrypt.hashpw/checkpw are TUNED to be "
                  "CPU-expensive — that is the point of a password/PII KDF. Called directly from "
                  "an async def request path, that cost blocks the event loop every time. Fix: "
                  "`await asyncio.to_thread(...)`, same as the other gate's network calls.")
        return 1
    print(f"{checked} async function(s) reaching open() or a slow KDF across services/: none "
          f"block the event loop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
