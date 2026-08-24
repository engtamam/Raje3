/**
 * Turns a tour SCRIPT (data — what to find, what to say, in what order) into an mp4, by driving
 * the real console app in a real browser and recording it in real time.
 *
 * WHY REAL TIME, NOT THE AD'S FROZEN CLOCK. record.mjs freezes Date.now()/performance.now() and
 * steps it forward one rendered frame at a time — perfect for the ad, because the ad's every
 * animation is OUR OWN JS reading that clock. The console app is not ours to rewrite: its
 * transitions are the browser's own CSS engine running on the real compositor clock, which does
 * not read window.performance at all. Freezing JS time around it would not freeze those
 * transitions — it would just make our OWN capture loop's timing unpredictable relative to them,
 * which is worse than plain real-time capture, not better. So this recorder does what a screen
 * recorder does: grab a frame on a fixed real-time cadence while real actions happen, the same
 * way a person would show someone else their own screen.
 *
 * WHY A SCRIPT IS DATA. Every screen-specific decision — which button, what to say about it,
 * whether it has a reverse — lives in one small file per tour under tours/scripts/. This engine
 * reads that file and does not know or care which screen it describes; a tour that names the
 * wrong selector fails loudly and names the step, and a tour that needs a new KIND of step (an
 * upload, a drag) is a new step handler added once here, immediately available to every tour.
 *
 * WHY LOGIN IS BORROWED, NOT REWRITTEN. apps/console/e2e/fixtures.ts already owns "how to open a
 * shop and keep a session alive across runs" — token rotation, expiry, all of it. A second copy
 * of that logic here would drift from the first the moment either one changed. This recorder
 * imports openShop/SESSION_FILE from that exact file instead: one login, wherever it's needed.
 *
 * Usage:
 *   node media/tours/record-tour.mjs media/tours/scripts/stop-service.mjs
 *   CONSOLE=http://localhost:5174 node media/tours/record-tour.mjs <script> [--seconds-cap 90]
 */
import { mkdir, rm } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, resolve, dirname, basename, extname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { chromiumModule } from '../lib/browser.mjs';
import { findFfmpeg, assembleMp4, run } from '../lib/ffmpeg.mjs';
import { readConfig } from '../lib/read-config.mjs';
import { locate } from './lib/locate.mjs';
import { installOverlay } from './lib/overlay.mjs';
import { captionHoldMs } from './lib/caption.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');
const CONSOLE_DIR = resolve(ROOT, '../apps/console');

const args = process.argv.slice(2);
const scriptPath = args.find((a) => !a.startsWith('--'));
if (!scriptPath) {
  console.error('usage: node media/tours/record-tour.mjs <tour-script.mjs> [--seconds-cap N]');
  process.exit(1);
}
const flag = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i === -1 ? fallback : Number(args[i + 1]);
};
// A CIRCUIT BREAKER, NOT A TARGET LENGTH. Same philosophy as config.ts's LENGTH.maxSeconds: a
// tour whose steps run away (a selector that never resolves, a wait loop with no exit) should
// stop and say so rather than record for an hour and produce a file nobody uploads.
const SECONDS_CAP = flag('seconds-cap', 180);

const CONFIG = readConfig(join(ROOT, 'config.ts'));
const FPS = CONFIG.VIDEO.fps;

