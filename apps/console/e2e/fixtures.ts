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
/**
 * '' for every real run (the dev server's own webServer serves the app at the SITE root — no
 * marketing landing page competes for it in dev). Set ONLY for a manual pass against the real
 * cluster, where the edge's own Caddyfile serves the marketing landing page at bare `/` and the
 * app lives under `/app/` (deploy/edge/console.yaml — the same split affiliates.<domain> and
 * admin.<domain> use their own root for, this is the shop's own domain's version of it). Every
 * `page.goto` in this file is an absolute, leading-slash path on purpose — see this file's own
 * "IT RUNS FIRST" convention — so a bare `baseURL` with a path segment cannot fix this; the path
 * itself has to carry the prefix.
 */
const APP_BASE = process.env.E2E_APP_BASE ?? '';

export async function openShop(page: Page): Promise<string> {
  const phone = newPhone();
  await page.goto(`${APP_BASE}/`);

  // THE DOOR IS THE WHOLE PAGE when signed out. If this finds the nav instead, a previous run left
  // a session behind and everything after it would be testing a shop we did not create.
  //
  // TWO RADIOGROUPS, NOT ONE — Door.tsx defaults to «تسجيل الدخول» (sign IN), and «محل جديد» lives
  // inside the sign-UP pane that only mounts once the OUTER mode radio is switched to «تسجيل جديد».
  // Asking for «محل جديد» straight away found nothing on a door that had never shown it yet, which
  // reads as a page that failed to load rather than as a tab that was never opened.
  //
  // A RADIO, NOT A BUTTON — the kit's `Segmented` renders `role="radiogroup"` with `role="radio"`
  // children. Asking for a button found nothing and reported "element not found", which reads as a
  // page that failed to load rather than as a name for the same control.
  //
  // NO SECOND RADIO AFTER THIS ONE. Door.tsx's «new» mode renders `NewShopPane` directly — phone,
  // password, shop name, right on the pane, no further "محل جديد" choice to make. An earlier
  // version of this fixture waited for and clicked a second radio by that name; it no longer
  // exists anywhere in Door.tsx, and that wait always failed once the pane it was ever going to
  // find had already been removed — silently, since nothing runs this fixture outside an actual
  // e2e pass to notice.
  //
  // AN EXPLICIT TIMEOUT, NOT THE BARE DEFAULT. `expect()`'s own default is 5s; playwright.config.ts
  // widens it to 15s project-wide ("anything here is slow by design" — its own comment, about
  // exactly the first-compile/cold-tunnel delay a fresh signup hits). That widened value is read
  // by the TEST RUNNER's config loader — a caller outside the runner (media/tours/record-tour.mjs
  // borrows this function directly, not through `playwright test`) never sees it, and would
  // otherwise fail this exact assertion on the same slowness the config was written to tolerate.
  // Stating the timeout here instead of relying on ambient config makes openShop() correct for
  // every caller, not just ones that happen to load this project's config.
  await expect(page.getByRole('radio', { name: 'تسجيل جديد' })).toBeVisible({ timeout: 15_000 });
  await page.getByRole('radio', { name: 'تسجيل جديد' }).click();

  await page.getByLabel('رقم الجوال').fill(phone);
  // BY ROLE, NOT BY LABEL — the password field's show/hide toggle button (added since) carries its
  // own `aria-label="إظهار كلمة المرور"`, which contains «كلمة المرور» as a substring and matches
  // getByLabel's default non-exact search just as well as the field itself; `exact: true` doesn't
  // fix it either, because the FIELD's own label carries a required-marker suffix (the rendered
  // «كلمة المرور *») so it no longer equals the bare string exactly. `textbox` is the one role that
  // is only ever true of the input, never of the toggle button beside it.
  await page.getByRole('textbox', { name: 'كلمة المرور' }).fill(PASSWORD);
  await page.getByLabel('اسم المحل').fill(SHOP_NAME);
  // THREE VALUES AND A BOX. The form once had a fourth control — a card per trade — and this
  // fixture clicked whichever came first. Nothing asks a shop its trade any more.
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: 'ابدأ' }).click();

  // A FULL-SCREEN WELCOME DIALOG COVERS THE APP NEXT (WelcomeTrial.tsx, `role="dialog"
  // aria-modal="true"`) — it fires the moment a brand-new shop first lands inside, with no
  // click-outside and no separate close button, only «لنبدأ». Everything behind it — including
  // «حسابي» — cannot be reached until it's dismissed. `.catch()` because this is the ONE-TIME
  // welcome: a re-run that reused a still-alive session would never see it at all, and that must
  // not fail here.
  await page.getByRole('button', { name: 'لنبدأ' }).click({ timeout: 15_000 }).catch(() => undefined);

  // HE IS INSIDE, not "signup returned 200". The response carries no token; the app signs in
  // behind it, and the only proof that worked is a screen only a session can render.
  //
  // A BUTTON, NOT A LINK — AppShell.tsx renders «حسابي» as `<Button variant="ghost" size="icon"
  // onClick={onAccount}>`, an icon control that opens the account screen rather than navigating
  // to it by href. It was never an `<a>`, so `role: 'link'` never matched regardless of the name.
  await expect(page.getByRole('button', { name: 'حسابي' })).toBeVisible({ timeout: 45_000 });

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
  await page.goto(`${APP_BASE}${path}`);

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
    await page.goto(`${APP_BASE}/`);

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
