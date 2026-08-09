"""The report — the only place 'it didn't arrive' can be answered."""
from __future__ import annotations

from app.core.report import build, history, summarise, totals

NOW = 1_800_000_000
DAY = 86400


def run_row(**over):
    d = {"at": NOW, "matched": 47, "sent": 43, "suppressed": 3, "failed": 1,
         "reasons": {"بلغ الحد اليومي": 3}, "fired_by": "system"}
    d.update(over)
    return d


# ── the sentence ───────────────────────────────────────────────────────────────────────────────
def test_the_summary_names_what_did_not_arrive_and_why():
    """Every rule we wrote becomes a suspected bug unless this line explains itself."""
    r = build(run_row())
    assert "وصلت 43" in r.summary
    assert "امتنعت 3" in r.summary and "الحد اليومي" in r.summary


def test_it_is_a_count_not_a_rate():
    """A delivery rate hides the three customers whose messages were held; the sentence names
    them as a number the owner can act on."""
    s = build(run_row()).summary
    assert "%" not in s and "91" not in s


def test_a_run_that_matched_nobody_says_so_rather_than_showing_zeros():
    """'Nobody matched' is information — it means the rule found nobody, which is different from
    a run that did not happen."""
    r = build(run_row(matched=0, sent=0, suppressed=0, failed=0, reasons={}))
    assert r.summary == "لم تنطبق على أحد هذه المرة."


def test_at_most_two_reasons_are_named_in_the_line():
    """A sentence listing nine causes is a paragraph, and a paragraph on a summary line is not
    read. The rest are one tap away."""
    reasons = {f"سبب {i}": 1 for i in range(9)}
    s = summarise(sent=1, suppressed=9, failed=0, reasons=reasons)
    assert s.count("سبب") == 2


def test_the_largest_reasons_are_the_ones_named():
    s = summarise(sent=1, suppressed=12, failed=0,
                  reasons={"نادر": 1, "الحد اليومي": 8, "التهدئة": 3})
    assert "الحد اليومي" in s and "التهدئة" in s and "نادر" not in s


def test_a_reason_is_truncated_but_never_rewritten():
    """A reason the owner reads here must match the detail view word for word, or they will
    believe they are two different problems."""
    long = "العميل أوقف الرسائل الدعائية من صفحته وإيقافه مطلق ولا يُتجاوَز أبداً مهما كان"
    s = summarise(sent=0, suppressed=1, failed=0, reasons={long: 1})
    assert long[:30] in s


def test_failures_are_reported_separately_from_refusals():
    """A refusal is the system working; a failure is the system broken, and merging them hides
    the second inside the first."""
    s = summarise(sent=5, suppressed=2, failed=3, reasons={"الحد اليومي": 2})
    assert "امتنعت 2" in s and "تعذّرت 3" in s


# ── per run, never aggregated ──────────────────────────────────────────────────────────────────
def test_history_is_per_run_and_newest_first():
    """An owner asking why it reached nobody last Tuesday needs Tuesday — an average across forty
    runs answers a question they did not ask."""
    rows = [run_row(at=NOW - 2 * DAY, sent=1), run_row(at=NOW, sent=9),
            run_row(at=NOW - DAY, sent=5)]
    got = history(rows)
    assert [r.sent for r in got] == [9, 5, 1]


def test_history_is_bounded():
    rows = [run_row(at=NOW - i * DAY) for i in range(100)]
    assert len(history(rows, limit=30)) == 30


def test_totals_are_a_separate_function_so_nobody_renders_one_where_a_run_belongs():
    rows = [run_row(sent=3, suppressed=1), run_row(sent=4, suppressed=0)]
    t = totals(rows)
    assert t == {"runs": 2, "matched": 94, "sent": 7, "suppressed": 1, "failed": 2}


def test_a_missing_field_does_not_break_a_report():
    """A run row written by an older version must still render — an owner's history is the last
    place to throw."""
    r = build({"at": NOW})
    assert r.sent == 0 and r.summary


def test_who_fired_it_is_carried():
    """The same campaign can be fired by a person and by the clock over its life, and 'why did
    this go out at 3am' starts with which one it was."""
    assert build(run_row(fired_by="owner")).fired_by == "owner"
