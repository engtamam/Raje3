"""core/soft_decline.py::is_decline — the pure heuristic, unit-tested directly, same shape as
tests/unit/test_frustration.py right beside it."""
from app.core.soft_decline import is_decline


def test_bare_no_is_a_decline():
    assert is_decline("لا")
    assert is_decline("لا شكراً")
    assert is_decline("لا شكرا")


def test_common_dismissive_phrases_are_declines():
    for text in ("ما ابغى", "ما أبغى", "لا ابغى", "بلاش", "خلاص", "مو الحين", "مو الآن", "بعدين",
                "no thanks", "No"):
        assert is_decline(text), text


def test_a_real_question_is_never_a_decline():
    for text in ("لا أدري، هل ينفع أستخدمها بأي خدمة؟", "متى يبدأ العرض؟",
                "لا بس ابغى اعرف اكثر عنها", "ما فهمت، ايش تقصد؟"):
        assert not is_decline(text), text


def test_empty_or_whitespace_is_not_a_decline():
    assert not is_decline("")
    assert not is_decline("   ")


def test_a_long_message_is_never_treated_as_a_bare_decline():
    """Anchored to SHORT messages on purpose — a long message that happens to contain the word
    "لا" somewhere is a real sentence, not a wave-off."""
    long_text = "لا أعتقد إني بحاجة لها الآن بس ممكن تفيدني لاحقاً، خلينا نشوف الأسعار أول"
    assert not is_decline(long_text)
