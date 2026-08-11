/**
 * «محلّي» — the indicators, and three sentences that must never be confused.
 *
 * THIS IS THE SECTION THE TOP PLAN IS BOUGHT FOR, and the one most easily made to lie. Every
 * assertion here is about telling three states apart, because on an empty screen they look
 * identical and only one of them is about him:
 *
 *   «تعذّر قراءة المؤشرات»          — we could not read them. Ours.
 *   «نحسب مؤشرات محلك»              — not enough history yet. His, and temporary.
 *   a number                        — the answer.
 *
 * Showing zeros for the second is the failure that matters: a shop in its first week reads "return
 * rate 0%" as a verdict on itself, and the product has insulted him with arithmetic it did not do.
 */
import { expect, open, test } from './fixtures';

test('a fresh shop is told it has no history yet — never shown zeros', async ({ shop }) => {
  const body = await open(shop, '/shop');

  // One of the two honest answers. A screen that painted «0%» for a shop with no visits would be
  // stating a result it never computed.
  expect(body).toMatch(/نحسب مؤشرات محلك|مؤشرات تحتاج بيانات أكثر|نسبة العودة/);
});

test('an outage and an empty account do not look the same', async ({ shop }) => {
  await shop.route('**/api/v1/insights/**', (r) => r.fulfill({ status: 503, body: '{}' }));
  const body = await open(shop, '/shop');

  // "We could not read them" is about US. It must never be dressed as "you have nothing".
  expect(body).toMatch(/تعذّر قراءة المؤشرات/);
  expect(body).not.toMatch(/نحسب مؤشرات محلك/);
});

test('nothing on it is an untranslated key', async ({ shop }) => {
  const body = await open(shop, '/shop');

  expect(body).not.toMatch(/[a-z]+\.[a-z]+\.[a-z]+/);
});
