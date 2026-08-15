"""Which number a message goes out from — one string, and everything else keys off it.

THE PROBLEM IN ONE LINE. Everything that sends today is keyed by TENANT: the credentials sealed in
the platform, the body of the send, the connection row. That is exactly right for a shop with one
number, and it has no way at all to say «من رقم فرع جدة».

THE ANSWER IS A STRING, NOT A SCHEMA. `tenant` for an establishment that sends from one number,
`tenant:branch` for a chain whose branches each have their own. Every peer treats it as an opaque
key — the platform seals credentials against it without knowing what a branch is, the send carries
it without learning our data model, and the connection row is stored under it. So the whole feature
is one function and three call sites rather than a change to four services.

AND `central` PRODUCES EXACTLY WHAT EXISTS TODAY. A shop in the default mode resolves to its own
tenant id, byte for byte — so nothing about today's sending changes, no credential is re-sealed,
and no shop is migrated. The second shape only appears for a chain that deliberately moved
(core/shop_mode.py), which is what makes this safe to ship before the mode is even sellable.

THE BRANCH IS DROPPED WHEN THE SHOP IS CENTRAL, deliberately and in one place. A caller that passes
a branch to a central shop is not wrong — the visit really did happen there — it simply must not
change which number the message leaves from. Deciding that at each call site is how two of them
end up disagreeing.
"""
from __future__ import annotations

from app.core import shop_mode as SM

SEPARATOR = ":"


def identity(tenant: str, branch_id: str = "", *, mode: str = SM.CENTRAL) -> str:
    """The sending identity for this establishment, at this branch, in this mode.

    EMPTY TENANT ANSWERS EMPTY, rather than a bare separator. A caller with no tenant has nothing
    to send under, and `":brn-jed"` would be a key that looks valid and belongs to nobody.
    """
    tenant = (tenant or "").strip()
    if not tenant:
        return ""
    branch = (branch_id or "").strip()
    if mode != SM.PER_BRANCH or not branch:
        return tenant
    return f"{tenant}{SEPARATOR}{branch}"


def split(sending_identity: str) -> tuple[str, str]:
    """`(tenant, branch_id)` — the inverse, for whoever receives one back.

    A NUMBER'S CREDENTIALS COME BACK KEYED BY THIS, and a report that cannot say which branch a
    message went out from is a report an owner cannot act on.
    """
    value = (sending_identity or "").strip()
    if not value:
        return "", ""
    tenant, sep, branch = value.partition(SEPARATOR)
    return tenant, branch if sep else ""


async def resolve(store: object, tenant: str, branch_id: str = "") -> str:
    """The identity, with the shop's mode read for you.

    ONE READ, AND IT FAILS TOWARD THE ESTABLISHMENT. An unreadable mode means we do not know
    whether this chain has moved — and answering `tenant` sends from the number every one of its
    customers already knows, which is the wrong-but-harmless half of the choice. Answering
    `tenant:branch` on a guess would address credentials that may not exist and send nothing at
    all.
    """
    try:
        row = await SM.ModeStore(store).get(tenant)
        mode = str(row.get("mode") or SM.CENTRAL)
    except Exception:                                                        # noqa: BLE001
        mode = SM.CENTRAL
    return identity(tenant, branch_id, mode=mode)
