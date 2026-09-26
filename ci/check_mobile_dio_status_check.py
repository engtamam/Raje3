#!/usr/bin/env python3
"""Every mobile service method that reads `apiClient.dio`'s response must check
`response.statusCode` itself before trusting the body — it cannot rely on `on DioException
catch` alone to detect a refusal.

WHY THIS EXISTS. `ApiClient` (api_client.dart) configures Dio with
`validateStatus: (status) => status != null && status < 500 && status != 401` — EVERY 4xx
except 401 (400, 402, 403, 404, 409, 422, ...) resolves as an ordinary response, not a thrown
DioException. A method that only branches on `on DioException catch (e)` for its error path,
and never reads `response.statusCode` in the success path, silently treats a real server refusal
as success. This is not a hypothetical: it broke `MutualBenefitService.propose()` (returned
"status: null" and no error surfaced) and `_act()` (accept/reject/cancel would have returned
`true` on a 403/409 refusal) — both live bugs, found and fixed 2026-09-23, both in a method
shaped exactly like the ones this gate flags. `AuthService._call()` already carries the correct
pattern (its own doc comment explains it) — this gate is that same fix, enforced everywhere else.

WHY A HEURISTIC, not a type-checker: Dart's own analyzer cannot express "this catch clause is
insufficient" — the bug is a missing check, not a type error. This script looks for the specific
shape that produced the real bugs above: a method with a `try` block that (a) calls
`apiClient.dio.<verb>` and (b) has an `on DioException catch` clause, but (c) never mentions
`.statusCode` anywhere in the method body. `.statusCode` covers both `response.statusCode` (the
success-path check) and `e.response?.statusCode` (a status-aware catch) — either is an
acknowledgement that non-2xx needs handling; a method with neither has none.

WHY AN ALLOWLIST-BY-EXEMPTION, not a SCREENS allowlist like the l10n gate: this is a fresh
correctness gate, not a migration in progress — every current call site already needs to be
correct (or explicitly exempted with a reason), never "not yet migrated."

Usage:
    python ci/check_mobile_dio_status_check.py --all
    python ci/check_mobile_dio_status_check.py apps/mobile/lib/core/services/x.dart

Exits 1 and prints every offending method if any lacks a statusCode check; exits 0 (silent) if
clean.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TARGET_DIRS = [
    "apps/mobile/lib/core/services",
    "apps/mobile/lib/core/network",
]

# A one-line reason belongs next to the call itself when a method is a deliberate exception —
# e.g. a bare fire-and-forget where the caller genuinely does not act on refusal vs success
# differently. Mark it with `// dio-status-check: exempt — <why>` on the line before the method
# signature.
EXEMPT_MARKER = "dio-status-check: exempt"

METHOD_START = re.compile(r"^\s{2}(?:static\s+)?Future<[^>]*>\s+\w+\s*\(")
DIO_CALL = re.compile(r"await\s+(?:apiClient\.dio|_dio)\.\w+\s*[<(]")
DIO_CATCH = re.compile(r"on\s+DioException\s+catch")
STATUS_CODE = re.compile(r"\.statusCode")


def _iter_methods(lines: list[str]) -> list[tuple[int, int]]:
    """Return (start, end) line-index ranges (0-based, end exclusive) for each top-level method."""
    starts = [i for i, line in enumerate(lines) if METHOD_START.match(line)]
    ranges = []
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(lines)
        ranges.append((start, end))
    return ranges


def scan(path: Path) -> list[tuple[int, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    hits: list[tuple[int, str]] = []
    for start, end in _iter_methods(lines):
        body = lines[start:end]
        text = "\n".join(body)
        if not DIO_CALL.search(text):
            continue
        if not DIO_CATCH.search(text):
            # No DioException catch at all — errors propagate raw to the caller, which is its
            # own explicit choice, not this bug's silent-success shape.
            continue
        if STATUS_CODE.search(text):
            continue
        if start > 0 and EXEMPT_MARKER in lines[start - 1]:
            continue
        sig = body[0].strip()
        hits.append((start + 1, sig))
    return hits


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    if argv[0] == "--all":
        targets = []
        for d in TARGET_DIRS:
            targets.extend(sorted((ROOT / d).glob("*.dart")))
    else:
        targets = [ROOT / a for a in argv]
    failed = False
    for path in targets:
        hits = scan(path)
        if hits:
            failed = True
            print(f"✗ {path.relative_to(ROOT)}: {len(hits)} method(s) with no statusCode check")
            for lineno, sig in hits:
                print(f"    {lineno}: {sig}")
        else:
            print(f"✓ {path.relative_to(ROOT)}: clean")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
