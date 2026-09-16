"""`NullTranslationEngine` and `Nllb200TranslationEngine` — the port contract itself, and the
model-unavailable paths that never touch a real model (no ctranslate2/sentencepiece dependency in
this test environment, deliberately — see pyproject.toml's own `translation` extra).
"""
from __future__ import annotations

import pytest

from app.core.translation_engine import (
    FLORES200, NullTranslationEngine, Nllb200TranslationEngine, TranslationEngineUnavailable,
)


def test_null_engine_always_answers_empty():
    engine = NullTranslationEngine()
    assert engine.translate("غسيل خارجي", ["en", "ur"]) == {}


def test_null_engine_driver_name():
    assert NullTranslationEngine().driver == "null"


def test_flores200_covers_every_target_locale():
    from app.core.translations import TARGET_LOCALES
    for locale in TARGET_LOCALES:
        assert locale in FLORES200, locale


def test_nllb_refuses_honestly_with_no_model_path_configured():
    engine = Nllb200TranslationEngine("", "")
    with pytest.raises(TranslationEngineUnavailable):
        engine.translate("غسيل خارجي", ["en"])


def test_nllb_caches_the_failed_load_rather_than_retrying_every_call():
    engine = Nllb200TranslationEngine("/no/such/path", "/no/such/path")
    with pytest.raises(TranslationEngineUnavailable):
        engine.translate("a", ["en"])
    assert engine._broken is True
    # second call fails fast on the cached flag, never re-attempts a real load
    with pytest.raises(TranslationEngineUnavailable):
        engine.translate("b", ["en"])


def test_empty_text_answers_empty_without_touching_the_model():
    engine = Nllb200TranslationEngine("/no/such/path", "/no/such/path")
    assert engine.translate("", ["en"]) == {}
    assert engine.translate("   ", ["en"]) == {}
    # never marked broken — the empty-text short-circuit runs before `_ensure_loaded`
    assert engine._broken is False
