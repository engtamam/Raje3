"""A blocking call inside `async def` freezes the whole pod, not just that request.

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
event loop. This gate is what stops a next one landing unnoticed — asyncio is the right concurrency
model for I/O-bound work like this; the defect was never using it.

TWO DIFFERENT DEFECT SHAPES, TWO DIFFERENT FIXES — kept as one gate because they are the same root
cause (a synchronous wait inside a coroutine) with different correct remedies:

1. NETWORK/PROCESS I/O (`urllib.request.urlopen`, `requests.get`/`.post`/`.put`/`.patch`/`.delete`/
   `.head`/`.request`, `subprocess.run`/`.call`/`.check_call`/`.check_output`, `os.system`) — fine
   inside `async def` only if that SAME function's body ALSO calls `asyncio.to_thread` or
   Starlette's `run_in_threadpool` (the two offload mechanisms already used correctly elsewhere:
   notification-service's `core/notifier.py`, `services/operations`'s `adapters/whatsapp_admin.py`/
   `adapters/renewal_provider.py`). A nested SYNCHRONOUS helper (a plain `def`, not `async def`)
   that makes the call is exactly the correct shape — the offload happens at the `async def` call
   site that invokes it via `asyncio.to_thread`, so sync helpers are never flagged; only an
   `async def` whose OWN body reaches one of these calls directly is. `requests` is not a
   dependency this codebase uses today (everything is stdlib `urllib`) — flagged anyway so a
   future dependency add does not reopen the exact same bug under a different library name.

2. `time.sleep(...)` and `threading.Lock()`/`threading.RLock()` — NEVER correct inside
   `async def`, offloaded or not. A slept THREAD holds nothing that helps (the point of sleeping in
   a coroutine is to let the loop serve other work meanwhile, which `asyncio.to_thread(time.sleep,
   n)` does not restore — it just moves the freeze to a thread-pool slot for the same duration); a
   `threading.Lock` blocks the acquiring THREAD on `.acquire()`, same freeze, and this codebase's
   event loop has exactly one thread running it. The fixes are `await asyncio.sleep(...)` and
   `asyncio.Lock()` respectively. Flagged unconditionally, no offload exception.

SCOPE. `services/*/app/**/*.py` — this product's own services, never `platform/` (vendored,
read-only, and already holds the correct pattern throughout). Test files are excluded: a test's own
mocked call inside an `async def` is fixture plumbing, not a live request path.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

_OFFLOAD_NAMES = {"to_thread", "run_in_threadpool"}
#: `urlopen(...)`, however imported (bare name or `urllib.request.urlopen`) — this one alone is
#: precise as a bare name too: nothing else in this codebase's style is ever named `urlopen`.
_BLOCKING_IO_BARE_NAMES = {"urlopen"}
#: `subprocess.<METHOD>(...)` / `os.system(...)` — matched ONLY when qualified on the exact module
#: name (`subprocess.run`, `os.system`, ...), never as a bare name: `run`/`call`/`system` are
#: common method names for entirely unrelated, already-correct async calls (a peer client's own
#: `.call(...)`), and flagging every one of those would drown the real findings in noise. A
#: deployment that did `from subprocess import run` and called it bare would slip past this — an
#: accepted gap, since nothing in this codebase's own style imports stdlib unqualified (see
#: `urlopen`'s own convention throughout `adapters/*.py`).
_SUBPROCESS_QUALIFIED = {("subprocess", "run"), ("subprocess", "call"),
                        ("subprocess", "check_call"), ("subprocess", "check_output"),
                        ("os", "system")}
#: `requests.<METHOD>(...)` — same qualified-only rule as subprocess above (`get`/`post`/etc. are
#: too generic as bare names).
_REQUESTS_QUALIFIED = {("requests", m) for m in
                       ("get", "post", "put", "patch", "delete", "head", "request")}
_SLEEP_NAMES = {"sleep"}
#: `threading.Lock(...)`/`threading.RLock(...)` — flagged at CONSTRUCTION, not at `.acquire()`
#: (which would need data-flow tracking of which object came from a Lock() call). Building one
#: inside `async def` is already the smell: the fix is `asyncio.Lock()`, not a differently-placed
#: `threading.Lock()`.
_THREAD_LOCK_QUALIFIED = {("threading", "Lock"), ("threading", "RLock")}


def _call_name(node: ast.AST) -> str:
    """The function name a Call node invokes — bare (`sleep`) or the attribute (`time.sleep` ->
    `sleep`, `subprocess.run` -> `run`). Empty string for anything else (e.g. a call through a
    subscript or a lambda result)."""
    if not isinstance(node, ast.Call):
        return ""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _is_time_sleep(node: ast.AST) -> bool:
    """`time.sleep(...)` or a bare `sleep(...)` from `from time import sleep` — never
    `asyncio.sleep`/`anyio.sleep`, which are the correct, non-blocking calls and must not be
    flagged. Distinguished by the attribute's OWN object name when qualified."""
    if not isinstance(node, ast.Call) or _call_name(node) not in _SLEEP_NAMES:
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return func.value.id in ("time",)
    # A bare `sleep(...)` — correct only if it came from `from time import sleep`, which this
    # per-function scan cannot see the import for; treated as time.sleep (the common case in this
    # codebase, which imports `time` qualified everywhere it does — see module docstring). A
    # deployment that imports `asyncio.sleep` bare under the same name would be a false positive
    # this gate accepts rather than build full import-alias tracking for.
    return isinstance(func, ast.Name)


