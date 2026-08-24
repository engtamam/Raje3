# TTS — narrating the tours

Every tour already writes `out/meta/<id>.captions.json` — the raw sentence, start second, and end
second of every caption in the tour, in order. That file is the entire input a text-to-speech pass
over a tour needs; nothing else in this project changes to add voice.

## What was actually decided

**Model: [SILMA TTS](https://huggingface.co/silma-ai/silma-tts) — Apache-2.0, code AND weights,
verified directly against the model page.** Real commercial use, no restriction, no attribution
requirement even.

This took three tries to land on. `NAMAA-Saudi-TTS-V2` (Saudi Najdi dialect, looked ideal) turned
out to be `CC-BY-NC-SA-4.0` — non-commercial only, wrong for a paid product's own tutorials. Meta's
`MMS-TTS-Ara` looked like the safe fallback and turned out to be `CC-BY-NC 4.0` too. Every dialect-
aware Arabic TTS model checked shares the same non-commercial license; SILMA (MSA only, no
documented Saudi dialect) is the one that is actually free to use here.

## The reference clip this uses — never a real person's voice

**Every model in this class — SILMA included — is voice CLONING, not a fixed built-in voice.**
There is no "pick a voice and go" option among the models good enough to sound real; each one
needs a genuine reference clip to clone from, every time it generates anything. Tamam's own call:
never his voice, never anyone at Raje3's — a licensed clip from a corpus built for exactly this.

`media/tts/reference/voice.wav` is utterance `ARA NORM 0033` from the **Arabic Speech Corpus**
(Nawar Halabi) — CC BY 4.0, a single professional speaker recorded in a real studio specifically
for TTS research. Picked over an HTTP range-request read of the corpus zip's central directory
(never downloaded the full 1.2GB archive) for a clean, undashed, 6–9 second single sentence. Full
provenance and required attribution: `media/tts/reference/SOURCE.md`.

## THE AUDIO IS THE CLOCK, NOT THE VIDEO — Tamam's own requirement, explicit

Every caption's `startSeconds`/`endSeconds` in `captions.json` today comes from how long the
RECORDING happened to take at each step — real, but incidental; nothing about it was ever tuned
against how long a sentence takes to actually SAY. Once real narration exists, that stops being
good enough: **a caption must appear the instant its narration starts and disappear the instant it
ends, and the video itself must stretch or hold to match — never the other way around.** A fast
sentence keeps the pace it already has; a slow one holds the frame (freeze the last one, or slow
the step's own settle wait) until the narration actually finishes, rather than cutting audio off
or racing text ahead of a voice still speaking.

Concretely, once synthesis exists: **`captions.json`'s recorded seconds become a fallback/minimum,
never the final timing.** The real per-tour build order becomes:

1. Synthesize every caption's audio first (SILMA, against `reference/voice.wav`).
2. Measure each clip's REAL rendered duration (not estimated — read the actual generated WAV).
3. Re-derive the tour's frame timeline from those durations, not from the original capture: a
   caption's on-screen window becomes exactly its audio's length; wherever narration outlasts the
   original recorded segment, insert a hold (frozen final frame of that segment) rather than
   letting the caption vanish mid-sentence or the audio play into silent screen.
4. Only THEN mux — narration audio replaces/joins the sfx track, and the final mp4's total length
   is whatever step 3 actually produced, not the original recording's own length.

This is a real second pass over `record-tour.mjs`'s output, not a detail inside the synthesis
script alone — flagging it here now so it isn't rediscovered as a surprise once SILMA is actually
generating audio.

## Resuming — everything below is ready to run

1. `media/tts/.venv/Scripts/pip install silma-tts`
2. Write the generic synthesis step: reads ONE tour's `captions.json`, calls SILMA once per line
   against `reference/voice.wav` + `reference/voice.txt`, writes timed WAV segments, done — no
   tour-specific knowledge belongs in that script, same as every other engine file under
   `media/tours/`.
3. Write the audio-is-the-clock retiming pass described above, BEFORE muxing narration into any
   real tour's video — skipping it ships captions/frames timed against the wrong clock.
