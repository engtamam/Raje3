"""`_strip_tenant_prefix` — the fix for a live bug: `find_key_by_phone` used to hand its caller
the RAW `kv_store.key` value straight off the narrow view, which is `core/stores.py`'s own
`_key()` composite `"{tenant}|{id}"`, never a bare id. The caller
(`Operations.customer_by_phone_searched`) passes whatever it gets into
`CustomerStore.get(tenant, ident)`, which re-prefixes tenant itself — so the unstripped composite
became `"{tenant}|{tenant}|{id}"`, a key nothing ever wrote, and every phone lookup under this
role missed silently (200, `{"customer": null}`, indistinguishable from "no such customer"). The
existing unit tests for `customer_by_phone_searched` never caught this because their own fake
`_FakePhoneSearchRO` returned a bare id directly, never the real adapter's composite format — this
file tests the real adapter's own stripping logic instead."""
from app.adapters.datastore.phone_search_ro import _strip_tenant_prefix

TENANT = "411b7725040649499e1c931f0bf62a6a"


def test_strips_the_tenant_prefix_kv_store_actually_stores():
    composite = f"{TENANT}|cus_add32406da444f50b3bd797e35ca2a56"

    assert _strip_tenant_prefix(TENANT, composite) == "cus_add32406da444f50b3bd797e35ca2a56"


def test_a_key_with_no_prefix_is_returned_unchanged():
    """Defensive: nothing in this view is ever expected to omit the prefix, but a caller that
    later stops prefixing must not have this silently double-strip or corrupt a bare id."""
    bare = "cus_add32406da444f50b3bd797e35ca2a56"

    assert _strip_tenant_prefix(TENANT, bare) == bare


def test_a_key_prefixed_with_a_different_tenant_is_left_alone():
    """The view's own WHERE tenant=$1 already refuses a cross-tenant row — this only guards
    against stripping the wrong establishment's prefix if that filter is ever weakened."""
    other_tenant_key = "some_other_tenant|cus_add32406da444f50b3bd797e35ca2a56"

    assert _strip_tenant_prefix(TENANT, other_tenant_key) == other_tenant_key
