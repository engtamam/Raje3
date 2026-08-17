"""The last line of every utility message — an invitation, or a quiet reward for having accepted.

WHY THIS EXISTS AT ALL. Marketing is opt-IN: no grant, no promotional message, ever. And there was
no way to grant. The template library declared a `button` on sixty of sixty-six templates;
`submission.py` submits name, language, category, body, variables and examples and no button, and
notification-service has no notion of a button anywhere in its source. So the door was drawn on the
plan and never cut into the wall — the campaigns engine, complete and sold as an app, could not
lawfully send one message for the life of the product, and nothing reported it.

The address therefore moves into the BODY, where nothing between us and the customer can drop it.

THREE STATES, BECAUSE «HAS NOT AGREED» IS TWO DIFFERENT PEOPLE (§8.5):

    never_asked   an invitation, with the link to the screen where he can say yes
    granted       an acknowledgement, with NO link
    withdrawn     a neutral line — NO invitation and NO link

RE-INVITING SOMEBODY WHO REFUSED IS NOT MARKETING, IT IS PURSUIT. The specification says so in as
many words — «إعادة دعوة من رفض ملاحقة، لا تسويق» — and the first version of this file had a
boolean, which made a withdrawal indistinguishable from silence: every service message the shop
sent would have re-asked a customer who had already said no, forever. His way back is his own
choice from the preferences page, not an invitation we repeat at him.

WHY THE GRANTED LINE CARRIES NO LINK. It used to point at his page — and the page is closed for
this release (portal's PUBLIC_PAGE_ENABLED). A message that invites him to open «صفحتك» and lands
on «قيد التجهيز» breaks a promise in the first sentence we ever send him. A link is only ever
mentioned where it opens something real; the day the page opens (#349) this line gains one and no
template is touched.

AND THE INVITATION IS DELIBERATELY QUIET. Everything in it wants to shout — the discounts are the
reason anybody says yes. But this line rides inside a UTILITY template, and a utility text that
sells is re-categorised by Meta as MARKETING: a higher price on every message the shop sends, and
a service confirmation that suddenly needs the very consent it was trying to collect. `SELLING_WORDS`
in ci/gen_templates.py already refuses that for the awareness class, and this obeys the same rule
by carrying no price, no discount, no offer and no number.

ALL OF THE PERSUASION LIVES ONE TAP AWAY, on portal's `/allow` screen — our own page, which Meta
does not review and where nothing is held back.

Meta refuses an EMPTY variable, so neither branch may return "".
"""
from __future__ import annotations

from app.core import links as L

#: Somebody who has not agreed. It names no discount and no price on purpose (see the module note);
#: what it promises is that something is waiting, and the screen behind the link says what.
NOT_GRANTED = "ولك عندنا مزايا خاصة — فعّلها من هنا: {link}"

#: Somebody who already agreed. NO LINK: the page it would point at is closed for this release, and
#: a first message that opens on «قيد التجهيز» is worse than a message with one line fewer.
GRANTED = "ومزاياك الخاصة مفعّلة — جديدنا يوصلك أول بأول 🎁"


#: Somebody who asked us to stop. No invitation, no link — and NOT an empty string, because Meta
#: refuses a template whose variable arrives blank.
WITHDRAWN = "نتشرّف بخدمتك دائماً 🌿"


def line(*, consent: str, public_base_url: str, reference: str) -> str:
    """The invitation, the acknowledgement, or the neutral line. Never empty, never two.

    RAISES `LinkError` when the grant link cannot be composed — from `links.py`, deliberately, and
    the send fails rather than delivering a sentence that invites somebody to tap nothing. That is
    the same refusal the stop link already makes, for the same reason: a message reported as sent
    which carries a dead address is worse than one that was never sent, because nobody looks again.
    """
    if consent == "granted":
        return GRANTED
    if consent == "withdrawn":
        return WITHDRAWN
    # `never_asked` — and anything unrecognised lands here too, which is the safe direction: the
    # worst case is one invitation to somebody who might have had one already, never a message
    # that re-asks a person who refused.
    return NOT_GRANTED.format(link=L.grant_link(public_base_url, reference))
