/**
 * One place that knows where ffmpeg lives — shared by every recorder (the ad's frozen-clock one
 * and the live tours' real-time one), so a fix here fixes both instead of one at a time.
 *
 * winget installs it to a folder that isn't on PATH until the terminal is closed and reopened —
 * a manual step that's easy to forget, so the very first run after installing fails and reads
 * as a defect in the recorder rather than an unfinished install. Searching for it directly here
 * means that step is never required.
 */
import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

export function findFfmpeg() {
  if (process.env.FFMPEG) return process.env.FFMPEG;
  const home = process.env.USERPROFILE || process.env.HOME || '';
  const wingetRoot = join(home, 'AppData/Local/Microsoft/WinGet/Packages');
  try {
    for (const dir of readdirSync(wingetRoot)) {
      if (!dir.startsWith('Gyan.FFmpeg')) continue;
      for (const build of readdirSync(join(wingetRoot, dir))) {
        const exe = join(wingetRoot, dir, build, 'bin', 'ffmpeg.exe');
        if (existsSync(exe)) return exe;
      }
    }
  } catch { /* no such folder — fall through to PATH, which is the case on Linux/macOS anyway */ }
  return 'ffmpeg';
}

/** Assemble numbered PNG frames into the one mp4 format every recorder needs — yuv420p, or
 *  Instagram and WhatsApp refuse the file while YouTube plays it with shifted colors. */
export function assembleMp4({ ffmpeg, framesDir, fps, out, run }) {
  return run(ffmpeg, [
    '-y', '-framerate', String(fps),
    '-i', join(framesDir, '%06d.png'),
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'slow',
    '-movflags', '+faststart',
    out,
  ]);
}

/**
 * Mixes a click sound in at each given timestamp, in place — no background music, ever (the
 * brief was explicit: sound effects only, matching each action, nothing playing underneath).
 * `sfxFile` plays once per entry in `atSeconds`; `-shortest` caps the result at the SILENT
 * video's own length so a click landing near the very end can never extend the file by even a
 * frame. Re-encodes audio only (`-c:v copy`) — the video stream itself, already correct, is
 * never touched a second time.
 */
export function mixSfx({ ffmpeg, videoIn, sfxFile, atSeconds, videoOut, run }) {
  if (!atSeconds.length) return Promise.resolve();
  const inputs = ['-i', videoIn];
  const branches = [];
  atSeconds.forEach((s, i) => {
    inputs.push('-i', sfxFile);
    const ms = Math.max(0, Math.round(s * 1000));
    branches.push(`[${i + 1}:a]adelay=${ms}|${ms}[a${i}]`);
  });
  const mixed = atSeconds.map((_, i) => `[a${i}]`).join('');
  // duration=longest, NOT first. `adelay` only pads silence BEFORE a click starts — it does not
  // extend the stream with trailing silence after the click ends, so each branch's own duration
  // is just its delay plus the click's own ~90ms, nothing more. `duration=first` sets the WHOLE
  // mixed output's length to the FIRST branch alone — the very first click's own short stream —
  // cutting off every later one outright. This was the exact bug: sound on the first click only,
  // silence for the rest of the tour. `longest` extends to the LAST (latest-delayed) branch
  // instead, and the outer `-shortest` flag already caps the true final length against the video.
  // normalize=0, EXPLICITLY. amix's default (normalize=1) divides the mixed volume by however
  // many input streams are still "active" at each moment, to prevent clipping when several play
  // at once — but each click here is a short, staggered, NON-overlapping burst, so ffmpeg counts
  // fewer streams as "still active" the further into the timeline a click lands (earlier ones
  // have already ended), and progressively divides by less. The real, measured result: clicks
  // got audibly louder every few seconds, from -20.7dB up to -1.7dB across one recording, purely
  // from this automatic compensation — nothing else changed between them. Turning it off means
  // every click plays at the source file's own single, unscaled volume throughout, which is
  // correct here precisely because they never overlap and there is nothing to compensate for.
  const filter = `${branches.join(';')};${mixed}amix=inputs=${atSeconds.length}:duration=longest:dropout_transition=0:normalize=0[aout]`;
  return run(ffmpeg, [
    '-y', ...inputs,
    '-filter_complex', filter,
    '-map', '0:v', '-map', '[aout]',
    '-c:v', 'copy', '-c:a', 'aac', '-shortest',
    videoOut,
  ]);
}

export function run(cmd, argv) {
  return import('node:child_process').then(({ spawn }) => new Promise((ok, no) => {
    const p = spawn(cmd, argv, { stdio: ['ignore', 'ignore', 'inherit'] });
    p.on('error', () => no(new Error('ffmpeg is not installed. Get it from ffmpeg.org, or: winget install Gyan.FFmpeg')));
    p.on('close', (code) => (code === 0 ? ok() : no(new Error('ffmpeg exited ' + code))));
  }));
}
