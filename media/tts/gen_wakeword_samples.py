"""Ad-hoc real-voice test clips for the mobile wake-word ("راجِع") — NOT part of the tour
narration pipeline (synthesize.py), which only knows how to read a tour's captions.json. This
calls HamsaProvider directly for a fixed list of short phrases, since a wake-word test clip has
no tour, no caption, no timeline — just text in, WAV out.

Usage (same env HamsaProvider already reads via synthesize.py's own .env loader):
    C:/Users/TEMOA/miniconda3/envs/raje3-tts/python.exe media/tts/gen_wakeword_samples.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

PHRASES = {
    "ya_rajeh": "يا راجِع",
    "rajeh_bare": "راجِع",
    "hala_rajeh": "هلا راجِع",
}

OUT_DIR = HERE / "out" / "wakeword_samples"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()


def main() -> None:
    _load_dotenv(HERE / ".env")
    os.environ.setdefault("TTS_PROVIDER", "hamsa")
    from providers.hamsa import HamsaProvider

    provider = HamsaProvider()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in PHRASES.items():
        out_path = OUT_DIR / f"{name}.wav"
        print(f"synthesizing {name!r} ({text}) -> {out_path}")
        provider.synthesize(text, out_path)
        print(f"  done: {out_path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
