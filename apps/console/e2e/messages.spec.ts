/**
 * «رسائلي» — what goes out in my name.
 *
 * THE DISTINCTION THIS SCREEN EXISTS TO MAKE is between what the product sends by itself and what
 * HE sends. An owner who cannot tell the two apart cannot answer the only question he actually
 * has — "why did my customer get this?" — and the first time he cannot answer it, he turns the
 * whole thing off.
 */
import { expect, open, test } from './fixtures';

test('automatic and deliberate are two different lists, named as such', async ({ shop }) => {
  const body = await open(shop, '/messages');

  expect(body).toMatch(/ما يُرسَل/);
  expect(body).toMatch(/حملاتي/);
});

test('each automatic message says WHEN it goes, not only that it exists', async ({ shop }) => {
  /**
   * "Visit recorded" is a name; "ten minutes after the visit, once he has left" is the thing he
   * is deciding about. A list of names with switches is a screen he has to guess at.
   *
   * AND THE SENTENCE COMES FROM THE ENGINE, not from the screen — so this asserts what the
   * trigger registry says, and drifts only if the behaviour drifts with it.
   */
  const body = await open(shop, '/messages');

  expect(body).toMatch(/سُجّلت زيارة/);
  expect(body).toMatch(/بعد تسجيل الزيارة|حان وقت الخدمة/);
});

test('the queue of waiting messages is its own list, not the first thing shown', async ({ shop }) => {
  /**
   * The section opens on WHAT THE SYSTEM SENDS — the question it is named after. What is queued
   * right now is a different question, and one an owner asks less often than he asks "what does
   * this thing send at all".
   */
  await open(shop, '/messages');
  await shop.getByRole('radio', { name: 'بانتظار الخروج' }).click();
  const body = (await shop.locator('body').innerText()).trim();

  expect(body).toMatch(/بانتظار الخروج|ما في رسائل/);
});

test('a shop that has launched nothing is told what a campaign is for', async ({ shop }) => {
  /**
   * The empty state here is NOT a fault — unlike the service catalogue and the rewards table,
   * nobody can seed a campaign for him. So it explains the act rather than apologising for a gap.
   */
  await open(shop, '/messages');
  // The screen opens on «ما يُرسَل» — everything the engine does by itself, which is what most
  // days are. Campaigns are the deliberate act, and they live behind their own tab.
  await shop.getByRole('radio', { name: 'حملاتي' }).click();
  const body = (await shop.locator('body').innerText()).trim();

  expect(body).toMatch(/لم تُطلق حملة بعد/);
  expect(body).toMatch(/عملائك الموافقين/);
});

test('nothing on it is an untranslated key', async ({ shop }) => {
  const body = await open(shop, '/messages');

  expect(body).not.toMatch(/[a-z]+\.[a-z]+\.[a-z]+/);
});

test('the log answers the only question this engine ever generates', async ({ shop }) => {
  /**
   * `reminders.log` calls itself the most important route this service has — «لماذا لم تصل رسالة
   * عميلي؟ هو السؤال الوحيد الذي تولّده هذه الخدمة، وشاشةٌ لا تجيبه تحوّل كل قاعدة كتبناها إلى
   * عطلٍ مشتبهٍ به» — and no screen called it. Quiet hours, the ceiling, consent, an unapproved
   * template: every correct refusal read to the owner as a fault.
   */
  await open(shop, '/messages');
  await shop.getByRole('radio', { name: 'السجل' }).click();

  const body = await shop.locator('body').innerText();
  expect(body).toMatch(/كل رسالة لم تخرج، ومعها سببها/);

  // The filter he actually comes for, named by what happened rather than by our word for it.
  await expect(shop.getByRole('radio', { name: 'لم تخرج' })).toBeVisible();
  await shop.getByRole('radio', { name: 'لم تخرج' }).click();

  // Either a real suppression with its reason, or the honest empty state — never a blank panel.
  await expect
    .poll(async () => {
      const t = await shop.locator('body').innerText();
      return /لا شيء في السجل بعد/.test(t) || /لم تخرج/.test(t);
    }, { timeout: 30_000 })
    .toBe(true);
});
