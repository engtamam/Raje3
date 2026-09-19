"""An internal route or scheduled poller in whatsapp-assistant sends an outbound message or writes
real state for a tenant WITHOUT checking `container.licence` (or `self._licence`) first.

WHY THIS EXISTS. `core/licence.py::ToggleGatedLicence`'s own docstring is unambiguous: a toggled-off
or never-subscribed tenant must read EXACTLY like never-subscribed, on every path, not only the
one a human tester happened to click through. Three real instances of the same mistake were found
and fixed the same way, all reachable WITHOUT going through `conversation.py`'s own door gate
(`handle_inbound_text`'s `self._licence.allowed(tenant)`), which is the ONE check most of this
service's behaviour actually depends on:

  1. `app/api/internal.py::whatsapp_flow_booking` — the platform's Flow engine calling straight
     into the booking backend, bypassing conversation.py entirely.
  2. `app/core/inbound_ingest.py`'s `_gate_consent`, which used to run and send a real outbound
     consent request BEFORE `ingest_inbound_message`'s own licence check.
  3. `app/core/coexistence_poll.py::CoexistencePoller.run()`, which noted (wrote) an owner reply
     for every tenant in one global-cursor feed with no per-tenant licence check at all.

Each of these is an entrypoint that does NOT go through conversation.py's own gate, so nothing else
in the codebase was going to catch a fourth one by construction. This gate is that machine check.

WHAT IT DOES. For every candidate function below, look for `licence.allowed(` or `licence is None`
in the function's own source, OR — because a route is allowed to delegate to a helper that does the
actual checking (see `whatsapp_assistant/tick` → `_tick_one_tenant` → the conversation engine) — in
the source of anything it calls directly, resolved one hop: a same-file function/method by name, or
a function imported with `from app.core.X import name` and called as `name(...)`. This deliberately
does NOT do full call-graph analysis; a helper more than one hop away must be verified by a human
and either inlined into the one-hop check or added to `ALLOWLIST` below with a reason.

CANDIDATES:
  - every `@router.<verb>(...)`-decorated `async def` in `app/api/internal.py`;
  - every `run`/`tick` method of a class whose name ends in `Poller`, anywhere under `app/core/`.

EXEMPTIONS ARE NEVER SILENT. A route that is genuinely fine without a licence check (a pure read, a
health check, an erasure/purge route that must work even when toggled off, a billing/renewal notice
about the subscription itself) is named in `ALLOWLIST` below with a non-empty `reason` — never by a
bare substring match, a broad path exclusion, or an inline `# noqa`-style comment nobody has to
justify.

    python ci/check_a_tenant_effecting_entrypoint_skips_the_licence_gate.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICE = ROOT / "services" / "whatsapp-assistant"
INTERNAL_PY = SERVICE / "app" / "api" / "internal.py"
CORE_DIR = SERVICE / "app" / "core"

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

_VERBS = {"get", "post", "put", "patch", "delete"}
_MARKERS = ("licence.allowed(", "licence is None", "licence is not None")

# Every entry here is a route or poller this gate would otherwise flag, kept out of CI red by a
# reviewed, written-down reason — never by weakening the heuristic itself.
#
#   key: "relative/path.py:function_or_ClassName.method"
ALLOWLIST: dict[str, str] = {
    "app/api/internal.py:internal_health": "pure health check, no tenant, no effect",
    "app/api/internal.py:manifest": "pure read of this deployment's own manifest",
    "app/api/internal.py:carousel_shown": (
        "records that campaigns' own Dispatcher already sent the carousel and decided the button "
        "was allowed at all — this write is bookkeeping so a later tap resolves, never itself an "
        "outbound message or a decision the AI toggle governs"
    ),
    "app/api/internal.py:tick": (
        "delegates to _tick_one_tenant -> ConversationEngine.compose_reply, which makes the same "
        "self._licence.allowed(tenant) check conversation.py's own door gate makes (see "
        "core/conversation.py ~line 1474) — more than one hop away, verified by hand"
    ),
    "app/api/internal.py:upcoming_renewal_trigger": (
        "a renewal/billing notice about the subscription itself, not gated by whether the AI "
        "toggle is on — same category as other billing reminders across the platform"
    ),
    "app/api/internal.py:erase_subject": (
        "a data-subject erasure/purge route must run regardless of subscription state, same as "
        "every other erasure route on this platform"
    ),
    "app/api/internal.py:backup_export": "internal backup export, not tenant-message-effecting",
    "app/api/internal.py:backup_verify": "internal backup verification, not tenant-message-effecting",
    "app/api/internal.py:backup_import": "internal backup restore, not tenant-message-effecting",
}


def _is_router_route_decorator(dec: ast.expr) -> bool:
    return (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute)
            and dec.func.attr in _VERBS and isinstance(dec.func.value, ast.Name)
            and dec.func.value.id == "router")


def _source(path: pathlib.Path, node: ast.AST) -> str:
    seg = ast.get_source_segment(path.read_text(encoding="utf-8"), node)
    return seg or ""


def _called_names(node: ast.AST) -> set[str]:
    names: set[str] = set()
    for n in ast.walk(node):
        if not isinstance(n, ast.Call):
            continue
        if isinstance(n.func, ast.Name):
            names.add(n.func.id)
        elif isinstance(n.func, ast.Attribute):
            names.add(n.func.attr)
    return names


def _module_functions(path: pathlib.Path, tree: ast.Module) -> dict[str, ast.AST]:
    out: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            out[node.name] = node
    return out


def _imported_from_app_core(tree: ast.Module) -> dict[str, str]:
    """name -> dotted module, for every `from app.core.X import name[, ...]`."""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("app.core"):
            for alias in node.names:
                out[alias.asname or alias.name] = node.module
    return out


def _module_path_for(dotted: str) -> pathlib.Path | None:
    # "app.core.inbound_ingest" -> services/whatsapp-assistant/app/core/inbound_ingest.py
    parts = dotted.split(".")
    return SERVICE.joinpath(*parts).with_suffix(".py")


def _one_hop_source(path: pathlib.Path, tree: ast.Module, node: ast.AST) -> str:
    """The candidate's own source is checked separately; this returns the source of everything it
    calls directly, one hop, same-file or a `from app.core.X import name` import."""
    same_file_funcs = _module_functions(path, tree)
    imported = _imported_from_app_core(tree)
    called = _called_names(node)
    chunks: list[str] = []
    for name in called:
        if name in same_file_funcs and same_file_funcs[name] is not node:
            chunks.append(_source(path, same_file_funcs[name]))
        elif name in imported:
            other_path = _module_path_for(imported[name])
            if other_path and other_path.exists():
                try:
                    other_tree = ast.parse(other_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, SyntaxError):
                    continue
                other_funcs = _module_functions(other_path, other_tree)
                if name in other_funcs:
                    chunks.append(_source(other_path, other_funcs[name]))
    return "\n".join(chunks)


def _has_licence_check(text: str) -> bool:
    return any(marker in text for marker in _MARKERS)


def _check_internal_routes() -> tuple[list[str], list[str], int]:
    ok, bad = [], []
    if not INTERNAL_PY.exists():
        print(f"cannot find {INTERNAL_PY.relative_to(ROOT).as_posix()} — this gate needs "
              "re-pointing")
        sys.exit(1)
    try:
        tree = ast.parse(INTERNAL_PY.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        print(f"cannot parse {INTERNAL_PY}: {exc}")
        sys.exit(1)

    checked = 0
    rel = INTERNAL_PY.relative_to(ROOT).as_posix()
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
            continue
        if not any(_is_router_route_decorator(d) for d in node.decorator_list):
            continue
        checked += 1
        key = f"app/api/internal.py:{node.name}"
        own = _source(INTERNAL_PY, node)
        hop = _one_hop_source(INTERNAL_PY, tree, node)
        if _has_licence_check(own) or _has_licence_check(hop):
            ok.append(key)
            continue
        if key in ALLOWLIST:
            ok.append(f"{key} (exempt: {ALLOWLIST[key]})")
            continue
        bad.append(f"{rel}:{node.lineno} {node.name}() — no licence check in the route itself "
                   "or in what it calls directly")
    return ok, bad, checked


def _check_pollers() -> tuple[list[str], list[str], int]:
    ok, bad = [], []
    checked = 0
    for path in sorted(CORE_DIR.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            print(f"cannot parse {path}: {exc}")
            sys.exit(1)
        rel = path.relative_to(ROOT).as_posix()
        for cls in ast.walk(tree):
            if not isinstance(cls, ast.ClassDef) or not cls.name.endswith("Poller"):
                continue
            for node in cls.body:
                if not isinstance(node, ast.AsyncFunctionDef | ast.FunctionDef):
                    continue
                if node.name not in ("run", "tick"):
                    continue
                checked += 1
                key = f"{rel}:{cls.name}.{node.name}"
                own = _source(path, node)
                hop = _one_hop_source(path, tree, node)
                if _has_licence_check(own) or _has_licence_check(hop):
                    ok.append(key)
                    continue
                if key in ALLOWLIST:
                    ok.append(f"{key} (exempt: {ALLOWLIST[key]})")
                    continue
                bad.append(f"{rel}:{node.lineno} {cls.name}.{node.name}() — no licence check in "
                           "the method itself or in what it calls directly")
    return ok, bad, checked


def main() -> int:
    route_ok, route_bad, route_checked = _check_internal_routes()
    poller_ok, poller_bad, poller_checked = _check_pollers()

    seen_keys = {k.split(" (exempt:")[0] for k in route_ok + poller_ok}
    for key, reason in ALLOWLIST.items():
        if not reason.strip():
            print(f"{C_R}ALLOWLIST entry {key!r} has an empty reason — every exemption must be "
                  f"written down{C_N}")
            return 1
        if key not in seen_keys:
            print(f"{C_Y}ALLOWLIST entry {key!r} no longer matches anything this gate scans — "
                  f"remove it{C_N}")
            return 1

    bad = route_bad + poller_bad
    if bad:
        print(f"{C_R}A tenant-effecting internal route or poller never checks the licence:{C_N}")
        for line in sorted(bad):
            print("  " + line)
        print("\nEither add the same `container.licence`/`self._licence` check every other "
              "customer-visible-effect path makes (see app/api/v1/connectors.py::_invoke or "
              "app/core/inbound_ingest.py::ingest_inbound_message), or — if this one is genuinely "
              "exempt — add it to ALLOWLIST in this script with a real reason.")
        return 1

    checked = route_checked + poller_checked
    exempt = sum(1 for k in route_ok + poller_ok if " (exempt:" in k)
    print(f"{C_G}{checked} tenant-effecting entrypoint(s) checked, {exempt} explicitly exempt, "
          f"none forgets the licence gate{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
