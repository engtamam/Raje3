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

## Resuming — everything below is ready to run

1. `media/tts/.venv/Scripts/pip install silma-tts`
2. Write the generic synthesis step: reads ONE tour's `captions.json`, calls SILMA once per line
   against `reference/voice.wav` + `reference/voice.txt`, writes timed WAV segments, done — no
   tour-specific knowledge belongs in that script, same as every other engine file under
   `media/tours/`.
