#!/usr/bin/env python3
"""The mobile app's own half of the branch-scope project — the same enforcement
`ci/check_branch_scope.py` already gives the backend, for `apps/mobile`.

WHY THIS EXISTS. `services/operations/app/core/branch_domains.py` (and its console mirror,
`apps/console/src/branch-domains.ts`) name which domains are branch-scoped at all. The backend
gate proves every route serving one of them actually calls `branch_scope()`. Nothing proved the
same thing for the mobile client until this file — and the mobile side had exactly the gap the
backend gate exists to catch: `customers_service.dart`'s own `recent()` had a `branchId` parameter
nobody ever passed, for weeks, silently combining every branch's customers into one list on a
screen that already had a branch switcher sitting right above it.

WHAT IT CHECKS, for each mobile-side branch-scoped domain named in `DOMAIN_MOBILE_SERVICES` below:

  1. THE SERVICE METHOD ITSELF still declares a real `branchId` parameter — so a future refactor
     that quietly drops it (not just a caller that forgets to pass one) is caught too.
  2. EVERY REAL CALL SITE passes `branchId:` — never a docstring/comment mention, a real
     `branchId:` argument inside that call's own balanced parentheses. A call site may opt out
     with an inline `// branch-scope-exempt: <reason>` comment on the line before it — the same
     "a list whose entries nobody can justify grows until the check means nothing" discipline
     `ci/check_branch_scope.py`'s own `NOT_A_BRANCH_READ` holds to, just spelled as a comment
     instead of a dict, since a mobile call site moves around far more than a backend route does.

TWO SCOPING MODES, because one generic rule cannot survive this codebase's own real shape:

  · "file"     — every relevant screen constructs its ONE service type once (`late final
                 XxxService _service`) and calls it from several methods across the class. A
                 single check across the whole file is correct and sufficient.
  · "function" — `action_executor.dart` is the one file where this breaks: it is a flat list of
                 `static` handlers, each constructing WHICHEVER service type it happens to need
                 into a local variable always named `service`. Several unrelated service classes
                 (`MobileRequestsService`, `RatingsService`, ...) share a method named `list()`,
                 so a file-wide check would misread `MobileRequestsService.list()` — which the
                 backend already scopes from the caller's own token, no client param exists at
                 all — as an unscoped `RatingsService.list()` call. Scoping to the SAME `static`
                 handler block, split on this file's own real, flat structure, resolves it without
                 needing a full Dart type checker.

WHAT IT CANNOT SEE, said plainly: a call site whose service instance was constructed under a
different variable name than what this file's own regex expects (`_service`/`service`), or a
"function"-mode file whose real structure is not a flat sequence of `static` methods. Neither
happens today; if one ever does, this file's own docstring is where to widen it — never widen the
check by loosening what "branchId:" itself means.

Usage:
    python ci/check_mobile_branch_scope.py

Exits 1 and prints every unscoped call/definition if any is found; exits 0 (silent-ish) otherwise.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE_LIB = ROOT / "apps" / "mobile" / "lib"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

EXEMPT_COMMENT = re.compile(r"//\s*branch-scope-exempt:")


@dataclass(frozen=True)
class MobileDomainService:
    domain_id: str
    service_class: str
    #: Path to the service's own definition file, relative to apps/mobile/lib.
    def_file: str
    methods: tuple[str, ...]
    #: Files (relative to apps/mobile/lib) allowed to call these methods, each with its own
    #: scoping mode — see the module docstring for what "file" vs "function" means.
    callers: tuple[tuple[str, str], ...]


# ── the mobile-side half of branch_domains.py's plain (derived_from is None) domains that this
# app actually implements today. mobile_requests (derived_from="assigned_operator_branch") is
# deliberately absent — the backend derives its scope from the caller's own token, and no
# branchId parameter exists on MobileRequestsService at all to check for.
DOMAIN_MOBILE_SERVICES: tuple[MobileDomainService, ...] = (
    MobileDomainService(
        domain_id="customers",
        service_class="CustomersService",
        def_file="core/services/customers_service.dart",
        methods=("recent", "suggest", "byRefs"),
        callers=(
            ("features/customers/customers_screen.dart", "file"),
            ("features/customers/customer_detail_screen.dart", "file"),
            ("core/actions/action_executor.dart", "function"),
        ),
    ),
    MobileDomainService(
        domain_id="rating",
        service_class="RatingsService",
        def_file="core/services/ratings_service.dart",
        methods=("list", "staffPerformance", "exportStaffPerformance"),
        callers=(
            ("features/rating/rating_screen.dart", "file"),
            ("core/actions/action_executor.dart", "function"),
        ),
    ),
)


def _balanced_call_args(text: str, open_paren_idx: int) -> str:
    """The text between one `(` (at `open_paren_idx`) and its own matching `)` — never a naive
    "up to the next )", which would truncate on the first nested call's own closing paren."""
    depth = 0
    for i in range(open_paren_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren_idx:i + 1]
    return text[open_paren_idx:]


