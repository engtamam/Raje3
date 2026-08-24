/**
 * THE AUDIO IS THE CLOCK, NOT THE VIDEO — see media/tts/README.md's own section on why. This
 * takes a tour's already-assembled silent mp4, its captions.json (real recorded timing — a
 * fallback/minimum, never the final one), and synthesize.py's own manifest.json (the REAL,
 * measured duration of each generated narration clip), and produces the one thing this project
 * didn't have before: a video whose pace actually follows the voice.
 *
 * THE ONLY RULE: a caption's on-screen window becomes exactly its audio's length. Never shorter
 * (never cut narration to fit an old, incidental recording length) — where the audio runs longer
 * than the original recorded segment, the video HOLDS (freezes its own last frame) for the
 * difference rather than racing text ahead of a voice still speaking. Where the audio is shorter,
 * the original segment length is kept as-is (a caption disappearing before its screen segment
 * ends is fine — a caption's own display window is driven by the audio regardless, downstream of
 * this script's own timeline; this script only ever decides how long the VIDEO stays on each
 * beat, never trims one short).
 *
 * NOTHING HERE NAMES A TOUR — same rule every engine file in this project follows. It reads
 * whatever `out/meta/<id>.captions.json` and `media/tts/out/<id>/manifest.json` already exist for
 * a given id; a new tour or new caption wording never touches this file.
 *
 * Usage:
 *   node media/tts/retime-and-mux.mjs <tour-id>
 */
import { existsSync, readFileSync, mkdtempSync, rmSync } from 'node:fs';
import { readFile, writeFile } from 'node:fs/promises';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';

import { findFfmpeg } from '../lib/ffmpeg.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '../..');

const tourId = process.argv[2];
if (!tourId) {
  console.error(`usage: node ${process.argv[1]} <tour-id>`);
  process.exit(1);
}

// TOUR VIDEOS ARE NAMED BY TITLE (record-tour.mjs's own filenameBase), NOT ID — captions.json
// and manifest.json are both named by id instead. Nothing reliably maps title back to id (a
// title can change without the id changing, or vice versa), so this asks for the exact path
// rather than guessing by scanning `out/*.mp4` — the console log from the SAME recording run
// that wrote captions.json already names it, one line up from the one that names the id.
const videoIn = process.env.TOUR_VIDEO;
if (!videoIn) {
  console.error(`set TOUR_VIDEO to the recorded mp4's exact path, e.g.:\n` +
    `  TOUR_VIDEO="media/tours/out/محلّي — كل مؤشراتك بالتفصيل.mp4" node ${process.argv[1]} ${tourId}`);
  process.exit(1);
}

const outDir = join(ROOT, 'media', 'tours', 'out');
const captionsPath = join(outDir, 'meta', `${tourId}.captions.json`);
const manifestPath = join(HERE, 'out', tourId, 'manifest.json');

for (const [label, path] of [['tour video', videoIn], ['captions', captionsPath], ['audio manifest', manifestPath]]) {
  if (!existsSync(path)) {
    console.error(`missing ${label}: ${path}\nRecord the tour, then run synthesize.py, before this script.`);
    process.exit(1);
  }
}

