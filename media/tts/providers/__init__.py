"""Every provider speaks the same one-method interface — `synthesize(text, out_path)` writes a
real WAV file at `out_path` and returns nothing else. `synthesize.py` never imports a provider by
name; it reads `TTS_PROVIDER` (default "silma") and asks THIS file for whichever one that names.

WHY THIS EXISTS: Tamam's own ask, direct — "تجهّز البنية التحتية بحيث تبديل سريع مباشر" (set up
the plumbing so switching is fast and direct). Today there's one working provider (SILMA, local,
free, already verified end to end). ElevenLabs is wired the same way, ready the moment a paid
subscription with API access to library voices exists — switching providers for every future
recording is ONE environment variable (`TTS_PROVIDER=elevenlabs`), never a code change, never a
different call site in synthesize.py or retime-and-mux.mjs (which never knows or cares which
provider made a given WAV — it only reads the file back and measures its real duration).
"""
from __future__ import annotations

import os


def get_provider():
    name = os.environ.get('TTS_PROVIDER', 'silma').strip().lower()
    if name == 'silma':
        from . import silma
        return silma.SilmaProvider()
    if name == 'elevenlabs':
        from . import elevenlabs
        return elevenlabs.ElevenLabsProvider()
    raise ValueError(f'unknown TTS_PROVIDER {name!r} — expected "silma" or "elevenlabs"')
