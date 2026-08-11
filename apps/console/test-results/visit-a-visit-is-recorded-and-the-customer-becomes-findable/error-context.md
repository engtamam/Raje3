# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: visit.spec.ts >> a visit is recorded and the customer becomes findable
- Location: e2e\visit.spec.ts:48:1

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: locator.click: Target page, context or browser has been closed
Call log:
  - waiting for locator('button[aria-pressed]').first()

```

# Page snapshot

```yaml
- generic [ref=f1e2]:
  - heading "Unexpected Application Error!" [level=2] [ref=f1e3]
  - heading "Should have a queue. You are likely calling Hooks conditionally, which is not allowed. (https://react.dev/link/invalid-hook-call)" [level=3] [ref=f1e4]
  - generic [ref=f1e5]: "Error: Should have a queue. You are likely calling Hooks conditionally, which is not allowed. (https://react.dev/link/invalid-hook-call) at updateReducerImpl (http://localhost:5174/node_modules/.vite/deps/react-dom_client.js?v=dee743f0:5892:17) at updateReducer (http://localhost:5174/node_modules/.vite/deps/react-dom_client.js?v=dee743f0:5887:16) at Object.useState (http://localhost:5174/node_modules/.vite/deps/react-dom_client.js?v=dee743f0:18996:20) at exports.useState (http://localhost:5174/node_modules/.vite/deps/chunk-FYOQSAIZ.js?v=dee743f0:959:36) at App (http://localhost:5174/src/App.tsx?t=1786417218391:34:31) at Object.react_stack_bottom_frame (http://localhost:5174/node_modules/.vite/deps/react-dom_client.js?v=dee743f0:18509:20) at renderWithHooks (http://localhost:5174/node_modules/.vite/deps/react-dom_client.js?v=dee743f0:5654:24) at updateFunctionComponent (http://localhost:5174/node_modules/.vite/deps/react-dom_client.js?v=dee743f0:7475:21) at beginWork (http://localhost:5174/node_modules/.vite/deps/react-dom_client.js?v=dee743f0:8525:20) at runWithFiberInDEV (http://localhost:5174/node_modules/.vite/deps/react-dom_client.js?v=dee743f0:997:72)"
  - paragraph [ref=f1e6]: 💿 Hey developer 👋
  - paragraph [ref=f1e7]:
    - text: You can provide a way better UX than this when your app throws errors by providing your own
    - code [ref=f1e8]: ErrorBoundary
    - text: or
    - code [ref=f1e9]: errorElement
    - text: prop on your route.
