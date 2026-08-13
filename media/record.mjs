/**
 * يصوّر صفحةً ويخرج mp4 — للإعلانات اليوم، وللشروحات حين تُبنى.
 *
 * لماذا لقطاتٌ إطاراً إطاراً، لا تسجيل فيديو جاهز:
 *
 * Playwright يسجّل فيديو بنفسه، لكنه يسجّل **بالزمن الحقيقي**: إن تعثّر المتصفّح للحظة
 * سقطت إطارات، وإن كان الجهاز مشغولاً امتدّ المشهد. والإعلان الذي بنيناه يقوم على
 * وقفةٍ مقدارها ثانية ونصف — ومقطعٌ تختلف وقفته في كل تصيير ليس مقطعاً نملكه.
 *
 * فالساعة تُزوَّر: نوقف زمن المتصفّح، ونقدّمه بمقدار إطارٍ واحد، ونلتقط، ونكرّر. النتيجة
 * أن التصيير على جهازٍ بطيء وجهازٍ سريع يعطي **الملف نفسه** بايتاً بايت.
 *
 * والاستعمال:
 *     node media/record.mjs media/ads/your-shop-talks.html
 *     node media/record.mjs <ملف> --seconds 20 --portrait
 */
import { spawn } from 'node:child_process';
import { mkdtemp, rm, mkdir } from 'node:fs/promises';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, basename, extname, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createRequire } from 'node:module';

const HERE = dirname(fileURLToPath(import.meta.url));

// ── من أين يأتي المتصفّح ────────────────────────────────────────────────────────────
// Playwright مثبَّتٌ مع الواجهة، لا في جذر المستودع — وهذا صحيح: هو أداة اختبارها.
// فنحلّه من هناك صراحةً بدل نسخةٍ ثانية تُثبَّت لنا وحدنا وتتأخّر عن نسختها.
const req = createRequire(resolve(HERE, '../apps/console/package.json'));
const { chromium } = req('@playwright/test');

// ── ما يُقرأ من config.ts ────────────────────────────────────────────────────────────
// قراءةً نصّية بلا مترجم: ملفٌ واحد يحكم الشكل، وسكربتٌ لا يحتاج بناءً ليقرأه.
const CONFIG = (() => {
  const src = existsSync(join(HERE, 'config.ts')) ? readFileSync(join(HERE, 'config.ts'), 'utf8') : '';
  const num = (key, fallback) => {
    const m = src.match(new RegExp(`${key}:\\s*(\\d+)`));
    return m ? Number(m[1]) : fallback;
  };
  return {
    fps: num('fps', 30),
    width: num('width', 1920),
    height: num('height', 1080),
    portraitW: num('deviceWidth', 1080),
    portraitH: num('deviceHeight', 1920),
  };
})();

const args = process.argv.slice(2);
const target = args.find((a) => !a.startsWith('--'));
if (!target) {
  console.error('استعمال: node media/record.mjs <ملف.html> [--seconds 20] [--portrait]');
  process.exit(1);
}
const flag = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i === -1 ? fallback : Number(args[i + 1]);
};
// المدّة تُقرأ من الصفحة (`window.__duration`) — والراية للتجربة وحدها: أردتَ أول خمس
// ثوانٍ لتفحص المقدّمة؟ مرّرها وتجاوز الإعلان.
const SECONDS_OVERRIDE = flag('seconds', 0);
const PORTRAIT = args.includes('--portrait') || basename(target).startsWith('ad-')
  || target.includes('/ads/');

// الإعلان رأسيّ 9:16، والشرح أفقيّ — والافتراض يُشتقّ من المجلد فلا يُنسى.
const WIDTH = PORTRAIT ? 1080 : CONFIG.width;
const HEIGHT = PORTRAIT ? 1920 : CONFIG.height;
const FPS = CONFIG.fps;

const OUT_DIR = join(HERE, target.includes('ads') ? 'ads/out' : 'out');
const OUT = join(OUT_DIR, basename(target, extname(target)) + '.mp4');

