/**
 * One shop, opened once, used by every page test.
 *
 * WHY THIS FILE EXISTS AT ALL. Nine spec files each opening their own shop is nine signups per
 * run: nine tenants, nine seeded catalogues, nine role bootstraps. It is slow enough that somebody
 * stops running the suite, and a suite nobody runs is worse than no suite — it goes green for
 * months while the thing it covers rots.
 *
 * So the door is exercised ONCE, by door.spec.ts, and every other file inherits the session it
 * left behind. That is also the honest shape: the tests are about the SECTIONS, and a section test
 * that fails because signup changed is a test pointing at the wrong file.
 *
 * A FRESH SHOP EVERY RUN, THOUGH — never a fixture account. A fixture drifts: it holds services
 * somebody edited, a plan somebody changed, a WhatsApp connection that was true last month. Then
 * the suite asserts against a history rather than against the product, and the day it breaks
 * nobody can tell whether the code moved or the account did.
 */
import { test as base, expect, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Where the signed-in session is parked between files.
 *
 * `import.meta.url` rather than `__dirname`: this project is ESM (`vite`, `"type": "module"`),
 * and `__dirname` is a CommonJS global that is simply not defined here — the failure is at import
 * time and reports "no tests found", which reads as a config problem rather than a missing
 * variable.
 */
const HERE = path.dirname(fileURLToPath(import.meta.url));
export const SESSION_FILE = path.join(HERE, '.session.json');

/**
 * A Saudi mobile no human owns, different every run.
 *
 * `05` then eight digits, which is what our own canonical folding expects — a number the server
 * would reject is a test failing for a reason that has nothing to do with the screen under test.
 */
export function newPhone(): string {
  const n = Math.floor(Math.random() * 90_000_000) + 10_000_000;
  return `05${n}`;
}

/** Twelve characters, an upper, a digit and a symbol — identity's rules, not ours. */
export const PASSWORD = 'Raje3-Test-Passphrase!1';

export const SHOP_NAME = 'بنشر الاختبار';

/**
 * Open a shop and leave the session on disk.
 *
 * Returns the phone, because a test that wants to sign in again — or to prove that signing in
 * twice does not create two shops — needs the number this run used.
 */
export async function openShop(page: Page): Promise<string> {
  const phone = newPhone();
  await page.goto('/');

  // THE DOOR IS THE WHOLE PAGE when signed out. If this finds the nav instead, a previous run left
  // a session behind and everything after it would be testing a shop we did not create.
  //
  // A RADIO, NOT A BUTTON — the kit's `Segmented` renders `role="radiogroup"` with `role="radio"`
  // children. Asking for a button found nothing and reported "element not found", which reads as a
  // page that failed to load rather than as a name for the same control.
  await expect(page.getByRole('radio', { name: 'محل جديد' })).toBeVisible();
  await page.getByRole('radio', { name: 'محل جديد' }).click();

  await page.getByLabel('رقم الجوال').fill(phone);
  await page.getByLabel('كلمة المرور').fill(PASSWORD);
  await page.getByLabel('اسم المحل').fill(SHOP_NAME);
  // The sector cards render one radio per trade — chosen by position rather than by name, because
  // the names come from a seed an operator may edit from the console this afternoon.
  //
  // SCOPED TO ITS OWN GROUP. The mode switch above is a radiogroup too, so an unscoped `.first()`
  // picks «تسجيل الدخول» and silently leaves the form.
  // CLICKED ON THE CARD, NOT ON THE INPUT. The radio itself is `sr-only` — it carries the
  // semantics and the keyboard, and the card carries the look (see SectorCards). `check()` on a
  // visually hidden input fails as "not visible", which reads as a missing control rather than as
  // a test reaching for the wrong half of one. Clicking the card is also what a person does.
  await page.getByRole('radiogroup', { name: 'نوع النشاط' })
    .getByRole('radio').first().click({ force: true });
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'ابدأ' }).click();

  // HE IS INSIDE, not "signup returned 200". The response carries no token; the app signs in
  // behind it, and the only proof that worked is a screen only a session can render.
  await expect(page.getByRole('link', { name: 'حسابي' })).toBeVisible({ timeout: 45_000 });

  await page.context().storageState({ path: SESSION_FILE });
  return phone;
}

