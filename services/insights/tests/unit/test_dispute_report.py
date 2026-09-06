"""core/dispute_report.py — identity resolution stays a distinct failure from a source failure,
each source fails independently, and an unknown scenario is refused before any peer call."""
from __future__ import annotations

import pytest

from app.core.dispute_report import (
    PeerCallFailed, SourceUnavailable, _Urls, resolve_tenant, run_scenario,
)


class FakeCaller:
    def __init__(self, get_answers=None, post_answers=None, fail_paths=None):
        self.get_answers = get_answers or {}
        self.post_answers = post_answers or {}
        self.fail_paths = fail_paths or set()
        self.calls = []

    def get(self, base_url, path, query=None):
        self.calls.append(("GET", base_url, path, query))
        if path in self.fail_paths:
            raise PeerCallFailed("unreachable")
        return self.get_answers.get(path, {})

    def post(self, base_url, path, body=None):
        self.calls.append(("POST", base_url, path, body))
        if path in self.fail_paths:
            raise PeerCallFailed("unreachable")
        return self.post_answers.get(path, {})


URLS = _Urls(
    operations="http://operations:8000", billing="http://billing-service:8000",
    backup="http://backup-service:8000", audit="http://audit-service:8000",
    reminders="http://reminders:8000", compliance="http://compliance-service:8000",
    tenant_by_phone_path="/internal/operations/tenant-by-phone",
    branches_full_path="/internal/operations/branches-full",
    operators_full_path="/internal/operations/operators-full",
    subscriptions_path="/internal/billing/subscriptions",
    invoices_path="/internal/billing/invoices",
    tenant_coverage_path="/internal/backup/tenant-coverage",
    audit_query_path="/internal/audit", evidence_path="/internal/reminders/evidence",
    legal_list_path="/internal/compliance/legal",
    legal_history_path="/internal/compliance/legal/{doc_id}/history",
    identity="http://identity-service:8000",
    tenancy_members_path="/internal/tenancy/members",
    consent_history_path="/internal/compliance/consent-history",
)


def test_an_unknown_scenario_is_refused_before_any_peer_call():
    caller = FakeCaller()
    with pytest.raises(SourceUnavailable, match="سيناريو غير معروف"):
        run_scenario(caller, URLS, "0501234567", "made_up")
    assert caller.calls == []


def test_an_unresolvable_phone_raises_before_any_source_runs():
    caller = FakeCaller(post_answers={"/internal/operations/tenant-by-phone": {"found": False}})
    with pytest.raises(SourceUnavailable, match="لا توجد منشأة"):
        run_scenario(caller, URLS, "0501234567", "data_loss")
    assert len(caller.calls) == 1


def test_data_loss_scenario_reports_backup_coverage():
    caller = FakeCaller(
        post_answers={"/internal/operations/tenant-by-phone": {"found": True, "tenant": "tnt_x"}},
        get_answers={"/internal/backup/tenant-coverage": {
            "tenant": "tnt_x", "run": "run_1", "started_at": 1000, "covered": True,
            "covered_by": ["backup-service"], "verified_by": ["backup-service"],
            "unverified_by": [], "fully_verified": True, "run_incomplete": False}},
    )
    result = run_scenario(caller, URLS, "0501234567", "data_loss")
    assert result.tenant == "tnt_x"
    assert len(result.items) == 1
    assert "مُغطّى ومُتحقَّق منه فعلياً" in result.items[0].label
    assert result.errors == []


def test_a_failing_source_is_reported_not_raised_and_the_rest_still_run():
    caller = FakeCaller(
        post_answers={"/internal/operations/tenant-by-phone": {"found": True, "tenant": "tnt_x"},
                      "/internal/operations/branches-full": {"branches": [{"name": "فرع", "created": 500}]},
                      "/internal/operations/operators-full": {"operators": []}},
        fail_paths={"/internal/audit"},
    )
    result = run_scenario(caller, URLS, "0501234567", "suspended_no_notice")
    assert len(result.errors) == 1 and "audit" in result.errors[0]
    assert len(result.items) == 1  # the branch, from `staff`, still came through
    assert "فرع" in result.items[0].label