// ── العثور على ffmpeg بلا تدخّل ────────────────────────────────────────────────────
// winget يثبّته في مجلدٍ لا يدخل PATH إلا بعد إغلاق الطرفيّة وفتحها — وهي خطوةٌ يدوية
// تُنسى، فتفشل أول محاولة بعد التثبيت مباشرة وتبدو كعطلٍ فينا. فنبحث عنه بأنفسنا.
const ffmpeg = (() => {
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
  } catch { /* لا وجود للمجلد: نعود إلى PATH، وهو الحال على لينكس وماك */ }
  return 'ffmpeg';
})();

async function main() {
  await mkdir(OUT_DIR, { recursive: true });
  const frames = await mkdtemp(join(tmpdir(), 'raje3-frames-'));

  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: WIDTH, height: HEIGHT },
    deviceScaleFactor: 1,
  });

  // ── الساعة المزوّرة ───────────────────────────────────────────────────────────────
  // تُحقن قبل أي كود في الصفحة، فكل مؤقّت وكل إطارٍ متحرّك يقرأ زمننا نحن. من غيرها
  // يعمل الشريط الزمني على ساعة الجهاز والتقاطنا على ساعةٍ أخرى، فيتفاوت الاثنان.
  await page.addInitScript(() => {
    let now = 0;
    const raf = [];
    const timers = [];

    window.__advance = (ms) => {
      now += ms;
      for (const t of timers.splice(0)) { if (t.at <= now) t.fn(); else timers.push(t); }
      for (const fn of raf.splice(0)) fn(now);
    };

    Date.now = () => now;
    performance.now = () => now;
    window.setTimeout = (fn, ms = 0) => { timers.push({ at: now + ms, fn }); return timers.length; };
    window.setInterval = () => 0;          // لا شيء في مقاطعنا يحتاجه، ولو احتاجه لدار للأبد
    window.clearTimeout = () => {};
    window.requestAnimationFrame = (fn) => { raf.push(fn); return raf.length; };
  });

  await page.goto(pathToFileURL(resolve(target)).href);
  // انتظار الخطوط قبل الإطار الأول: التقاطٌ قبلها يعطي أول ثانيةٍ بخطٍّ احتياطي.
  await page.evaluate(() => document.fonts.ready);

  // الضغطة التي تبدأ الإعلان — ثم لا شيء يتحرّك إلا بأمرنا.
  await page.evaluate(() => document.querySelector('#play')?.click());

  // الصفحة تعلن طولها؛ ولو لم تعلنه فهي ليست جاهزة للتصيير — والرفض هنا أرحم من ملفٍ
  // مقطوعٍ يُكتشف بعد الرفع.
  const declared = await page.evaluate(() => window.__duration || 0);
  const seconds = SECONDS_OVERRIDE || declared / 1000;
  if (!seconds) {
    throw new Error('الصفحة لا تعلن طولها: أضف window.__duration بالمللي، أو مرّر --seconds.');
  }
  const FRAMES = Math.round(seconds * FPS);
  console.log(`${basename(target)} · ${seconds.toFixed(1)} ث · ${WIDTH}×${HEIGHT} · ${FPS} إطار/ث`);

  const step = Math.round(1000 / FPS);
  for (let i = 0; i < FRAMES; i++) {
    await page.evaluate((ms) => window.__advance(ms), step);
    await page.screenshot({
      path: join(frames, String(i).padStart(5, '0') + '.png'),
      animations: 'disabled',
    });
  }
  await browser.close();

  await run(ffmpeg, [
    '-y', '-framerate', String(FPS),
    '-i', join(frames, '%05d.png'),
    // yuv420p وإلا رفضته إنستقرام وواتساب وشغّلته يوتيوب بألوانٍ مزاحة.
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', '-preset', 'slow',
    '-movflags', '+faststart',
    OUT,
  ]);

  await rm(frames, { recursive: true, force: true });
  console.log('✔ ' + OUT);
}

function run(cmd, argv) {
  return new Promise((ok, no) => {
    const p = spawn(cmd, argv, { stdio: ['ignore', 'ignore', 'inherit'] });
    p.on('error', () => no(new Error(
      'ffmpeg غير مثبَّت. نزّله من ffmpeg.org أو: winget install Gyan.FFmpeg')));
    p.on('close', (code) => (code === 0 ? ok() : no(new Error('ffmpeg ' + code))));
  });
}

main().catch((e) => { console.error(e.message); process.exit(1); });
