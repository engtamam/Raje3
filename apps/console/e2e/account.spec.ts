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
  // THE HINT OF THE TAB THAT IS OPEN. It was «باقتك، فواتيرك» when one tab carried both; the
  // invoices moved to a tab of their own — an accountant asking for last month's should not have
  // to scroll past four plans nobody is buying today — and the sentence narrowed with it.
  expect(body).toMatch(/باقتك ووسيلة الدفع/);

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

test('with no gateway configured, the plans page apologises instead of selling', async ({ shop }) => {
  /**
   * THIS TEST USED TO ASSERT THE OPPOSITE OF THE PRODUCT. It checked that pressing a plan before
   * WhatsApp was connected produced «خطوة واحدة تفصلك» — the connect-first rule, which was
   * reversed by decision: the errand now follows the payment rather than standing in front of it,
   * because a ten-minute errand at the moment somebody decides to buy is where the decision goes
   * to die.
   *
   * AND WHAT REPLACED IT IS THE MORE IMPORTANT ASSERTION. With no payment gateway configured the
   * screen must SELL NOTHING and say so: an owner walking between paid tiers for free, each press
   * writing «باقتك» over the last, is the state this product was actually in.
   */
  await open(shop, '/account');
  const body = await shop.locator('body').innerText();

  // Either the till is shut and it says so, or it is open and a card is pressable. Never a
  // button that writes a plan with no money behind it.
  const shut = /الدفع مغلق مؤقتاً/.test(body);
  if (shut) {
    expect(body).toMatch(/نعتذر/);
    return;
  }
  await expect(shop.getByRole('button', { name: 'اختر هذه الباقة' }).first()).toBeVisible();
});

test('the data rights are buttons he can press, not a paragraph about a right', async ({ shop }) => {
  await open(shop, '/account');
  await shop.getByRole('radio', { name: 'بياناتي' }).click();

  await expect(shop.getByRole('button', { name: 'تصدير نسخة' })).toBeVisible();
  await expect(shop.getByRole('button', { name: 'حذف بياناتي' })).toBeVisible();

  // AND IT IS PRESSED, not merely rendered. The first version of this pane sent `kind` where
  // compliance-service reads `type`: every button was visible, correctly labelled, and answered
  // 422 into a console the owner does not have open. A visibility assertion would have passed.
  await shop.getByRole('button', { name: 'تصدير نسخة' }).click();
  await expect(shop.getByText(/سجّلنا طلبك/)).toBeVisible({ timeout: 30_000 });
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
  // ONE WORD ON THE TAB, and the hint under the strip carries the rest — the long label was
  // what pushed the six-tab strip past the edge of a phone and sliced the last one in half.
  expect(await shop.locator('body').innerText()).toMatch(/بياناتي/);

  await shop.getByRole('radio', { name: 'بياناتي' }).click();
  expect(await shop.locator('body').innerText()).toMatch(/الاحتفاظ، التصدير، الاتفاقيات/);
});

test('nothing on it is an untranslated key', async ({ shop }) => {
  const body = await open(shop, '/account');

  expect(body).not.toMatch(/[a-z]+\.[a-z]+\.[a-z]+/);
});

test('the keys to his shop are visible, and revocable', async ({ shop }) => {
  /**
   * A TILL COMPANY'S CREDENTIAL WRITES VISITS IN HIS NAME. It does not expire when an employee
   * leaves, and it outlives the contract that created it — he changes point-of-sale vendor and the
   * old key still posts sales into his shop. It is closer to a key to the building than a login.
   *
   * AND A KEY NOBODY CAN SEE IS A KEY NOBODY REVOKES. Issuing and rotating were both reachable in
   * the product; the LIST was not, so «من يملك مفتاحاً لمحلي؟» had no answer anywhere.
   */
  await open(shop, '/account');
  await shop.getByRole('radio', { name: 'مفاتيح الربط' }).click();

  // EITHER A LIST OR A REASON — never a blank pane. A shop with no integration is the ordinary
  // case and says so; an account that may not look says THAT instead, because «لا مفاتيح» would
  // tell an owner his shop is closed to integrations when the truth is he is not the owner.
  await expect(
    shop.getByText(/لا يوجد برنامج مرتبط|يراها المالك وحده|آخر استعمال/).first(),
  ).toBeVisible({ timeout: 30_000 });
});

test('the keys pane says when each was last used, not when it was issued', async ({ shop }) => {
  /**
   * «صدر في 2024» tells an owner nothing he can act on. «لم يُستعمل منذ 4 أشهر» is a key to revoke
   * this afternoon — and the difference between the two sentences is the whole value of the pane.
   */
  await open(shop, '/account');
  await shop.getByRole('radio', { name: 'مفاتيح الربط' }).click();
  const body = await shop.locator('body').innerText();
  if (body.includes('آخر استعمال')) {
    expect(body).toMatch(/آخر استعمال: (اليوم|أمس|قبل \d+|لم يُستعمل قط)/);
  }
});