def _is_blocking_io(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    name = _call_name(node)
    if name in _BLOCKING_IO_BARE_NAMES:
        return True
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        qualified = (func.value.id, func.attr)
        return qualified in _SUBPROCESS_QUALIFIED or qualified in _REQUESTS_QUALIFIED
    return False


def _is_thread_lock(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return (func.value.id, func.attr) in _THREAD_LOCK_QUALIFIED
    return False


def _calls_offload(node: ast.AST) -> bool:
    return isinstance(node, ast.Call) and _call_name(node) in _OFFLOAD_NAMES


def _scan_async_function(fn: ast.AsyncFunctionDef) -> tuple[bool, bool, bool, bool]:
    """(reaches blocking I/O directly, reaches time.sleep directly, reaches threading.Lock/RLock
    directly, offloads somewhere) over THIS function's own body — a nested `def`/`async def`'s
    body belongs to that nested function, not this one, so it is walked separately (or, for a
    nested sync `def`, never flagged at all — see the module docstring)."""
    reaches_io = False
    reaches_sleep = False
    reaches_lock = False
    offloads = False
    for node in ast.walk(fn):
        if node is fn:
            continue
        # A nested function's body is a DIFFERENT scope — skip its subtree here; ast.walk over the
        # module still visits it independently as its own FunctionDef/AsyncFunctionDef.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_time_sleep(node):
            reaches_sleep = True
        elif _is_thread_lock(node):
            reaches_lock = True
        elif _is_blocking_io(node):
            reaches_io = True
        if _calls_offload(node):
            offloads = True
    return reaches_io, reaches_sleep, reaches_lock, offloads


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

    _EXCLUDED_DIRS = {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}
    files = sorted(
        p for p in SERVICES.rglob("*.py")
        if "/tests/" not in p.as_posix() and not p.name.startswith("test_")
        and not (_EXCLUDED_DIRS & set(p.parts)))
    if not files:
        print("no service .py files found — this gate needs re-pointing")
        return 1

    io_hits: list[str] = []
    sleep_hits: list[str] = []
    lock_hits: list[str] = []
    checked = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {f.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        # A CHEAP PRE-FILTER, NOT THE CHECK ITSELF — skip parsing a file that could not possibly
        # match any of the flagged names, without hand-rolling a second, looser matcher.
        if not any(name in text for name in
                  ("urlopen", "subprocess", "os.system", "requests", "threading", *_SLEEP_NAMES)):
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
            reaches_io, reaches_sleep, reaches_lock, offloads = _scan_async_function(fn)
            if reaches_io and not offloads:
                io_hits.append(f"{rel}:{fn.lineno}: async def {fn.name}() calls blocking "
                               f"network/process I/O directly, with no asyncio.to_thread/"
                               f"run_in_threadpool in the same function")
            if reaches_sleep:
                sleep_hits.append(f"{rel}:{fn.lineno}: async def {fn.name}() calls time.sleep() "
                                  f"— use `await asyncio.sleep(...)` instead, offloading does "
                                  f"not fix this one")
            if reaches_lock:
                lock_hits.append(f"{rel}:{fn.lineno}: async def {fn.name}() builds a "
                                 f"threading.Lock/RLock() — use `asyncio.Lock()` instead, "
                                 f"offloading does not fix this one")

    hits = io_hits + sleep_hits + lock_hits
    if hits:
        if io_hits:
            print(f"{len(io_hits)} async function(s) block the event loop on direct I/O:")
            for line in io_hits:
                print("  " + line)
            print("\nA blocking call inside `async def` freezes the WHOLE pod for its duration — "
                  "its own /healthz/readyz included, every other tenant's request on the same pod, "
                  "all of it — not just the slow call. Fix: move the blocking call into a plain "
                  "(non-async) helper method, then call that helper via "
                  "`await asyncio.to_thread(self._helper, ...)` from the async def — see "
                  "services/operations/app/adapters/renewal_provider.py or platform's "
                  "notification-service/app/core/notifier.py for the established pattern.")
        if sleep_hits:
            print(f"\n{len(sleep_hits)} async function(s) call time.sleep() instead of "
                  f"asyncio.sleep():")
            for line in sleep_hits:
                print("  " + line)
            print("\n`asyncio.to_thread(time.sleep, n)` does NOT fix this one — it just moves the "
                  "freeze to a thread-pool slot for the same duration, defeating the reason to "
                  "sleep inside a coroutine at all. The only fix is `await asyncio.sleep(...)`.")
        if lock_hits:
            print(f"\n{len(lock_hits)} async function(s) build a threading.Lock/RLock() instead "
                  f"of asyncio.Lock():")
            for line in lock_hits:
                print("  " + line)
            print("\n`.acquire()` on a threading.Lock blocks the acquiring THREAD, and this "
                  "codebase's event loop has exactly one thread running it — same freeze as "
                  "time.sleep(). The only fix is `asyncio.Lock()`.")
        return 1
    print(f"{checked} async function(s) reaching blocking I/O, time.sleep() or threading.Lock() "
          f"across services/: none block the event loop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
