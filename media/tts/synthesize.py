"""Generic narration synthesis — ONE tour's captions.json in, one WAV per caption line out.

NOTHING HERE NAMES A TOUR. This reads whatever `out/meta/<id>.captions.json` record-tour.mjs
already wrote (a plain list of `{text, startSeconds, endSeconds}`, in order) and calls SILMA once
per line — the same relationship every other engine file in this project has with a tour script:
it knows the SHAPE of the input, never the content of any particular tour. Adding a new tour never
touches this file.

WHAT THIS DOES NOT DO YET: retime anything. It writes each line's raw synthesized clip and its
REAL measured duration to a manifest — the input the audio-is-the-clock retiming pass (see
media/tts/README.md's own section on this) needs, not a finished narrated video. Muxing narration
into a tour's mp4 is that later, separate step.

Usage (from this project's root, using the conda env pynini forced onto Windows):
    C:/Users/TEMOA/miniconda3/envs/raje3-tts/python.exe media/tts/synthesize.py shop-dashboard
"""
from __future__ import annotations

import json
import sys
import time
import wave
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REFERENCE_WAV = HERE / "reference" / "voice.wav"
REFERENCE_TXT = HERE / "reference" / "voice.txt"


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
    if not REFERENCE_WAV.exists() or not REFERENCE_TXT.exists():
        sys.exit(f"missing {REFERENCE_WAV} or {REFERENCE_TXT} — see media/tts/README.md.")

    captions = json.loads(captions_file.read_text(encoding="utf-8"))
    if not captions:
        sys.exit(f"{captions_file} has no lines — nothing to narrate for {tour_id!r}.")

    out_dir = HERE / "out" / tour_id
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_text = REFERENCE_TXT.read_text(encoding="utf-8").strip()

    from silma_tts.api import SilmaTTS  # imported here, not at module load — this file must still
    # be readable (and its --help-equivalent usage error above still fire) even before silma-tts
    # is installed; the argv-count check runs first either way.

    print("loading SILMA…")
    t0 = time.time()
    tts = SilmaTTS()
    print(f"  ready in {time.time() - t0:.1f}s")

    manifest = []
    for i, cap in enumerate(captions):
        text = cap["text"]
        wav_path = out_dir / f"{i:03d}.wav"
        t0 = time.time()
        tts.infer(
            ref_file=str(REFERENCE_WAV), ref_text=ref_text,
            gen_text=text, file_wave=str(wav_path),
            seed=None, speed=1,
        )
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