def _method_declares_branch_param(def_text: str, method: str) -> bool:
    """Whether `method`'s own DEFINITION (not a call site) in `def_text` declares a `branchId`
    parameter — catches a future refactor that quietly drops the parameter itself, not only a
    caller that forgets to pass one."""
    for m in re.finditer(rf"\b{re.escape(method)}\s*\(", def_text):
        args = _balanced_call_args(def_text, m.end() - 1)
        if "branchId" in args:
            return True
    return False


def _call_sites(text: str, method: str) -> list[tuple[int, str]]:
    """Every real call site of `.method(` — never the definition itself, which has no leading
    dot — as (line number, this call's own balanced argument text)."""
    out = []
    for m in re.finditer(rf"\.{re.escape(method)}\s*\(", text):
        args = _balanced_call_args(text, m.end() - 1)
        line_no = text.count("\n", 0, m.start()) + 1
        out.append((line_no, args))
    return out


def _line_is_exempt(text: str, line_no: int) -> bool:
    """A `// branch-scope-exempt: <reason>` comment on this call's own line or the line right
    before it — the caller's own, reasoned opt-out, same discipline
    `ci/check_branch_scope.py`'s own `NOT_A_BRANCH_READ` dict holds to."""
    lines = text.splitlines()
    # `line_no` is 1-indexed; `lines[line_no - 2]` is the line directly ABOVE it (1-indexed
    # line_no - 1), `lines[line_no - 3]`/`lines[line_no - 4]` two/three lines above — a comment
    # explaining the exemption is often two lines long, so this window covers both.
    for idx in (line_no - 2, line_no - 3, line_no - 4):
        if 0 <= idx < len(lines) and EXEMPT_COMMENT.search(lines[idx]):
            return True
    return False


def _function_blocks(text: str) -> list[str]:
    """Split a flat `static Future<...> _name(...) async { ... }` file (action_executor.dart's
    own real shape) into one block per handler — see the module docstring's own "function" mode
    for why this file specifically cannot be checked file-wide."""
    parts = re.split(r"\n(?=  static (?:Future|Map|void))", text)
    return parts


def main() -> int:
    unscoped: list[str] = []
    undeclared: list[str] = []
    exempted = 0
    checked = 0

    for domain in DOMAIN_MOBILE_SERVICES:
        def_path = MOBILE_LIB / domain.def_file
        if not def_path.exists():
            # Not built on mobile yet at all — nothing to check, never a failure (the same
            # "an unlisted screen is not yet expected to be clean" posture
            # check_mobile_screen_localized.py's own docstring already holds to).
            continue
        def_text = def_path.read_text(encoding="utf-8")
        for method in domain.methods:
            if not _method_declares_branch_param(def_text, method):
                undeclared.append(
                    f"{domain.def_file}: {domain.service_class}.{method}() no longer declares a "
                    f"branchId parameter — `{domain.domain_id}` is branch-scoped per "
                    f"branch_domains.py, this method needs one back")

        for caller_rel, mode in domain.callers:
            caller_path = MOBILE_LIB / caller_rel
            if not caller_path.exists():
                continue
            caller_text = caller_path.read_text(encoding="utf-8")
            if domain.service_class not in caller_text:
                continue  # this file doesn't touch this service at all

            if mode == "file":
                blocks = [caller_text]
            else:
                blocks = [b for b in _function_blocks(caller_text) if domain.service_class in b]

            for block in blocks:
                offset = caller_text.index(block) if mode == "function" else 0
                for method in domain.methods:
                    for rel_line, args in _call_sites(block, method):
                        line_no = rel_line + (caller_text.count("\n", 0, offset) if mode == "function" else 0)
                        checked += 1
                        if "branchId:" in args:
                            continue
                        if _line_is_exempt(caller_text, line_no):
                            exempted += 1
                            continue
                        unscoped.append(
                            f"{caller_rel}:{line_no} calls {domain.service_class}.{method}() "
                            f"without branchId: (`{domain.domain_id}` is branch-scoped) — pass "
                            f"BranchProvider's own selectedId, or mark the call "
                            f"`// branch-scope-exempt: <reason>` if it genuinely should not "
                            f"narrow by branch")

    if undeclared:
        print(f"{C_R}  ✘ {len(undeclared)} branch-scoped service method(s) with no branchId "
              f"parameter:{C_N}")
        for line in undeclared:
            print(f"{C_R}      {line}{C_N}")
    if unscoped:
        print(f"{C_R}  ✘ {len(unscoped)} call site(s) reading branch-scoped data without "
              f"passing the selected branch:{C_N}")
        for line in unscoped:
            print(f"{C_R}      {line}{C_N}")

    if undeclared or unscoped:
        return 1

    print(f"{C_G}  ✔ every mobile call site reading branch-scoped data passes the selected "
          f"branch ({checked} call site(s) checked, {exempted} reasoned exemption(s)){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
