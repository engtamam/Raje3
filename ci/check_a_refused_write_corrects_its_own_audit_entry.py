"""A privileged write audited BEFORE it is validated must correct that entry on refusal.

WHY THIS EXISTS. This codebase's own convention, applied deliberately across every operator/admin
route that changes a credential or a policy value: the audit record is written BEFORE the mutating
call, never after — because the mutation itself can make the PREVIOUS value unrecoverable (a secret
is overwritten, a config value is replaced), so an unrecorded change is unprovable the moment it
happens. See `operator.py`'s own module docstrings throughout services/: "EVERY MUTATION IS
AUDITED WRITE-AHEAD AND CRITICAL... an unprovable one is indistinguishable from an attacker's."

THE GAP THAT CREATES. Write-ahead is right for the case that succeeds. It is wrong, silently, for
the case that is REFUSED: a bad key name, an out-of-range value, a business-rule violation the
`try`/`except` around the mutating call catches and turns into a clean 400 for the caller. The
audit log still shows the write-ahead entry claiming the action happened — nothing ever corrects
it. An investigator reading that log later sees a credential rotation, a config change, an
employment decision that, in fact, never took effect.

FOUND AND FIXED, REPEATEDLY, BY HAND. `error-collector`, `affiliate-service` and `secrets-admin`
each independently grew the identical fix during this codebase's QA sweep: a small
`_audit_refused(...)` helper (or an inline second `.record(...)` call) in the `except` branch,
writing a SECOND, corrective entry for the same action/resource with `metadata={"outcome":
"refused", "reason": ...}` — append-only, never editing the first entry. A second, independent
audit pass then found the identical unfixed gap still sitting in `campaigns`, `portal`, `reminders`
and `affiliate-service`'s own `admin_employment.py` (a route the FIRST pass's own fix to its sibling
admin routes simply never reached) — proof this is exactly the failure mode a hand-run, per-file
review cannot guarantee against and a mechanical gate can.

WHAT THIS CHECKS. For every function in `services/*/app/**/*.py` (tests excluded): find a `try`
block whose body's own top-level statement is a call ending in `.record(` written EARLIER in the
same function, OUTSIDE any try/except, followed later by a DIFFERENT `try` block wrapping the
actual mutating call. If that `try`'s own `except` handler(s) contain no call to `.record(` and no
call to any name this file's own functions register as "itself calls `.record(` somewhere in its
body" (the `_audit_refused`-style indirection every fixed instance already uses), it is flagged.

WHAT THIS CANNOT SEE, said plainly: a corrective entry written by calling into a DIFFERENT file's
helper (this gate's registry is per-file, matching the actual convention observed everywhere so
far — every fix so far defines `_audit_refused` in the SAME file as its call sites) — and a
refusal shape that does not use `try`/`except` at all (an early `if not ok: return ...` guard with
no exception involved carries nothing this gate can distinguish from an ordinary early return, so
it is out of scope; every instance found so far raises/catches a domain error).

    python ci/check_a_refused_write_corrects_its_own_audit_entry.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"

#: Demonstrated, evidence-backed exclusions — never a guess, added only after reading the actual
#: code and confirming the flagged `try` is NOT a refused mutation. Keyed by (relative path, the
#: `try`'s own line number). Same convention as `check_no_blocking_call_inside_async_def.py`'s own
#: `_TOO_GENERIC_FOR_HELPER_REGISTRY`: a specific, checked exception, not a broadened rule.
_KNOWN_NOT_A_REFUSAL_GAP: set[tuple[str, int]] = {
    # `dispute_report`'s audit call fires AFTER `run_scenario(...)` already succeeded — the report
    # data genuinely exists by that point. The try flagged here only wraps the OPTIONAL PDF
    # conversion step; a PdfConversionUnavailable there means one output FORMAT isn't available,
    # not that the report was never generated — the docx path already returned successfully for
    # that format. Auditing "dispute_report.generated" stays true regardless of this try's outcome.
    ("services/insights/app/api/v1/insights.py", 574): "PDF conversion is optional post-processing, not the audited action",
}
_EXCLUDED_DIRS = {".venv", "venv", "site-packages", "__pycache__", "node_modules", ".git"}


def _is_excluded(path: pathlib.Path) -> bool:
    return any(part in _EXCLUDED_DIRS for part in path.parts)


def _is_record_call(node: ast.AST) -> bool:
    """A call to `<receiver>.record(...)` whose receiver's OWN source mentions "audit" —
    `request.app.state.auditor.record(...)`, `self._auditor.record(...)`, a bare `auditor.record(
    ...)` parameter — never a same-named method on an unrelated domain object. `.record(` alone
    is not distinctive: this codebase also has `self._notices.record(...)`, `self._reach.record(
    ...)` and `c.visits.record(...)`, none of them an audit sink, and treating every `.record(`
    as the audit call produced false positives on all three the first time this gate ran."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "record"):
        return False
    try:
        receiver_src = ast.unparse(node.func.value)
    except Exception:                                                        # noqa: BLE001
        return False
    return "audit" in receiver_src.lower()


