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
 * NOTHING HERE NAMES A SCREEN. This module knows how to dim, ring, and caption — never which
 * button on which page. Every call takes coordinates or text handed to it by record-tour.mjs,
 * which in turn takes them from a tour script's data. Teaching this file a new SHAPE of overlay
 * (say, an arrow instead of a ring) helps every tour; teaching it a screen's name would not.
 */

/**
 * Runs INSIDE the browser (passed to page.evaluate/addInitScript). `cfg` carries only the
 * config.ts constants this file actually uses — brand colors/font and caption pacing — so the
 * look of every tour comes from the one file that already governs the ad's look, never a
 * duplicate copy of the same numbers.
 */
export function installOverlay(cfg) {
  if (window.__tour) return; // already installed — a tour restarting mid-page must not double it up.

  const NS = 'http://www.w3.org/2000/svg';
  const root = document.createElement('div');
  root.id = '__tour_overlay';
  Object.assign(root.style, {
    position: 'fixed', inset: '0', zIndex: '2147483647',
    pointerEvents: 'none', opacity: '0', transition: 'opacity 260ms ease',
  });

  // ── the dim mask ──────────────────────────────────────────────────────────────────────────
  // One full-viewport rect, minus a rounded-rect hole over the target — an SVG mask rather than
  // four positioned divs (top/bottom/left/right bars), because a mask survives the target moving
  // or resizing between frames without four separate rectangles to keep in sync by hand.
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('width', '100%');
  svg.setAttribute('height', '100%');
  Object.assign(svg.style, { position: 'absolute', inset: '0' });
  const mask = document.createElementNS(NS, 'mask');
  mask.id = '__tour_mask';
  const maskBg = document.createElementNS(NS, 'rect');
  maskBg.setAttribute('width', '100%'); maskBg.setAttribute('height', '100%'); maskBg.setAttribute('fill', 'white');
  const hole = document.createElementNS(NS, 'rect');
  hole.setAttribute('fill', 'black'); hole.setAttribute('rx', '14');
  mask.append(maskBg, hole);
  const dimRect = document.createElementNS(NS, 'rect');
  dimRect.setAttribute('width', '100%'); dimRect.setAttribute('height', '100%');
  dimRect.setAttribute('fill', 'rgba(27,42,58,0.55)'); // BRAND.ink at low opacity — dims toward the brand, not to flat black.
  dimRect.setAttribute('mask', 'url(#__tour_mask)');
  const defs = document.createElementNS(NS, 'defs');
  defs.append(mask);
  svg.append(defs, dimRect);

  // ── the ring ──────────────────────────────────────────────────────────────────────────────
  const ring = document.createElement('div');
  Object.assign(ring.style, {
    position: 'fixed', border: `3px solid ${cfg.BRAND.accent}`, borderRadius: '14px',
    boxShadow: `0 0 0 4px ${cfg.BRAND.accent}33`, transition: 'all 220ms ease',
    opacity: '0',
  });

  // ── the caption bar ───────────────────────────────────────────────────────────────────────
  const caption = document.createElement('div');
  Object.assign(caption.style, {
    position: 'fixed', left: '50%', transform: 'translateX(-50%)',
    bottom: `${cfg.CAPTION.positionFromBottom * 100}%`,
    maxWidth: '82%', padding: '14px 22px', borderRadius: '14px',
    background: cfg.BRAND.ink, color: cfg.BRAND.paper,
    fontFamily: `'${cfg.BRAND.fontFamily}', sans-serif`, fontSize: '28px', lineHeight: '1.5',
    textAlign: 'center', direction: 'rtl', opacity: '0', transition: 'opacity 220ms ease',
    boxShadow: '0 8px 28px rgba(0,0,0,.28)',
  });

  root.append(svg, ring, caption);
  document.body.appendChild(root);
  requestAnimationFrame(() => { root.style.opacity = '1'; });

  /**
   * Point the ring/mask hole at a live rect (already computed on the Node side from the real
   * Playwright locator's own boundingBox() — this file never resolves a selector itself, so it
   * never needs to know Playwright's query vocabulary at all).
   */
  function spotlight(rect) {
    if (!rect) {
      ring.style.opacity = '0';
      hole.setAttribute('width', '0'); hole.setAttribute('height', '0');
      return;
    }
    const pad = 8;
    const x = rect.x - pad, y = rect.y - pad, w = rect.width + pad * 2, h = rect.height + pad * 2;
    ring.style.opacity = '1';
    ring.style.left = `${x}px`; ring.style.top = `${y}px`;
    ring.style.width = `${w}px`; ring.style.height = `${h}px`;
    hole.setAttribute('x', String(x)); hole.setAttribute('y', String(y));
    hole.setAttribute('width', String(w)); hole.setAttribute('height', String(h));
  }

  /**
   * `text` is already wrapped/length-checked by the tour engine against CAPTION.maxLines /
   * maxCharsPerLine before it ever reaches here — this only ever renders what it's handed.
   */
  function say(text) {
    if (!text) { caption.style.opacity = '0'; return; }
    caption.textContent = text;
    caption.style.opacity = '1';
  }

  function clear() { spotlight(null); say(null); }

  window.__tour = { spotlight, say, clear };
}