def test_billing_scenario_lists_subscriptions_and_both_invoice_statuses():
    def post_fake(base_url, path, body):
        if path == "/internal/operations/tenant-by-phone":
            return {"found": True, "tenant": "tnt_x"}
        return {}

    caller = FakeCaller(post_answers={"/internal/operations/tenant-by-phone": {"found": True, "tenant": "tnt_x"}})

    def get_fake(base_url, path, query=None):
        caller.calls.append(("GET", base_url, path, query))
        if path == "/internal/billing/subscriptions":
            return {"subscriptions": [{"plan_id": "base", "status": "active", "current_period_end": 2000}]}
        if query and query.get("status") == "paid":
            return {"invoices": [{"amount_minor": 10000, "currency": "SAR", "paid_at": "2026-01-01T00:00:00Z",
                                  "paid_sequence": 1, "refunded_minor": 0}]}
        return {"invoices": []}

    caller.get = get_fake
    result = run_scenario(caller, URLS, "0501234567", "billing_error")
    labels = [it.label for it in result.items]
    assert any("اشتراك" in x for x in labels)
    assert any("فاتورة (مدفوعة)" in x and "أول دفعة" in x for x in labels)


def test_resolve_tenant_directly_raises_on_a_peer_failure():
    caller = FakeCaller(fail_paths={"/internal/operations/tenant-by-phone"})
    with pytest.raises(SourceUnavailable, match="تعذّر تحديد المنشأة"):
        resolve_tenant(caller, URLS, "0501234567")


def test_contract_breach_scenario_lists_legal_versions_newest_last_by_ts():
    caller = FakeCaller(
        post_answers={"/internal/operations/tenant-by-phone": {"found": True, "tenant": "tnt_x"}},
        get_answers={
            "/internal/compliance/legal": {"documents": [{"doc_id": "terms", "version": "2"}]},
            "/internal/compliance/legal/terms/history": {"versions": [
                {"version": "2", "status": "published", "published_at": 3000, "requires_acceptance": True},
                {"version": "1", "status": "published", "published_at": 1000, "requires_acceptance": True},
            ]},
        },
        fail_paths={"/internal/audit"},
    )
    result = run_scenario(caller, URLS, "0501234567", "contract_breach")
    labels = [it.label for it in result.items]
    assert any("«terms» — نسخة 2 — منشورة" in x for x in labels)
    assert any("«terms» — نسخة 1 — منشورة" in x for x in labels)
    assert labels.index("مستند قانوني «terms» — نسخة 1 — منشورة (تتطلب موافقة العميل)") < \
        labels.index("مستند قانوني «terms» — نسخة 2 — منشورة (تتطلب موافقة العميل)")
    # `/internal/compliance/legal/{doc_id}/history` was resolved per-doc, from the list's own doc_id.
    hist_calls = [c for c in caller.calls if c[2] == "/internal/compliance/legal/terms/history"]
    assert len(hist_calls) == 1


def test_acceptance_source_reports_the_owners_actual_consent_proofs_not_just_published_versions():
    caller = FakeCaller(
        post_answers={"/internal/operations/tenant-by-phone": {"found": True, "tenant": "tnt_x"}},
        get_answers={
            "/internal/compliance/legal": {"documents": []},
            "/internal/tenancy/members": {"members": [
                {"person_id": "p_staff", "roles": ["staff"]},
                {"person_id": "p_owner", "roles": ["owner"]},
            ]},
            "/internal/compliance/consent-history": {"proofs": [
                {"purpose": "legal:terms", "action": "granted", "notice_version": "1",
                 "ip": "1.2.3.4", "at": 1000},
                {"purpose": "legal:terms", "action": "granted", "notice_version": "2", "at": 3000},
                {"purpose": "marketing:promos", "action": "granted", "at": 2000},  # not legal — excluded
            ]},
        },
        fail_paths={"/internal/audit"},
    )
    result = run_scenario(caller, URLS, "0501234567", "contract_breach")
    labels = [it.label for it in result.items]
    assert any("وافق على مستند «terms» — نسخة 1 — من IP 1.2.3.4" in x for x in labels)
    assert any("وافق على مستند «terms» — نسخة 2" in x for x in labels)
    assert not any("marketing" in x for x in labels)
    # the OWNER's person_id was used, never the staff member's
    member_call = [c for c in caller.calls if c[2] == "/internal/compliance/consent-history"][0]
    assert member_call[3] == {"tenant": "tnt_x", "subject": "p_owner"}


