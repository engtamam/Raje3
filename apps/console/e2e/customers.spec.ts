/**
 * «عملائي» — who I have, and who is overdue.
 */
import { expect, open, test } from './fixtures';

test('the list renders, and an empty one says so rather than showing nothing', async ({ shop }) => {
  // Either customers, or a sentence — `open` already fails if neither ever appears. What this
  // adds is that the sentence is ARABIC and ours, not a raw state leaking through.
  const body = await open(shop, '/customers');

  expect(body).toMatch(/[؀-ۿ]/);
});

test('the keypad finds a customer by part of his number', async ({ shop }) => {
  /**
   * THE ROUTE THIS NEEDS WAS MISSING FROM THE GATEWAY, and a browser found it: every keystroke
   * 404'd on /api/v1/search, so searching simply did not work — and nothing in any service log
   * said so, because a 404 at the gateway never reaches a service.
   *
   * Prefix search is search-service's, not operations': operations answers an EXACT number, and a
   * prefix scan over the datastore is a table scan inside a five-second budget.
   */
  await open(shop, '/customers');
  const box = shop.getByRole('textbox').first();
  if (await box.count() === 0) test.skip(true, 'no search box on this screen');

  const failed: string[] = [];
  shop.on('response', (r) => { if (r.status() === 404 && r.url().includes('/search')) failed.push(r.url()); });

  await box.fill('05');
  await shop.waitForTimeout(1500);

  expect(failed, 'the search route 404s — the gateway has no /api/v1/search prefix').toEqual([]);
});

test('the third reason it exists is answered: who has not come back', async ({ shop }) => {
  /**
   * This screen names three reasons to open it — how many do I have, find this one, WHO IS
   * OVERDUE — and for weeks it answered two. The third could not be built at all: the overdue list
   * lives in reminders, and reminders holds no names, deliberately.
   *
   * An empty answer here is the one empty state in the product that is good news, so it is
   * asserted as a SENTENCE rather than as an absence — a blank panel would be indistinguishable
   * from a read that failed.
   */
  await open(shop, '/customers');
  await shop.getByRole('radio', { name: 'من تأخّر' }).click();

  await expect(shop.getByText(/لا أحد متأخر|كل عميل إما زار/).first())
    .toBeVisible({ timeout: 30_000 });
});

test('the search belongs to the list it searches', async ({ shop }) => {
  /**
   * Typing a number while «من تأخّر» is open would search everybody and quietly leave the tab the
   * owner is looking at — the same control answering a different question than the one on screen.
   */
  await open(shop, '/customers');
  await expect(shop.getByPlaceholder('ابحث برقم الجوال أو الاسم')).toBeVisible();

  await shop.getByRole('radio', { name: 'من تأخّر' }).click();
  await expect(shop.getByPlaceholder('ابحث برقم الجوال أو الاسم')).toBeHidden();
});

test('nothing on it is an untranslated key', async ({ shop }) => {
  await open(shop, '/customers');
  const body = await shop.locator('body').innerText();

  expect(body).not.toMatch(/\bauth\.[a-z]+\./);
  expect(body).not.toMatch(/\bpager\.[a-z]+/);
});

test('a customer row opens his record, and the record is not a dead end', async ({ shop }) => {
  /**
   * THE ROW USED TO BE INERT. The owner tapped a customer, nothing happened, and the only question
   * this section could answer was "does he exist" — his visits and his offers were in the product
   * and reachable from nowhere.
   *
   * A shop with no customers yet cannot prove this, and pretending otherwise would make the spec
   * green for the wrong reason: it says so and stops.
   */
  const body = await open(shop, '/customers');

  // THE EMPTY STATE IS THE SKIP SIGNAL, not a button count. Counting buttons found the tab
  // control and the search affordances and reported "there are rows" for a shop with none — so
  // the spec clicked something that did not navigate and then asserted against the list it was
  // still looking at. A shop with no customers cannot prove this, and it says so.
  if (body.includes('لا يوجد عملاء بعد')) {
    test.info().annotations.push({ type: 'skipped', description: 'لا عملاء في هذا المحل بعد' });
    return;
  }

  await shop.getByRole('button').filter({ hasText: /05\d/ }).first().click();
  await expect(shop).toHaveURL(/\/customers\/.+/);
  // The record answers all three of its questions — his offers included.
  await expect(shop.getByText('عروضه')).toBeVisible({ timeout: 30_000 });
  await expect(shop.getByText('زياراته')).toBeVisible();
});

test('a customer who was sent nothing is told that, not shown an apology', async ({ shop }) => {
  /**
   * Unlike an empty service catalogue, an empty offers list is not a fault: nobody seeds a customer
   * an offer. He gets one when the shop runs one, and saying so plainly beats apologising for a
   * gap that is not there.
   */
  const list = await open(shop, '/customers');
  if (list.includes('لا يوجد عملاء بعد')) return;

  await shop.getByRole('button').filter({ hasText: /05\d/ }).first().click();
  // WAIT FOR THE RECORD, do not re-open a URL: `open()` on the current path raced the navigation
  // and read the list again.
  await expect(shop.getByText('عروضه')).toBeVisible({ timeout: 30_000 });
  const body = await shop.locator('body').innerText();
  expect(body).toMatch(/لم يصله أي عرض بعد|ساري|انتهى/);
});
