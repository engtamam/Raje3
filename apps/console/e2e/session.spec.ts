/**
 * The session, proven in a real browser rather than in a unit test.
 *
 * renew.test.ts proves the RULES — no refresh token means give up, a refused renewal ends the
 * session, concurrent 401s spend the token once. All four pass, and the owner was still thrown out.
 * That gap is the reason this file exists: unit tests prove the function, and the thing that
 * actually breaks is the wiring between signing in, what reaches storage, and who reads it back.
 *
 * SO IT GOES THROUGH THE DOOR. It types the password like a person, then corrupts the bearer the
 * way fifteen minutes would, and asks the only question that matters: is he still working, or is
 * he looking at the login screen again.
 */
import { expect, test } from '@playwright/test';

const PHONE = process.env.SHOP_PHONE ?? '0549491771';
const PASSWORD = process.env.SHOP_PASSWORD ?? 'Raje3-Test-Passphrase!1';
const KEY = 'raje3.session';

test('signing in keeps the refresh token, or the 31 days are a claim about nothing', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/جوال/).first().fill(PHONE);
  await page.getByLabel(/كلمة المرور/).first().fill(PASSWORD);
  await page.getByRole('button', { name: /دخول|تسجيل الدخول/ }).first().click();
  await expect(page.getByRole('navigation')).toBeVisible({ timeout: 30_000 });

  const held = await page.evaluate((k) => JSON.parse(localStorage.getItem(k) || 'null'), KEY);
  expect(held, 'no session was stored at all').toBeTruthy();
  expect(held.token, 'no bearer stored').toBeTruthy();
  // THE ASSERTION THIS FILE IS FOR. Everything downstream — the retry, the 31 days, not being
  // thrown out at the counter — rests on this one field surviving the trip from `signIn` through
  // `onSignedIn` into storage. It is one word, and it is the whole feature.
  expect(held.refresh, 'the refresh token did not reach storage').toBeTruthy();
});

test('a dead bearer is renewed under the screen, and he never sees the door', async ({ page }) => {
  await page.goto('/');
  await page.getByLabel(/جوال/).first().fill(PHONE);
  await page.getByLabel(/كلمة المرور/).first().fill(PASSWORD);
  await page.getByRole('button', { name: /دخول|تسجيل الدخول/ }).first().click();
  await expect(page.getByRole('navigation')).toBeVisible({ timeout: 30_000 });

  // FIFTEEN MINUTES, SIMULATED. The bearer is replaced with one the server will refuse and the
  // refresh token is left alone — exactly the state an owner's browser is in after a quiet lunch.
  await page.evaluate((k) => {
    const s = JSON.parse(localStorage.getItem(k) || '{}');
    s.token = 'expired.on.purpose';
    localStorage.setItem(k, JSON.stringify(s));
    sessionStorage.clear();          // the catalogue is cached under the old token
  }, KEY);

  await page.goto('/visit');

  // He is working, not signing in.
  await expect(page.getByRole('navigation')).toBeVisible({ timeout: 30_000 });
  await expect(page.getByLabel(/كلمة المرور/)).toHaveCount(0);

  const after = await page.evaluate((k) => JSON.parse(localStorage.getItem(k) || 'null'), KEY);
  expect(after?.token, 'the dead bearer was never replaced').not.toBe('expired.on.purpose');
});
