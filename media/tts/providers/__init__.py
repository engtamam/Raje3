"""Every provider speaks the same one-method interface — `synthesize(text, out_path)` writes a
real WAV file at `out_path` and returns nothing else. `synthesize.py` never imports a provider by
name; it reads `TTS_PROVIDER` (default "silma") and asks THIS file for whichever one that names.

WHY THIS EXISTS: a direct ask — "تجهّز البنية التحتية بحيث تبديل سريع مباشر" (set up
the plumbing so switching is fast and direct). SILMA (local, free) was the first working
provider, already verified end to end. ElevenLabs is wired the same way, ready the moment a paid
subscription with API access to library voices exists. Hamsa is wired and CONFIRMED LIVE (a real
Saudi/Gulf dialect voice, not MSA or Egyptian standing in for one — see hamsa.py's own header).
Switching providers for every future recording is ONE environment variable
(`TTS_PROVIDER=hamsa`), never a code change, never a different call site in synthesize.py or
retime-and-mux.mjs (which never knows or cares which provider made a given WAV — it only reads
the file back and measures its real duration).
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
    if name == 'hamsa':
        from . import hamsa
        return hamsa.HamsaProvider()
    raise ValueError(f'unknown TTS_PROVIDER {name!r} — expected "silma", "elevenlabs" or "hamsa"')
