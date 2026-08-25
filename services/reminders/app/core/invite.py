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
NOT_GRANTED = "تحب توصلك عروضنا على واتساب؟ فعّلها من هنا، وتوقفها وقت ما تحب: {link}"

#: Somebody who already agreed. NO LINK: the page it would point at is closed for this release, and
#: a first message that opens on «قيد التجهيز» is worse than a message with one line fewer.
GRANTED = "وعروضنا توصلك على واتساب، وتوقفها وقت ما تحب"


#: Somebody who asked us to stop. No invitation, no link — and NOT an empty string, because Meta
#: refuses a template whose variable arrives blank.
WITHDRAWN = "نتشرّف بخدمتك دائماً 🌿"

#: THE SAME INVITATION, WITH NOWHERE TO SEND HIM YET.
#:
#: WHAT THIS COSTS AND WHAT IT SAVES. The grant screen lives on the customer page, and the page is
#: closed for this release. Until it opens there is no address to hand anybody — and the first
#: version of this file answered that by REFUSING, which killed the whole message: thirty-six
#: wordings, every service confirmation and every reminder in the fleet, because an invitation
#: could not be made perfect.
#:
#: A VISIT CONFIRMATION IS LAWFUL WITHOUT AN INVITATION. So the line steps back to an ASK with no
#: address in it, and the difference between an ask and a claim is the whole of this note.
#:
#: THE FIRST VERSION SAID «ولك عندنا مزايا خاصة» — you have special benefits with us — but
#: we do not know that. The shop may run no offer at all, and then a message in the
#: shop's name has told his customer something untrue, and told it at the moment the customer
#: trusts it most, right after a visit. It is the defect family this whole repository chases,
#: arriving in the friendliest possible sentence.
#:
#: What is true whatever the shop is doing is the QUESTION: would you like our offers to reach
#: you? It asks for the consent §8.5 needs, promises nothing that has to exist, and points him at
#: the counter — where a person can answer — rather than at a link that opens nothing.
#:
#: AND NO EMOJI, which was the second half of the same mistake. The body it lands in already ends
#: with one: `... {{3}} 🎁`. The line carried its own, so the customer read «🎁 🎁». No price, no
#: discount, no number either, for the reason every line here avoids them: a utility text that
#: sells is re-categorised by Meta as marketing.
NOT_GRANTED_NO_LINK = "وإن أحببت توصلك عروضنا، أخبرنا في زيارتك القادمة"


def line(*, consent: str, public_base_url: str, reference: str) -> str:
    """The invitation, the acknowledgement, or the neutral line. Never empty, never two.

    NEVER RAISES. It used to: `links.py` refuses to compose an address it cannot honour, and that
    refusal travelled all the way up and killed the message. Correct for a stop link on a
    promotional text — that one is the law — and wrong here, where the message is a visit
    confirmation and the line is an invitation. The fleet sent nothing for it.

    So an address that cannot be composed costs the LINK, not the MESSAGE: the invitation is made
    in words and the confirmation goes out. The day the page opens, the link returns on its own
    and no template is touched.
    """
    if consent == "granted":
        return GRANTED
    if consent == "withdrawn":
        return WITHDRAWN
    # `never_asked` — and anything unrecognised lands here too, which is the safe direction: the
    # worst case is one invitation to somebody who might have had one already, never a message
    # that re-asks a person who refused.
    try:
        return NOT_GRANTED.format(link=L.grant_link(public_base_url, reference))
    except L.LinkError:
        # NO ADDRESS TODAY IS NOT A REASON TO SAY NOTHING AT ALL.
        #
        # The refusal from `links.py` is right on its own terms — a message must never carry a
        # link that opens nothing. What was wrong was letting it end the MESSAGE. The stop link on
        # a promotional text still refuses and still should: that one is the customer's right and
        # the law's requirement. This one is an offer, and an offer we cannot address is an offer
        # we make in words.
        return NOT_GRANTED_NO_LINK
