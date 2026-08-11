/**
 * «نقاطي» — the rewards table, and what a visit is worth.
 *
 * THE PROMISE UNDER TEST IS §10.8: the table ARRIVES FILLED for his sector. That sentence was on
 * the screen for weeks while no service in this product had ever been asked to fill it — the empty
 * state told every owner on his first day that something had gone wrong and to contact us. A
 * promise nothing implements is worse than a missing feature, because it wastes his time proving
 * ours is broken.
 *
 * AND THE SCREEN MUST BE ABLE TO DO WHAT §9.4 SAYS: edit a number, retire one, add one. It was
 * read-only over an API that has always accepted all three.
 */
import { expect, open, test } from './fixtures';

test('the table arrives filled for his sector — he never starts from a blank page', async ({ shop }) => {
  await open(shop, '/points');

  await expect(shop.getByText('جدول المكافآت فارغ')).toBeHidden();
  // The rewards are seeded with their cost, and «نقطة» is the unit beside every one of them.
  await expect(shop.getByText('نقطة').first()).toBeVisible();
});

test('every reward says what KIND it is, because the kinds behave differently', async ({ shop }) => {
  /**
   * §9.4: a `service` reward IS a catalogue service — redeeming it records a real visit and
   * restarts the reminder cycle. An owner who cannot tell it from a gift cannot price either.
   */
  const body = await open(shop, '/points');

  expect(body).toMatch(/خدمة من الكتالوج|منتج أو هدية|خصم/);
});

test('a reward can be retired without being deleted', async ({ shop }) => {
  /**
   * RETIRED, NEVER DELETED. Every redemption in history references a reward, and its name and cost
   * are snapshotted onto the receipt precisely so that repricing it does not restate what a
   * customer was told last year.
   */
  await open(shop, '/points');

  const stop = shop.getByRole('button', { name: 'إيقاف' }).first();
  await expect(stop).toBeVisible();
  await stop.click();

  await expect(shop.getByText('موقوفة').first()).toBeVisible({ timeout: 30_000 });
  // It is still in the table — the row did not disappear, it changed state.
  await expect(shop.getByRole('button', { name: 'تفعيل' }).first()).toBeVisible();
});

test('the earning tab is a SWITCH, never two boxes ticked at once', async ({ shop }) => {
  /**
   * §9.3: a shop granting by invoice AND by service grants twice for one transaction — an error
   * that does not appear on any screen, only at the end of the month as an obligation double what
   * he expected. A radiogroup can hold exactly one answer; two checkboxes cannot.
   */
  await open(shop, '/points');
  await shop.getByRole('radio', { name: 'الكسب' }).click();

  const mode = shop.getByRole('radiogroup', { name: 'طريقة احتساب النقاط' });
  await expect(mode).toBeVisible();
  await expect(mode.getByRole('radio')).toHaveCount(2);
  await expect(mode.getByRole('radio', { name: 'بالخدمات' })).toBeChecked();
});

test('nothing on it is an untranslated key', async ({ shop }) => {
  const body = await open(shop, '/points');

  // The kit degrades to printing the raw key when a string is missing from its i18n context —
  // three of those reached a real screen before this assertion existed on every page.
  expect(body).not.toMatch(/[a-z]+\.[a-z]+\.[a-z]+/);
});
