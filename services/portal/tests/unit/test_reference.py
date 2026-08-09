"""The link — where the security model is inverted and getting it backwards is the whole risk."""
from __future__ import annotations

import pytest

from app.core.reference import build, parse

REF = "tnt-alpha.sub_113084dcdcd3f97d290c50a23fdc13ef"


def test_a_valid_reference_splits():
    r = parse(REF)
    assert r.valid and r.tenant == "tnt-alpha"
    assert r.subject_ref.startswith("sub_")


@pytest.mark.parametrize("bad", [
    "", "   ", "no-separator", ".sub_113084dcdcd3f97d290c50a23fdc13ef",
    "tnt-alpha.", "tnt-alpha.notasubject", "tnt-alpha.sub_ZZZZ",
    "TNT_ALPHA!!.sub_113084dcdcd3f97d290c50a23fdc13ef",
    "a" * 200 + ".sub_113084dcdcd3f97d290c50a23fdc13ef",
])
def test_every_malformed_reference_returns_the_same_empty_answer(bad):
    """Distinguishing 'malformed' from 'unknown' in the response would be an oracle: a stranger
    with a forwarded link could learn whether a shop exists by watching which error came back."""
    assert not parse(bad).valid


def test_parsing_never_raises():
    """This string comes off a URL. A page that 500s on a mangled link is a page an attacker can
    turn into a log flood, and a customer with a broken message into a support ticket."""
    for weird in (None, "..", "a.b.c.d", "\x00.sub_113084dcdcd3f97d290c50a23fdc13ef", "؟.؟"):
        parse(weird)


def test_case_is_folded_so_a_copied_link_still_works():
    """A customer who retypes a link, or a chat app that capitalises a host, must not get a dead
    page for it."""
    assert parse(REF.upper()).valid


def test_build_and_parse_are_the_same_module():
    """A separator chosen independently on two sides means every button in every message 404s —
    and the templates are already approved by Meta with the broken link baked in."""
    r = parse(build("tnt-alpha", "sub_113084dcdcd3f97d290c50a23fdc13ef"))
    assert r.valid and str(r) == REF
