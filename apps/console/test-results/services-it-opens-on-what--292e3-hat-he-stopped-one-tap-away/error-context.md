# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: services.spec.ts >> it opens on what he sells, with what he stopped one tap away
- Location: e2e\services.spec.ts:140:1

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: locator.click: Target page, context or browser has been closed
Call log:
  - waiting for getByRole('button', { name: 'تفعيل' }).first()

```

# Page snapshot

```yaml
- generic [ref=f1e3]:
  - complementary [ref=f1e4]:
    - button "طيّ القائمة" [ref=f1e5] [cursor=pointer]
    - generic [ref=f1e9]: راجِع
    - navigation [ref=f1e17]:
      - generic [ref=f1e18]:
        - link "اليوم" [ref=f1e19] [cursor=pointer]:
          - /url: /
        - link "تسجيل زيارة" [ref=f1e20] [cursor=pointer]:
          - /url: /visit
        - link "عملائي" [ref=f1e21] [cursor=pointer]:
          - /url: /customers
        - link "محلّي" [ref=f1e22] [cursor=pointer]:
          - /url: /shop
        - link "خدماتي ومنتجاتي" [ref=f1e23] [cursor=pointer]:
          - /url: /services
        - link "رسائلي" [ref=f1e24] [cursor=pointer]:
          - /url: /messages
        - link "نقاطي" [ref=f1e25] [cursor=pointer]:
          - /url: /points
        - link "فريقي" [ref=f1e26] [cursor=pointer]:
          - /url: /team
        - link "حسابي" [ref=f1e27] [cursor=pointer]:
          - /url: /account
    - button "تسجيل الخروج" [ref=f1e31] [cursor=pointer]
  - main [ref=f1e36]:
    - generic [ref=f1e39]:
      - radiogroup "عرض الخدمات والمنتجات" [ref=f1e40]:
        - radio "المفعّلة" [ref=f1e41] [cursor=pointer]
        - radio "الموقوفة (1)" [checked] [ref=f1e42] [cursor=pointer]
      - generic [ref=f1e43]:
        - navigation "مجموعات الخدمات" [ref=f1e44]:
          - button "الكل 1" [ref=f1e45] [cursor=pointer]
          - button "مجموعة الإثبات 1" [ref=f1e46] [cursor=pointer]
        - generic [ref=f1e47]:
          - button "إضافة خدمة أو منتج" [ref=f1e49] [cursor=pointer]
          - generic [ref=f1e50]:
            - generic [ref=f1e51]:
              - heading "مجموعة الإثبات" [level=2] [ref=f1e52]
              - button "حذف المجموعة" [ref=f1e53] [cursor=pointer]
            - button "تبديل إطارات كل 37 يوماً · واطمئنان بعد 19 موقوفة إعداد خاص" [active] [ref=f1e55] [cursor=pointer]:
              - generic [ref=f1e56]:
                - generic [ref=f1e57]: تبديل إطارات
                - generic [ref=f1e58]: كل 37 يوماً · واطمئنان بعد 19
              - generic [ref=f1e59]:
                - generic [ref=f1e60]: موقوفة
                - generic [ref=f1e61]: إعداد خاص
