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
