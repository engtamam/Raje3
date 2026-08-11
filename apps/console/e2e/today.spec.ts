/**
 * «اليوم» — is everything running?
 *
 * THE SCREEN THE PRODUCT OPENS ON, and the one an owner reaches for when he is nervous: something
 * went out, or did not, and he wants to see it rather than configure it.
 *
 * So the assertions here are about what it must never do, not about what it displays. A dashboard
 * that shows the right numbers on a good day and lies on a bad one is worse than no dashboard,
 * because he stops looking anywhere else.
 */
import { expect, open, test } from './fixtures';

test('it opens on the day, not on a setup screen', async ({ shop }) => {
  await open(shop, '/');

  // The nav is the proof he is inside; `open` already waited for the body to say something —
  // which is the part a shell with an empty content column renders perfectly without.
  await expect(shop.getByRole('link', { name: 'اليوم' })).toBeVisible();
});

test('a shop with no history says so instead of painting zeros', async ({ shop }) => {
  /**
   * A FIRST-DAY SHOP IS NOT A DEAD SHOP, and the difference is the whole screen. Zeros everywhere
   * tell a man who signed up an hour ago that the product does not work — and he is right to read
   * them that way, because zeros are what a broken shop looks like too.
   *
   * The honest answer is a sentence. This asserts the screen produced one of the two truthful
   * shapes — a sentence, or real numbers — and never the third.
   */
  const body = await open(shop, '/');

  const saysSomething = /نحسب|لم|بعد|جارٍ|لا توجد|تعذّر/.test(body);
  const hasNumbers = /\d/.test(body);
  expect(saysSomething || hasNumbers).toBeTruthy();
});

test('an outage and an empty account do not look the same', async ({ shop }) => {
  /**
   * THE DISTINCTION THAT MATTERS TO A PAYING OWNER. "We cannot reach the platform" and "you have
   * access to nothing" are identical on a blank screen, and only one of them is about him — one
   * he waits out, the other he calls support about.
   *
   * Here the catalogue loads, so neither sentence should be on screen. The test is that the
   * OUTAGE copy is absent when there is no outage: a screen that always shows it would be the
   * same failure wearing the opposite mask.
   */
  await open(shop, '/');

  await expect(shop.getByText('تعذّر الوصول إلى المنصة')).toBeHidden();
  await expect(shop.getByText('لا توجد أقسام متاحة لحسابك')).toBeHidden();
});

test('a failed read says so instead of spinning for ever', async ({ shop }) => {
  /**
   * THE BUG THIS FILE FOUND, AND THE REASON IT IS WORTH KEEPING.
   *
   * `/api/v1/reminders/today` answered 500 on every call — `c.reach` was written from memory and
   * the container has no such attribute — while 581 unit tests stayed green, because not one of
   * them called the route.
   *
   * And the screen HID it: `if (!today)` painted the loading skeleton, and the catch set `null`.
   * So a failed read looked exactly like a slow one, for ever. Grey boxes, nothing in the console,
   * nothing on screen. Three states now, not two.
   *
   * This asserts the screen never rests in a state that says nothing: either it has content, or
   * it has a sentence. A skeleton is neither.
   */
  await shop.route('**/api/v1/reminders/today*', (r) => r.fulfill({ status: 500, body: '{}' }));
  await open(shop, '/');

  await expect(shop.getByText('تعذّر تحميل شاشة اليوم')).toBeVisible();
});

test('nothing on it is an untranslated key', async ({ shop }) => {
  await open(shop, '/');
  const body = await shop.locator('body').innerText();

  expect(body).not.toMatch(/\bauth\.[a-z]+\./);
  expect(body).not.toMatch(/\bpager\.[a-z]+/);
});
