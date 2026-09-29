/**
 * Bulk-import services/products from a CSV — against the REAL cluster, a REAL new shop, and a
 * REAL uploaded file (Playwright's own `setInputFiles` with an inline buffer, no disk file
 * needed). Self-contained: opens its own shop rather than depending on door.spec.ts's shared
 * session, so this file can run alone while the feature is being proven.
 *
 * `test.describe.configure({ mode: 'serial' })` — same reasoning as door.spec.ts: each test
 * builds on the shop's catalogue state the one before it left, on purpose, to exercise a REAL
 * re-upload rather than a fresh shop pretending to be one.
 *
 * VERIFIED LIVE against the deployed console, not just the local dev server — all
 * seven cases here, including the two silent-corruption risks a bulk import invites (duplicate
 * names blocking the whole file, a partial re-upload never retiring anything unless asked): a
 * throwaway config (baseURL: https://ra-je3.com, no local webServer) plus
 * `E2E_APP_BASE=/app` (fixtures.ts's own note explains why — the edge serves the marketing
 * landing page at bare `/`, the app lives under `/app/`), all seven green against a real shop.
 */
import { expect, test } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { open, openShop } from './fixtures';

const HERE = path.dirname(fileURLToPath(import.meta.url));

test.describe.configure({ mode: 'serial' });

function csvFile(text: string, name = 'services.csv') {
  return { name, mimeType: 'text/csv', buffer: Buffer.from(text, 'utf-8') };
}

test.beforeAll(async ({ browser }) => {
  // storageState: undefined OVERRIDES the file-level `test.use` below — that default exists for
  // every actual TEST's own page, but this one signup context must start fresh (there is no
  // session yet; this IS what creates it), or it tries to read a file this same call is about to
  // write.
  const context = await browser.newContext({ storageState: undefined });
  const page = await context.newPage();
  await openShop(page);
  await context.storageState({ path: `${HERE}/.import-session.json` });
  await context.close();
});

test.use({ storageState: `${HERE}/.import-session.json` });

test('an empty catalogue offers "استيراد من ملف" next to typing the first service', async ({ page }) => {
  await open(page, '/services');
  await expect(page.getByText('ابدأ بإضافة خدماتك')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole('button', { name: 'استيراد من ملف' })).toBeVisible();
});

test('two new rows import as جديد, and land on the real catalogue', async ({ page }) => {
  await open(page, '/services');
  await page.getByRole('button', { name: 'استيراد من ملف' }).click();

  await page.setInputFiles('input[type="file"]',
    csvFile('name,price\nقص شعر,50\nغسيل,20'));

  await expect(page.getByText('قص شعر')).toBeVisible();
  await expect(page.getByText('غسيل')).toBeVisible();
  await expect(page.getByText('جديد').first()).toBeVisible();

  await page.getByRole('button', { name: /استيراد 2 صف/ }).click();
  await expect(page.getByText(/2 خدمة جديدة/)).toBeVisible({ timeout: 30_000 });

  await page.getByRole('button', { name: 'إغلاق' }).last().click();
  await expect(page.getByText('قص شعر')).toBeVisible();
  await expect(page.getByText('غسيل')).toBeVisible();
});

test('re-uploading the SAME names updates in place — تحديث, not a duplicate row', async ({ page }) => {
  await open(page, '/services');
  await page.getByRole('button', { name: 'استيراد من ملف' }).click();

  await page.setInputFiles('input[type="file"]', csvFile('name,price\nقص شعر,60'));
  // The important assertion: تحديث, because "قص شعر" is already on this shop's catalogue from
  // the previous test — a fresh shop would have shown جديد here instead.
  await expect(page.getByText('تحديث')).toBeVisible();

  await page.getByRole('button', { name: /استيراد 1 صف/ }).click();
  await expect(page.getByText(/1 تحديث/)).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'إغلاق' }).last().click();

  // EXACTLY ONE «قص شعر» on the catalogue — the whole point being proven here is that a re-upload
  // updated the existing row rather than adding a second one beside it.
  await expect(page.getByText('قص شعر')).toHaveCount(1);
});

test('a duplicate name within one file blocks the import button entirely', async ({ page }) => {
  await open(page, '/services');
  await page.getByRole('button', { name: 'استيراد من ملف' }).click();

  await page.setInputFiles('input[type="file"]', csvFile('name\nصبغة\nصبغة'));
  await expect(page.getByText(/الاسم مكرر/).first()).toBeVisible();

  const importBtn = page.getByRole('button', { name: /استيراد 2 صف/ });
  await expect(importBtn).toBeDisabled();
});

test('an empty name is refused with a clear reason, not a silent skip', async ({ page }) => {
  await open(page, '/services');
  await page.getByRole('button', { name: 'استيراد من ملف' }).click();

  await page.setInputFiles('input[type="file"]', csvFile('name,price\n,50'));
  await expect(page.getByText('الاسم فاضي.')).toBeVisible();
  await expect(page.getByRole('button', { name: /استيراد 1 صف/ })).toBeDisabled();
});

test('a partial re-upload leaves the omitted service ACTIVE by default — no silent retirement', async ({ page }) => {
  await open(page, '/services');
  await page.getByRole('button', { name: 'استيراد من ملف' }).click();

  // "غسيل" exists from the first test; this file omits it on purpose.
  await page.setInputFiles('input[type="file"]', csvFile('name\nقص شعر'));
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText(/1 خدمة مفعّلة حالياً غائبة/)).toBeVisible();
  await expect(dialog.getByText('غسيل')).toBeVisible();   // named in the warning box

  // The toggle defaults OFF — confirmed by aria-checked, not by trusting the default blindly.
  await expect(page.getByRole('switch')).toHaveAttribute('aria-checked', 'false');

  await page.getByRole('button', { name: /استيراد 1 صف/ }).click();
  await expect(page.getByText(/0 إيقاف|تحديث/).first()).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'إغلاق' }).last().click();

  // "غسيل" is still on the ACTIVE list — the destructive path was never taken.
  await expect(page.getByText('غسيل')).toBeVisible();
});

test('opting in to deactivate_missing retires exactly the omitted service, reversibly', async ({ page }) => {
  await open(page, '/services');
  await page.getByRole('button', { name: 'استيراد من ملف' }).click();

  await page.setInputFiles('input[type="file"]', csvFile('name\nقص شعر'));
  await expect(page.getByText(/غائبة/)).toBeVisible();
  await page.getByRole('switch').click();
  await expect(page.getByRole('switch')).toHaveAttribute('aria-checked', 'true');

  await page.getByRole('button', { name: /استيراد 1 صف/ }).click();
  await expect(page.getByText(/1 إيقاف/)).toBeVisible({ timeout: 30_000 });
  await page.getByRole('button', { name: 'إغلاق' }).last().click();

  // "غسيل" is gone from the active view — NOT deleted (توقيف لا حذف): switch to الموقوفة and
  // confirm it is exactly there, not vanished.
  await expect(page.getByText('غسيل')).toBeHidden();
  await page.getByRole('radio', { name: /الموقوفة/ }).click();
  await expect(page.getByText('غسيل')).toBeVisible();
});
