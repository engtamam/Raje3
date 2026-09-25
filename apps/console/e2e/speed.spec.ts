/**
 * How long each screen takes to be USABLE — measured, because «تحس أنها بطيئة» cannot be re-checked.
 *
 * THE BUDGET COMES FROM THE PRODUCT, NOT FROM A BENCHMARK. «تسجيل زيارة» is used a hundred times a
 * day with a customer standing there, and the spec gives that journey five seconds END TO END —
 * so the screen being ready has to cost a fraction of it. The owner's sections are read once or
 * twice a day and can afford more.
 *
 * WHAT IS MEASURED IS THE SKELETONS DISAPPEARING, not `load`. A page that has painted its shell
 * and is still showing three grey boxes is not a page anybody can act on, and `load` fires long
 * before that.
 *
 * AND IT RUNS AGAINST THE REAL CLUSTER over an SSH tunnel, which is SLOWER than production will
 * be — a number that passes here passes there. The failure message carries the milliseconds so
 * the next person argues with a measurement rather than an impression.
 */
import { expect, test } from './fixtures';

/** Screen → how long it may take to become actionable, in milliseconds. */
const BUDGET: [string, string, number][] = [
  // THE ONE THAT MATTERS. Everything else on this list is somebody deciding; this is somebody
  // working, with a customer waiting.
  ['/visit', 'تسجيل زيارة', 4_000],
  ['/', 'اليوم', 6_000],
  ['/customers', 'جهات الاتصال', 6_000],
  ['/services', 'خدماتي ومنتجاتي', 6_000],
  ['/points', 'نقاط الولاء', 6_000],
  ['/messages', 'رسائلي', 6_000],
  ['/team', 'فريقي', 6_000],
  ['/account', 'حسابي', 6_000],
  ['/shop', 'محلّي', 8_000],   // the indicators are a heavier read by design
];

for (const [path, name, budget] of BUDGET) {
  test(`«${name}» is usable within ${budget / 1000}s`, async ({ shop }) => {
    const started = Date.now();
    await shop.goto(path);
    await expect(shop.getByRole('navigation').first()).toBeVisible({ timeout: 30_000 });

    // THE SKELETONS ARE THE SIGNAL. A screen still painting grey boxes has not arrived, whatever
    // the network panel says.
    await expect
      .poll(async () => shop.locator('[class*="animate-pulse"]').count(), { timeout: 30_000 })
      .toBe(0);

    const took = Date.now() - started;
    expect(took, `«${name}» استغرقت ${took}ms والميزانية ${budget}ms`).toBeLessThanOrEqual(budget);
  });
}
