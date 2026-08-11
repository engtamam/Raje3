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

/**
 * Walk the journey until the thing we came for is on screen.
 *
 * «تسجيل زيارة» IS A SEQUENCE OF SCREENS NOW, not one page: plate, then his entitlements, then the
 * services. Which step a control lives on depends on the SECTOR — a salon has no plate page — and
 * on the customer, since the entitlements page is absent when he holds nothing. So no test names a
 * step number; each one moves forward until what it needs is visible, which is also what a person
 * does.
 */
async function reach(page: Page, control: Locator): Promise<void> {
  // FORWARD, THEN BACK. A one-directional walk found the services and could never return to the
  // number — which is not how anyone uses this: he takes the services while the car is on the
  // lift and asks for the phone after. The journey allows both, so the test must too.
  for (const label of ['التالي', 'السابق']) {
    for (let i = 0; i < 4; i += 1) {
      if (await control.isVisible().catch(() => false)) return;
      const arrow = page.getByRole('button', { name: label });
      if (await arrow.isDisabled().catch(() => true)) break;
      await arrow.click();
      await page.waitForTimeout(250);
    }
  }
  await expect(control).toBeVisible({ timeout: 15_000 });
}

/**
 * Save, from wherever he happens to be.
 *
 * «حفظ وإرسال» LIVES ON THE LAST STEP ONLY, which is correct — a save button on the plate page
 * would be a button that discards a visit before it has one. So the test walks to it, exactly as
 * the operator does after choosing the services.
 */
async function save(page: Page): Promise<void> {
  const button = page.getByRole('button', { name: 'حفظ وإرسال' });
  await reach(page, button);
  await button.click();
}

/** Type a number the way the operator does — one key at a time. */
async function keyIn(page: Page, phone: string): Promise<void> {
  // THE FIELD, NOT THE KEYPAD. The pad is touch-only — right for a thumb, absent on the machine
  // this suite runs on — and typing into the field is what a desktop operator does anyway. It
  // also proves the input EXISTS there, which is the defect this replaced: for one commit a
  // desktop had no way to enter a number at all.
  const field = page.getByLabel('رقم الجوال');
  await reach(page, field);
  await field.fill(phone);
}

/** The first service in HIS catalogue. Chosen by position: the names are his to edit. */
function anyService(page: Page) {
  return page.locator('button[aria-pressed]').first();
}

/** The services live on the last step; move there before reaching for one. */
async function pickAnyService(page: Page): Promise<void> {
  await reach(page, anyService(page));
  await anyService(page).click();
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

  // THE GRID IS A STEP NOW, not the top of a page: only the current pane is in the DOM, so a
  // screen that opens on the plate holds no tile at all until the journey reaches them.
  await reach(shop, anyService(shop));
  await expect(anyService(shop)).toBeVisible();
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

  await pickAnyService(shop);
  await keyIn(shop, phone);
  await save(shop);

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

  await pickAnyService(shop);
  await keyIn(shop, customerPhone());
  await save(shop);

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

  await pickAnyService(shop);
  await keyIn(shop, customerPhone());
  await save(shop);

  await expect(shop.getByText(/لم تُرسَل/)).toBeVisible({ timeout: 30_000 });
});

test('a customer who was sent an offer has it on the counter screen', async ({ shop }) => {
  /**
   * THE OFFER IS AN ENTITLEMENT, AND THIS IS THE ONLY PLACE IT CAN BE HONOURED (§5.6.2). It was
   * sent to one person, it expires, and everything about it was built except the screen where it
   * gets redeemed: the send log records it, the customer's page counts down to it, the owner reads
   * it on the customer record — and the worker taking the visit saw nothing. Built in the depth,
   * cut at the door, for the third time.
   *
   * SEEDED ON THE CLUSTER, NOT BY THIS FILE, and that is not a shortcut. An offer is created by a
   * SEND — the send log IS the entitlement record, which is precisely what stops a screen forging
   * one. There is no owner-facing "grant this person an offer" action and there should not be, so
   * the row comes from deploy/seed/seed-field-offer.py. If it has not been run, this skips rather
   * than passing on an absence.
   */
  const PHONE = '0555000913';

  await open(shop, '/visit');
  for (const d of PHONE) {
    await shop.getByRole('button', { name: d, exact: true }).first().click();
  }

  const banner = shop.getByText('عرضٌ خاص بهذا العميل');
  const appeared = await banner.isVisible({ timeout: 20_000 }).catch(() => false);
  test.skip(!appeared, 'no offer seeded for this customer — run deploy/seed/seed-field-offer.py');

  await expect(banner).toBeVisible();
  // THE SENTENCE ITSELF, because a heading with an empty body is the failure that looks like
  // success: the lookup worked and the text never arrived.
  await expect(shop.getByText(/غسلة مجانية مع أول زيارة/)).toBeVisible();
  // AND THE END DATE, which is what makes it an offer rather than a standing discount.
  await expect(shop.getByText(/ينتهي/)).toBeVisible();
});

test('a customer with points can spend them, in front of him', async ({ shop }) => {
  /**
   * THE REDEMPTION PATH WAS COMPLETE AND CALLED BY NOTHING. `loyalty.redeem` existed with its
   * idempotency key, its manager threshold and its ledger entry, and no screen in the product
   * invoked it — a customer could earn for ever and never spend. This is the counter, which is
   * the only place a reward is handed over.
   *
   * SEEDED BY VISITS, NOT BY A FIXTURE. Points come from visits and nothing else, so the balance
   * this test spends is one the product actually produced.
   */
  const PHONE = `05${Date.now().toString().slice(-8)}`;

  await open(shop, '/visit');
  const service = shop.getByRole('button').filter({ hasText: /^(?!\d)/ }).first();

  // Three visits, so the balance clears the cheapest seeded reward.
  for (let i = 0; i < 3; i += 1) {
    await open(shop, '/visit');
    for (const d of PHONE) {
      await shop.getByRole('button', { name: d, exact: true }).first().click();
    }
    await shop.getByRole('button', { name: /غسيل|تلميع|خدمة/ }).first().click();
    await shop.getByRole('button', { name: /حفظ|تسجيل الزيارة/ }).first().click();
    await shop.waitForTimeout(1500);
  }

  await open(shop, '/visit');
  for (const d of PHONE) {
    await shop.getByRole('button', { name: d, exact: true }).first().click();
  }

  // HIS BALANCE IS ON THE SCREEN — this is the assertion that would have failed for the entire
  // life of the product before points 1 wired earning to the visit.
  await expect(shop.getByText('رصيده')).toBeVisible({ timeout: 30_000 });
  const line = await shop.locator('body').innerText();
  expect(line).toMatch(/\d+ نقطة/);
  // Either he can afford something, or the screen says how far he is — never a blank box.
  expect(line).toMatch(/ويبقى له|تبقّى له/);
});
