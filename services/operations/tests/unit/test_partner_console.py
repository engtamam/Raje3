"""The partner console — the boundary that is easy to state and easy to lose."""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.api.v1.partner import _partner_id


class P:
    def __init__(self, raw):
        self.raw = raw
        self.subject = "u1"
        self.tenant = ""


def test_the_partner_comes_off_the_token_never_off_the_path():
    """A partner id in a URL is a partner id an attacker can change — and this is the one route
    family where that hands over another company's commercial position."""
    assert _partner_id(P({"partner": "prt_1"})) == "prt_1"


def test_a_token_that_speaks_for_no_partner_is_refused():
    with pytest.raises(HTTPException) as exc:
        _partner_id(P({}))
    assert exc.value.status_code == 403


def test_the_refusal_does_not_name_the_missing_field():
    """Telling the caller which claim is missing helps them forge a better token."""
    with pytest.raises(HTTPException) as exc:
        _partner_id(P({"tenant": "t1"}))
    assert exc.value.detail == "FORBIDDEN"


def _code_names(path):
    """Every NAME the module actually references — imports, attributes, calls.

    Read from the AST, not from the file text. A first version of this test grepped the source and
    failed on the module's own docstring, which says in prose what a partner must never see. Text
    matching cannot tell a rule from a description of the rule — the same false positive the deploy
    guards produced, wearing different clothes.
    """
    import ast
    tree = ast.parse(open(path, encoding="utf-8").read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.rsplit(".", 1)[-1])
            if node.asname:
                names.add(node.asname)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # String literals count — a collection name is a string, not an identifier. Docstrings
            # are excluded because they are documentation, and a rule written down is not a rule
            # broken.
            if node.value.count(" ") < 3:
                names.add(node.value)
    return names


def test_the_console_reads_only_from_stamps_and_statements():
    """A console that gains 'just show me how the shop is doing' grows into a customer list, one
    reasonable request at a time. This asserts the module cannot even reach the others."""
    import app.api.v1.partner as mod
    names = _code_names(mod.__file__)
    for forbidden in ("CustomerStore", "VisitStore", "customers", "visits", "phone",
                      "subject_ref", "OperationsService"):
        assert forbidden not in names, f"the partner console must not touch {forbidden}"


def test_a_partner_cannot_trigger_a_recomputation():
    """A disputed month must not be a month they can re-run until they like the number."""
    import app.api.v1.partner as mod
    src = open(mod.__file__, encoding="utf-8").read()
    assert "@router.post" not in src and "@router.put" not in src
    assert "build(" not in src