```

# Test source

```ts
  1   | /**
  2   |  * «تسجيل زيارة» — the screen used a hundred times a day.
  3   |  *
  4   |  * THE ONLY SCREEN WITH A BUDGET. Five seconds, with a customer standing at the counter, and every
  5   |  * assertion here is about that: what the operator must not have to think about, and what must not
  6   |  * cost him a second attempt.
  7   |  *
  8   |  * WRITTEN AGAINST THE SCREEN, NOT AGAINST A FORM WE IMAGINED. The first version of this file
  9   |  * reached for `getByLabel(/جوال/)` and a generic "first button" — there is no labelled phone input
  10  |  * anywhere on it. The number is entered on a KEYPAD, because an operator with a customer in front
  11  |  * of him is not opening a soft keyboard, and the first button on the page is the digit 7. Three
  12  |  * specs failed for that reason and read like product bugs.
  13  |  */
  14  | import { expect, open, test, type Page } from './fixtures';
  15  | 
  16  | /** A customer number that belongs to nobody, fresh per run. */
  17  | function customerPhone(): string {
  18  |   return `05${Math.floor(Math.random() * 90_000_000) + 10_000_000}`;
  19  | }
  20  | 
  21  | /** Type a number the way the operator does — one key at a time. */
  22  | async function keyIn(page: Page, phone: string): Promise<void> {
  23  |   const pad = page.getByRole('group', { name: 'لوحة الأرقام' });
  24  |   for (const digit of phone) await pad.getByRole('button', { name: digit, exact: true }).click();
  25  | }
  26  | 
  27  | /** The first service in HIS catalogue. Chosen by position: the names are his to edit. */
  28  | function anyService(page: Page) {
  29  |   return page.locator('button[aria-pressed]').first();
  30  | }
  31  | 
  32  | test('the services come from his own catalogue, not from a list in the app', async ({ shop }) => {
  33  |   /**
  34  |    * Seeded from his sector at creation, and EDITABLE by him alone. A grid built from a constant in
  35  |    * the front end would show every shop the same services and quietly ignore what he changed this
  36  |    * morning.
  37  |    *
  38  |    * `aria-pressed` IS THE ASSERTION, and it is not a technicality: a service tile is a toggle, and
  39  |    * an element that carries the state is one a screen reader — and this test — can read. Counting
  40  |    * "buttons" would have counted the keypad.
  41  |    */
  42  |   await open(shop, '/visit');
  43  | 
  44  |   await expect(shop.locator('button[aria-pressed]').first()).toBeVisible();
  45  |   await expect(shop.getByText('لا توجد خدمات')).toBeHidden();
  46  | });
  47  | 
  48  | test('a visit is recorded and the customer becomes findable', async ({ shop }) => {
  49  |   /**
  50  |    * THE INDEXING RUNS AFTER THE RESPONSE, not in front of it — the operator is not waiting for it,
  51  |    * and a slow search service must never become a slow screen. Which is exactly why it needs an
  52  |    * assertion: work that happens off the request path is work nothing else proves happened.
  53  |    */
  54  |   const phone = customerPhone();
  55  |   await open(shop, '/visit');
  56  | 
> 57  |   await anyService(shop).click();
      |                          ^ Error: locator.click: Target page, context or browser has been closed
  58  |   await keyIn(shop, phone);
  59  |   await shop.getByRole('button', { name: 'حفظ وإرسال' }).click();
  60  | 
  61  |   await expect(shop.getByText(/تم الحفظ/)).toBeVisible({ timeout: 30_000 });
  62  | 
  63  |   await open(shop, '/customers');
  64  |   await expect(shop.getByText(phone.slice(-4), { exact: false }).first())
  65  |     .toBeVisible({ timeout: 30_000 });
  66  | });
  67  | 
  68  | test('nothing on it asks who is recording this', async ({ shop }) => {
  69  |   /**
  70  |    * IDENTITY COMES FROM THE SESSION (§3.5), and there is no field for it anywhere in the product.
  71  |    * An operator asked to pick his own name picks the first one in the list, and then every visit
  72  |    * in the shop is attributed to one man.
  73  |    */
  74  |   await open(shop, '/visit');
  75  |   const body = await shop.locator('body').innerText();
  76  | 
  77  |   expect(body).not.toMatch(/من سجّل|اسم الموظف|الموظف المسؤول/);
  78  | });
  79  | 
  80  | test('an outage does not lose the visit — it waits, and says it is waiting', async ({ shop }) => {
  81  |   /**
  82  |    * THE FORM CLEARS ON PURPOSE, and asserting that it does not was this test's original mistake.
  83  |    * The next customer is already waiting; a screen that held still for a round trip would spend
  84  |    * its five-second budget on a network the operator can neither see nor fix. So the visit goes to
  85  |    * the queue at the press and the screen is ready again — the queue is the design, not a fallback.
  86  |    *
  87  |    * What must be true is that the visit is not silently gone: the counter says one is waiting.
  88  |    */
  89  |   await shop.route('**/api/v1/field/visits', (r) => r.fulfill({ status: 500, body: '{}' }));
  90  |   await open(shop, '/visit');
  91  | 
  92  |   await anyService(shop).click();
  93  |   await keyIn(shop, customerPhone());
  94  |   await shop.getByRole('button', { name: 'حفظ وإرسال' }).click();
  95  | 
  96  |   await expect(shop.getByText(/بانتظار الإرسال/)).toBeVisible({ timeout: 30_000 });
  97  | });
  98  | 
  99  | test('a visit that will never send is reported, not left in a silent queue', async ({ shop }) => {
  100 |   /**
  101 |    * A 400 IS NOT AN OUTAGE. The queue has always told the two apart — retrying a refusal for ever
  102 |    * burns battery and hides the problem — but it told nobody, so the visit left the screen, the
  103 |    * counter said "waiting" for ever, and the shop lost a customer with no reminder, no points and
  104 |    * no metric. Holding a visit nobody is told about is the same as dropping it.
  105 |    */
  106 |   await shop.route('**/api/v1/field/visits',
  107 |                    (r) => r.fulfill({ status: 400, body: '{"message":"لا"}' }));
  108 |   await open(shop, '/visit');
  109 | 
  110 |   await anyService(shop).click();
  111 |   await keyIn(shop, customerPhone());
  112 |   await shop.getByRole('button', { name: 'حفظ وإرسال' }).click();
  113 | 
  114 |   await expect(shop.getByText(/لم تُرسَل/)).toBeVisible({ timeout: 30_000 });
  115 | });
  116 | 
```