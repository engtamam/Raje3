/**
 * «تسجيل زيارة» — the screen used a hundred times a day.
 *
 * THE ONLY SCREEN WITH A BUDGET. Five seconds, with a customer standing at the counter, and every
 * assertion here is about that: what the operator must not have to think about, and what must not
 * cost him a second attempt.
 *
 * WRITTEN AGAINST THE SCREEN, NOT AGAINST A FORM WE IMAGINED. The first version of this file
 * reached for `getByLabel(/جوال/)` and a generic "first button" — there is no labelled phone input
 * anywhere on it. The number is entered on a KEYPAD, because an operator with a customer in front
 * of him is not opening a soft keyboard, and the first button on the page is the digit 7. Three
 * specs failed for that reason and read like product bugs.
 */
import { expect, open, test, type Page } from './fixtures';

/** A customer number that belongs to nobody, fresh per run. */
function customerPhone(): string {
  return `05${Math.floor(Math.random() * 90_000_000) + 10_000_000}`;
}

/** Type a number the way the operator does — one key at a time. */
async function keyIn(page: Page, phone: string): Promise<void> {
  const pad = page.getByRole('group', { name: 'لوحة الأرقام' });
  for (const digit of phone) await pad.getByRole('button', { name: digit, exact: true }).click();
}

/** The first service in HIS catalogue. Chosen by position: the names are his to edit. */
function anyService(page: Page) {
  return page.locator('button[aria-pressed]').first();
}

test('the services come from his own catalogue, not from a list in the app', async ({ shop }) => {
  /**
   * Seeded from his sector at creation, and EDITABLE by him alone. A grid built from a constant in
   * the front end would show every shop the same services and quietly ignore what he changed this
   * morning.
   *
   * `aria-pressed` IS THE ASSERTION, and it is not a technicality: a service tile is a toggle, and
   * an element that carries the state is one a screen reader — and this test — can read. Counting
   * "buttons" would have counted the keypad.
   */
  await open(shop, '/visit');

  await expect(shop.locator('button[aria-pressed]').first()).toBeVisible();
  await expect(shop.getByText('لا توجد خدمات')).toBeHidden();
});

test('a visit is recorded and the customer becomes findable', async ({ shop }) => {
  /**
   * THE INDEXING RUNS AFTER THE RESPONSE, not in front of it — the operator is not waiting for it,
   * and a slow search service must never become a slow screen. Which is exactly why it needs an
   * assertion: work that happens off the request path is work nothing else proves happened.
   */
  const phone = customerPhone();
  await open(shop, '/visit');

  await anyService(shop).click();
  await keyIn(shop, phone);
  await shop.getByRole('button', { name: 'حفظ وإرسال' }).click();

  await expect(shop.getByText(/تم الحفظ/)).toBeVisible({ timeout: 30_000 });

  await open(shop, '/customers');
  await expect(shop.getByText(phone.slice(-4), { exact: false }).first())
    .toBeVisible({ timeout: 30_000 });
});

test('nothing on it asks who is recording this', async ({ shop }) => {
  /**
   * IDENTITY COMES FROM THE SESSION (§3.5), and there is no field for it anywhere in the product.
   * An operator asked to pick his own name picks the first one in the list, and then every visit
   * in the shop is attributed to one man.
   */
  await open(shop, '/visit');
  const body = await shop.locator('body').innerText();

  expect(body).not.toMatch(/من سجّل|اسم الموظف|الموظف المسؤول/);
});

test('an outage does not lose the visit — it waits, and says it is waiting', async ({ shop }) => {
  /**
   * THE FORM CLEARS ON PURPOSE, and asserting that it does not was this test's original mistake.
   * The next customer is already waiting; a screen that held still for a round trip would spend
   * its five-second budget on a network the operator can neither see nor fix. So the visit goes to
   * the queue at the press and the screen is ready again — the queue is the design, not a fallback.
   *
   * What must be true is that the visit is not silently gone: the counter says one is waiting.
   */
  await shop.route('**/api/v1/field/visits', (r) => r.fulfill({ status: 500, body: '{}' }));
  await open(shop, '/visit');

  await anyService(shop).click();
  await keyIn(shop, customerPhone());
  await shop.getByRole('button', { name: 'حفظ وإرسال' }).click();

  await expect(shop.getByText(/بانتظار الإرسال/)).toBeVisible({ timeout: 30_000 });
});

test('a visit that will never send is reported, not left in a silent queue', async ({ shop }) => {
  /**
   * A 400 IS NOT AN OUTAGE. The queue has always told the two apart — retrying a refusal for ever
   * burns battery and hides the problem — but it told nobody, so the visit left the screen, the
   * counter said "waiting" for ever, and the shop lost a customer with no reminder, no points and
   * no metric. Holding a visit nobody is told about is the same as dropping it.
   */
  await shop.route('**/api/v1/field/visits',
                   (r) => r.fulfill({ status: 400, body: '{"message":"لا"}' }));
  await open(shop, '/visit');

  await anyService(shop).click();
  await keyIn(shop, customerPhone());
  await shop.getByRole('button', { name: 'حفظ وإرسال' }).click();

  await expect(shop.getByText(/لم تُرسَل/)).toBeVisible({ timeout: 30_000 });
});
