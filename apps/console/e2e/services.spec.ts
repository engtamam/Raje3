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

  expect(body).toMatch(/غير مجمّعة/);
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

test('the follow-up is saved AND reported — a summary that drops half of it is a wrong answer', async ({ shop }) => {
  /**
   * THE BUG THIS CATCHES, found by using the screen: the row's summary line read only the cycle.
   * An owner who typed 15 into «الاطمئنان», closed the row and saw «كل 10 يوماً» had every reason
   * to conclude it had not saved. It had — the service stores both, and the line reported one.
   */
  await open(shop, '/services');
  await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();

  const followUp = shop.getByLabel('الاطمئنان بعد الزيارة (بالأيام)');
  await expect(followUp).toBeVisible();
  await followUp.fill('19');
  await followUp.blur();

  // 19 is nobody's default, so finding it after a reload is proof rather than coincidence.
  await expect(shop.getByText(/اطمئنان بعد 19/).first()).toBeVisible({ timeout: 30_000 });
  const body = await open(shop, '/services');
  expect(body).toMatch(/اطمئنان بعد 19/);
});

test('each reminder field says what it sends, and previews when', async ({ shop }) => {
  /**
   * «الاطمئنان بعد الزيارة (بالأيام)» is a label, not a meaning: it never said what the customer
   * receives. Two identical number boxes read as one setting asked twice.
   */
  await open(shop, '/services');
  await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();

  // THE CONSEQUENCE IS ON THE CARD; THE EXPLANATION MOVED BEHIND «؟». Two paragraphs per field
  // filled a phone screen with prose an owner reads once in his life, so the sentence is one tap
  // away and the line that CHANGES AS HE TYPES stayed where it was. This asserts both: the
  // preview visible, and the explanation reachable.
  const body = await shop.locator('body').innerText();
  expect(body).toMatch(/تذكير بعد \d+ يوماً من كل زيارة|لا تذكير لهذه الخدمة|لا تذكير — إلا لخدمة خصّصتها/);

  // THE «؟» OF THE FIELD, not the first one on the page — the general card carries one of its own
  // about inheritance, and `.first()` picked that. Two controls with the same accessible name on
  // one page is exactly what an index-based click gets wrong, so this one is scoped to the row.
  const field = shop.locator('div').filter({ hasText: /^دورة التذكير/ }).first();
  await field.getByRole('button', { name: 'شرح' }).first().click();
  expect(await shop.locator('body').innerText())
    .toMatch(/الرسالة التي تُرجعه|كل كم يوماً يحتاج العميل/);
});

test('a service can be put in a group directly, not only when the system offers', async ({ shop }) => {
  /**
   * Grouping used to exist ONLY as a suggestion the system made after the owner had repeated
   * himself across three services. An owner who already knows «هذه كلها خدمات محرك» had no way to
   * say so. The suggestion is a shortcut now, not the gate.
   */
  await open(shop, '/services');
  await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();

  const picker = shop.getByLabel(/^مجموعة /);
  await expect(picker).toBeVisible();
  await expect(picker.locator('option', { hasText: 'مجموعة جديدة…' })).toHaveCount(1);
});

