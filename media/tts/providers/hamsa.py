"""Hamsa (tryhamsa.com) — Arabic-dialect voice AI, the one provider with a real Saudi (`ksa`)
voice rather than MSA or Egyptian pretending to be Gulf. Wired the same way ElevenLabs is: an
opaque voice (`speaker`) addressed by name, not a reference clip — no reuse of SILMA's cloning
pairing here.

API CONFIRMED LIVE against the Realtime endpoint (POST /v1/realtime/tts, `Authorization: Token
<key>`), not assumed from docs alone — see the test call this file's own history records. Response
is raw `audio/wav` bytes on success, JSON error body on failure.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

API_URL = 'https://api.tryhamsa.com/v1/realtime/tts'


class HamsaProvider:
    def __init__(self):
        self.api_key = os.environ.get('HAMSA_API_KEY', '')
        # `ksa` is the whole reason this provider exists — a real Gulf/Saudi dialect, not MSA
        # dressed up as one. `HAMSA_DIALECT`/`HAMSA_SPEAKER` stay overridable for the other 14
        # dialects this same account can reach, with no code change.
        self.dialect = os.environ.get('HAMSA_DIALECT', 'ksa')
        self.speaker = os.environ.get('HAMSA_SPEAKER', 'Hiba')
        if not self.api_key:
            raise RuntimeError('HAMSA_API_KEY must be set — from the Hamsa dashboard.')

    def synthesize(self, text: str, out_path: Path) -> None:
        req = urllib.request.Request(
            API_URL,
            data=json.dumps({
                'text': text, 'speaker': self.speaker, 'dialect': self.dialect,
                'sampleRate': '16k',
            }).encode('utf-8'),
            headers={'Authorization': f'Token {self.api_key}', 'Content-Type': 'application/json',
                    # Cloudflare in front of api.tryhamsa.com returns 403 (error 1010) to a bare
                    # urllib request with no User-Agent — confirmed live, not a documented
                    # requirement. A real browser UA clears it; this is bot-signature filtering,
                    # not an API-key or payload problem.
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                                  '(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                wav_bytes = resp.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'Hamsa generation failed ({exc.code}): '
                              f'{exc.read().decode(errors="replace")[:300]}') from exc

        # ALREADY WAV, BUT AT 16kHz — normalized to the same 44100/mono every other provider here
        # produces, so synthesize.py's downstream (retime-and-mux.mjs) never has to special-case
        # a provider by its sample rate.
        tmp_raw = out_path.with_suffix('.raw.wav')
        tmp_raw.write_bytes(wav_bytes)
        subprocess.run(
            ['ffmpeg', '-y', '-i', str(tmp_raw), '-ar', '44100', '-ac', '1', str(out_path)],
            check=True, capture_output=True,
        )
        tmp_raw.unlink()
