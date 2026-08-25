"""Wired, not yet active — needs a paid ElevenLabs subscription with API access to voices (the
free tier's API returned "Free users cannot use library voices via the API" on the one real call
tried against it; confirmed live, not assumed from docs, which don't state a tier requirement).
The moment a working subscription exists, this needs no code change: set TTS_PROVIDER=elevenlabs,
ELEVENLABS_API_KEY, and ELEVENLABS_VOICE_ID (see below), and synthesize.py picks this up exactly
the way it already uses SilmaProvider.

WHY A VOICE ID, NOT A REFERENCE CLIP — ElevenLabs' own model is a library of pre-existing voices
(or a cloned one, once created through their own UI/API separately — a step this file does not
do), addressed by an opaque ID, not a wav+transcript pair the way SILMA's cloning works. Nothing
here should ever try to reuse media/tts/reference/voice.wav for this provider; that pairing is
SILMA-specific.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

API_URL = 'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'


class ElevenLabsProvider:
    def __init__(self):
        self.api_key = os.environ.get('ELEVENLABS_API_KEY', '')
        self.voice_id = os.environ.get('ELEVENLABS_VOICE_ID', '')
        if not self.api_key or not self.voice_id:
            raise RuntimeError(
                'ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID must both be set — '
                'find a voice_id via GET https://api.elevenlabs.io/v1/voices once the '
                'subscription is active.')

    def synthesize(self, text: str, out_path: Path) -> None:
        req = urllib.request.Request(
            API_URL.format(voice_id=self.voice_id),
            data=json.dumps({
                'text': text,
                'model_id': 'eleven_multilingual_v2',
                'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75},
            }).encode('utf-8'),
            headers={'xi-api-key': self.api_key, 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                mp3_bytes = resp.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f'ElevenLabs generation failed ({exc.code}): {exc.read().decode(errors="replace")[:300]}') from exc

        # ElevenLabs RETURNS MP3, NOT WAV — synthesize.py's own duration measurement
        # (wav_duration_seconds, via wave.open()) needs real PCM, so this converts immediately
        # rather than making every downstream consumer handle two audio formats depending on
        # which provider ran. Same ffmpeg binary every other script in this project already
        # depends on; no new tool introduced for one provider.
        tmp_mp3 = out_path.with_suffix('.mp3')
        tmp_mp3.write_bytes(mp3_bytes)
        subprocess.run(
            ['ffmpeg', '-y', '-i', str(tmp_mp3), '-ar', '44100', '-ac', '1', str(out_path)],
            check=True, capture_output=True,
        )
        tmp_mp3.unlink()