```

# Test source

```ts
  65  |   /**
  66  |    * THE BUG THIS CATCHES, found by using the screen: the row's summary line read only the cycle.
  67  |    * An owner who typed 15 into «الاطمئنان», closed the row and saw «كل 10 يوماً» had every reason
  68  |    * to conclude it had not saved. It had — the service stores both, and the line reported one.
  69  |    */
  70  |   await open(shop, '/services');
  71  |   await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();
  72  | 
  73  |   const followUp = shop.getByLabel('الاطمئنان بعد الزيارة (بالأيام)');
  74  |   await expect(followUp).toBeVisible();
  75  |   await followUp.fill('19');
  76  |   await followUp.blur();
  77  | 
  78  |   // 19 is nobody's default, so finding it after a reload is proof rather than coincidence.
  79  |   await expect(shop.getByText(/اطمئنان بعد 19/).first()).toBeVisible({ timeout: 30_000 });
  80  |   const body = await open(shop, '/services');
  81  |   expect(body).toMatch(/اطمئنان بعد 19/);
  82  | });
  83  | 
  84  | test('each reminder field says what it sends, and previews when', async ({ shop }) => {
  85  |   /**
  86  |    * «الاطمئنان بعد الزيارة (بالأيام)» is a label, not a meaning: it never said what the customer
  87  |    * receives. Two identical number boxes read as one setting asked twice.
  88  |    */
  89  |   await open(shop, '/services');
  90  |   await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();
  91  | 
  92  |   const body = await shop.locator('body').innerText();
  93  |   expect(body).toMatch(/الرسالة التي تُرجعه/);
  94  |   expect(body).toMatch(/تسأل إن كان كل شيء تمام/);
  95  |   // The consequence of the number now in the box, shown before he leaves the field.
  96  |   expect(body).toMatch(/تذكير بعد \d+ يوماً من كل زيارة|لا تذكير لهذه الخدمة/);
  97  | });
  98  | 
  99  | test('a service can be put in a group directly, not only when the system offers', async ({ shop }) => {
  100 |   /**
  101 |    * Grouping used to exist ONLY as a suggestion the system made after the owner had repeated
  102 |    * himself across three services. An owner who already knows «هذه كلها خدمات محرك» had no way to
  103 |    * say so. The suggestion is a shortcut now, not the gate.
  104 |    */
  105 |   await open(shop, '/services');
  106 |   await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();
  107 | 
  108 |   const picker = shop.getByLabel(/^مجموعة /);
  109 |   await expect(picker).toBeVisible();
  110 |   await expect(picker.locator('option', { hasText: 'مجموعة جديدة…' })).toHaveCount(1);
  111 | });
  112 | 
  113 | test('a service can leave its group, and a group can be deleted', async ({ shop }) => {
  114 |   /**
  115 |    * THE BUG THIS FILE WOULD HAVE CAUGHT, and did not: grouping was one-way. `set_group` wrote
  116 |    * `service_group[id]` and nothing anywhere could unset it — «بلا مجموعة» sat in the dropdown as
  117 |    * an option with no action behind it, and a group, once made, was permanent. Found by an owner
  118 |    * trying to undo his own edit, which is the only way a one-way door is ever found.
  119 |    */
  120 |   await open(shop, '/services');
  121 |   await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();
  122 | 
  123 |   const picker = shop.getByLabel(/^مجموعة /);
  124 |   await picker.selectOption({ label: 'مجموعة جديدة…' });
  125 |   const name = shop.getByLabel('اسم المجموعة الجديدة');
  126 |   await expect(name).toBeVisible();
  127 |   await name.fill('مجموعة الإثبات');
  128 |   await name.press('Enter');
  129 | 
  130 |   // It is a heading now, and the heading carries the act that unmakes it.
  131 |   await expect(shop.getByRole('heading', { name: /مجموعة الإثبات/ })).toBeVisible({ timeout: 30_000 });
  132 |   await expect(shop.getByRole('button', { name: 'حذف المجموعة' })).toBeVisible();
  133 | 
  134 |   // AND THE SERVICE CAN WALK OUT ON ITS OWN, without taking the group with it.
  135 |   await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();
  136 |   await shop.getByLabel(/^مجموعة /).first().selectOption('');
  137 |   await expect(shop.getByRole('heading', { name: /مجموعة الإثبات/ })).toHaveCount(0, { timeout: 30_000 });
  138 | });
  139 | 
  140 | test('it opens on what he sells, with what he stopped one tap away', async ({ shop }) => {
  141 |   /**
  142 |    * REACHABLE IS NOT THE SAME AS ALWAYS PRESENT. A retired line must be findable or «تفعيل» acts
  143 |    * on nothing — that is the bug that produced the owner's list at all. But a shop open two years
  144 |    * accumulates lines it stopped selling, and mixing them into the working list makes every
  145 |    * ordinary edit a matter of reading past the dead ones.
  146 |    */
  147 |   await open(shop, '/services');
  148 | 
  149 |   // Stop the first one, so there is something to filter for.
  150 |   await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();
  151 |   await shop.getByRole('button', { name: 'إيقاف' }).first().click();
  152 | 
  153 |   // THE STRIP APPEARS ONLY NOW — offering «الموقوفة» to a shop with none is a control answering a
  154 |   // question nobody asked.
  155 |   const stopped = shop.getByRole('radio', { name: /الموقوفة/ });
  156 |   await expect(stopped).toBeVisible({ timeout: 30_000 });
  157 |   // And it opened on «المفعّلة» without being asked: fewest taps for the ordinary visit.
  158 |   await expect(shop.getByRole('radio', { name: 'المفعّلة' })).toBeChecked();
  159 | 
  160 |   await stopped.click();
  161 |   await expect(shop.getByText('موقوفة').first()).toBeVisible({ timeout: 30_000 });
  162 | 
  163 |   // Put it back, so the next run starts where this one did.
  164 |   await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();
> 165 |   await shop.getByRole('button', { name: 'تفعيل' }).first().click();
      |                                                             ^ Error: locator.click: Target page, context or browser has been closed
  166 | });
  167 | 
```