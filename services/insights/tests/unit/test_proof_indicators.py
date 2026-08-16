"""proofs 2, 3 and 4 — the three numbers that describe our own effect, and must not flatter it."""
from app.core import indicators as I
from app.core import holdout as H

DAY = 86400
NOW = 1_800_000_000


# ── proof 2 — the holdout comparison ───────────────────────────────────────────────────────────
def test_the_comparison_refuses_a_thin_sample():
    """Fifteen a side is already thin; below it one returning customer moves the answer by seven
    points, and we would be claiming a triumph on the strength of one man changing his oil."""
    visits = [{"subject_ref": f"c{i}", "occurred_at": NOW - 10 * DAY} for i in range(12)]
    r = I.holdout_comparison(visits, tenant="shop-1", now=NOW, enabled=True)
    assert r["ready"] is False and r["reason"] == "learning"


def test_the_comparison_reports_both_rates_and_no_verdict():
    visits = []
    for i in range(500):
        ref = f"c{i}"
        visits.append({"subject_ref": ref, "occurred_at": NOW - 100 * DAY})
        held = H.is_holdout("shop-1", ref)
        if (not held and i % 2 == 0) or (held and i % 5 == 0):
            visits.append({"subject_ref": ref, "occurred_at": NOW - 20 * DAY})
    r = I.holdout_comparison(visits, tenant="shop-1", now=NOW, enabled=True)
    assert r["ready"] is True
    assert r["reached_rate"] > r["held_rate"]
    assert r["gap"] == round(r["reached_rate"] - r["held_rate"], 3)
    # no claim, no adjective, no "raje3 improved you by": just the two numbers
    assert set(r) == {"ready", "held", "reached", "held_rate", "reached_rate", "gap", "window_days"}


# ── proof 3 — visits credited to a message ─────────────────────────────────────────────────────
def credited(visits, sends, **kw):
    """The count, from a read of the send log that SUCCEEDED. `have_log` is the caller stating it
    actually read the log — see ي-3 — and it is the ordinary case these tests are about."""
    return I.returned_after_reminder(visits, sends, now=NOW, have_log=True, **kw)


def test_a_customer_who_had_already_come_back_is_not_credited():
    """The self-flattery this whole indicator is written against: counting somebody who was in the
    shop last week, got a message, came again, and is then read as proof the message worked."""
    visits = [{"subject_ref": "a", "occurred_at": NOW - 9 * DAY},   # before the message
              {"subject_ref": "a", "occurred_at": NOW - 2 * DAY}]   # after it
    sends = [{"subject_ref": "a", "at": NOW - 5 * DAY}]
    assert credited(visits, sends)["visits"] == 0


def test_a_visit_inside_the_window_is_credited_once():
    visits = [{"subject_ref": "b", "occurred_at": NOW - 3 * DAY}]
    sends = [{"subject_ref": "b", "at": NOW - 6 * DAY}]
    assert credited(visits, sends)["visits"] == 1


def test_a_visit_long_after_the_message_is_not_ours():
    visits = [{"subject_ref": "c", "occurred_at": NOW - 1 * DAY}]
    sends = [{"subject_ref": "c", "at": NOW - 25 * DAY}]     # 24 days apart, window is 14
    assert credited(visits, sends)["visits"] == 0


def test_one_visit_after_two_messages_is_one_visit():
    """ي-4. The credit loop ran over MESSAGES, so a customer who got a reminder on Sunday and
    another on Tuesday and walked in on Wednesday was TWO returned visits. One person, one visit,
    counted twice — and the inflation scales with messages-per-customer, so it is worst at the
    shops sending most. The owner multiplies this number by his average bill to decide whether to
    renew, which is what makes an inflated one expensive rather than untidy."""
    visits = [{"subject_ref": "d", "occurred_at": NOW - 2 * DAY}]
    sends = [{"subject_ref": "d", "at": NOW - 6 * DAY},
             {"subject_ref": "d", "at": NOW - 4 * DAY},
             {"subject_ref": "d", "at": NOW - 3 * DAY}]
    assert credited(visits, sends)["visits"] == 1


def test_two_separate_walk_ins_after_two_messages_are_two():
    """The dedupe is on the VISIT, not on the customer — a person who came back twice, each time
    after a message, really did come back twice, and flattening him to one would undercount."""
    visits = [{"subject_ref": "e", "occurred_at": NOW - 20 * DAY},
              {"subject_ref": "e", "occurred_at": NOW - 2 * DAY}]
    sends = [{"subject_ref": "e", "at": NOW - 22 * DAY},
             {"subject_ref": "e", "at": NOW - 4 * DAY}]
    assert credited(visits, sends)["visits"] == 2


