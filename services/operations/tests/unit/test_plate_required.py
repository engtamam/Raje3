"""A vehicle sector must not be able to record a visit with no plate — and the rule must be one a
man with a customer waiting can actually satisfy."""
# arabic-indic-digits: intentional — a plate typed in Arabic-Indic digits is the input under test.
from app.core import plate as P


def test_a_real_plate_passes_in_either_script():
    assert P.is_plausible("ا ب ج 1234")
    assert P.is_plausible("ABJ 1234")
    assert P.is_plausible("ا ب ج ٤٥٦")          # Arabic-Indic digits are digits


def test_the_two_ways_the_box_actually_gets_abused():
    assert not P.is_plausible("")
    assert not P.is_plausible("   ")
    assert not P.is_plausible("----")
    assert not P.is_plausible("0501234567")     # a phone typed into the wrong box
    assert not P.is_plausible("ا ب ج")          # letters with no number


def test_arabic_digits_are_normalised_once_on_the_way_in():
    """Stored twice in two scripts is a car nobody can find."""
    assert P.normalise("ا ب ج ٤٥٦") == "ا ب ج 456"
    assert P.normalise("  ABJ   1234 ") == "ABJ 1234"


def test_a_temporary_or_gulf_plate_is_not_refused():
    """The reason there is no format check: these are all real, and none matches the Saudi form."""
    for real in ("TRN 88", "K 7", "٩٩ ب", "77 XYZ"):
        assert P.is_plausible(real), real
