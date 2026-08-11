/**
 * «حسابي» — the section every role has, and the only one gated on nothing.
 *
 * `requires: []` IS CORRECT HERE AND NOWHERE ELSE. It holds the things every person has regardless
 * of role — his password, his language, signing out — and the rows that are NOT his (billing, the
 * WhatsApp connection) are hidden one by one inside the screen, from the same catalogue. An
 * operator opening it must see a SHORT page, never a broken one.
 *
 * AND THE CONNECTION LINE MUST BE TRUE. «واتساب مربوط» on a shop that is not connected is the one
 * lie that costs an owner customers silently: he stops checking, and the reminders were never
 * going out.
 */
import { expect, open, test } from './fixtures';

test('it opens as tabs, and the open one says what it is for', async ({ shop }) => {
  const body = await open(shop, '/account');

  expect(body).toMatch(/الاشتراك/);
  expect(body).toMatch(/واتساب/);
  expect(body).toMatch(/دخولي/);
  // THE SENTENCE UNDER THE STRIP, which is what stops five nouns being five things he must open
  // to understand. It follows the tab, so it is asserted on the tab that is actually open.
  expect(body).toMatch(/باقتك، فواتيرك/);

  await shop.getByRole('radio', { name: 'دخولي' }).click();
  expect(await shop.locator('body').innerText()).toMatch(/جوالك وكلمة مرورك/);
});

test('the plans arrive from billing, with a price and what each one buys', async ({ shop }) => {
  /**
   * NOT A LIST IN THE APP. The names and the prices are rows in billing-service, so this asserts
   * the screen is reading them rather than carrying its own copy — the copy is what goes stale the
   * first time a price changes and nobody remembers there were two of them.
   */
  const body = await open(shop, '/account');

  expect(body).toMatch(/ريال \/ شهر/);
  expect(body).toMatch(/اختر هذه الباقة/);
  // What a plan buys, in words rather than in machine keys like `staff.seats`.
  expect(body).toMatch(/مقاعد للموظفين|رسائل في الشهر/);
  expect(body).not.toMatch(/staff\.seats|feature\./);
});

test('choosing a plan before the number is linked is answered, never refused', async ({ shop }) => {
  /**
   * A wall at the moment somebody decided to pay is the most expensive sentence in the product.
   * The press is accepted, the choice is remembered by name, and the button in front of him is the
   * next step rather than a dismissal.
   */
  await open(shop, '/account');
  await shop.getByRole('button', { name: 'اختر هذه الباقة' }).first().click();

  const body = await shop.locator('body').innerText();
  expect(body).toMatch(/خطوة واحدة تفصلك/);
  expect(body).toMatch(/رقم واتساب محلّك أنت/);
  await expect(shop.getByRole('button', { name: 'اربط رقمي الآن' })).toBeVisible();
});

test('the data rights are buttons he can press, not a paragraph about a right', async ({ shop }) => {
  await open(shop, '/account');
  await shop.getByRole('radio', { name: 'بياناتي وأوراقي' }).click();

  await expect(shop.getByRole('button', { name: 'تصدير نسخة' })).toBeVisible();
  await expect(shop.getByRole('button', { name: 'حذف بياناتي' })).toBeVisible();
});

test('an unconnected shop is told it is unconnected', async ({ shop }) => {
  /**
   * A fresh shop has no WhatsApp account, and the line must say so rather than default to the
   * comfortable answer. This is the assertion that would fail the day somebody renders the status
   * from an optimistic default instead of from the connection.
   */
  const body = await open(shop, '/account');

  expect(body).toMatch(/واتساب غير مربوط|يحتاج ربط/);
  expect(body).not.toMatch(/واتساب مربوط/);
});

test('the legal papers are reachable from here, because PDPL is not a footnote', async ({ shop }) => {
  await open(shop, '/account');
  expect(await shop.locator('body').innerText()).toMatch(/بياناتي وأوراقي/);

  await shop.getByRole('radio', { name: 'بياناتي وأوراقي' }).click();
  expect(await shop.locator('body').innerText()).toMatch(/الاحتفاظ، التصدير، الاتفاقيات/);
});

test('nothing on it is an untranslated key', async ({ shop }) => {
  const body = await open(shop, '/account');

  expect(body).not.toMatch(/[a-z]+\.[a-z]+\.[a-z]+/);
});
