#!/usr/bin/env python3
# =============================================================================
# check_order_item_cap_invariant.py — the one cross-service number this feature cannot share by
# import (services in this fleet do not import each other's code — see
# ci/check_shared_features_match.py's own docstring for why that rule exists) gets a GATE instead,
# same remedy that file already established for a shared feature card's wording.
#
# THE INVARIANT, NOT EQUALITY. whatsapp-assistant's own `_MAX_ORDER_ITEMS` (core/conversation.py)
# is a circuit breaker against a pathological payload bloating `ConversationState`, deliberately
# looser than operations' own real business limit (`orders.py::MAX_DISTINCT_LINES`) — the two are
# NOT meant to be equal, so a byte-for-byte match check would be the wrong gate here. What must
# never happen is whatsapp-assistant's breaker becoming SMALLER than operations' real limit: that
# would make whatsapp-assistant refuse (its own generic "تعذّر قراءة الطلب" text) an ordinary cart
# operations would have happily accepted — a confusing, needless refusal nobody decided on. This
# gate fails the build the moment that ordering is violated, in either direction it could drift:
# someone raising operations' own limit without noticing whatsapp-assistant's breaker is now too
# tight, or someone shrinking whatsapp-assistant's constant without realising what it guards.
# =============================================================================
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

OPERATIONS_FILE = ROOT / "services/operations/app/core/orders.py"
OPERATIONS_CONST = "MAX_DISTINCT_LINES"

ASSISTANT_FILE = ROOT / "services/whatsapp-assistant/app/core/conversation.py"
ASSISTANT_CONST = "_MAX_ORDER_ITEMS"


def _find_int_constant(path: Path, name: str) -> int | None:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id != name:
            continue
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, int):
            return node.value.value
    return None


def main() -> int:
    operations_cap = _find_int_constant(OPERATIONS_FILE, OPERATIONS_CONST)
    assistant_cap = _find_int_constant(ASSISTANT_FILE, ASSISTANT_CONST)

    if operations_cap is None:
        print(f"  \033[31m✗ could not find `{OPERATIONS_CONST}` in {OPERATIONS_FILE}\033[0m")
        return 1
    if assistant_cap is None:
        print(f"  \033[31m✗ could not find `{ASSISTANT_CONST}` in {ASSISTANT_FILE}\033[0m")
        return 1

    if assistant_cap < operations_cap:
        print(f"  \033[31m✗ whatsapp-assistant's `{ASSISTANT_CONST}` ({assistant_cap}) is now "
             f"SMALLER than operations' real `{OPERATIONS_CONST}` ({operations_cap}) -- an "
             f"ordinary cart operations would accept would be refused earlier, by the wrong "
             f"service, with the wrong sentence\033[0m")
        return 1

    print(f"  \033[32m✔ whatsapp-assistant's circuit breaker ({assistant_cap}) stays >= "
         f"operations' real limit ({operations_cap})\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
