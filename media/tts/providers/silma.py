"""The provider actually in use — local, free, verified end to end (see media/tts/README.md).
Voice cloning against media/tts/reference/voice.wav + voice.txt, the licensed Arabic Speech Corpus
clip. Loads the model once, lazily, on first `synthesize()` call — importing this module (e.g. to
just check `TTS_PROVIDER`) never pays SILMA's own load cost for a provider that isn't being used.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REFERENCE_WAV = HERE / 'reference' / 'voice.wav'
REFERENCE_TXT = HERE / 'reference' / 'voice.txt'


class SilmaProvider:
    def __init__(self):
        self._tts = None
        self._ref_text = None

    def _ensure_loaded(self):
        if self._tts is not None:
            return
        if not REFERENCE_WAV.exists() or not REFERENCE_TXT.exists():
            raise RuntimeError(f'missing {REFERENCE_WAV} or {REFERENCE_TXT} — see media/tts/README.md.')
        from silma_tts.api import SilmaTTS  # imported here — loading the model is the expensive
        # part; a caller that only wants to KNOW the provider name (get_provider()) never pays it.
        self._tts = SilmaTTS()
        self._ref_text = REFERENCE_TXT.read_text(encoding='utf-8').strip()

    def synthesize(self, text: str, out_path: Path) -> None:
        self._ensure_loaded()
        self._tts.infer(
            ref_file=str(REFERENCE_WAV), ref_text=self._ref_text,
            gen_text=text, file_wave=str(out_path),
            seed=None, speed=1,
        )
