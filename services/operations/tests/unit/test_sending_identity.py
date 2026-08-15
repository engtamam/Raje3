"""Which number a message goes out from — and the three places that must agree.

THE DANGER IS NOT THAT THIS FAILS. It is that one call site keeps the branch while another drops
it: credentials sealed under `tnt:brn-jed` while the send asks for `tnt`, which resolves a
credential that addresses a different number — or none. Every screen would say «مربوط».

AND THE SAFETY RULE THIS PINS: a central shop — every shop today — must resolve byte for byte to
its own tenant id. If that ever changes, every existing seal is orphaned at once.
"""
from __future__ import annotations

import asyncio

from app.core import sending_identity as SI
from app.core import shop_mode as SM


def run(c):
    return asyncio.run(c)


class Store:
    def __init__(self, mode=None, *, boom=False):
        self._mode = mode
        self._boom = boom

    async def get(self, coll, key):
        if self._boom:
            raise RuntimeError("datastore is restarting")
        return {"mode": self._mode} if self._mode else None

    async def put(self, coll, key, row):
        return row


def test_a_central_shop_is_its_tenant_id_exactly():
    """The whole reason this is safe to ship before the mode is sellable."""
    assert SI.identity("tnt_1", "", mode=SM.CENTRAL) == "tnt_1"
    # AND A BRANCH IS DROPPED RATHER THAN HONOURED. The visit really did happen at that branch;
    # it simply must not change which number the message leaves from.
    assert SI.identity("tnt_1", "brn-jed", mode=SM.CENTRAL) == "tnt_1"


def test_a_per_branch_shop_names_its_branch():
    assert SI.identity("tnt_1", "brn-jed", mode=SM.PER_BRANCH) == "tnt_1:brn-jed"
    # No branch on the event — a till that sends none — still sends from the establishment.
    assert SI.identity("tnt_1", "", mode=SM.PER_BRANCH) == "tnt_1"


def test_an_empty_tenant_is_empty_not_a_bare_separator():
    """`":brn-jed"` would be a key that looks valid and belongs to nobody."""
    assert SI.identity("", "brn-jed", mode=SM.PER_BRANCH) == ""


def test_split_is_the_exact_inverse():
    for tenant, branch, mode in (("tnt_1", "", SM.CENTRAL),
                                 ("tnt_1", "brn-jed", SM.PER_BRANCH),
                                 ("tnt_1", "", SM.PER_BRANCH)):
        got = SI.identity(tenant, branch, mode=mode)
        back_tenant, back_branch = SI.split(got)
        assert back_tenant == tenant
        assert back_branch == (branch if mode == SM.PER_BRANCH else "")


def test_resolve_reads_the_mode():
    assert run(SI.resolve(Store(), "tnt_1", "brn-jed")) == "tnt_1"
    assert run(SI.resolve(Store(SM.PER_BRANCH), "tnt_1", "brn-jed")) == "tnt_1:brn-jed"


def test_an_unreadable_mode_sends_from_the_establishment():
    """FAIL TOWARD THE NUMBER THE CUSTOMER ALREADY KNOWS.

    Guessing `tenant:branch` would address credentials that may not exist and send nothing at all;
    guessing the establishment sends from the number every one of its customers has already seen.
    Wrong-but-harmless beats silent.
    """
    assert run(SI.resolve(Store(boom=True), "tnt_1", "brn-jed")) == "tnt_1"
