/**
 * «نقاط الولاء» — the rewards table, and what a visit is worth.
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

test('the table he edits is his own — every row came from him', async ({ shop }) => {
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
   *
   * IT RETIRES A REWARD IT CREATED, and this is the whole fix. The first version clicked «إيقاف»
   * on the FIRST row of the shop's own table — so every run retired one more of the seeded
   * rewards, and after three runs the table this file's first test asserts is filled was empty.
   * The suite was eating the fixture it depends on, one run at a time, and reported it as a
   * product failure on the fourth.
   *
   * A TEST THAT MUTATES SHARED STATE MUST CREATE WHAT IT MUTATES.
   */
  await open(shop, '/points');

  const name = `مكافأة اختبار ${Date.now().toString().slice(-6)}`;
  await shop.getByRole('button', { name: 'إضافة مكافأة' }).click();
  await shop.getByLabel('اسم المكافأة').fill(name);
  await shop.getByLabel('التكلفة بالنقاط').fill('999');
  // «هدية», EXPLICITLY. The form opens on «من خدماتي», which makes «ما يحصل عليه» required — and
  // the native block is silent to a test: the click lands, nothing submits, and the failure reads
  // as a broken create path thirty seconds later. A gift needs no second choice.
  await shop.getByLabel('النوع').selectOption({ label: 'هدية' });
  await shop.getByRole('button', { name: 'حفظ' }).click();

  const row = shop.locator('li', { hasText: name }).first();
  await expect(row).toBeVisible({ timeout: 30_000 });

  await row.getByRole('button', { name: 'إيقاف' }).click();
  await expect(row.getByText('موقوفة')).toBeVisible({ timeout: 30_000 });
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
