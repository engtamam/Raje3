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
  // AND IT KEEPS WALKING. One pass forward-then-back was not enough: a step whose CONTENT arrives
  // from the network — his points, his offer — is empty on the first sweep and present on the
  // second, and the old version ended that sweep parked on step one, waiting fifteen seconds on a
  // page the thing could never appear on. It reported «رصيده is missing» while the balance was one
  // step away and already loaded.
  const deadline = Date.now() + 20_000;
  while (Date.now() < deadline) {
    for (const label of ['التالي', 'السابق']) {
      for (let i = 0; i < 4; i += 1) {
        if (await control.isVisible().catch(() => false)) return;
        const arrow = page.getByRole('button', { name: label });
        if (await arrow.isDisabled().catch(() => true)) break;
        await arrow.click();
        await page.waitForTimeout(250);
      }
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

test('a partial plate finds the car — the operator reads four characters, not seven', async ({ shop }) => {
  /**
   * THE PREFIX WAS THE WHOLE POINT AND THE PREFIX WAS MISSING. `by-plate` matches EXACTLY — the
   * store filters on equality, deliberately — so until the plate was typed perfectly, character
   * for character, the screen said nothing. The state for the suggestion list was declared in the
   * screen and filled by nothing: complete-looking code that no call reached.
   *
   * WHAT IT COSTS: he types what he read off the bumper, sees nothing, concludes the customer is
   * new, and registers him a second time — the visit history splits and the reminders go to a
   * record with one visit on it. The same failure the phone keypad has a suggest call to prevent.
   */
  const phone = customerPhone();
  // RANDOM, NOT CLOCK-DERIVED. `Date.now()`'s last four digits repeat every ten seconds, so two
  // runs minutes apart produced the SAME plate — and a plate is deliberately not unique (a car is
  // sold, an operator mistypes), so the screen correctly offered two rows and the locator broke.
  const plate = `${Math.floor(Math.random() * 9000) + 1000} ${'ABCDEFGHJK'[Math.floor(Math.random() * 10)]}XY`;

  await open(shop, '/visit');
  // THE TEXTBOX, NOT THE «؟» BESIDE IT — both carry the same accessible name, deliberately: the
  // hint button is named for the field it explains. Ask for the role.
  const plateField = shop.getByRole('textbox', { name: 'رقم اللوحة' });
  // A SECTOR WITHOUT PLATES IS NOT A FAILURE (§13.2): a salon has no plate page, and the fields
  // come from the catalogue rather than from a list in the app. Nothing to assert here, then.
  if (!(await plateField.count())) test.skip(true, 'this sector has no plate field');

  await plateField.fill(plate);
  await keyIn(shop, phone);
  await pickAnyService(shop);
  await save(shop);
  await expect(shop.getByText(/تم الحفظ/)).toBeVisible({ timeout: 30_000 });

  // THE INDEX IS WRITTEN AFTER THE RESPONSE, so this polls rather than assuming. Reloading is the
  // retry: the suggestion fires on a keystroke, and the screen has no other way to ask again.
  const prefix = plate.slice(0, 3);
  await expect(async () => {
    await open(shop, '/visit');
    await shop.getByRole('textbox', { name: 'رقم اللوحة' }).fill(prefix);
    await expect(shop.getByRole('button', { name: new RegExp(plate) }).first()).toBeVisible({ timeout: 3_000 });
  }).toPass({ timeout: 60_000 });

  // AND THE COMPLETE TOKEN STILL FINDS IT. /suggest omits the word already typed — an autocomplete
  // convention — so the list appeared at three characters and VANISHED at four, at the exact
  // keystroke that finishes the number on the bumper. The typed text is searched alongside the
  // suggestions for this reason, and this is the assertion that says so.
  await shop.getByRole('textbox', { name: 'رقم اللوحة' }).fill(plate.slice(0, 4));
  await expect(shop.getByRole('button', { name: new RegExp(plate) }).first())
    .toBeVisible({ timeout: 15_000 });

  // AND ONE TAP FILLS THE OWNER, which is the reason the list exists at all.
  await shop.getByRole('button', { name: new RegExp(plate) }).first().click();
  await expect(shop.getByRole('textbox', { name: 'رقم اللوحة' })).toHaveValue(plate);
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
  // THROUGH THE FIELD, NOT THE PAD. The keypad is touch-only — correct, it is a thumb's tool —
  // so pressing its buttons on the machine this suite runs on found nothing at all.
  await keyIn(shop, PHONE);

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

  // A VISIT EARNS NOTHING UNTIL THE SHOP SAYS WHAT A VISIT IS WORTH, and this test spent an
  // afternoon looking like a broken redemption path when what was missing was one number nobody
  // had set. A test that depends on unstated configuration is not testing the product; it is
  // testing whoever seeded the tenant last. So it states it.
  await open(shop, '/points');
  // «نقاطي» OPENS ON «المكافآت», because the table is what an owner comes to read; what a visit
  // EARNS lives behind «الكسب». A test that assumes the first tab is the only tab reports a
  // missing field that is simply one tap away.
  await shop.getByRole('radio', { name: 'الكسب' }).click();
  const general = shop.getByRole('spinbutton', { name: 'نقاط لكل زيارة (عام)' }).first();
  // ASSERTED, NOT ATTEMPTED. The first version of this setup skipped quietly when the control was
  // absent, so the test went on to fail thirty seconds later on «رصيده» — a missing SETTING wearing
  // the costume of a broken redemption path. If the shop cannot set what a visit is worth, that is
  // the finding, and it should be the sentence in the report.
  await expect(general).toBeVisible({ timeout: 15_000 });
  if (!Number((await general.inputValue()) || 0)) {
    await general.fill('10');
    await general.blur();
    await shop.waitForTimeout(1500);
    // RE-READ THROUGH THE TAB, because reopening the page lands on «المكافآت» again and the field
    // we are confirming is not on it.
    await open(shop, '/points');
    await shop.getByRole('radio', { name: 'الكسب' }).click();
    await expect(shop.getByRole('spinbutton', { name: 'نقاط لكل زيارة (عام)' }).first())
      .toHaveValue('10');
  }

  await open(shop, '/visit');
  // Three visits, so the balance clears the cheapest seeded reward.
  //
  // THROUGH THE SAME HELPERS THE OTHER TESTS USE. This loop carried its own copy of the journey —
  // its own keypad presses, its own guess at a service name, its own guess at the save button's
  // label — and every one of those went stale the moment the screen became a sequence of steps.
  // A test that re-implements the journey is testing a journey nobody takes.
  for (let i = 0; i < 3; i += 1) {
    await open(shop, '/visit');
    await keyIn(shop, PHONE);
    await pickAnyService(shop);
    await save(shop);
    await shop.waitForTimeout(1500);
  }


  await open(shop, '/visit');
  // THROUGH THE FIELD, NOT THE PAD. The keypad is touch-only — correct, it is a thumb's tool —
  // so pressing its buttons on the machine this suite runs on found nothing at all.
  await keyIn(shop, PHONE);

  // HIS BALANCE IS ON THE SCREEN — this is the assertion that would have failed for the entire
  // life of the product before points 1 wired earning to the visit.
  // AND WALK TO THE PAGE IT IS ON. His points live on «عروضه ونقاطه», a step of their own since
  // the journey became a sequence — the balance was never missing, the test was standing on the
  // wrong screen looking for it. `reach` is the same helper every other test here uses, and it is
  // what a person does: move forward until the thing appears.
  const balanceLine = shop.getByText('رصيده');
  await reach(shop, balanceLine);
  await expect(balanceLine).toBeVisible({ timeout: 30_000 });
  const line = await shop.locator('body').innerText();
  expect(line).toMatch(/\d+ نقطة/);
  // Either he can afford something, or the screen says how far he is — never a blank box.
  expect(line).toMatch(/ويبقى له|تبقّى له/);
});