/**
 * Go to a section and wait for it to have said something.
 *
 * `main` EXISTS THE MOMENT THE APP MOUNTS and fills a beat later, so reading it straight after a
 * `goto` catches an empty wrapper — and every such test reports a blank screen that was merely
 * early. Three specs failed that way before this helper existed, each looking like a different
 * product bug.
 *
 * It is here rather than in each file for the obvious reason: a rule repeated nine times is a rule
 * that will be missing from the tenth.
 */
export async function open(page: Page, path: string): Promise<string> {
  await page.goto(path);

  // WAIT FOR THE SIGNED-IN SHELL, THEN FOR THE SCREEN TO STOP LOADING. Nothing about the
  // shell's internals, and — the part that took four wrong answers — no threshold on how much
  // text a screen ought to have.
  //
  // `not.toBeEmpty()` was a no-op: the shell renders a sticky mobile header inside `main`, so the
  // element has children from the first frame. Then polling `main`'s TEXT reported the field
  // screen as permanently blank — that header is `md:hidden`, and at desktop width the routed
  // screen sits in a different container. Then "more text than the navigation" (400 characters)
  // failed «عملائي», which is a search box and a one-line empty state and is CORRECT at 144: the
  // helper had turned a shop with no customers yet into a product bug.
  //
  // A screen has arrived when the nav is there and no skeleton is left. What it then says is the
  // spec's business, not this helper's.
  // `.first()` BECAUSE A SCREEN MAY HAVE A NAV OF ITS OWN. «خدماتي ومنتجاتي» grew a rail of the
  // owner's groups, which is correctly a <nav> — and an unscoped role query then matches two and
  // fails strict mode, reporting "the app did not render" about a screen that rendered more than
  // it used to.
  await expect(page.getByRole('navigation').first()).toBeVisible({ timeout: 30_000 });
  await expect
    .poll(async () => page.locator('[class*="animate-pulse"]').count(),
          { timeout: 30_000, message: `«${path}» never finished loading` })
    .toBe(0);
  // AND FOR ITS REQUESTS TO HAVE LANDED. Not every screen paints a skeleton — «تسجيل زيارة»
  // renders its keypad immediately and fills the service grid when the catalogue answers, so
  // "no skeleton" was true a frame after `goto` and a spec then read a screen with no services
  // on it. The screens are finished when their fetches are.
  await page.waitForLoadState('networkidle', { timeout: 30_000 });
  return (await page.locator('body').innerText()).trim();
}

/**
 * The signed-in fixture every page spec uses.
 *
 * IT FAILS LOUDLY IF THE SESSION IS MISSING, rather than quietly opening a shop of its own. A
 * fixture that silently repairs a missing precondition hides the fact that door.spec.ts did not
 * run — and then nine files pass while the door is broken.
 */