test('a service can leave its group, and a group can be deleted', async ({ shop }) => {
  /**
   * THE BUG THIS FILE WOULD HAVE CAUGHT, and did not: grouping was one-way. `set_group` wrote
   * `service_group[id]` and nothing anywhere could unset it — «بلا مجموعة» sat in the dropdown as
   * an option with no action behind it, and a group, once made, was permanent. Found by an owner
   * trying to undo his own edit, which is the only way a one-way door is ever found.
   */
  await open(shop, '/services');
  await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();

  const picker = shop.getByLabel(/^مجموعة /);
  await picker.selectOption({ label: 'مجموعة جديدة…' });
  const name = shop.getByLabel('اسم المجموعة الجديدة');
  await expect(name).toBeVisible();
  // A NAME OF ITS OWN, EVERY RUN. A fixed name is a group that survives the run that made it —
  // the next run finds «مجموعة الإثبات» already on screen, selects «مجموعة جديدة…» to make it
  // again, and the assertions then race two identical headings. The test passed alone and failed
  // in the file, which is the signature of state left behind rather than a product fault.
  // RANDOM, NOT CLOCK-DERIVED: the last five digits of `Date.now()` repeat every hundred seconds,
  // so two runs in one afternoon collided on the very name this line exists to keep unique.
  const group = `مجموعة الإثبات ${Math.floor(Math.random() * 90_000) + 10_000}`;
  await name.fill(group);
  await name.press('Enter');

  // It is a heading now, and the heading carries the act that unmakes it.
  await expect(shop.getByRole('heading', { name: new RegExp(group) })).toBeVisible({ timeout: 30_000 });
  await expect(shop.getByRole('button', { name: 'حذف المجموعة' })).toBeVisible();

  // AND THE SERVICE CAN WALK OUT ON ITS OWN, without taking the group with it.
  //
  // THE ROW IS ALREADY OPEN. Re-clicking it here CLOSED it — the header is a toggle — and the
  // picker then never appeared, which the run reported as a missing control on a screen that was
  // behaving exactly as designed. Opened only if it is shut, which is also what a person does.
  if (!(await shop.getByLabel(/^مجموعة /).first().isVisible().catch(() => false))) {
    await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();
  }
  await shop.getByLabel(/^مجموعة /).first().selectOption('');
  await expect(shop.getByRole('heading', { name: new RegExp(group) })).toHaveCount(0, { timeout: 30_000 });
});

test('it opens on what he sells, with what he stopped one tap away', async ({ shop }) => {
  /**
   * REACHABLE IS NOT THE SAME AS ALWAYS PRESENT. A retired line must be findable or «تفعيل» acts
   * on nothing — that is the bug that produced the owner's list at all. But a shop open two years
   * accumulates lines it stopped selling, and mixing them into the working list makes every
   * ordinary edit a matter of reading past the dead ones.
   */
  await open(shop, '/services');

  // Stop the first one, so there is something to filter for.
  await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();
  await shop.getByRole('button', { name: 'إيقاف' }).first().click();

  // THE STRIP APPEARS ONLY NOW — offering «الموقوفة» to a shop with none is a control answering a
  // question nobody asked.
  const stopped = shop.getByRole('radio', { name: /الموقوفة/ });
  await expect(stopped).toBeVisible({ timeout: 30_000 });
  // And it opened on «المفعّلة» without being asked: fewest taps for the ordinary visit.
  await expect(shop.getByRole('radio', { name: 'المفعّلة' })).toBeChecked();

  await stopped.click();
  await expect(shop.getByText('موقوفة').first()).toBeVisible({ timeout: 30_000 });

  // PUT IT BACK, so the next run starts where this one did — and reach for the row the way this
  // tab actually renders it. The cycle line («كل 90 يوماً») belongs to the ACTIVE list; a retired
  // row is headed by its name and its «موقوفة» badge, so filtering on a cycle here matched nothing
  // and the cleanup hung for the full minute — leaving the service stopped for every later run.
  // EVERY STOPPED LINE, not only the one this run stopped. Earlier runs died before their own
  // cleanup and left services retired behind them — the tab already read «الموقوفة (2)» — and a
  // shop that accumulates dead lines run after run is a fixture rotting one failure at a time.
  for (let i = 0; i < 10; i += 1) {
    const stoppedRow = shop.getByRole('button', { name: /موقوفة/ }).first();
    if (!(await stoppedRow.isVisible().catch(() => false))) break;
    await stoppedRow.click();
    const restore = shop.getByRole('button', { name: 'تفعيل' }).first();
    await expect(restore).toBeVisible({ timeout: 30_000 });
    await restore.click();
    await shop.waitForTimeout(800);
  }
  // AND PROVEN BACK: nothing is left retired. A cleanup that is not asserted is a cleanup that
  // silently stopped working, which is exactly how this one was found.
  await expect(shop.getByRole('radio', { name: /الموقوفة/ })).toBeHidden({ timeout: 30_000 });
});
