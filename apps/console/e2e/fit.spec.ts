/**
 * «تسجيل زيارة» fits the screen it is given — including INSIDE the pane.
 *
 * THE EARLIER VERSION OF THIS TEST PASSED WHILE THE SCREEN WAS BROKEN. It measured the page's
 * scroll height and the arrows' position, both of which were fine: the journey sized itself to the
 * window correctly, and the overflow was one level down, inside the pane, where the keypad was
 * taller than the room the pane had. The owner saw a scrollbar next to the digits and I saw green.
 *
 * So this asserts on the PANE's own overflow, which is the thing that was actually wrong.
 */
import { expect, test } from './fixtures';

const SIZES = [[390, 720], [484, 754], [768, 1024], [1280, 800]] as const;

for (const [w, h] of SIZES) {
  test(`الرحلة تسع شاشة ${w}×${h} بلا تمرير`, async ({ shop }) => {
    await shop.setViewportSize({ width: w, height: h });
    await shop.goto('/visit');
    await expect(shop.getByRole('button', { name: 'التالي' })).toBeVisible({ timeout: 30_000 });

    // Walk every step: each one has to fit, not just the first.
    for (let i = 0; i < 3; i += 1) {
      const overflow = await shop.evaluate(() => {
        const el = document.querySelector('[data-pane]') as HTMLElement | null;
        if (!el) return -1;
        return el.scrollHeight - el.clientHeight;
      });
      expect(overflow, `اللوحة نفسها تحتاج تمريراً عند ${w}×${h}`).toBeLessThanOrEqual(2);

      const box = await shop.getByRole('button', { name: 'التالي' }).boundingBox();
      if (box) expect(box.y + box.height, `الأسهم تحت الطيّة عند ${w}×${h}`).toBeLessThanOrEqual(h);

      const page = await shop.evaluate(
        () => document.documentElement.scrollHeight - window.innerHeight,
      );
      expect(page, `الصفحة تحتاج تمريراً عند ${w}×${h}`).toBeLessThanOrEqual(2);

      const next = shop.getByRole('button', { name: 'التالي' });
      if (await next.isDisabled()) break;
      await next.click();
      await shop.waitForTimeout(300);
    }
  });
}
