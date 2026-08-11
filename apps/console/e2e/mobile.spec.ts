/**
 * The phone, which is the device this product is actually used on.
 *
 * A counter in a workshop has a phone on it, not a laptop. Every screen here was built and looked
 * at on a wide window, and the failures that follow from that are not a matter of taste — they are
 * measurable, and this file measures them.
 *
 * TWO THINGS ARE ASSERTED, AND BOTH ARE OBJECTIVE.
 *
 *   1. Nothing overflows the viewport horizontally. A page you can drag sideways on a phone is a
 *      page with a control half off the screen, and the owner finds it by not finding it.
 *   2. Every control you are meant to press is at least 40px tall. Below that it is a target you
 *      miss with a thumb, which on the visit screen means a mis-recorded visit.
 *
 * WHY A SPEC RATHER THAN A LOOK. "It looks cramped" cannot be re-checked next month by somebody
 * else. This can, and it fails the build rather than waiting for a screenshot in a message.
 */
import { expect, open, test } from './fixtures';

const PHONE = { width: 390, height: 844 };   // iPhone 14-class, the common floor

const SCREENS: [string, string][] = [
  ['/', 'اليوم'],
  ['/visit', 'تسجيل زيارة'],
  ['/customers', 'عملائي'],
  ['/shop', 'محلّي'],
  ['/services', 'خدماتي ومنتجاتي'],
  ['/messages', 'رسائلي'],
  ['/points', 'نقاطي'],
  ['/team', 'فريقي'],
  ['/account', 'حسابي'],
];

/**
 * OPEN WHAT COLLAPSES. The first version of this file measured every screen as it loads, and a
 * screen as it loads is the half of it with no controls on: an owner photographed a row of inputs
 * hanging off the side of his phone, and this spec had passed on that page minutes earlier. What
 * overflows is almost always a label next to a fixed-width control, and those live inside the
 * things you tap to open.
 */
async function expandFirst(page: import('@playwright/test').Page): Promise<void> {
  const opener = page.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة|واطمئنان/ }).first();
  if (await opener.count()) {
    await opener.click();
    await page.waitForTimeout(300);
  }
}

for (const [path, name] of SCREENS) {
  test(`«${name}» fits a phone — nothing hangs off the side`, async ({ shop }) => {
    await shop.setViewportSize(PHONE);
    await open(shop, path);
    await expandFirst(shop);

    const overflow = await shop.evaluate(() => {
      const doc = document.documentElement;
      // scrollWidth beyond clientWidth IS the horizontal drag. Reported with the widest offenders
      // so the failure names what to fix rather than only that something is wrong.
      const over: string[] = [];
      if (doc.scrollWidth > doc.clientWidth + 1) {
        for (const el of Array.from(document.querySelectorAll<HTMLElement>('body *'))) {
          const r = el.getBoundingClientRect();
          if (r.width > 0 && (r.right > doc.clientWidth + 1 || r.left < -1)) {
            over.push(`${el.tagName.toLowerCase()}.${el.className.toString().slice(0, 60)}`);
          }
        }
      }
      return { width: doc.scrollWidth, viewport: doc.clientWidth, over: over.slice(0, 6) };
    });

    expect(overflow.over, `«${name}» يُسحب أفقياً: ${JSON.stringify(overflow)}`).toEqual([]);
    expect(overflow.width).toBeLessThanOrEqual(overflow.viewport + 1);
  });

  test(`«${name}» has no control too small for a thumb`, async ({ shop }) => {
    await shop.setViewportSize(PHONE);
    await open(shop, path);
    await expandFirst(shop);

    const small = await shop.evaluate(() => {
      const bad: string[] = [];
      const sel = 'button, a[href], input:not([type=hidden]), select, [role=radio]';
      for (const el of Array.from(document.querySelectorAll<HTMLElement>(sel))) {
        const r = el.getBoundingClientRect();
        // Zero-sized means hidden, not small — a collapsed nav is not a broken target.
        if (r.width === 0 || r.height === 0) continue;
        if (r.height < 36) bad.push(`${el.tagName.toLowerCase()} «${(el.textContent || '').trim().slice(0, 24)}» ${Math.round(r.height)}px`);
      }
      return bad.slice(0, 8);
    });

    expect(small, `«${name}» أهداف أصغر من إصبع: ${JSON.stringify(small)}`).toEqual([]);
  });
}
