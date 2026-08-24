/**
 * What a silent tutorial draws on top of the real screen, so a viewer with no voice-over still
 * knows exactly where to look and what just happened.
 *
 * INJECTED INTO THE LIVE PAGE, NOT COMPOSITED AFTER RECORDING — same decision media/README.md
 * already documents for the ad, extended to a screen we do not author. A layer drawn over a
 * saved video is drawn at FIXED coordinates; a real screen reflows the moment anything changes
 * (a longer name, a new badge, a narrower viewport), and a fixed-coordinate ring then points at
 * whatever now happens to sit there. Drawn INSIDE the page against the target's OWN live
 * bounding box, the ring is wrong in exactly the cases a saved-coordinate ring is wrong in too —
 * except here the tour re-generates and either still finds the target or fails loudly, instead
 * of quietly filming the wrong spot forever.
 *
 * NOTHING HERE NAMES A SCREEN. This module knows how to frame and caption — never which button
 * on which page. Every call takes coordinates or text handed to it by record-tour.mjs, which in
 * turn takes them from a tour script's data. Teaching this file a new SHAPE of overlay (say, an
 * arrow instead of a ring) helps every tour; teaching it a screen's name would not.
 */

/**
 * Runs INSIDE the browser (passed to page.evaluate/addInitScript). `cfg` carries only the
 * config.ts constants this file actually uses — brand colors/font and caption pacing — so the
 * look of every tour comes from the one file that already governs the ad's look, never a
 * duplicate copy of the same numbers.
 */