async function main() {
  const tourModule = await import(pathToFileURL(resolve(scriptPath)).href);
  const tour = tourModule.default;
  if (!tour?.id || !Array.isArray(tour.steps)) {
    throw new Error(`${scriptPath} must default-export { id, steps: [...] }`);
  }

  const { openShop, SESSION_FILE } = await import(pathToFileURL(join(CONSOLE_DIR, 'e2e/fixtures.ts')).href)
    .catch(() => { throw new Error('could not import apps/console/e2e/fixtures.ts — is the console app checked out?'); });

  // Trailing slash enforced here, once — new URL(relativePath, base) needs it to APPEND rather
  // than replace the last path segment of base, and a tour script shouldn't have to know that.
  const rawBase = process.env.CONSOLE ?? 'http://localhost:5174';
  const baseURL = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;
  const outDir = join(HERE, 'out');
  await mkdir(outDir, { recursive: true });
  const out = join(outDir, `${tour.id}.mp4`);
  const framesDir = join(outDir, `.${tour.id}-frames`);
  await rm(framesDir, { recursive: true, force: true });
  await mkdir(framesDir, { recursive: true });

  const chromium = chromiumModule();
  const browser = await chromium.launch();
  // baseURL IS REQUIRED, NOT OPTIONAL — openShop() (borrowed verbatim from e2e/fixtures.ts) does
  // `page.goto('/')` itself, a relative navigation Playwright can only resolve against a
  // context-level baseURL. Without one it throws "Cannot navigate to invalid URL" — a context
  // built for standalone use (this script), unlike Playwright's own test runner, does not set
  // this automatically from anywhere.
  // A TOUR ABOUT SIGNING UP CAN'T HAVE SIGNUP HAPPEN OFFSCREEN FIRST. Every other tour wants
  // ensureSignedIn() to make signup someone else's problem — silent, before capture even starts,
  // exactly the convenience it exists for. A tour whose own subject IS that flow needs the
  // opposite: `skipAutoSignIn: true` skips this call entirely and leaves the door on screen as
  // the tour's own first frame, so its own steps (goto, type, click «ابدأ») are what the
  // recording actually shows happening, not a fait accompli.
  const contextOpts = { baseURL, viewport: deviceViewport(tour) };
  const context = tour.skipAutoSignIn
    ? await browser.newContext(contextOpts)
    : existsSync(SESSION_FILE)
      ? await browser.newContext({ ...contextOpts, storageState: SESSION_FILE })
      : await browser.newContext(contextOpts);
  const page = await context.newPage();

  if (!tour.skipAutoSignIn) {
    await ensureSignedIn(page, baseURL, openShop, SESSION_FILE);
    await context.storageState({ path: SESSION_FILE }).catch(() => undefined); // save any rotation from ensureSignedIn back out.
  }

  await page.addInitScript(installOverlay, CONFIG);
  await page.evaluate(installOverlay, CONFIG).catch(() => undefined); // in case the page was already loaded by ensureSignedIn.

  let frameIndex = 0;
  const frameFile = () => join(framesDir, String(frameIndex++).padStart(6, '0') + '.png');
  const shoot = () => page.screenshot({ path: frameFile(), animations: 'disabled' }).catch(() => undefined);

  // ── the real-time capture loop ─────────────────────────────────────────────────────────────
  // A fixed cadence corrected against a running target time (`next += stepMs`), not `setTimeout`
  // chained naively — the latter drifts by however long each screenshot itself takes, and over a
  // minute-long tour that drift is seconds, not milliseconds.
  let capturing = true;
  const stepMs = 1000 / FPS;
  const captureLoop = (async () => {
    let next = Date.now();
    while (capturing) {
      await shoot();
      next += stepMs;
      const delay = next - Date.now();
      if (delay > 0) await sleep(delay);
    }
  })();

  // ── chapter marks ──────────────────────────────────────────────────────────────────────────
  // YOUTUBE'S OWN RESEARCH-BACKED ADVICE ("a chapter per real sub-topic, not per technical step")
  // maps onto this project's own vocabulary exactly: a STATION on tours/PLAN.md's table, not
  // every click. So a step only becomes a chapter mark when its data explicitly says `chapter:
  // 'title'` — most steps (a click, a caption between two chapter-marked ones) contribute
  // nothing here, which is the point: the tour author decides what counts as a station, this
  // engine only ever timestamps what it's told to.
  const chapters = [];
  // EVERY CAPTION'S EXACT PLACEMENT, WRITTEN OUT — the piece VOICE.enabled's own comment in
  // config.ts calls "activated the day the key arrives": when that day comes, a TTS pass needs
  // to know exactly WHEN each line started and how long the engine actually held it (not the
  // config-estimated read time — the real, lived duration this specific run gave it, which is
  // what audio must be timed against so a synthesized line neither races ahead of nor lags
  // behind its caption). Nothing here calls a TTS API — this only writes down the placement data
  // so that whichever script eventually does needs no change to this recorder to use it.
  const captionTimeline = [];
  const elapsedSeconds = () => frameIndex / FPS;

  const deadline = Date.now() + SECONDS_CAP * 1000;
  console.log(`${tour.id} · recording ${tour.steps.length} step(s) live from ${baseURL}`);
  try {
    for (const [i, step] of tour.steps.entries()) {
      if (Date.now() > deadline) {
        throw new Error(`exceeded --seconds-cap ${SECONDS_CAP}s at step ${i + 1}/${tour.steps.length} — a selector likely never resolved`);
      }
      if (step.chapter) chapters.push({ seconds: elapsedSeconds(), title: step.chapter });
      const startSeconds = elapsedSeconds();
      await runStep(page, step, i, tour, baseURL);
      if (step.say) {
        captionTimeline.push({
          text: step.say, // the RAW sentence, never the display-wrapped version — this is what TTS should read
          startSeconds, endSeconds: elapsedSeconds(),
        });
      }
    }
  } finally {
    capturing = false;
    await captureLoop;
  }

  await browser.close();

  const ffmpeg = findFfmpeg();
  await assembleMp4({ ffmpeg, framesDir, fps: FPS, out, run });
  await rm(framesDir, { recursive: true, force: true });
  const seconds = frameIndex / FPS;
  console.log(`✔ ${out} · ${seconds.toFixed(1)}s · ${frameIndex} frames`);

  if (chapters.length) await writeChapters(join(outDir, `${tour.id}.chapters.txt`), chapters);
  const { writeFile } = await import('node:fs/promises');
  await writeFile(join(outDir, `${tour.id}.captions.json`), JSON.stringify(captionTimeline, null, 2), 'utf8');
  console.log(`✔ ${join(outDir, `${tour.id}.captions.json`)} · ${captionTimeline.length} line(s) timed — ready for a future TTS pass`);
}

