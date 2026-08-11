/**
 * «خدماتي» — two stores behind one form.
 *
 *   name, price, order        → operations (the Service row)
 *   cycle, lead, follow-up    → REMINDERS' settings tree
 *
 * THE ENGINE READS THE TREE. A screen that wrote operations' `cycle_days` column instead would
 * reproduce exactly what the tree exists to prevent: the owner changes a cycle, sees no effect, and
 * concludes the feature is broken. Nothing errors, nothing is logged, and he stops trusting the
 * settings screen. So the test that matters is that a saved cycle SURVIVES A RELOAD — read back
 * from the store the engine actually consults.
 */
import { expect, open, test } from './fixtures';

test('the catalogue arrives seeded from his sector — he never starts from a blank page', async ({ shop }) => {
  const body = await open(shop, '/services');

  await expect(shop.getByText('لا توجد خدمات')).toBeHidden();
  // Every service says its cycle, including the ones that legitimately have none: "0" is a real
  // answer for a puncture repair, and «بلا دورة» is how it is said.
  expect(body).toMatch(/كل \d+ يوماً|بلا دورة/);
});

test('the services are shown under the groups the system already knows', async ({ shop }) => {
  /**
   * The settings tree has held groups since it was written, and this screen listed twenty services
   * flat and showed none of it — an owner who had organised his shop was shown a wall. The
   * remainder bin is named too, because a list with no heading above it reads as unfiled rather
   * than as deliberate.
   */
  const body = await open(shop, '/services');

  expect(body).toMatch(/خدمات غير مجمّعة/);
});

test('a changed cycle is written to the tree the engine reads, and survives a reload', async ({ shop }) => {
  await open(shop, '/services');

  // Open the first service — the names are his to edit, so it is chosen by position.
  await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();

  const cycle = shop.getByLabel('دورة التذكير (بالأيام)');
  await expect(cycle).toBeVisible();
  await cycle.fill('37');
  await cycle.blur();

  // A NUMBER NOBODY WOULD SEED. 37 cannot be a default that happened to already be there, which
  // is what makes the reload below proof rather than coincidence.
  await expect(shop.getByText('كل 37 يوماً').first()).toBeVisible({ timeout: 30_000 });

  const body = await open(shop, '/services');
  expect(body).toMatch(/كل 37 يوماً/);
  // AND IT SAYS WHERE IT HAPPENED (§10.8.1): a service holding its own value says so on itself,
  // never in a distant settings screen he would have to find.
  expect(body).toMatch(/إعداد خاص/);
});

test('nothing on it is an untranslated key', async ({ shop }) => {
  const body = await open(shop, '/services');

  expect(body).not.toMatch(/[a-z]+\.[a-z]+\.[a-z]+/);
});