# ── _fetch_audit — no test at all covered this source before this pass, despite it backing 3 of
# the 7 scenarios (including ai_hallucination, this report's own answer to "the AI acted without
# a real confirmation") ─────────────────────────────────────────────────────────────────────────
def test_audit_scenario_labels_each_event_with_actor_action_and_resource():
    caller = FakeCaller(
        post_answers={"/internal/operations/tenant-by-phone": {"found": True, "tenant": "tnt_x"}},
        get_answers={"/internal/audit": {"events": [
            {"action": "whatsapp_assistant.booking_confirmed", "actor": "sub_abc",
             "resource": "booking:bkg_1", "at": 1000},
            {"action": "subject.erased", "resource": "subject:sub_xyz", "at": 2000},  # no actor
        ]}},
    )
    result = run_scenario(caller, URLS, "0501234567", "ai_hallucination")
    labels = [it.label for it in result.items]
    assert any("whatsapp_assistant.booking_confirmed" in x and "sub_abc" in x and "bkg_1" in x
              for x in labels)
    # a system action with no actor reads «النظام», never a blank or a crash
    assert any("subject.erased" in x and "النظام" in x for x in labels)
    call = [c for c in caller.calls if c[2] == "/internal/audit"][0]
    assert call[3]["limit"] == 1000


def test_audit_scenario_follows_next_cursor_across_a_full_page_and_a_half():
    """A first page at exactly the page limit, carrying next_cursor — audit-service v0.18.31's
    real pagination signal — is followed to a second, final page (next_cursor null) rather than
    stopping at the first 1000. Every event from BOTH pages ends up in the report, and no warning
    is emitted: next_cursor going null is proof nothing was left behind, unlike the old
    `count == limit` guess this replaces."""
    page_1 = [{"action": "x.happened", "actor": "sub_1", "resource": "r", "at": i}
              for i in range(1000)]
    page_2 = [{"action": "y.happened", "actor": "sub_2", "resource": "r2", "at": 1000}]
    caller = FakeCaller(
        post_answers={"/internal/operations/tenant-by-phone": {"found": True, "tenant": "tnt_x"}})

    def get_fake(base_url, path, query=None):
        caller.calls.append(("GET", base_url, path, query))
        if path != "/internal/audit":
            return {}
        if query and query.get("after"):
            assert query["after"] == "cursor_1"
            return {"events": page_2, "next_cursor": None}
        return {"events": page_1, "next_cursor": "cursor_1"}

    caller.get = get_fake
    result = run_scenario(caller, URLS, "0501234567", "ai_hallucination")
    assert not any("⚠" in it.label for it in result.items)
    assert any("y.happened" in it.label and "sub_2" in it.label for it in result.items)
    audit_calls = [c for c in caller.calls if c[2] == "/internal/audit"]
    assert len(audit_calls) == 2


def test_audit_scenario_warns_only_when_the_page_cap_itself_is_reached():
    """next_cursor never goes null — the tenant's history genuinely outruns
    `_AUDIT_MAX_PAGES * _AUDIT_PAGE_LIMIT` — so the fetch stops at the bound and says so, rather
    than paging forever or silently truncating."""
    caller = FakeCaller(
        post_answers={"/internal/operations/tenant-by-phone": {"found": True, "tenant": "tnt_x"}})

    def get_fake(base_url, path, query=None):
        caller.calls.append(("GET", base_url, path, query))
        if path != "/internal/audit":
            return {}
        return {"events": [{"action": "x.happened", "actor": "sub_1", "resource": "r", "at": 1}],
                "next_cursor": "always_more"}

    caller.get = get_fake
    result = run_scenario(caller, URLS, "0501234567", "ai_hallucination")
    assert any("⚠" in it.label for it in result.items)
    audit_calls = [c for c in caller.calls if c[2] == "/internal/audit"]
    assert len(audit_calls) == 20   # _AUDIT_MAX_PAGES, then it gives up and says so


def test_audit_scenario_says_nothing_extra_when_well_under_the_page_limit():
    caller = FakeCaller(
        post_answers={"/internal/operations/tenant-by-phone": {"found": True, "tenant": "tnt_x"}},
        get_answers={"/internal/audit": {"events": [
            {"action": "x.happened", "actor": "sub_1", "resource": "r", "at": 1}]}},
    )
    result = run_scenario(caller, URLS, "0501234567", "ai_hallucination")
    assert not any("⚠" in it.label for it in result.items)
