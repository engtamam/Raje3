# Where `voice.wav` came from

Utterance `ARA NORM 0033` from the **Arabic Speech Corpus** (Nawar Halabi, University of
Southampton) — <https://en.arabicspeechcorpus.com/>, licensed **CC BY 4.0**.

Picked via a script that read the zip's central directory over HTTP range requests (never
downloaded the full 1.2GB archive) and filtered for a single, undashed utterance in the 6–9 second
range — a dash in the corpus's own `.lab` transcript marks multiple joined sub-utterances, not one
clean sentence.

- **Transcript (Buckwalter, as shipped in the corpus):** `voice.buckwalter.txt`
- **Transcript (Arabic script, hand-transliterated for SILMA's `ref_text`):** `voice.txt` — "لعل
  الزمن الفاصل بين المرحلتين يوضح له ما استعصى على فهمه حينها"
- **Format:** 48kHz, 16-bit, mono PCM, 7.04s, -14.6dB mean / -3.1dB peak (no clipping, not too
  quiet — verified via `ffmpeg -af volumedetect`).

**Attribution, as CC BY 4.0 requires:** Arabic Speech Corpus by Nawar Halabi
(<https://en.arabicspeechcorpus.com/>), licensed under CC BY 4.0
(<https://creativecommons.org/licenses/by/4.0/>).
