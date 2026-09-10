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

A THIRD SHAPE, FOUND TWICE MORE WHILE BUILDING THIS GATE'S OWN FIX — an `async def` that never
touches `urlopen` ITSELF, but calls a plain (non-async) helper that does, one function away
(`app/adapters/llm/assistant_service.py`'s `respond()` called `ensure_connection(...)` and
`self._connections.invoke(...)` un-awaited and un-offloaded; `core/flows.py`'s `provision()`/
`ensure_encryption()` called their own `self._post(...)`/`self._post_to(...)` the same way) — the
direct check above cannot see this: it only looks INSIDE the async function's own body, and
`ensure_connection`/`invoke`/`_post` live in a different function entirely. Section 3 below closes
this the only way an AST-only gate can: a repo-wide first pass names every plain `def` that
itself reaches a blocking call directly (the exact shape section 1 already detects, just for a
SYNC function instead of an async one), then a second pass flags any `async def` that CALLS one of
those names directly — `asyncio.to_thread(self._post, body)` references `self._post` bare, never
calling it, so it produces no matching Call node and is correctly never flagged; only
`self._post(body)` invoked directly is.

FOUR DEFECT SHAPES, DIFFERENT REMEDIES — kept as one gate because they are the same root cause (a
synchronous wait inside a coroutine, direct or one call away) with different correct fixes:

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

3. AN `async def` CALLING A KNOWN-BLOCKING SYNC HELPER DIRECTLY (see above) — fine only if that
   call itself is offloaded (`await asyncio.to_thread(self._post, body)`), same rule as section 1,
   just one call further away. The fix is identical: wrap the CALL SITE in `asyncio.to_thread`,
   never touch the helper (it is already correctly synchronous).

NAME-BASED, NOT TYPE-CHECKED, BUT SCOPED PER FILE — section 3's helper registry is keyed by the
plain function/method NAME only (`_post`, `invoke`, `ensure_connection`, ...), never its fully-
qualified origin (no real type checker is available to this gate), BUT each registry entry is
built and consulted ONE FILE AT A TIME, never merged across the whole services/ tree. That is the
fix for a real defect this section shipped with once: a GLOBAL registry treated any sync `_post`
anywhere in services/ as proof that every async function calling anything named `_post` was
calling a blocking one, which both false-positived on `direct.py`'s own already-offloaded async
`_post` (a same-named but unrelated, already-safe method elsewhere) AND, when a blocklist was
added to silence that, blinded the gate to REAL bugs sharing the `_post` name in other files
(`core/library.py`'s `register()`/`drain()`, `core/quota.py`'s `consume()`/`take()`/`release()`,
`core/submission.py`'s `submit()` — all found by manual audit only after the blocklist hid them
from this gate). Scoping the registry per file removes the cross-file collision that caused every
false positive seen so far, without hiding a single true positive: a name only counts as
"known-blocking" for an async function in the SAME FILE as the sync definition that earned it.
A same-file collision (two genuinely different things sharing both a name AND a file) remains
theoretically possible and has never been observed — if one ever is, exclude that ONE name from
`_TOO_GENERIC_FOR_HELPER_REGISTRY` below with the specific evidence, never widen it by guessing.

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
#: NAMES TO EXCLUDE FROM THE PER-FILE REGISTRY even so — empty today. Per-file scoping (see the
#: module docstring's "NAME-BASED, NOT TYPE-CHECKED, BUT SCOPED PER FILE" section) already removes
#: every collision actually observed (`get`/`_get`/`send`/`read`/`_send`/`_read`/`call`/`_call`/
#: `request`/`_request`/`post`/`_post` all turned out to be CROSS-FILE collisions, not same-file
#: ones, and per-file scoping resolves those by construction with no blocklist needed). Add a name
#: here only for a demonstrated SAME-FILE collision — two genuinely different functions, one
#: async-safe and one blocking, sharing both a name and a file — with the specific evidence in a
#: comment beside it; never pre-emptively, and never by guessing which names sound generic.
_TOO_GENERIC_FOR_HELPER_REGISTRY: set[str] = set()
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


def _service_and_module(f: pathlib.Path) -> tuple[str, str]:
    """(service name, dotted module path) for a file — e.g. `services/operations/app/adapters/
    internal_http.py` -> `("operations", "app.adapters.internal_http")`. The dotted path is exactly
    what an import statement inside that same service names (every service's own code imports as
    `app.foo.bar`, never a package-qualified path crossing service boundaries — services share no
    Python package). Keyed by service too, not just the dotted string, so two different services
    that both happen to have `app.adapters.internal_http` never merge into one shared registry
    entry — a name collision ACROSS services must stay as invisible to this gate as one across
    unrelated files within a service already is."""
    parts = f.relative_to(ROOT).parts   # ("services", "<svc>", "app", ...)
    svc = parts[1]
    app_idx = parts.index("app")
    tail = list(parts[app_idx:])
    tail[-1] = tail[-1][:-3] if tail[-1] != "__init__.py" else None  # strip ".py"
    if tail[-1] is None:
        tail = tail[:-1]
    return svc, ".".join(tail)


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    """local name -> dotted module path, for THIS file's own top-level imports — only the shape
    that matters here: `import app.foo.bar [as x]` and `from app.foo import bar [as x]`, both of
    which bind a name to a MODULE (never to a function/class pulled out of one — `from app.core.x
    import some_func` binds `some_func` to a NAME, not a module, and a later `some_func(...)` call
    is just a bare-name call already covered by section 3's ordinary same-file/cross-file-by-name
    matching path, not this one). Only imports reachable at module top level are tracked — an
    import inside a function body is rare in this codebase's own style and not worth the added
    branch-tracking to resolve correctly."""
    aliases: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                aliases[a.asname or a.name] = f"{node.module}.{a.name}"
    return aliases