/**
 * YouTube's own required format, pasted straight into a video's description: the FIRST line
 * MUST read exactly `0:00`, each following line `M:SS` or `H:MM:SS` ascending, each at least
 * ten seconds after the last. YouTube silently ignores the whole chapter list if any of that is
 * violated — so this checks the same rules here, where a wrong tour script fails loudly instead
 * of uploading a video that looks chaptered locally and shows no chapters at all once live.
 */
async function writeChapters(path, chapters) {
  if (chapters[0].seconds > 0.05) {
    throw new Error(`first chapter "${chapters[0].title}" starts at ${chapters[0].seconds.toFixed(1)}s — YouTube requires the first chapter at 0:00, or it drops the whole list. Add \`chapter\` to the tour's very first step.`);
  }
  for (let i = 1; i < chapters.length; i++) {
    const gap = chapters[i].seconds - chapters[i - 1].seconds;
    if (gap < 10) {
      throw new Error(`chapters "${chapters[i - 1].title}" and "${chapters[i].title}" are only ${gap.toFixed(1)}s apart — YouTube requires at least 10s between chapters, or it drops the whole list.`);
    }
  }
  const lines = chapters.map((c) => `${formatChapterTime(c.seconds)} ${c.title}`);
  const { writeFile } = await import('node:fs/promises');
  await writeFile(path, lines.join('\n') + '\n', 'utf8');
  console.log(`✔ ${path} · ${chapters.length} chapter(s) — paste into the YouTube description as-is`);
}

