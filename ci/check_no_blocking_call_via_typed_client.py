"""A blocking sync client, called through `self.<attr>.<method>(...)`, still freezes the event loop
— even when the attribute's declared TYPE, not its bare name, is the only thing that says so.

WHY THIS EXISTS. `ci/check_no_blocking_call_inside_async_def.py` already closes this for a bare
helper NAME shared between a file and its own caller — but it deliberately scopes that registry
PER FILE, after a real false-positive incident from doing it globally (see that gate's own
docstring: `get`/`post`/`call`/... collided across unrelated files). That leaves exactly one shape
unclosed: a small, deliberately-shared client class (`Http` — "the same tiny client as operations'
core/signup.py, kept identical on purpose rather than reinvented per service", per its own
docstring in both `affiliate-service/app/core/onboarding.py` and `operations/app/core/signup.py`)
whose one blocking method (`.call()`) is DEFINED in one file and CALLED, as `self._http.call(...)`,
from a completely different file in the same service — invisible to a per-file registry by
construction, and invisible to a global one because `call`/`post`/`get` are exactly the generic
names that produced the earlier false positive.

THE FIX: type-based, not name-based. `self._http = http` inside `__init__(self, *, http: Http,
...)` gives `_http` a DECLARED TYPE from the constructor's own annotation — a real signal a purely
name-based registry cannot use. Only a class actually PROVEN to reach blocking I/O directly in one
of its own plain (non-`async def`) methods is ever registered, so this stays exactly as narrow as
the sibling gate's own per-file registry, just resolved across files by TYPE instead of by name.

FOUND, TWICE, THE SAME WAY THE SIBLING GATE'S OWN DEFECTS WERE FOUND: a hand-run second QA pass
caught `affiliate-service`'s `TicketsClient` (`core/tickets.py`) calling `self._http.call(...)`
directly inside `async def support_kpis`/`list_tickets`/`get_ticket`/`reply`/`open_ticket`/
`escalate`/`grant_share` — seven call sites, all unoffloaded — plus `WafaService.performance_for`
fanning the SAME call out, sequentially, once per referral. `operations`'s WhatsApp
registration/health-sweep (`core/connect.py`) and its entire signup/login flow (`core/signup.py`)
share the identical `Http` class and the identical defect. `loyalty`'s `HttpPeers`/licence client
(`adapters/peers/__init__.py`, `core/licence.py`) do the same through their own small HTTP class.

WHAT THIS CHECKS. Per SERVICE (never across services — they share no Python package): every class
whose OWN plain (non-async) method directly reaches `urlopen`/`subprocess.*`/`os.system` is
registered as `(ClassName, method_name)`. Every `__init__` in the service is read for `self.X =
param` assignments where `param` carries a type annotation naming one of those classes — giving
`X` a known type. Every `async def` in the service is then checked for a direct
`self.X.method(...)` call matching that registered (type, method) pair, with no
`asyncio.to_thread`/`run_in_threadpool` anywhere in the same function.

WHAT THIS CANNOT SEE, said plainly: an attribute assigned from something OTHER than a directly
type-annotated constructor parameter (a container/registry lookup like
`request.app.state.container.token_verifier` — see the separate
`check_token_verify_is_offloaded.py` gate for that specific, already-named shape); and a blocking
method reached two or more attribute hops away (`self.a.b.call(...)`) — not observed anywhere in
this codebase's own style, which always holds a client directly as one attribute.

    python ci/check_no_blocking_call_via_typed_client.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
_EXCLUDED_DIRS = {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}

_OFFLOAD_NAMES = {"to_thread", "run_in_threadpool"}
_BLOCKING_IO_BARE_NAMES = {"urlopen"}
_SUBPROCESS_QUALIFIED = {("subprocess", "run"), ("subprocess", "call"),
                        ("subprocess", "check_call"), ("subprocess", "check_output"),
                        ("os", "system")}


def _is_excluded(path: pathlib.Path) -> bool:
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def _call_name(node: ast.AST) -> str:
    if not isinstance(node, ast.Call):
        return ""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _is_blocking_io(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name) and func.id in _BLOCKING_IO_BARE_NAMES:
        return True
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if (func.value.id, func.attr) in _SUBPROCESS_QUALIFIED:
            return True
    # `urllib.request.urlopen(...)` — module-qualified two hops deep.
    if isinstance(func, ast.Attribute) and func.attr == "urlopen":
        return True
    return False


def _calls_offload(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else (
        func.id if isinstance(func, ast.Name) else "")
    return name in _OFFLOAD_NAMES


def _service_blocking_function_names(trees: dict) -> set[str]:
    """Every plain, TOP-LEVEL (module-scope, not a method) function name ANYWHERE in this
    SERVICE that reaches blocking I/O — directly, OR transitively through calling another
    module-level function already known to (a fixed-point closure, since the real chain found
    here is three calls deep: `Registration.register` -> `internal_http.post_json` ->
    `internal_http.read` -> `internal_http.send` -> `urlopen`, each a plain function calling the
    next by bare name). Registered by bare name and consulted only within this SAME service —
    the module docstring's own reasoning on why a purely global registry produced false
    positives elsewhere applies here too."""
    all_funcs: dict[str, ast.FunctionDef] = {}
    for tree in trees.values():
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                all_funcs[node.name] = node

    blocking = {name for name, fn in all_funcs.items() if _reaches_blocking_io_directly(fn)}
    changed = True
    while changed:
        changed = False
        for name, fn in all_funcs.items():
            if name in blocking:
                continue
            for node in ast.walk(fn):
                if node is fn or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if _call_name(node) in blocking:
                    blocking.add(name)
                    changed = True
                    break
    return blocking


def _reaches_blocking_io_directly(fn: ast.FunctionDef) -> bool:
    for node in ast.walk(fn):
        if node is fn or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_blocking_io(node):
            return True
    return False


def _sync_method_reaches_blocking_io(fn: ast.FunctionDef, known_helpers: set[str]) -> bool:
    """Blocking, directly OR one call away — `Http.call()` in more than one service does not
    `urlopen` itself, it calls a module-level `internal_http.send()`/`.request()` that does (the
    identical "one function away" shape `check_no_blocking_call_inside_async_def.py`'s own
    section 3 already handles for async callers; this is the same idea for the SYNC method being
    registered as blocking in the first place)."""
    if _reaches_blocking_io_directly(fn):
        return True
    for node in ast.walk(fn):
        if node is fn or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        name = _call_name(node)
        if name in known_helpers:
            return True
    return False


def _annotation_name(annotation: ast.AST | None) -> str:
    if annotation is None:
        return ""
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Attribute):
        return annotation.attr
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return annotation.value  # a quoted forward-reference annotation
    return ""


def _param_types(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str]:
    """param name -> annotated type name, for every kind of argument `__init__` might declare."""
    out: dict[str, str] = {}
    args = fn.args
    for a in (*args.posonlyargs, *args.args, *args.kwonlyargs):
        t = _annotation_name(a.annotation)
        if t:
            out[a.arg] = t
    return out


def _attr_type_map(cls: ast.ClassDef) -> dict[str, str]:
    """attribute name -> declared type, resolved from every `self.X = param` assignment inside
    THIS class's own `__init__`, where `param` is one of `__init__`'s own type-annotated
    arguments."""
    init = next((m for m in cls.body
                if isinstance(m, ast.FunctionDef) and m.name == "__init__"), None)
    if init is None:
        return {}
    ptypes = _param_types(init)
    attrs: dict[str, str] = {}
    for node in ast.walk(init):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name)
                and target.value.id == "self"):
            continue
        value = node.value
        if isinstance(value, ast.Name) and value.id in ptypes:
            attrs[target.attr] = ptypes[value.id]
    return attrs


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    violations: list[str] = []
    services_checked = 0

    for svc_dir in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        app_dir = svc_dir / "app"
        if not app_dir.is_dir():
            continue
        services_checked += 1

        files = sorted(
            f for f in app_dir.rglob("*.py")
            if not _is_excluded(f) and "test" not in f.parts and not f.name.startswith("test_")
        )
        trees: dict[pathlib.Path, ast.Module] = {}
        for f in files:
            try:
                trees[f] = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
            except (SyntaxError, UnicodeDecodeError):
                continue

        # PASS 0 — every module-level sync function in this SERVICE reaching blocking I/O,
        # directly or transitively (e.g. `adapters/internal_http.py::send()`), consulted only
        # within this same service, never merged across services.
        known_helpers = _service_blocking_function_names(trees)

        # PASS 1 — every class in this SERVICE reaching blocking I/O, directly or one call away
        # through a PASS-0 helper, in a plain method.
        blocking_registry: dict[str, set[str]] = {}   # ClassName -> {method names}
        for tree in trees.values():
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for m in node.body:
                    if (isinstance(m, ast.FunctionDef)
                            and _sync_method_reaches_blocking_io(m, known_helpers)):
                        blocking_registry.setdefault(node.name, set()).add(m.name)

        if not blocking_registry:
            continue

        # PASS 2 — every class's own attribute -> declared-type map, then every async method
        # checked against ITS OWN class's map (an attribute typed in one class never leaks into
        # an unrelated class that happens to share an attribute name).
        for f, tree in trees.items():
            for cls in ast.walk(tree):
                if not isinstance(cls, ast.ClassDef):
                    continue
                attr_types = _attr_type_map(cls)
                if not attr_types:
                    continue
                for fn in cls.body:
                    if not isinstance(fn, ast.AsyncFunctionDef):
                        continue
                    offloaded = any(_calls_offload(n) for n in ast.walk(fn))
                    if offloaded:
                        continue
                    for node in ast.walk(fn):
                        if node is fn or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            continue
                        if not isinstance(node, ast.Call):
                            continue
                        func = node.func
                        if not (isinstance(func, ast.Attribute)
                                and isinstance(func.value, ast.Attribute)
                                and isinstance(func.value.value, ast.Name)
                                and func.value.value.id == "self"):
                            continue
                        attr = func.value.attr
                        method = func.attr
                        cls_name = attr_types.get(attr)
                        if cls_name and method in blocking_registry.get(cls_name, set()):
                            violations.append(
                                f"{f.relative_to(ROOT)}:{node.lineno}: `async def {fn.name}` "
                                f"calls `self.{attr}.{method}(...)` directly — `self.{attr}` is "
                                f"declared as `{cls_name}`, whose own `{method}()` reaches "
                                f"blocking I/O directly, with no asyncio.to_thread/"
                                f"run_in_threadpool anywhere in this function")

    if violations:
        print(f"  ✘ {len(violations)} unoffloaded call(s) through a typed blocking client "
              f"(across {services_checked} services):")
        for v in sorted(set(violations)):
            print(f"      {v}")
        return 1

    print(f"  ✔ every typed client attribute known to reach blocking I/O is called only through "
          f"an offload, across {services_checked} services")
    return 0


if __name__ == "__main__":
    sys.exit(main())