async function main() {
  const captions = JSON.parse(await readFile(captionsPath, 'utf8'));
  const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
  if (captions.length !== manifest.length) {
    throw new Error(`captions.json has ${captions.length} line(s) but manifest.json has ${manifest.length} — re-run synthesize.py against the current recording before this script.`);
  }

  const ffmpeg = findFfmpeg();
  const tmp = mkdtempSync(join(tmpdir(), 'raje3-retime-'));
  const videoDur = probeDuration(ffmpeg, videoIn);

  // ── build the ordered interval list: gap, caption, gap, caption, …, gap ────────────────────
  const intervals = [];
  let cursor = 0;
  for (const cap of manifest) {
    const start = cap.recordedStartSeconds;
    const end = cap.recordedEndSeconds;
    if (start > cursor) intervals.push({ kind: 'gap', start: cursor, end: start });
    const originalDur = end - start;
    const hold = Math.max(0, cap.audioSeconds - originalDur);
    intervals.push({
      kind: 'caption', start, end, hold,
      wav: join(HERE, 'out', tourId, cap.wav),
      audioSeconds: cap.audioSeconds,
    });
    cursor = end;
  }
  if (cursor < videoDur) intervals.push({ kind: 'gap', start: cursor, end: videoDur });

  // ── video: trim each interval, hold (freeze last frame) where narration outlasts it ────────
  const videoParts = [];
  const filterVideo = [];
  intervals.forEach((iv, i) => {
    const label = `v${i}`;
    const trimmed = `t${i}`;
    filterVideo.push(`[0:v]trim=${iv.start}:${iv.end},setpts=PTS-STARTPTS[${trimmed}]`);
    if (iv.kind === 'caption' && iv.hold > 0) {
      filterVideo.push(`[${trimmed}]tpad=stop_mode=clone:stop_duration=${iv.hold.toFixed(3)}[${label}]`);
    } else {
      filterVideo.push(`[${trimmed}]copy[${label}]`);
    }
    videoParts.push(`[${label}]`);
  });
  filterVideo.push(`${videoParts.join('')}concat=n=${intervals.length}:v=1:a=0[vout]`);

  // ── audio: silence for gaps, real narration (padded to the held length) for captions ───────
  const audioInputs = [];
  const filterAudio = [];
  let inputIndex = 1; // 0 is the video
  intervals.forEach((iv, i) => {
    const label = `a${i}`;
    const dur = iv.kind === 'gap' ? (iv.end - iv.start) : (iv.end - iv.start + iv.hold);
    if (iv.kind === 'gap') {
      filterAudio.push(`anullsrc=r=44100:cl=stereo:d=${dur.toFixed(3)}[${label}]`);
    } else {
      audioInputs.push('-i', iv.wav);
      // apad, then trim to EXACTLY `dur` — a real synthesized clip can be a few ms shorter or
      // longer than its own measured duration once resampled/reformatted here; padding first and
      // trimming after guarantees this segment's audio and its paired video segment agree to the
      // millisecond, which is the entire point of this script.
      filterAudio.push(`[${inputIndex}:a]aformat=sample_rates=44100:channel_layouts=stereo,apad,atrim=0:${dur.toFixed(3)}[${label}]`);
      inputIndex += 1;
    }
  });
  const audioParts = intervals.map((_, i) => `[a${i}]`).join('');
  filterAudio.push(`${audioParts}concat=n=${intervals.length}:v=0:a=1[aout]`);

  const filterComplex = [...filterVideo, ...filterAudio].join(';');
  const finalOut = videoIn.replace(/\.mp4$/, ' — بصوت.mp4');

  const argv = [
    '-y', '-i', videoIn, ...audioInputs,
    '-filter_complex', filterComplex,
    '-map', '[vout]', '-map', '[aout]',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-shortest',
    finalOut,
  ];
  const res = spawnSync(ffmpeg, argv, { stdio: 'inherit' });
  rmSync(tmp, { recursive: true, force: true });
  if (res.status !== 0) throw new Error(`ffmpeg exited ${res.status}`);

  const originalHold = intervals.filter((iv) => iv.kind === 'caption' && iv.hold > 0);
  console.log(`✔ ${finalOut}`);
  console.log(`  ${originalHold.length}/${manifest.length} caption(s) needed a hold (narration outlasted the recorded segment) — longest: ${
    originalHold.length ? Math.max(...originalHold.map((iv) => iv.hold)).toFixed(2) : 0}s`);
}

function probeDuration(ffmpeg, file) {
  const ffprobe = ffmpeg.replace(/ffmpeg(\.exe)?$/, 'ffprobe$1');
  const res = spawnSync(ffprobe, [
    '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file,
  ]);
  return parseFloat(res.stdout.toString().trim());
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
