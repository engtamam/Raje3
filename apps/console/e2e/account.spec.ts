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

test('it opens as an index of rows, each saying what is behind it', async ({ shop }) => {
  const body = await open(shop, '/account');

  expect(body).toMatch(/الاشتراك والفواتير/);
  expect(body).toMatch(/واتساب/);
  expect(body).toMatch(/دخولي/);
  // Each row carries the sentence that tells him whether to open it — a list of five nouns is a
  // list he has to open five times.
  expect(body).toMatch(/جوالك وكلمة مرورك/);
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
  const body = await open(shop, '/account');

  expect(body).toMatch(/بياناتي وأوراقي/);
  expect(body).toMatch(/الاحتفاظ، التصدير، الاتفاقيات/);
});

test('nothing on it is an untranslated key', async ({ shop }) => {
  const body = await open(shop, '/account');

  expect(body).not.toMatch(/[a-z]+\.[a-z]+\.[a-z]+/);
});