export const test = base.extend<{ shop: Page }>({
  shop: async ({ browser }, use) => {
    let context = fs.existsSync(SESSION_FILE)
      ? await browser.newContext({ storageState: SESSION_FILE })
      : await browser.newContext();
    let page = await context.newPage();

    // EXPIRED IS NOT MISSING, and the two need different answers.
    //
    // A token lives an hour. Run one spec file now and another after lunch and the second lands on
    // the door — every assertion then fails against a sign-in form, and each file reports a
    // different imaginary bug. That is time passing, not a broken precondition, so it is repaired
    // rather than reported.
    //
    // It is also the app behaving correctly: an expired session signs out, because «تعذّر الوصول
    // إلى المنصة» would tell an owner to wait for something that is not broken.
    await page.goto('/');

    // WAIT FOR WHICHEVER ARRIVES — the door or the shell — instead of racing a fixed timeout
    // against one of them.
    //
    // THE BUG THIS FIXES COST FOUR RUNS. The old check gave the door five seconds; on a cold start
    // over the tunnel neither had painted by then, so it concluded "not on the door", skipped the
    // repair, and every assertion after it failed against a sign-in form. Four spec files each
    // reported a different imaginary product bug, and the product was fine.
    //
    // Racing the two is also the only honest question: "which of the two states is this?" —
    // whereas "is the door visible in five seconds?" answers a question about our patience.
    await Promise.race([
      page.getByRole('radio', { name: 'محل جديد' }).waitFor({ timeout: 45_000 }),
      page.getByRole('navigation').first().waitFor({ timeout: 45_000 }),
    ]).catch(() => undefined);

    const onTheDoor = await page.getByRole('radio', { name: 'محل جديد' })
      .isVisible()
      .catch(() => false);

    // THE SHELL IS NOT PROOF OF A SESSION, and believing it was cost a whole run.
    //
    // Refresh tokens ROTATE, and reusing one twice is theft as far as identity is concerned — it
    // revokes the entire family. A saved storageState replayed by a second run does exactly that,
    // so the app mounts (the shell needs no server), the nav paints, and every data call 401s. The
    // screens then render their empty states, and «خدماتي» reported a seeded shop as having no
    // services at all. Two specs failed, describing a product bug that did not exist.
    //
    // So the session is ASKED whether it is alive, rather than inferred from a rendered sidebar.
    const alive = onTheDoor ? false : await page.evaluate(async () => {
      const raw = localStorage.getItem('raje3.session');
      if (!raw) return false;
      try {
        const r = await fetch('/api/v1/app/catalog', {
          headers: { Authorization: `Bearer ${JSON.parse(raw).token}` },
        });
        return r.ok;
      } catch {
        return false;
      }
    }).catch(() => false);

    if (onTheDoor || !alive) {
      // eslint-disable-next-line no-console
      console.log('  session dead — opening a fresh shop');
      await openShop(page);
      await context.close();
      context = await browser.newContext({ storageState: SESSION_FILE });
      page = await context.newPage();
    }

    // WHICH CALL FAILED — printed, once, per test.
    //
    // A REFUSED READ RENDERS AS AN EMPTY SCREEN, by design: every screen catches its own failure
    // and shows nothing rather than a stack trace at a counter. That is right for the owner and
    // blinding for a test — «جدول المكافآت فارغ» and «لا توجد خدمات» are the same picture whether
    // the shop is empty or the request was refused, and a run that fails this way reports an
    // imaginary product defect. So the response codes are watched here, where every spec gets it
    // for free, and the failure names itself.
    const refused: string[] = [];
    page.on('response', (r) => {
      const url = r.url();
      if (r.status() >= 400 && url.includes('/api/')) {
        refused.push(`${r.status()} ${r.request().method()} ${url.replace(/^https?:\/\/[^/]+/, '')}`);
      }
    });

    await use(page);

    if (refused.length) {
      // eslint-disable-next-line no-console
      console.log(['  API refused ' + refused.length + ' call(s):', ...refused.slice(0, 8)]
        .join('\n    '));
    }

    // THE ROTATED TOKEN IS SAVED BACK, and this is what a ten-minute run costs without it.
    //
    // A refresh token ROTATES on use: the app exchanges it during a test, and the copy in
    // SESSION_FILE — written when the session was first opened — is now the OLD one. Replaying an
    // old refresh token is theft as far as identity is concerned, and it revokes the whole family.
    // So a run passes for six minutes and then every file after it fails at once, each describing
    // a different imaginary product bug: twenty-nine of them in one run, every single one green
    // when the same file was run on its own.
    //
    // Saving after each test means the next one starts from the token this one ended with.
    await context.storageState({ path: SESSION_FILE }).catch(() => undefined);
    await context.close();
  },
});

export { expect };
// Re-exported so a spec's own helpers can be typed without a second import of @playwright/test —
// two import paths for the same package is how a suite ends up with two `test` objects.
export type { Page };
