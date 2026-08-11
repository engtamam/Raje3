/**
 * The door — and the shop every other file inherits.
 *
 * IT RUNS FIRST, and the config orders it: it is the one file that opens the shop, and the
 * fixture the others use refuses rather than quietly opening one of its own.
 *
 * WHAT IS WORTH ASSERTING HERE. Not that the form submits — that is the least interesting thing
 * about it. The assertions below are the four failures this screen has actually produced, each
 * found by using it rather than by reading it.
 */
import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import { openShop, PASSWORD, SESSION_FILE } from './fixtures';

test.describe.configure({ mode: 'serial' });

test('a new owner opens a shop and lands inside it', async ({ page }) => {
  const phone = await openShop(page);

  // HIS CATALOGUE IS NOT EMPTY. Seeding fails SOFT by design — a timeout must not destroy a
  // working account — which is exactly why it needs an assertion rather than trust. An empty
  // «خدماتي» is a first day spent typing twenty services.
  await page.getByRole('link', { name: 'خدماتي ومنتجاتي' }).click();
  await expect(page.getByText('لا توجد خدمات')).toBeHidden();

  fs.writeFileSync(SESSION_FILE.replace('.session.json', '.phone'), phone);
});

test('the button is dimmed but never dead', async ({ page }) => {
  /**
   * THE TRAP THAT ALREADY BIT, and it is invisible from the code.
   *
   * A password manager writes into the inputs directly: the DOM holds the values, the person can
   * see them, and React's onChange never fires. Any button gated on component state then stays
   * disabled over a form that is plainly complete, and he has no move — he DID fill it in.
   *
   * So the sign-in button is dimmed, and clickable, and answers.
   */
  await page.goto('/');
  const button = page.getByRole('button', { name: 'تسجيل الدخول' }).last();

  await expect(button).toBeEnabled();
  await button.click();
  await expect(page.getByText('أدخل رقم الجوال وكلمة المرور.')).toBeVisible();
});

test('the password rules are shown while he types, not after he presses', async ({ page }) => {
  // Twelve characters is a long password. Announcing it after the button is how a signup is
  // abandoned — and he has already invented one by then.
  await page.goto('/');
  await page.getByRole('radio', { name: 'محل جديد' }).click();
  await page.getByLabel('كلمة المرور').fill('short');

  await expect(page.getByText('12 حرفاً على الأقل')).toBeVisible();
});

test('nothing is created without the consent box', async ({ page }) => {
  /**
   * PDPL Art. 6 wants a consent that is informed and demonstrable. The box gates the button, and
   * the version-pinned RECORD is written by the legal gate the moment he is inside — so what this
   * asserts is only the gate: no box, no shop.
   *
   * The form is filled completely FIRST, so the only thing standing between him and a shop is the
   * box — otherwise this would pass on a form that was simply incomplete.
   */
  await page.goto('/');
  await page.getByRole('radio', { name: 'محل جديد' }).click();
  await page.getByLabel('رقم الجوال').fill('0512345678');
  await page.getByLabel('كلمة المرور').fill(PASSWORD);
  await page.getByLabel('اسم المحل').fill('محل بلا موافقة');
  // CLICKED ON THE CARD, NOT ON THE INPUT. The radio itself is `sr-only` — it carries the
  // semantics and the keyboard, and the card carries the look (see SectorCards). `check()` on a
  // visually hidden input fails as "not visible", which reads as a missing control rather than as
  // a test reaching for the wrong half of one. Clicking the card is also what a person does.
  await page.getByRole('radiogroup', { name: 'نوع النشاط' })
    .getByRole('radio').first().click({ force: true });

  // DISABLED, AND HERE THAT IS SAFE — which it is not on the sign-in pane. The autofill trap needs
  // the browser to fill EVERY gate silently, and it cannot: no password manager ticks a consent
  // box. So the button can be genuinely dead without ever stranding somebody over a form he
  // plainly completed.
  //
  // This test first CLICKED it and waited sixty seconds for an answer that could not come. The
  // assertion is the state, not the response.
  await expect(page.getByRole('button', { name: 'ابدأ' })).toBeDisabled();

  await page.getByRole('checkbox').check();
  await expect(page.getByRole('button', { name: 'ابدأ' })).toBeEnabled();
});

test('nothing on the door is an untranslated key', async ({ page }) => {
  /**
   * THE LEAK THAT REACHED A REAL SCREEN. The kit has three independent i18n contexts and each one
   * degrades to printing its own key — so an unwrapped app paints `auth.otp.hint 0505536720` at a
   * shop owner, beside his own phone number. It renders, it is not an error, and nothing fails.
   *
   * A CI gate now proves every key has Arabic behind it. This proves the PROVIDERS are actually
   * wrapped, which the gate cannot see.
   */
  await page.goto('/');
  const body = await page.locator('body').innerText();

  expect(body).not.toMatch(/\bauth\.[a-z]+\./);
  expect(body).not.toMatch(/\blegal\.[a-z]+/);
  expect(body).not.toMatch(/\bpager\.[a-z]+/);
});
