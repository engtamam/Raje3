"""The branch on the schedule becomes the number the message leaves from — #386.

WHY THIS FILE EXISTS. «رقم لكل فرع» is built end to end and its switch is OFF, and the reason
recorded in `operations/app/config.py` is that it «was never tested» — not that anything is
missing. Measured before writing this: `tick._sending_identity` is the ONE line that turns a
schedule's branch into the credentials a message is sent with, it is called from both send paths,
and it had no test of its own. The only place it was named was the docstring of a campaign test
that asserts something else.

So the most-used path in the product — the ordinary service reminder after a visit — had nobody
checking that the branch reaches the sender at all. A shop switched to per-branch would have had
every reminder leave from the central number while its screens said otherwise, and the failure is
invisible from inside: the message sends, it just sends as the wrong shop.

WHAT IS STILL NOT PROVEN HERE, said plainly: that the sender's credential lookup resolves
`tenant:branch` to the branch's own Meta number. That needs two registered numbers and belongs to
#167; this closes everything up to that seam, so what remains is one live check rather than a
chain nobody has walked.
"""
from app.core.tick import _sending_identity


def test_a_visit_at_a_branch_sends_from_that_branch():
    assert _sending_identity("shop", {"branch_id": "riyadh-2"}) == "shop:riyadh-2"


def test_a_shop_with_no_branch_on_the_row_sends_as_itself():
    """Every establishment in the default mode. The identity must not gain a stray separator —
    the sender treats `tenant` and `tenant:` as two different lookups, and the second resolves
    to nothing."""
    assert _sending_identity("shop", {}) == "shop"
    assert _sending_identity("shop", {"branch_id": ""}) == "shop"
    assert _sending_identity("shop", {"branch_id": None}) == "shop"


def test_a_branch_written_with_stray_spaces_is_still_that_branch():
    """Whitespace arrives from a till posting its own branch id. It must not mint a second
    identity for the same branch — two identities means two credential lookups and one of them
    fails."""
    assert _sending_identity("shop", {"branch_id": "  riyadh-2  "}) == "shop:riyadh-2"


def test_a_row_whose_branch_is_only_spaces_is_the_establishment():
    assert _sending_identity("shop", {"branch_id": "   "}) == "shop"
