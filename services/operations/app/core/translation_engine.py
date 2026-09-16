"""The actual translator — a local, quantized NLLB-200 model via `ctranslate2`, never a cloud API
(see [[task-catalog-translation-phases]] memory: a shop's own service names and procedure text
never leave this box). This module is a PORT, same shape as `adapters/job_service.py`'s own
`NullJobService`/`HttpJobService` split: `NullTranslationEngine` is the honest default (every call
answers "nothing translated", never a crash, never a faked success) and `Nllb200TranslationEngine`
is the real one, picked by `TRANSLATION_ENGINE_DRIVER` in `container.py`.

SYNCHRONOUS, DELIBERATELY — `translate()` is CPU-bound model inference, not I/O; the caller
(`api/internal.py::translations_jobs_run`) is the one that knows to run it in a thread
(`run_in_threadpool`, the same convention `salla_jobs_run`'s own token-refresh call already uses),
so this module stays a plain, easily-unit-tested function with no event loop of its own.

CALLED FROM AT MOST ONE PLACE PER PROCESS AT A TIME — `translations_jobs_run`, itself reached only
through job-service's own schedule (a plain cron timer + push-dispatch, `deploy/hooks/
job-schedule.sh` — no separate scheduler, no k8s CronJob resource) and gated on
`core/server_load.py::is_idle` before it ever reaches this module at all. Model inference on a
weak, shared server is exactly the kind of cost that gate exists to keep off any path a shop owner
is actually waiting on.
"""
from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# FLORES-200 codes for every `operator-i18n.tsx` locale we ever translate INTO — Arabic is always
# the source, never a target (see `translations.TARGET_LOCALES`).
#
# `fil` -> `tgl_Latn` IS A DELIBERATE APPROXIMATION, DISCLOSED, NOT SILENT. NLLB-200 has no
# distinct code for Filipino; Tagalog is its own official regulated basis and the closest
# available target. Revisit only if NLLB ever ships a dedicated `fil_Latn`.
FLORES200 = {
    "ar": "arb_Arab",
    "en": "eng_Latn",
    "ur": "urd_Arab",
    "ha": "hau_Latn",
    "fil": "tgl_Latn",
    "bn": "ben_Beng",
}

# A REAL CEILING, NOT A GUESS — NLLB-200 was trained on sequences up to 512 SUBWORD tokens; a
# far shorter CHARACTER cap here is deliberately conservative (a shop's own service name or
# procedure step is a sentence, never a paragraph — see `Service.description`'s own 300-char
# field limit and `ProcedureStepIn.text`'s own 300-char one) so truncation is essentially never
# reached in practice, and on the rare pathological input this refuses to hang encoding an
# oversized sequence rather than translating a truncated fragment silently.
MAX_INPUT_CHARS = 2000


@runtime_checkable
class TranslationEngine(Protocol):
    driver: str

    def translate(self, text: str, target_locales: list[str]) -> dict[str, str]: ...


class TranslationEngineUnavailable(Exception):
    """Raised by `Nllb200TranslationEngine.translate` when the model could not be loaded — named
    rather than a silently empty dict, so `jobs/run` can tell "the model answered nothing useful
    for this text" (a real, if unusual, model outcome — see the empty-string handling below) apart
    from "there is no working model on this deployment at all" (every job in the batch should nack
    the same way, not each pay for its own failed load attempt)."""


class NullTranslationEngine:
    """No `TRANSLATION_MODEL_PATH` configured (or `ctranslate2`/`sentencepiece` not installed) —
    the honest default. Every `translations_jobs_run` call still runs, claims nothing (see that
    route's own pre-check), and every entry stays `pending` until a real engine is wired — the
    exact same "refuse honestly, never fake success" posture `NullJobService` already gives."""

    driver = "null"

    def translate(self, text: str, target_locales: list[str]) -> dict[str, str]:
        return {}


