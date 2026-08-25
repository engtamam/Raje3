"""Generic narration synthesis — ONE tour's captions.json in, one WAV per caption line out.

NOTHING HERE NAMES A TOUR. This reads whatever `out/meta/<id>.captions.json` record-tour.mjs
already wrote (a plain list of `{text, startSeconds, endSeconds}`, in order) and calls whichever
TTS PROVIDER `TTS_PROVIDER` names once per line — the same relationship every other engine file in
this project has with a tour script: it knows the SHAPE of the input, never the content of any
particular tour, and now not even WHICH ENGINE speaks it. Adding a new tour never touches this
file; neither does switching narration engines.

NOTHING HERE NAMES A PROVIDER EITHER — see media/tts/providers/__init__.py's own docstring.
Default is SILMA (local, free, verified end to end); `TTS_PROVIDER=elevenlabs` switches to
ElevenLabs the moment a working paid subscription exists, no code change here or anywhere else.

WHAT THIS DOES NOT DO YET: retime anything. It writes each line's raw synthesized clip and its
REAL measured duration to a manifest — the input the audio-is-the-clock retiming pass (see
media/tts/README.md's own section on this) needs, not a finished narrated video. Muxing narration
into a tour's mp4 is that later, separate step.

Usage (from this project's root, using the conda env pynini forced onto Windows):
    C:/Users/TEMOA/miniconda3/envs/raje3-tts/python.exe media/tts/synthesize.py shop-dashboard
    TTS_PROVIDER=elevenlabs ELEVENLABS_API_KEY=... ELEVENLABS_VOICE_ID=... \
        C:/Users/TEMOA/miniconda3/envs/raje3-tts/python.exe media/tts/synthesize.py shop-dashboard
"""
from __future__ import annotations

import json
import sys
import time
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))  # so `from providers import get_provider` resolves regardless of cwd
ROOT = HERE.parent.parent


def wav_duration_seconds(path: Path) -> float:
    """Read the REAL rendered length back from the file SILMA just wrote — never trust an
    estimate when the actual answer is one wave.open() away, same principle overlay.mjs's own
    say() already applies to caption line-counting (measure the real thing, don't predict it)."""
    with wave.open(str(path), "rb") as f:
        return f.getnframes() / f.getframerate()


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(f"usage: {sys.argv[0]} <tour-id>  (e.g. shop-dashboard, getting-started)")
    tour_id = sys.argv[1]

    captions_file = ROOT / "media" / "tours" / "out" / "meta" / f"{tour_id}.captions.json"
    if not captions_file.exists():
        sys.exit(
            f"no {captions_file} — record the tour first (it always writes this file, even "
            f"when you don't need TTS): node media/tours/record-tour.mjs media/tours/scripts/{tour_id}.mjs")
    captions = json.loads(captions_file.read_text(encoding="utf-8"))
    if not captions:
        sys.exit(f"{captions_file} has no lines — nothing to narrate for {tour_id!r}.")

    out_dir = HERE / "out" / tour_id
    out_dir.mkdir(parents=True, exist_ok=True)

    from providers import get_provider  # imported here, not at module load — this file must still
    # be readable (and its --help-equivalent usage error above still fire) even before a
    # provider's own dependencies (silma-tts, etc.) are installed; the argv-count check runs first
    # either way. sys.path needs this directory on it for a bare `import providers` to resolve —
    # see the sys.path.insert right below main()'s own definition.

    print("loading TTS provider…")
    t0 = time.time()
    provider = get_provider()
    print(f"  ready in {time.time() - t0:.1f}s")

    manifest = []
    for i, cap in enumerate(captions):
        text = cap["text"]
        wav_path = out_dir / f"{i:03d}.wav"
        t0 = time.time()
        provider.synthesize(text, wav_path)
        gen_seconds = time.time() - t0
        real_seconds = wav_duration_seconds(wav_path)
        print(f"  [{i + 1}/{len(captions)}] {real_seconds:.2f}s audio ({gen_seconds:.1f}s to "
              f"generate) — {text}")
        manifest.append({
            "index": i, "text": text, "wav": wav_path.name,
            "audioSeconds": round(real_seconds, 3),
            # THE ORIGINAL RECORDED WINDOW, CARRIED THROUGH — the retiming pass compares this
            # against audioSeconds to decide whether the video needs to hold or can stay as-is;
            # this script's own job stops at handing it that comparison, never doing it itself.
            "recordedStartSeconds": cap["startSeconds"], "recordedEndSeconds": cap["endSeconds"],
        })

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✔ {manifest_path} · {len(manifest)} line(s) synthesized")


if __name__ == "__main__":
    main()