function formatChapterTime(totalSeconds) {
  const s = Math.floor(totalSeconds);
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  const mm = h > 0 ? String(m).padStart(2, '0') : String(m);
  const ss = String(sec).padStart(2, '0');
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

function deviceViewport(tour) {
  if (tour.orientation === 'landscape') return { width: CONFIG.VIDEO.width, height: CONFIG.VIDEO.height };
  return { width: CONFIG.VIDEO.deviceWidth, height: CONFIG.VIDEO.deviceHeight };
}

/** Borrowed wholesale from e2e/fixtures.ts's own `shop` fixture logic: race the door against the
 *  shell, repair with a fresh openShop() only if genuinely signed out. Kept here instead of
 *  imported directly because that logic lives inside a Playwright `test.extend` fixture, not a
 *  standalone function — but the STEPS are copied verbatim from it, not reinvented. */
async function ensureSignedIn(page, baseURL, openShop, sessionFile) {
  await page.goto(baseURL);
  // «محل جديد» ONLY EXISTS AFTER SWITCHING TABS — Door.tsx defaults to «تسجيل الدخول» (sign in),
  // and the sign-up pane (where «محل جديد» lives) only mounts once «تسجيل جديد» is clicked. The
  // OUTER mode radio is what's actually on the door immediately either way, so THAT is the door
  // signal — checking for the inner one here was the exact bug openShop() itself had, fixed in
  // e2e/fixtures.ts, and it lived here too as a second, separate copy of the same wrong check.
  await Promise.race([
    page.getByRole('radio', { name: 'تسجيل جديد' }).waitFor({ timeout: 45_000 }),
    page.getByRole('navigation').first().waitFor({ timeout: 45_000 }),
  ]).catch(() => undefined);
  const onTheDoor = await page.getByRole('radio', { name: 'تسجيل جديد' }).isVisible().catch(() => false);
  if (onTheDoor) {
    console.log('  no live session — opening a fresh shop (this becomes the tour\'s demo data)');
    await openShop(page);
  }
}

async function runStep(page, step, index, tour, baseURL) {
  const label = `  ${index + 1}/${tour.steps.length}`;

  if (step.goto) {
    console.log(`${label} goto ${step.goto}`);
    // AGAINST baseURL, NEVER page.url(). The app is served under a base path (vite.config.ts's
    // `base: '/app/'`), and an absolute-path reference like "/services" resolved against the
    // CURRENT page's URL discards that prefix outright — WHATWG URL resolution replaces the
    // whole path for a leading slash, it does not append. Resolving relative to baseURL (which
    // already carries the base path, trailing slash and all) and stripping the tour script's own
    // leading slash keeps every step's path inside the app no matter where the page currently is.
    await page.goto(new URL(step.goto.replace(/^\//, ''), baseURL).href);
    await page.waitForLoadState('networkidle', { timeout: 30_000 }).catch(() => undefined);
    // NO EARLY RETURN — a `goto` step falls through to the shared caption block below like every
    // other step. It used to return here directly, which meant a goto's own `say` was silently
    // never shown at all: found by watching a recorded tour with no captions anywhere and
    // checking a real frame, not by reading the code and spotting it.
    await page.evaluate(() => window.__tour?.clear()).catch(() => undefined);
  }

  if (step.waitFor) {
    // FOR ASYNC CONTENT A GOTO ALONE CANNOT GUARANTEE — a freshly opened shop's starter
    // catalogue seeds in the BACKGROUND and fails soft by design (see door.spec.ts's own
    // assertion on this exact point), so a tour landing on «خدماتي» right after signup can find
    // it genuinely empty for a few seconds. This is a generic wait, not a workaround local to
    // one tour: any script whose target appears asynchronously reaches for it the same way.
    console.log(`${label} waitFor ${step.waitFor}`);
    await locate(page, step.waitFor).first().waitFor({ state: 'visible', timeout: step.timeoutMs ?? 30_000 });
    return;
  }

  const target = step.click ?? step.type ?? step.check;
  if (target) {
    // BOTH THE RING AND THE CAPTION, HIDDEN THROUGH THE WHOLE WAIT — not left showing while it
    // settles. Clearing only the ring still let the PREVIOUS step's CAPTION sit on screen over an
    // already-changed screen underneath it (the new screen fully rendered, the old sentence still
    // talking about the click that opened it) — the same class of stale-state bug, just the other
    // half of the overlay. clear() hides both, so a viewer only ever sees one of two things during
    // any transition: nothing, or the ring AND its caption already in their final, correct place.
    await page.evaluate(() => window.__tour?.clear()).catch(() => undefined);
    const locator = locate(page, target).first();
    // THE WHOLE SCREEN, NOT JUST THE ONE ELEMENT. stableBoundingBox() alone still wasn't enough —
    // a field that mounts at its FINAL position immediately (its own box never moves) reads as
    // "stable" on the very first poll even while its SIBLINGS — the rest of the form, still being
    // added around it by the same re-render — are still appearing. The target was right; the
    // screen around it wasn't finished. This waits for the DOM ITSELF to go quiet — no mutations
    // anywhere on the page for a short window — before trusting anything on it enough to measure.
    await waitForDomQuiet(page);
    await locator.scrollIntoViewIfNeeded().catch(() => undefined);
    const box = await stableBoundingBox(locator);
    if (!box) throw new Error(`step ${index + 1}: selector "${target}" resolved to nothing visible`);
    await page.evaluate((r) => window.__tour?.spotlight(r), box);
  } else {
    // A STEP WITH NO TARGET CLEARS THE RING, IT DOESN'T INHERIT THE LAST ONE. Leaving the
    // previous step's ring up was tried deliberately (comment used to live here) on the theory
    // that "what was just pressed" stays worth marking through its own settle — but a real
    // recording showed the actual failure mode: a caption-only step narrating something on a
    // DIFFERENT part of the screen (or a different topic entirely) with a stale ring still
    // circling an unrelated field from two steps back, which reads as a sync bug because it is
    // one. A step that wants the ring to stay names the same selector again explicitly.
    await page.evaluate(() => window.__tour?.spotlight(null)).catch(() => undefined);
  }

  if (step.say) {
    // THE RAW SENTENCE, NOT A NODE-SIDE PRE-WRAPPED ONE. overlay.mjs's own say() measures against
    // the caption bar's REAL rendered width in the actual browser and wraps to that — a
    // character-count guess here produced five lines instead of two the first time this ran at
    // the tour frame's real (narrower, portrait) width; see overlay.mjs's own note. The boolean
    // it returns is the ONLY trustworthy answer to "does this fit two lines" — surfaced as a
    // thrown error naming the exact step, not a silently overflowing caption bar.
    const fit = await page.evaluate((t) => window.__tour?.say(t), step.say);
    if (fit === false) {
      throw new Error(`step ${index + 1}: caption "${step.say}" doesn't fit CAPTION.maxLines (${CONFIG.CAPTION.maxLines}) at this frame's real width — shorten it or split it into two steps`);
    }
    await sleep(step.holdMs ?? captionHoldMs(step.say, CONFIG.CAPTION));
  } else {
    await sleep(CONFIG.PACE.betweenStepsMs);
  }

  // THE RING IS A FROZEN PIXEL SNAPSHOT, NOT A LIVE TRACK — spotlight(box) draws at the
  // coordinates it was given ONCE; it never re-queries the element it was drawn for. This is the
  // actual root of the bug that survived every earlier fix in this function: click a button that
  // then DISAPPEARS (replaced by a form, a table row, whatever the click reveals), and the ring
  // stays exactly where that button used to be — circling WHATEVER new content the re-render
  // happens to place at that same screen position. A field that lands there reads, correctly,
  // as "the ring is on an empty box" — because by then it genuinely is, just not the box anyone
  // meant. Clearing both ring and caption the MOMENT the action fires (not after settling, not
  // after the pace pause — immediately) means nothing is ever left pointing at stale coordinates
  // while the screen underneath changes shape. The next step spotlights fresh, at a live-read
  // position, once it actually has one to show.
  if (step.click) {
    console.log(`${label} click ${step.click}`);
    await locate(page, step.click).first().click();
    await page.evaluate(() => window.__tour?.clear()).catch(() => undefined);
    await waitForDomQuiet(page);
    await sleep(CONFIG.PACE.afterActionMs);
  } else if (step.type) {
    console.log(`${label} type ${step.type}`);
    // A FUNCTION, NOT ONLY A STRING — most tour text is fixed and belongs in the script verbatim,
    // but a signup tour needs a phone number that's different every run (the real backend refuses
    // a second signup on one already registered) or it can never be re-recorded. `text` as a
    // function generates that once, at the moment this step actually runs, instead of a tour
    // script trying to be its own random-data generator in static data.
    const text = typeof step.text === 'function' ? step.text() : step.text;
    await locate(page, step.type).first().pressSequentially(text, { delay: CONFIG.PACE.typeDelayMs });
    await page.evaluate(() => window.__tour?.clear()).catch(() => undefined);
    await waitForDomQuiet(page);
    await sleep(CONFIG.PACE.afterActionMs);
  } else if (step.check) {
    console.log(`${label} check ${step.check}`);
    await locate(page, step.check).first().check();
    await page.evaluate(() => window.__tour?.clear()).catch(() => undefined);
    await waitForDomQuiet(page);
    await sleep(CONFIG.PACE.afterActionMs);
  } else if (step.wait) {
    await sleep(step.wait);
  }
}

/**
 * Waits until nothing on the page has changed for a short quiet window — a MutationObserver
 * watching the whole document, not one element. stableBoundingBox() alone still let a real bug
 * through: a field that mounts at its FINAL position immediately reads as "stable" on its very
 * first poll even while its own SIBLINGS (the rest of a form the same click just opened) are
 * still being added around it — the element was right, the screen it lives on wasn't finished.
 * This is the general fix underneath that specific one: don't trust ANY measurement until the
 * DOM as a whole has stopped mutating, the same category of signal `waitForLoadState('networkidle')`
 * gives for a full navigation, applied here to a client-side re-render that has no network
 * request of its own to wait on.
 */
async function waitForDomQuiet(page, { quietMs = 150, timeoutMs = 5_000 } = {}) {
  await page.evaluate(({ quietMs, timeoutMs }) => new Promise((resolve) => {
    let timer;
    const done = () => { observer.disconnect(); clearTimeout(timer); clearTimeout(deadline); resolve(); };
    const observer = new MutationObserver(() => {
      clearTimeout(timer);
      timer = setTimeout(done, quietMs);
    });
    // STRUCTURE ONLY — childList/subtree (elements actually appearing or leaving), not attributes
    // or characterData. Those two are noisy in a way unrelated to "is new content still arriving":
    // a focus ring's own class toggling, a blinking caret, a hover state — none of it means the
    // screen has more to render, and watching them made real recordings take nearly twice as long
    // waiting out quiet windows that a genuinely finished screen kept re-triggering on its own.
    //
    // TWO ANIMATION FRAMES BEFORE THE OBSERVER EVEN STARTS ITS FIRST TIMER — the actual race this
    // fixes. React batches a click's state update asynchronously; the click handler itself
    // returns before React has scheduled, let alone started, the re-render it triggers. Arming
    // the "already quiet" timer immediately on observe() could win that race outright — the timer
    // firing before the mutation it's supposed to be watching for has even happened yet, reporting
    // "settled" on a screen that hasn't started changing. Two rAFs guarantee at least one real
    // paint has occurred first, so the observer starts watching AFTER whatever the click set in
    // motion has had a real chance to begin.
    requestAnimationFrame(() => requestAnimationFrame(() => {
      observer.observe(document.body, { childList: true, subtree: true });
      timer = setTimeout(done, quietMs); // already quiet by the time we actually start watching
    }));
    const deadline = setTimeout(done, timeoutMs); // a page that never truly settles (a live poll, a
                                                    // ticking clock) still gets released, not stuck forever
  }), { quietMs, timeoutMs });
}

/**
 * Waits for a locator's own boundingBox() to stop moving before returning it — the actual fix
 * for a ring caught mid-transition: a target element that just appeared (a form opening after a
 * click, a row that just mounted) can report a real, valid boundingBox() the very first instant
 * it exists, then shift as React finishes laying out ITS OWN SIBLINGS around it a frame or two
 * later. A fixed sleep before reading it is a guess about how long that settling takes on THIS
 * element, THIS action, THIS network — sometimes too short (the exact bug this fixes: a real
 * screenshot showed the ring on an empty box, mid-layout, before the field's own label had even
 * painted), sometimes wastefully long. Polling until two consecutive reads agree needs no
 * guessed number at all — it asks the actual page whether it has settled, the same category of
 * fix Playwright's own actionability checks already are for clicks.
 */
async function stableBoundingBox(locator, { intervalMs = 60, timeoutMs = 5_000 } = {}) {
  const deadline = Date.now() + timeoutMs;
  let last = null;
  while (Date.now() < deadline) {
    const box = await locator.boundingBox().catch(() => null);
    if (box && last && box.x === last.x && box.y === last.y && box.width === last.width && box.height === last.height) {
      return box;
    }
    last = box;
    await sleep(intervalMs);
  }
  return last; // best effort — a target that never truly stabilizes still gets its last known position, not nothing.
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

main().catch((e) => { console.error(e.message); process.exit(1); });