def _walk_functions(tree: ast.Module):
    """Every FunctionDef/AsyncFunctionDef in the tree, at any nesting depth — a plain `ast.walk`
    already reaches nested ones; this just filters to the two node types once."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _sync_function_reaches_blocking_io(fn: ast.FunctionDef) -> bool:
    """Does this PLAIN (non-async) function's own body reach blocking network/process I/O
    directly? The section-1 check, applied to a sync function instead of an async one — this is
    what makes a name worth registering as a known-blocking helper for section 3."""
    for node in ast.walk(fn):
        if node is fn:
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_blocking_io(node):
            return True
    return False


def _calls_blocking_helper(fn: ast.AsyncFunctionDef, helper_names: set[str], *,
                           import_aliases: dict[str, str] | None = None,
                           names_by_module: dict[str, set[str]] | None = None) -> bool:
    """Does this async function's own body directly CALL (invoke, not merely reference) a name
    registered as a known-blocking sync helper? A bare reference passed to `asyncio.to_thread`/
    `run_in_threadpool` (`to_thread(self._post, body)`) never produces a matching Call node here —
    only `self._post(body)` invoked directly does — so this needs no offload-aware exclusion of
    its own; the existing `_calls_offload` check elsewhere already decides that question for
    section 1's own direct-urlopen case.

    TWO WAYS A NAME COUNTS. `helper_names` (this file's own registry) matches ANY call ending in
    that name — bare or `self.X(...)`/`obj.X(...)`, same as before. `import_aliases`/
    `names_by_module` additionally match a MODULE-QUALIFIED call (`internal_http.get_json(...)`)
    when the qualifying name resolves, via this file's own imports, to ANOTHER file whose registry
    has that name — the cross-file-imported-helper shape a purely same-file registry would miss
    (`core/quota.py`'s own `internal_http.get_json(...)`, found only by manual audit before this)."""
    for node in ast.walk(fn):
        if node is fn:
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node) in helper_names:
            return True
        if import_aliases and names_by_module:
            func = node.func
            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                module = import_aliases.get(func.value.id)
                if module and func.attr in names_by_module.get(module, set()):
                    return True
    return False


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    _EXCLUDED_DIRS = {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}
    files = sorted(
        p for p in SERVICES.rglob("*.py")
        # "app/" ONLY — matches this module's own stated SCOPE. A service's `ci/` folder (its own
        # local dev-tool scripts, e.g. `security_gate.py`) is not request-path code and was
        # drowning section 3's findings in noise the day it was added (a CI script's own helper
        # named `_run` registered as "blocking", then matched against unrelated `_run`-named
        # methods across every service).
        if "/app/" in p.as_posix() and "/tests/" not in p.as_posix() and not p.name.startswith("test_")
        and not (_EXCLUDED_DIRS & set(p.parts)))
    if not files:
        print("no service .py files found — this gate needs re-pointing")
        return 1

    # EVERY FILE IS PARSED — NO KEYWORD PRE-FILTER. There used to be one ("skip a file that could
    # not possibly match"), and it was wrong the moment section 3 grew a cross-file import
    # resolution: `core/quota.py` calls `internal_http.get_json(...)` and its own text never
    # mentions `urlopen`/`subprocess`/etc. at all — the blocking call lives in the IMPORTED
    # module's file, not this one's text. A prefilter keyed on this file's own text can never see
    # that. Parsed trees are cached (one parse per file, used by every pass below), never re-read
    # from disk twice — and parsing every file here costs well under two seconds on this repo's
    # size (~1300 files), not worth trading correctness for.
    trees: dict[pathlib.Path, ast.Module] = {}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {f.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        try:
            trees[f] = ast.parse(text, filename=str(f))
        except SyntaxError as exc:
            print(f"cannot parse {f.relative_to(ROOT).as_posix()}: {exc}")
            return 1

    # ── PASS 1 (section 3): name every plain `def` that reaches blocking I/O directly ───────────
    #
    # SCOPED PER FILE, NOT GLOBALLY — the fix for the false-positive class the blocklist below used
    # to paper over. `_call_name` matches by bare name only (no receiver-type resolution: `x.get()`
    # and `dict.get()` and `self.get()` all read as "get"), so a GLOBAL registry treated any sync
    # `_post` anywhere in the whole services/ tree as evidence that EVERY async function calling
    # ANYTHING named `_post` was calling a blocking one — which blinded the gate to real bugs
    # sharing that name with an unrelated, already-safe `_post` elsewhere (library.py's own
    # HttpLibrary.register()/drain() were missed this exact way once `_post` was blocklisted to
    # silence a DIFFERENT file's false positive). A per-file registry means a name only counts as
    # "known-blocking" for async functions IN THE SAME FILE as the sync definition that earned it
    # — cross-file collisions (the actual source of every false positive found so far) cannot occur
    # by construction, and no name needs blocklisting away to fix them.
    blocking_helper_names: dict[pathlib.Path, set[str]] = {}
    # ALSO KEYED BY (service, dotted module path) — the cross-file-IMPORT resolution this section
    # was missing: a sync helper CALLED THROUGH AN IMPORT (`internal_http.get_json(...)`, the
    # module never one this file itself defines) needs the CALLEE's own file's registry, reached
    # via the CALLER's own import statement, not the caller's file. `core/quota.py`'s own
    # `internal_http.get_json(...)` — found only by manual audit, never by this gate, until this —
    # is exactly the shape this closes. See `_calls_blocking_helper`'s own docstring.
    names_by_module: dict[str, set[str]] = {}
    for f, tree in trees.items():
        names: set[str] = set()
        for fn in _walk_functions(tree):
            if (isinstance(fn, ast.FunctionDef) and fn.name not in _TOO_GENERIC_FOR_HELPER_REGISTRY
                    and _sync_function_reaches_blocking_io(fn)):
                names.add(fn.name)
        if names:
            blocking_helper_names[f] = names
            svc, module = _service_and_module(f)
            names_by_module[f"{svc}::{module}"] = names

    # ── PASS 2: every async def, checked against both the direct (section 1/2) and the
    # indirect-via-a-named-helper (section 3) shapes ───────────────────────────────────────────
    io_hits: list[str] = []
    indirect_hits: list[str] = []
    sleep_hits: list[str] = []
    lock_hits: list[str] = []
    checked = 0
    for f, tree in trees.items():
        rel = f.relative_to(ROOT).as_posix()
        svc, _module = _service_and_module(f)
        import_aliases = _import_aliases(tree)
        # RESOLVED AGAINST THIS FILE'S OWN SERVICE ONLY — `import app.foo.bar` inside operations
        # can only ever mean operations' own `app/foo/bar.py`; prefixing every alias's dotted
        # target with `svc::` before it is looked up in `names_by_module` is what keeps two
        # services' same-named modules from being treated as the same file (see
        # `_service_and_module`'s own docstring).
        import_modules = {alias: f"{svc}::{dotted}" for alias, dotted in import_aliases.items()}
        for fn in _walk_functions(tree):
            if not isinstance(fn, ast.AsyncFunctionDef):
                continue
            checked += 1
            reaches_io, reaches_sleep, reaches_lock, offloads = _scan_async_function(fn)
            if reaches_io and not offloads:
                io_hits.append(f"{rel}:{fn.lineno}: async def {fn.name}() calls blocking "
                               f"network/process I/O directly, with no asyncio.to_thread/"
                               f"run_in_threadpool in the same function")
            elif not offloads and _calls_blocking_helper(
                    fn, blocking_helper_names.get(f, set()),
                    import_aliases=import_modules, names_by_module=names_by_module):
                # `elif` — a function already flagged above (direct + unoffloaded) is not also
                # double-reported here for calling a second, indirect helper.
                indirect_hits.append(
                    f"{rel}:{fn.lineno}: async def {fn.name}() calls a known-blocking sync "
                    f"helper directly, with no asyncio.to_thread/run_in_threadpool in the same "
                    f"function")
            if reaches_sleep:
                sleep_hits.append(f"{rel}:{fn.lineno}: async def {fn.name}() calls time.sleep() "
                                  f"— use `await asyncio.sleep(...)` instead, offloading does "
                                  f"not fix this one")
            if reaches_lock:
                lock_hits.append(f"{rel}:{fn.lineno}: async def {fn.name}() builds a "
                                 f"threading.Lock/RLock() — use `asyncio.Lock()` instead, "
                                 f"offloading does not fix this one")

    hits = io_hits + indirect_hits + sleep_hits + lock_hits
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
        if indirect_hits:
            print(f"\n{len(indirect_hits)} async function(s) call a known-blocking sync helper "
                  f"one function away, unoffloaded:")
            for line in indirect_hits:
                print("  " + line)
            print("\nThe helper itself is correctly synchronous — do not touch it. Wrap the CALL "
                  "SITE instead: `await asyncio.to_thread(self._helper_name, ...)` (or the module-"
                  "level function directly) — see services/whatsapp-assistant/app/adapters/llm/"
                  "assistant_service.py's own `respond()` for the exact fix already applied to "
                  "this shape once.")
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