export function installOverlay(cfg) {
  if (window.__tour) return; // already installed — a tour restarting mid-page must not double it up.

  // DEFERRED UNTIL <body> EXISTS. This runs two ways: once via page.evaluate() after the page has
  // already loaded (body exists, `build()` can run immediately), and — the one that matters, so
  // the overlay survives every later navigation without reinstalling by hand — via
  // page.addInitScript(), which Playwright fires at `document_start`, BEFORE the parser has
  // created <html> or <body> at all. Calling document.body.appendChild() at that point throws,
  // and the recorder's own `.catch(() => undefined)` around its one-time manual install call was
  // swallowing that exact error silently — the overlay never existed and nothing said so. Found
  // by watching a real recorded tour show no ring and no caption anywhere, then reproducing it in
  // isolation against the real app before touching this file.
  if (document.body) build();
  else document.addEventListener('DOMContentLoaded', build, { once: true });

  function build() {
  const root = document.createElement('div');
  root.id = '__tour_overlay';
  Object.assign(root.style, {
    position: 'fixed', inset: '0', zIndex: '2147483647',
    pointerEvents: 'none', opacity: '0', transition: 'opacity 260ms ease',
  });

  // ── the frame ─────────────────────────────────────────────────────────────────────────────
  // A COLORED BORDER, NOTHING DIMMED. A full-screen dim mask was here originally — real feedback
  // on a real recording: "المنصة تتغطى برمادي… أبغى لون المنصة يبين فعلاً" (the platform's own
  // colors need to actually show, not read through a gray wash). The product's real palette is
  // the whole point of a product tour; a viewer who can't see it clearly because half the screen
  // is dimmed learns less about what raJa'i actually looks like, not more about where to click.
  // A clean border in the brand's own accent color marks the target just as unambiguously without
  // touching a single pixel of the real screen around it — double-bordered (an inner accent line,
  // an outer paper line) so it reads clearly against both light and dark real backgrounds, which
  // a single thin line often didn't.
  const ring = document.createElement('div');
  Object.assign(ring.style, {
    position: 'fixed', borderRadius: '14px',
    border: `3px solid ${cfg.BRAND.accent}`,
    boxShadow: `0 0 0 2px ${cfg.BRAND.paper}, 0 0 0 5px ${cfg.BRAND.accent}, 0 2px 10px rgba(0,0,0,.25)`,
    transition: 'all 220ms ease',
    opacity: '0',
  });

  // ── the caption bar ───────────────────────────────────────────────────────────────────────
  const caption = document.createElement('div');
  Object.assign(caption.style, {
    position: 'fixed', left: '50%', transform: 'translateX(-50%)',
    bottom: `${cfg.CAPTION.positionFromBottom * 100}%`,
    // A REAL width, NOT ONLY max-width. `position: fixed` with no width set shrinks-to-fit its
    // content — the box's own width then depends on the CSS shrink-to-fit algorithm's preferred-
    // width computation (which leans on the longest unbreakable run, not the total text), giving
    // an unstable, sometimes much-narrower-than-expected box that made even a short caption wrap
    // to four lines. `width: 82vw` makes the box's width a fixed, known quantity every time,
    // independent of what text happens to be in it — the only thing that should vary per caption.
    width: '82vw', maxWidth: '640px', padding: '14px 22px', borderRadius: '14px',
    background: cfg.BRAND.ink, color: cfg.BRAND.paper,
    fontFamily: `'${cfg.BRAND.fontFamily}', sans-serif`, fontSize: '28px', lineHeight: '1.5',
    textAlign: 'center', direction: 'rtl', opacity: '0', transition: 'opacity 220ms ease',
    boxShadow: '0 8px 28px rgba(0,0,0,.28)',
  });

  // ── the fingertip ─────────────────────────────────────────────────────────────────────────
  // A small filled dot standing in for a real touch — this app is a phone app, tapped with a
  // finger, not clicked with a mouse pointer. Real feedback: "حركة الاصبع لو في اسكرول او شي
  // معين" — a viewer needs to SEE where the next tap or swipe is heading, not just see the
  // frame appear at its destination. `left`/`top` transition (not transform) so record-tour.mjs
  // can await a real CSS transitionend and know the move actually finished before it acts.
  const finger = document.createElement('div');
  Object.assign(finger.style, {
    position: 'fixed', width: '30px', height: '30px', marginLeft: '-15px', marginTop: '-15px',
    borderRadius: '50%', background: cfg.BRAND.accent, opacity: '0',
    boxShadow: `0 0 0 6px ${cfg.BRAND.accent}33, 0 2px 8px rgba(0,0,0,.35)`,
    border: `2px solid ${cfg.BRAND.paper}`,
    transition: 'left 480ms ease, top 480ms ease, opacity 180ms ease',
  });

  root.append(ring, finger, caption);
  document.body.appendChild(root);
  requestAnimationFrame(() => { root.style.opacity = '1'; });

  /**
   * Moves the fingertip to (x, y) and resolves once the move has actually finished — a real
   * `transitionend` on whichever CSS property changed, not a guessed sleep, so record-tour.mjs
   * never acts before the viewer has actually seen the finger arrive.
   */
  function pointTo(x, y) {
    return new Promise((resolve) => {
      const wasAt = finger.style.left;
      finger.style.opacity = '1';
      if (wasAt === `${x}px` && finger.style.top === `${y}px`) { resolve(); return; }
      const done = () => { finger.removeEventListener('transitionend', done); resolve(); };
      finger.addEventListener('transitionend', done, { once: true });
      finger.style.left = `${x}px`;
      finger.style.top = `${y}px`;
      // FALLBACK TIMER — a transitionend can be missed entirely (e.g. the property was already
      // at its target value and the browser never fires one), which would otherwise hang the
      // tour forever waiting on an event that isn't coming.
      setTimeout(resolve, 600);
    });
  }

  function hidePointer() { finger.style.opacity = '0'; }

  /**
   * Point the ring at a live rect (already computed on the Node side from the real Playwright
   * locator's own boundingBox() — this file never resolves a selector itself, so it never needs
   * to know Playwright's query vocabulary at all).
   */
  function spotlight(rect) {
    if (!rect) { ring.style.opacity = '0'; return; }
    const pad = 8;
    const x = rect.x - pad, y = rect.y - pad, w = rect.width + pad * 2, h = rect.height + pad * 2;
    ring.style.opacity = '1';
    ring.style.left = `${x}px`; ring.style.top = `${y}px`;
    ring.style.width = `${w}px`; ring.style.height = `${h}px`;
  }

  /**
   * `text` is the RAW sentence, unwrapped. THE REAL CAPTION BAR DOES ITS OWN WORD-WRAP —
   * `white-space: normal` (the CSS default, left alone here) — rather than a separate measuring
   * element predicting line breaks ahead of time. A predicting ruler was tried first and kept
   * disagreeing with the real bar by exactly one line no matter how closely its font/size/
   * direction were matched to the real element's: bidi reordering, padding/box-sizing, and
   * subpixel rounding all shift a DIFFERENT element's measured width from THIS element's actual
   * rendered one, and chasing each mismatch by hand never converged. Letting the browser wrap
   * this exact element under its exact real conditions and then reading back what it did removes
   * the gap by construction — there is nothing left to disagree with.
   */
  async function say(text) {
    if (!text) { caption.style.opacity = '0'; return true; }
    // FONTS MUST BE LOADED FIRST, NOT JUST BEFORE THE FIRST CAPTURED FRAME. record.mjs's own
    // header already documents the general lesson for the ad ("capturing before fonts are ready
    // gives the first second a fallback font"); it applies to LAYOUT here too — text set before
    // the real font swaps in wraps by the fallback font's metrics, then reflows once the real,
    // usually wider, font arrives. document.fonts.ready resolves immediately once already loaded.
    await document.fonts.ready;
    caption.textContent = text;
    caption.style.opacity = '1';
    // GROUND TRUTH, READ BACK FROM THIS EXACT ELEMENT after it has actually laid the text out —
    // its own scrollHeight against its own computed line-height is the real line count, not an
    // estimate of one. scrollHeight includes the box's own padding (14px top + 14px bottom, from
    // this element's own `padding: '14px 22px'` above) — left in, two real lines of text (84px)
    // read as 112px, and 112/42 rounds UP to 3, over-counting a caption that is genuinely only
    // two lines by the padding alone. Subtracted out first so what's left is text height only.
    const cs = getComputedStyle(caption);
    const lineHeight = parseFloat(cs.lineHeight);
    const verticalPadding = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
    const actualLines = Math.round((caption.scrollHeight - verticalPadding) / lineHeight);
    if (actualLines > cfg.CAPTION.maxLines) { caption.style.opacity = '0'; return false; }
    return true;
  }

  function clear() { spotlight(null); say(null); hidePointer(); }

  window.__tour = { spotlight, say, clear, pointTo, hidePointer };
  } // end build()
}