class Nllb200TranslationEngine:
    """A local NLLB-200-distilled-600M model, quantized (int8) via `ctranslate2` — see
    `entai2965/nllb-200-distilled-600M-ctranslate2` on Hugging Face for the exact conversion this
    expects `model_path` to point at (a `ctranslate2.Translator`-loadable directory) alongside
    `sp_model_path` (the shared `sentencepiece.bpe.model`, NOT the source-specific `transformers`
    tokenizer — this module never imports `transformers` at all, deliberately: a single
    `sentencepiece` model is the whole tokenizer NLLB needs, and skipping `transformers` keeps the
    dependency light enough for the weak-server, scale-to-zero posture this was built for.

    LAZY-LOADED, ONCE, ON FIRST `translate()` CALL — not at construction, so `container.py`
    building this object at boot never pays the load cost (or fails startup) for a route nothing
    has called yet. A load failure is cached (`self._broken`) so a deployment with a bad/missing
    model path fails FAST on every subsequent call in the same process rather than re-attempting
    an expensive load per job in a batch.
    """

    driver = "nllb200"

    def __init__(self, model_path: str, sp_model_path: str, *, device: str = "cpu") -> None:
        self._model_path = model_path
        self._sp_model_path = sp_model_path
        self._device = device
        self._translator = None
        self._sp = None
        self._broken = False

    def _ensure_loaded(self) -> None:
        if self._translator is not None and self._sp is not None:
            return
        if self._broken:
            raise TranslationEngineUnavailable("model previously failed to load")
        if not self._model_path or not self._sp_model_path:
            self._broken = True
            raise TranslationEngineUnavailable("TRANSLATION_MODEL_PATH/_SP_MODEL_PATH not set")
        try:
            import ctranslate2
            import sentencepiece as spm
        except ImportError as exc:
            self._broken = True
            raise TranslationEngineUnavailable(
                f"ctranslate2/sentencepiece not installed: {exc}") from exc
        try:
            self._translator = ctranslate2.Translator(self._model_path, device=self._device)
            self._sp = spm.SentencePieceProcessor(model_file=self._sp_model_path)
        except Exception as exc:                                          # noqa: BLE001
            self._broken = True
            self._translator = None
            self._sp = None
            logger.error("nllb200 model load failed: %s", exc)
            raise TranslationEngineUnavailable(str(exc)) from exc

    def translate(self, text: str, target_locales: list[str]) -> dict[str, str]:
        """Translate `text` (Arabic, always) into every locale in `target_locales`.

        ONE `Translator.translate_batch` CALL FOR THE WHOLE LOCALE SET, not one per locale — the
        source is tokenized once and every target shares that same encoded input, only the target
        prefix differs. A cheaper, and simpler-to-reason-about, batch than N separate calls.

        A LOCALE MISSING FROM THE RETURNED DICT IS A REAL, IF UNUSUAL, MODEL OUTCOME (an empty or
        whitespace-only hypothesis) — never raised as an error, since the OTHER locales in the same
        call may have succeeded perfectly. The caller (`translations_jobs_run`) decides what an
        incomplete result means for `TranslationEntry.status`; this method's only job is to be
        honest about exactly what came back.
        """
        text = (text or "").strip()
        if not text or not target_locales:
            return {}
        self._ensure_loaded()
        assert self._translator is not None and self._sp is not None  # narrows for the type-checker

        source = text[:MAX_INPUT_CHARS]
        source_tokens = ["arb_Arab"] + self._sp.encode(source, out_type=str) + ["</s>"]

        out: dict[str, str] = {}
        for locale in target_locales:
            flores = FLORES200.get(locale)
            if not flores:
                continue
            try:
                results = self._translator.translate_batch(
                    [source_tokens], target_prefix=[[flores]])
                tokens = results[0].hypotheses[0][1:]                     # drop the echoed prefix
                text_out = self._sp.decode(tokens).strip()
            except Exception as exc:                                     # noqa: BLE001
                # ONE LOCALE'S OWN INFERENCE FAILING (a decode edge case, a transient allocation
                # failure) NEVER TAKES THE REST OF THE BATCH DOWN WITH IT — logged, skipped,
                # exactly like an empty hypothesis; the entry simply stays `pending` for the
                # locales that did not come back, and a later run retries only those.
                logger.warning("nllb200 translate failed for locale=%s: %s", locale, exc)
                continue
            if text_out:
                out[locale] = text_out
        return out