def _calls_record_anywhere(node: ast.AST) -> bool:
    for n in ast.walk(node):
        if _is_record_call(n):
            return True
    return False


def _file_record_helper_names(tree: ast.Module) -> set[str]:
    """Every function/method NAME in this file whose own body calls `.record(` somewhere —
    the `_audit_refused`-style indirection every fixed instance uses. A call to one of these
    names inside an except handler counts as a corrective entry, exactly like a bare
    `.record(...)` call would."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _calls_record_anywhere(node):
            names.add(node.name)
    return names


def _call_name(node: ast.AST) -> str:
    if not isinstance(node, ast.Call):
        return ""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _handler_has_correction(handler: ast.ExceptHandler, helper_names: set[str]) -> bool:
    for node in ast.walk(handler):
        if _is_record_call(node):
            return True
        if _call_name(node) in helper_names:
            return True
    return False


#: Node types whose `body`/`orelse`/`finalbody` attribute is genuinely a LIST OF STATEMENTS —
#: excludes `Lambda`/`IfExp`, whose same-named `body` attribute is a single EXPRESSION, not a
#: list, and would crash `list.index()`/`in` below.
_BLOCK_TYPES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
               ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith,
               ast.Try, ast.ExceptHandler)


def _statement_lists(node: ast.AST):
    """Every statement LIST this node directly owns (`body`, `orelse`, `finally`, handler bodies)
    — each yielded separately, never flattened together. A multi-branch dispatcher's sibling `if
    tool == "x": ...` / `if tool == "y": ...` blocks are two DIFFERENT statement lists; an audit
    call in one must never count as "preceding" a try that lives in the other, even though it
    sits at an earlier line number in the file."""
    if not isinstance(node, _BLOCK_TYPES):
        return
    for field in ("body", "orelse", "finalbody"):
        stmts = getattr(node, field, None)
        if stmts:
            yield stmts


def _find_try_parent_list(fn: ast.AST, target: ast.Try) -> list | None:
    """The exact statement list `target` is a direct member of, searched from `fn` downward. This
    walks EVERY nested block's own statement lists (so a try inside an `if`/`for`/`with`/another
    `try` is still found), but returns the one list that is `target`'s immediate, literal
    container — never a flattened, order-losing view of the whole function."""
    for node in ast.walk(fn):
        for stmts in _statement_lists(node):
            if target in stmts:
                return stmts
    return None


def _stmt_is_direct_record(stmt: ast.stmt) -> bool:
    """Is `stmt` ITSELF (not something nested inside a conditional/try/for sibling) a bare
    `await X.record(...)` / `X.record(...)` expression statement? Every confirmed real instance
    (operator.py's set_config, secrets.py's set_secret, admin_employment.py's decide, ...) writes
    the write-ahead audit call as exactly this shape — a plain top-level statement, never buried
    inside an `if`/`try` of its own. Restricting to this exact shape is what tells apart a real
    write-ahead record from an unrelated, best-effort audit call sitting inside a PRECEDING
    sibling's own conditional block (a `try/except: pass` telemetry note for a different action
    entirely) — a real false positive this gate produced once (whatsapp-assistant's own
    `_reserve_llm_hold`, whose preceding sibling conditionally records "unpriced_model_used"
    inside its own swallowed try, unrelated to the wallet reserve that follows)."""
    if not isinstance(stmt, ast.Expr):
        return False
    value = stmt.value
    if isinstance(value, ast.Await):
        value = value.value
    return _is_record_call(value)


def _preceding_record_call(fn: ast.AST, try_node: ast.Try) -> bool:
    """Is there a bare `.record(` statement TEXTUALLY BEFORE `try_node`, in the SAME statement
    list `try_node` itself sits in (never a sibling branch's own block, even one that appears
    earlier in the file) — the write-ahead shape this gate cares about is always "the record call
    and the try are adjacent statements in the same suite", exactly how every confirmed real
    instance (operator.py's set_config, secrets.py's set_secret, ...) is written. A dispatcher
    function with several independent `if tool == "...":` branches, each opening with its OWN
    audit call before its OWN try, is correctly treated as unrelated blocks: an earlier branch's
    record call never leaks into a later, sibling branch's own try — and a record call buried
    inside some OTHER preceding sibling's own conditional/try never counts either, only a bare
    top-level one directly in this same list."""
    parent_list = _find_try_parent_list(fn, try_node)
    if parent_list is None:
        return False
    try_index = parent_list.index(try_node)
    return any(_stmt_is_direct_record(stmt) for stmt in parent_list[:try_index])


def main() -> int:
    if not SERVICES.is_dir():
        print("no services/ directory — this gate cannot answer, so it refuses to")
        return 1

    files = sorted(
        f for f in SERVICES.rglob("*.py")
        if not _is_excluded(f) and "test" not in f.parts and not f.name.startswith("test_")
    )

    violations: list[str] = []
    tries_checked = 0

    for f in files:
        try:
            src = f.read_text(encoding="utf-8")
            tree = ast.parse(src, filename=str(f))
        except (SyntaxError, UnicodeDecodeError):
            continue

        helper_names = _file_record_helper_names(tree)

        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            # This function's own top-level (function-body-scoped) Try nodes, in source order —
            # `ast.walk` is breadth-first-ish but stable enough for "in this function" purposes;
            # exact ordering across nested scopes doesn't matter since we compare line numbers.
            own_tries = [n for n in ast.walk(fn) if isinstance(n, ast.Try)]
            if not own_tries:
                continue

            for try_node in own_tries:
                tries_checked += 1
                if (str(f.relative_to(ROOT)).replace("\\", "/"), try_node.lineno) \
                        in _KNOWN_NOT_A_REFUSAL_GAP:
                    continue
                # A try whose OWN body writes the audit entry (catching AuditUnavailable after a
                # mutation that ALREADY succeeded) is a completely different, already-correct
                # pattern — there is nothing to "correct", the write happened; this only degrades
                # gracefully if the audit sink itself is down. See whatsapp-assistant's own
                # tools.py::_execute_confirmed_proposal for the documented reasoning.
                body_has_record = any(_is_record_call(n) for stmt in try_node.body
                                      for n in ast.walk(stmt))
                if body_has_record:
                    continue
                if not _preceding_record_call(fn, try_node):
                    continue
                for handler in try_node.handlers:
                    if not _handler_has_correction(handler, helper_names):
                        violations.append(
                            f"{f.relative_to(ROOT)}:{try_node.lineno}: `{fn.name}` writes an "
                            f"audit `.record(...)` before this `try`, but its `except` at line "
                            f"{handler.lineno} never writes a corrective entry — a refusal here "
                            f"leaves the audit log claiming success")

    if violations:
        print(f"  ✘ {len(violations)} write-ahead audit entr(y/ies) with no correction on "
              f"refusal (of {tries_checked} try/except pairs checked):")
        for v in violations:
            print(f"      {v}")
        return 1

    print(f"  ✔ all write-ahead audit entries ({tries_checked} try/except pairs checked) are "
          f"corrected on refusal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