def test_an_unreadable_send_log_refuses_rather_than_printing_a_confident_zero():
    """ي-3. `reminders` holds the only send log there is, and when the read failed the peer
    answered `{"sends": [], "sent_count": 0}` — character for character what a shop that has never
    sent a message looks like. So «0 زيارة عادت بعد رسالة» went on the dashboard: our outage
    printed as his engine's result, in the one number that argues for renewal — while the card
    beside it, on the identical failure, already said «we cannot measure yet»."""
    visits = [{"subject_ref": "f", "occurred_at": NOW - 2 * DAY}]
    out = I.returned_after_reminder(visits, [], now=NOW, have_log=False)
    assert out["ready"] is False and out["reason"] == "no_send_log"
    assert "visits" not in out, "a refusal must not carry a number to be read as the answer"


def test_a_capped_send_log_says_the_count_is_a_floor():
    """ي-6. `reminders` exports `truncated` and it was fetched and dropped. Older sends are missing
    from the join, so the credit can only be low — and the shops that hit the cap are the busy
    ones, which is exactly where the number is read hardest."""
    visits = [{"subject_ref": "g", "occurred_at": NOW - 2 * DAY}]
    sends = [{"subject_ref": "g", "at": NOW - 5 * DAY}]
    assert credited(visits, sends, partial_log=True)["partial"] is True
    assert credited(visits, sends)["partial"] is False


# ── proof 4 — stops per thousand ───────────────────────────────────────────────────────────────
def test_no_warning_before_two_hundred_messages():
    """One stop in fifty is twenty per thousand — a red light on a shop that has done nothing."""
    r = I.opt_out_rate(50, 1, have_log=True)
    assert r["ready"] is False and r["need"] == 200 and r["reason"] == "too_few_sends"


def test_the_rate_is_per_thousand_and_rounded_once():
    r = I.opt_out_rate(1000, 7, have_log=True)
    assert r["ready"] is True and r["rate"] == 7.0


def test_an_unread_log_is_not_a_shop_that_sent_nothing():
    """ي-3, the other half. An unreadable log reached this function as `sent_count = 0` — the
    `int(x or 0)` that turns a missing field into a policy — and the card then told a shop which
    had sent forty thousand messages «أرسلت 0». The two states now have two sentences."""
    unread = I.opt_out_rate(0, 0, have_log=False)
    quiet = I.opt_out_rate(0, 0, have_log=True)
    assert unread["ready"] is False and unread["reason"] == "no_send_log"
    assert quiet["ready"] is False and quiet["reason"] == "too_few_sends"
    assert "sent" not in unread, "we do not know what he sent — saying 0 is the defect"


def test_a_capped_log_names_its_sample():
    """ي-6. Both halves of the rate are counted over the newest slice when the log is capped, so
    «لكل ألف رسالة» is true of a shorter period than the label implies. The flag travels with the
    number so the screen can say which — a card that goes quietest at the shops sending most is
    the opposite of what it is for."""
    assert I.opt_out_rate(5000, 40, have_log=True, partial_log=True)["partial"] is True
    assert I.opt_out_rate(5000, 40, have_log=True)["partial"] is False


def test_the_card_refuses_when_nothing_is_actually_withheld():
    """THE FAILURE THAT FLATTERS US, which is the direction nobody checks.

    This service splits customers by the same hash `reminders` uses — but if the holdout is switched
    OFF there, the «held» tenth received every message the rest did. The two rates then differ only
    by noise, and with enough traffic the card stops refusing and starts publishing that noise as
    our engine's effect: the one number in this product that is not our word for our own work,
    manufactured out of nothing.
    """
    from app.core.indicators import holdout_comparison

    visits = [{"subject_ref": f"sub_{i:05d}", "occurred_at": 1_700_000_000, "customer_id": f"c{i}"}
              for i in range(400)]

    out = holdout_comparison(visits, tenant="t1", now=1_700_100_000, enabled=False)

    assert out["ready"] is False
    assert out["reason"] == "holdout_off", "«لم يُقَس» is a different answer from «لم يكتمل القياس»"


def test_it_measures_the_same_tenth_reminders_withheld_from():
    """The share is configuration on both sides now. If they ever diverge, the group called «held»
    is not the group that was withheld from — and the comparison is between two sets of strangers."""
    import inspect

    from app.core import tick as T

    src = inspect.getsource(T)
    assert "share=self._holdout_share" in src, "the configured share must reach the comparison"
