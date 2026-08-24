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

export function run(cmd, argv) {
  return import('node:child_process').then(({ spawn }) => new Promise((ok, no) => {
    const p = spawn(cmd, argv, { stdio: ['ignore', 'ignore', 'inherit'] });
    p.on('error', () => no(new Error('ffmpeg is not installed. Get it from ffmpeg.org, or: winget install Gyan.FFmpeg')));
    p.on('close', (code) => (code === 0 ? ok() : no(new Error('ffmpeg exited ' + code))));
  }));
}
