"""The traps a thin public page has of its own.

Not the generic five — these are specific to a page anyone can open with a link they were
forwarded, and every one of them is silent when it goes wrong.
"""
from __future__ import annotations

import inspect
import re


# ── TRAP 1: the link built with a different separator than the one that parses it ──────────────
def test_the_builder_and_the_parser_are_the_same_module():
    """A separator chosen independently on two sides means every button in every message 404s —
    and the templates are already approved by Meta with the broken link baked in."""
    import app.core.reference as ref
    assert hasattr(ref, "build") and hasattr(ref, "parse")
    r = ref.parse(ref.build("tnt-a", "sub_" + "a" * 32))
    assert r.valid


def test_reminders_and_the_portal_agree_on_the_reference_shape():
    """reminders mints the link into the message; the portal parses it. They are different
    services, different repos-in-spirit, and nothing but this test connects the two decisions."""
    import pathlib
    rem = pathlib.Path(__file__).resolve().parents[3] / "reminders/app/api/v1/prefs.py"
    src = rem.read_text(encoding="utf-8")
    # reminders splits on the first '.', and so do we.
    assert 'partition(".")' in src
    assert 'partition(".")' in inspect.getsource(__import__(
        "app.core.reference", fromlist=["x"]).parse)


# ── TRAP 2: a page cached and served to the next person ────────────────────────────────────────
def test_nothing_may_store_this_page():
    """A proxy, or a phone shared between a father and his son: `private` alone permits the
    browser to keep it, and a back button shows the previous person's visits."""
    from app.api.page import NO_STORE
    assert "no-store" in NO_STORE["Cache-Control"]


def test_every_route_that_renders_sends_the_no_store_headers():
    """One route that forgets is the one route somebody's page leaks through."""
    import app.api.page as mod
    for fn in (mod.stop, mod.allow, mod.grant, mod.ask_about_data):
        assert "NO_STORE" in inspect.getsource(fn), f"{fn.__name__} does not send no-store"


# ── TRAP 3: an oracle in the difference between two answers ────────────────────────────────────
def test_no_route_ever_returns_a_404():
    """A 404 answers 'does this shop have a customer with this reference?' to anyone holding a
    forwarded link, and the caller can do nothing differently either way.

    Read from the AST, not the text: the first version of this test matched the docstring that
    EXPLAINS the rule. Grepping cannot tell a rule from a description of a rule — the same false
    positive the deploy guards produced, and the partner-console test before it.
    """
    import ast

    import app.api.page as mod
    tree = ast.parse(open(mod.__file__, encoding="utf-8").read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            assert node.value != 404, "a route returns 404"
        if isinstance(node, ast.Attribute):
            assert not node.attr.startswith("HTTP_404"), "a route returns 404"
        if isinstance(node, ast.Raise):
            raised = ast.unparse(node)
            assert "HTTPException" not in raised, f"a route raises: {raised[:60]}"


def test_an_unknown_and_a_malformed_reference_produce_the_same_shape():
    from app.core.reference import parse
    assert parse("garbage").valid == parse("tnt-a.sub_bad").valid is False


# ── TRAP 4: the page holding something after an erasure ────────────────────────────────────────
def test_the_service_has_no_storage_for_an_erasure_to_miss():
    """The strongest form of 'the erasure is complete': the one collection this service writes
    (runtime_config, keyed by tenant and knob — never by data subject) holds nothing a DSAR could
    reach, asserted structurally rather than promised in a comment."""
    from app.backup_manifest import BACKUP
    names = {c["name"] for c in BACKUP["collections"]}
    assert names == {"runtime_config"} and BACKUP["object_prefix"] == ""


def test_the_erase_ack_is_honest_and_idempotent():
    import asyncio

    from app.core.erasure import PortalErasure
    ack = asyncio.run(PortalErasure().erase("t1", "sub_x"))
    assert ack["already_absent"] is True and ack["erased"] == []


def test_the_page_does_not_forward_the_erasure_to_its_peers():
    """It talks to all three and could — which would be a second fan-out racing the real one,
    with its own partial failures and no record."""
    src = inspect.getsource(__import__("app.core.erasure", fromlist=["x"]))
    for peer in ("operations", "reminders", "tenant"):
        assert f"{peer}." not in src.split('"""', 2)[-1]


# ── TRAP 5: a peer URL that resolves in one namespace and not another ──────────────────────────
def test_no_peer_url_assumes_a_namespace_it_has_not_been_given():
    from app.config import Settings
    s = Settings(INTERNAL_SERVICE_TOKEN="x" * 40)
    for url in (s.TENANT_SERVICE_URL, s.OPERATIONS_SERVICE_URL, s.REMINDERS_SERVICE_URL):
        if url and "://" in url:
            host = url.split("://", 1)[1].split(":")[0].split("/")[0]
            assert "." not in host or host.endswith("svc.cluster.local")


# ── and the promise the whole design rests on ──────────────────────────────────────────────────
def test_the_rendered_page_can_never_carry_an_identifier():
    """Everything the page shows comes from customer-visits, which returns service names and a
    date. This asserts the renderer cannot print a field it was never given."""
    from app.core.render import render_page
    src = inspect.getsource(render_page)
    for field in ("phone", "subject_ref", "customer_id", "operator", "amount"):
        assert field not in src


# ── TRAP 6: a peer's outage rendered as a JSON blob to a customer exercising a legal right ─────
def test_the_privacy_request_survives_an_unreachable_operations():
    """THE DEFECT. `HttpOperations.privacy_request` lets a urllib error propagate, and the call had
    nothing around it. So a restarting operations pod reached the app-wide handler, which answers
    `{"error":"INTERNAL_ERROR"}` with a 500 — JSON rendered into a CUSTOMER's browser, on the page
    he opened from a WhatsApp message, on the one action that is his right under the PDPL. He
    cannot tell whether his request was recorded, and the thirty-day clock never starts.

    The honest sentence was already written four lines below and simply could not be reached.

    ASSERTED ON THE SOURCE, in this file's own idiom (see TRAP 2): the failure is a network error
    from a peer built at container time, and a test that stubs the peer proves the stub is
    catchable rather than that the call site catches."""
    import ast
    import inspect

    import app.api.page as mod

    tree = ast.parse(inspect.getsource(mod.ask_about_data))
    guarded = [n for n in ast.walk(tree) if isinstance(n, ast.Try)
               for c in ast.walk(n) if isinstance(c, ast.Attribute) and c.attr == "privacy_request"]
    assert guarded, "the peer call is unguarded — an outage renders INTERNAL_ERROR to the customer"
    # AND THE FALLBACK IS THE SENTENCE, not a silent success: `ok` must end up False.
    assert "تعذّر تسجيل طلبك الآن" in inspect.getsource(mod.ask_about_data)
