"""An owner's own wording keeps the class of the reason it replaces.

WHAT SHIPPED. `CustomTemplateStore.draft` took `cls` from its caller and defaulted it to
`"service"`, and `TextEditor.tsx` — the only screen that writes one — posts
`{reason_id, body, fills, replaces}` and no class at all. The registry holds four MARKETING
reasons («استرجاع», «تفعيل النقاط» twice, «مناسبة العميل»), so an owner who rewrote any of them
in his own words had that text filed as service.

Everything the class decides then goes the wrong way at once:
  · `mandatory_tail` appends the «أوقفها» link for marketing and an invite for service, so his
    advertising would have gone out with no way to stop it — §8.3 makes that link mandatory;
  · marketing needs granted consent and service does not, so it would reach people who never
    agreed to be advertised at;
  · the quiet window and the monthly marketing cap are both keyed on the class, so it would send
    at night and outside the ceiling that protects the shop's own number.

Nothing refuses it and nothing looks wrong — which is why this is a test and a gate rather than a
note. The same file already learnt this lesson once, for `version`: found, never trusted to the
caller.
"""
import pytest

from app.core import reasons as T
from app.core.custom_templates import CustomTemplateError, CustomTemplateStore
from app.core.reasons import MARKETING


class Store:
    """The datastore surface `draft` touches. Enough to observe what it wrote."""

    def __init__(self) -> None:
        self.rows: dict = {}

    async def get(self, collection, key):
        return self.rows.get((collection, key))

    async def put(self, collection, key, value):
        self.rows[(collection, key)] = value

    async def list(self, collection, **kw):
        return [v for (c, _), v in self.rows.items() if c == collection]

    async def count(self, collection, **kw):
        return len(await self.list(collection))


def a_marketing_reason() -> str:
    for r in T.REASONS:
        if r.cls == MARKETING and r.owner_can_retext:
            return r.id
    pytest.skip("no rewritable marketing reason in the registry")


@pytest.mark.asyncio
async def test_rewriting_a_marketing_reason_stores_it_as_marketing():
    reason_id = a_marketing_reason()
    row = await CustomTemplateStore(Store()).draft(
        "shop", reason_id=reason_id, body="عرضنا لك اليوم", fills=[])
    assert row.cls == MARKETING


@pytest.mark.asyncio
async def test_the_stop_link_rides_along_because_the_class_is_right():
    """The tail is composed FROM the class, so getting the class right is what puts the link in.
    This asserts the consequence rather than the field, because the link is what a customer
    needs and the field is only how we get there."""
    reason_id = a_marketing_reason()
    row = await CustomTemplateStore(Store()).draft(
        "shop", reason_id=reason_id, body="عرضنا لك اليوم", fills=[])
    assert "stop_link" in row.fills


@pytest.mark.asyncio
async def test_a_caller_naming_a_class_that_disagrees_is_refused():
    """Refused, not silently corrected: a caller that thinks a marketing reason is service has a
    defect of its own, and quietly overwriting the value hides it."""
    reason_id = a_marketing_reason()
    with pytest.raises(CustomTemplateError):
        await CustomTemplateStore(Store()).draft(
            "shop", reason_id=reason_id, body="عرضنا لك اليوم", fills=[], cls="service")


@pytest.mark.asyncio
async def test_an_unknown_reason_is_refused_before_any_class_is_assumed():
    with pytest.raises(CustomTemplateError):
        await CustomTemplateStore(Store()).draft(
            "shop", reason_id="no_such_reason", body="نص", fills=[])
