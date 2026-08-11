# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: services.spec.ts >> it opens on what he sells, with what he stopped one tap away
- Location: e2e\services.spec.ts:140:1

# Error details

```
Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:5174/
Call log:
  - navigating to "http://localhost:5174/", waiting until "load"

```

# Test source

```ts
  57  |   const phone = newPhone();
  58  |   await page.goto('/');
  59  | 
  60  |   // THE DOOR IS THE WHOLE PAGE when signed out. If this finds the nav instead, a previous run left
  61  |   // a session behind and everything after it would be testing a shop we did not create.
  62  |   //
  63  |   // A RADIO, NOT A BUTTON — the kit's `Segmented` renders `role="radiogroup"` with `role="radio"`
  64  |   // children. Asking for a button found nothing and reported "element not found", which reads as a
  65  |   // page that failed to load rather than as a name for the same control.
  66  |   await expect(page.getByRole('radio', { name: 'محل جديد' })).toBeVisible();
  67  |   await page.getByRole('radio', { name: 'محل جديد' }).click();
  68  | 
  69  |   await page.getByLabel('رقم الجوال').fill(phone);
  70  |   await page.getByLabel('كلمة المرور').fill(PASSWORD);
  71  |   await page.getByLabel('اسم المحل').fill(SHOP_NAME);
  72  |   // The sector cards render one radio per trade — chosen by position rather than by name, because
  73  |   // the names come from a seed an operator may edit from the console this afternoon.
  74  |   //
  75  |   // SCOPED TO ITS OWN GROUP. The mode switch above is a radiogroup too, so an unscoped `.first()`
  76  |   // picks «تسجيل الدخول» and silently leaves the form.
  77  |   // CLICKED ON THE CARD, NOT ON THE INPUT. The radio itself is `sr-only` — it carries the
  78  |   // semantics and the keyboard, and the card carries the look (see SectorCards). `check()` on a
  79  |   // visually hidden input fails as "not visible", which reads as a missing control rather than as
  80  |   // a test reaching for the wrong half of one. Clicking the card is also what a person does.
  81  |   await page.getByRole('radiogroup', { name: 'نوع النشاط' })
  82  |     .getByRole('radio').first().click({ force: true });
  83  |   await page.getByRole('checkbox').check();
  84  |   await page.getByRole('button', { name: 'ابدأ' }).click();
  85  | 
  86  |   // HE IS INSIDE, not "signup returned 200". The response carries no token; the app signs in
  87  |   // behind it, and the only proof that worked is a screen only a session can render.
  88  |   await expect(page.getByRole('link', { name: 'حسابي' })).toBeVisible({ timeout: 45_000 });
  89  | 
  90  |   await page.context().storageState({ path: SESSION_FILE });
  91  |   return phone;
  92  | }
  93  | 
  94  | /**
  95  |  * Go to a section and wait for it to have said something.
  96  |  *
  97  |  * `main` EXISTS THE MOMENT THE APP MOUNTS and fills a beat later, so reading it straight after a
  98  |  * `goto` catches an empty wrapper — and every such test reports a blank screen that was merely
  99  |  * early. Three specs failed that way before this helper existed, each looking like a different
  100 |  * product bug.
  101 |  *
  102 |  * It is here rather than in each file for the obvious reason: a rule repeated nine times is a rule
  103 |  * that will be missing from the tenth.
  104 |  */
  105 | export async function open(page: Page, path: string): Promise<string> {
  106 |   await page.goto(path);
  107 | 
  108 |   // WAIT FOR THE SIGNED-IN SHELL, THEN FOR THE SCREEN TO STOP LOADING. Nothing about the
  109 |   // shell's internals, and — the part that took four wrong answers — no threshold on how much
  110 |   // text a screen ought to have.
  111 |   //
  112 |   // `not.toBeEmpty()` was a no-op: the shell renders a sticky mobile header inside `main`, so the
  113 |   // element has children from the first frame. Then polling `main`'s TEXT reported the field
  114 |   // screen as permanently blank — that header is `md:hidden`, and at desktop width the routed
  115 |   // screen sits in a different container. Then "more text than the navigation" (400 characters)
  116 |   // failed «عملائي», which is a search box and a one-line empty state and is CORRECT at 144: the
  117 |   // helper had turned a shop with no customers yet into a product bug.
  118 |   //
  119 |   // A screen has arrived when the nav is there and no skeleton is left. What it then says is the
  120 |   // spec's business, not this helper's.
  121 |   await expect(page.getByRole('navigation')).toBeVisible({ timeout: 30_000 });
  122 |   await expect
  123 |     .poll(async () => page.locator('[class*="animate-pulse"]').count(),
  124 |           { timeout: 30_000, message: `«${path}» never finished loading` })
  125 |     .toBe(0);
  126 |   // AND FOR ITS REQUESTS TO HAVE LANDED. Not every screen paints a skeleton — «تسجيل زيارة»
  127 |   // renders its keypad immediately and fills the service grid when the catalogue answers, so
  128 |   // "no skeleton" was true a frame after `goto` and a spec then read a screen with no services
  129 |   // on it. The screens are finished when their fetches are.
  130 |   await page.waitForLoadState('networkidle', { timeout: 30_000 });
  131 |   return (await page.locator('body').innerText()).trim();
  132 | }
  133 | 
  134 | /**
  135 |  * The signed-in fixture every page spec uses.
  136 |  *
  137 |  * IT FAILS LOUDLY IF THE SESSION IS MISSING, rather than quietly opening a shop of its own. A
  138 |  * fixture that silently repairs a missing precondition hides the fact that door.spec.ts did not
  139 |  * run — and then nine files pass while the door is broken.
  140 |  */
  141 | export const test = base.extend<{ shop: Page }>({
  142 |   shop: async ({ browser }, use) => {
  143 |     let context = fs.existsSync(SESSION_FILE)
  144 |       ? await browser.newContext({ storageState: SESSION_FILE })
  145 |       : await browser.newContext();
  146 |     let page = await context.newPage();
  147 | 
  148 |     // EXPIRED IS NOT MISSING, and the two need different answers.
  149 |     //
  150 |     // A token lives an hour. Run one spec file now and another after lunch and the second lands on
  151 |     // the door — every assertion then fails against a sign-in form, and each file reports a
  152 |     // different imaginary bug. That is time passing, not a broken precondition, so it is repaired
  153 |     // rather than reported.
  154 |     //
  155 |     // It is also the app behaving correctly: an expired session signs out, because «تعذّر الوصول
  156 |     // إلى المنصة» would tell an owner to wait for something that is not broken.
> 157 |     await page.goto('/');
      |                ^ Error: page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:5174/
  158 |     const onTheDoor = await page.getByRole('radio', { name: 'محل جديد' })
  159 |       .isVisible({ timeout: 5_000 })
  160 |       .catch(() => false);
  161 |     if (onTheDoor) {
  162 |       // eslint-disable-next-line no-console
  163 |       console.log('  session expired — opening a fresh shop');
  164 |       await openShop(page);
  165 |       await context.close();
  166 |       context = await browser.newContext({ storageState: SESSION_FILE });
  167 |       page = await context.newPage();
  168 |     }
  169 | 
  170 |     await use(page);
  171 |     await context.close();
  172 |   },
  173 | });
  174 | 
  175 | export { expect };
  176 | // Re-exported so a spec's own helpers can be typed without a second import of @playwright/test —
  177 | // two import paths for the same package is how a suite ends up with two `test` objects.
  178 | export type { Page };
  179 | 
```