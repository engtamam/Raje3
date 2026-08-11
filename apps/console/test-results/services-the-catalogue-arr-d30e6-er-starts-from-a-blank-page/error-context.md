# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: services.spec.ts >> the catalogue arrives seeded from his sector — he never starts from a blank page
- Location: e2e\services.spec.ts:15:1

# Error details

```
Error: expect(received).toMatch(expected)

Expected pattern: /كل \d+ يوماً|بلا دورة/
Received string:  "راجِع
اليوم
تسجيل زيارة
عملائي
محلّي
خدماتي
رسائلي
نقاطي
فريقي
حسابي·
لا توجد خدمات·
قائمة قطاعك تُضاف تلقائياً عند إنشاء الحساب — تواصل معنا إن بقيت فارغة."
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
        - link "خدماتي" [ref=f1e23] [cursor=pointer]:
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
      - heading "خدمات غير مجمّعة" [level=2] [ref=f1e40]
      - button "تبديل إطارات بلا دورة" [ref=f1e42] [cursor=pointer]:
        - generic [ref=f1e43]:
          - generic [ref=f1e44]: تبديل إطارات
          - generic [ref=f1e45]: بلا دورة
      - button "غسيل المكينة بلا دورة" [ref=f1e47] [cursor=pointer]:
        - generic [ref=f1e48]:
          - generic [ref=f1e49]: غسيل المكينة
          - generic [ref=f1e50]: بلا دورة
      - button "تغيير فلتر هواء بلا دورة" [ref=f1e52] [cursor=pointer]:
        - generic [ref=f1e53]:
          - generic [ref=f1e54]: تغيير فلتر هواء
          - generic [ref=f1e55]: بلا دورة
      - button "تغيير فلتر مكيف بلا دورة" [ref=f1e57] [cursor=pointer]:
        - generic [ref=f1e58]:
          - generic [ref=f1e59]: تغيير فلتر مكيف
          - generic [ref=f1e60]: بلا دورة
      - button "تغيير بطارية بلا دورة" [ref=f1e62] [cursor=pointer]:
        - generic [ref=f1e63]:
          - generic [ref=f1e64]: تغيير بطارية
          - generic [ref=f1e65]: بلا دورة
      - button "تعبئة فريون المكيف بلا دورة" [ref=f1e67] [cursor=pointer]:
        - generic [ref=f1e68]:
          - generic [ref=f1e69]: تعبئة فريون المكيف
          - generic [ref=f1e70]: بلا دورة
      - button "تغيير مساحات بلا دورة" [ref=f1e72] [cursor=pointer]:
        - generic [ref=f1e73]:
          - generic [ref=f1e74]: تغيير مساحات
          - generic [ref=f1e75]: بلا دورة
      - button "تعبئة سوائل بلا دورة" [ref=f1e77] [cursor=pointer]:
        - generic [ref=f1e78]:
          - generic [ref=f1e79]: تعبئة سوائل
          - generic [ref=f1e80]: بلا دورة
      - button "ترصيص وموازنة بلا دورة" [ref=f1e82] [cursor=pointer]:
        - generic [ref=f1e83]:
          - generic [ref=f1e84]: ترصيص وموازنة
          - generic [ref=f1e85]: بلا دورة
      - button "ضبط زوايا بلا دورة" [ref=f1e87] [cursor=pointer]:
        - generic [ref=f1e88]:
          - generic [ref=f1e89]: ضبط زوايا
          - generic [ref=f1e90]: بلا دورة
      - button "تصليح بنشر بلا دورة" [ref=f1e92] [cursor=pointer]:
        - generic [ref=f1e93]:
          - generic [ref=f1e94]: تصليح بنشر
          - generic [ref=f1e95]: بلا دورة
      - button "تعبئة نيتروجين بلا دورة" [ref=f1e97] [cursor=pointer]:
        - generic [ref=f1e98]:
          - generic [ref=f1e99]: تعبئة نيتروجين
          - generic [ref=f1e100]: بلا دورة
      - button "فحص ضغط الإطارات بلا دورة" [ref=f1e102] [cursor=pointer]:
        - generic [ref=f1e103]:
          - generic [ref=f1e104]: فحص ضغط الإطارات
          - generic [ref=f1e105]: بلا دورة
      - button "تغيير زيت وفلتر بلا دورة" [ref=f1e107] [cursor=pointer]:
        - generic [ref=f1e108]:
          - generic [ref=f1e109]: تغيير زيت وفلتر
          - generic [ref=f1e110]: بلا دورة
      - button "تغيير زيت الجربوكس بلا دورة" [ref=f1e112] [cursor=pointer]:
        - generic [ref=f1e113]:
          - generic [ref=f1e114]: تغيير زيت الجربوكس
          - generic [ref=f1e115]: بلا دورة
      - button "غسيل الجربوكس بلا دورة" [ref=f1e117] [cursor=pointer]:
        - generic [ref=f1e118]:
          - generic [ref=f1e119]: غسيل الجربوكس
          - generic [ref=f1e120]: بلا دورة
      - button "خدمة أخرى بلا دورة" [ref=f1e122] [cursor=pointer]:
        - generic [ref=f1e123]:
          - generic [ref=f1e124]: خدمة أخرى
          - generic [ref=f1e125]: بلا دورة
```

# Test source

```ts
  1  | /**
  2  |  * «خدماتي» — two stores behind one form.
  3  |  *
  4  |  *   name, price, order        → operations (the Service row)
  5  |  *   cycle, lead, follow-up    → REMINDERS' settings tree
  6  |  *
  7  |  * THE ENGINE READS THE TREE. A screen that wrote operations' `cycle_days` column instead would
  8  |  * reproduce exactly what the tree exists to prevent: the owner changes a cycle, sees no effect, and
  9  |  * concludes the feature is broken. Nothing errors, nothing is logged, and he stops trusting the
  10 |  * settings screen. So the test that matters is that a saved cycle SURVIVES A RELOAD — read back
  11 |  * from the store the engine actually consults.
  12 |  */
  13 | import { expect, open, test } from './fixtures';
  14 | 
  15 | test('the catalogue arrives seeded from his sector — he never starts from a blank page', async ({ shop }) => {
  16 |   const body = await open(shop, '/services');
  17 | 
  18 |   await expect(shop.getByText('لا توجد خدمات')).toBeHidden();
  19 |   // Every service says its cycle, including the ones that legitimately have none: "0" is a real
  20 |   // answer for a puncture repair, and «بلا دورة» is how it is said.
> 21 |   expect(body).toMatch(/كل \d+ يوماً|بلا دورة/);
     |                ^ Error: expect(received).toMatch(expected)
  22 | });
  23 | 
  24 | test('the services are shown under the groups the system already knows', async ({ shop }) => {
  25 |   /**
  26 |    * The settings tree has held groups since it was written, and this screen listed twenty services
  27 |    * flat and showed none of it — an owner who had organised his shop was shown a wall. The
  28 |    * remainder bin is named too, because a list with no heading above it reads as unfiled rather
  29 |    * than as deliberate.
  30 |    */
  31 |   const body = await open(shop, '/services');
  32 | 
  33 |   expect(body).toMatch(/خدمات غير مجمّعة/);
  34 | });
  35 | 
  36 | test('a changed cycle is written to the tree the engine reads, and survives a reload', async ({ shop }) => {
  37 |   await open(shop, '/services');
  38 | 
  39 |   // Open the first service — the names are his to edit, so it is chosen by position.
  40 |   await shop.getByRole('button').filter({ hasText: /كل \d+ يوماً|بلا دورة/ }).first().click();
  41 | 
  42 |   const cycle = shop.getByLabel('دورة التذكير (بالأيام)');
  43 |   await expect(cycle).toBeVisible();
  44 |   await cycle.fill('37');
  45 |   await cycle.blur();
  46 | 
  47 |   // A NUMBER NOBODY WOULD SEED. 37 cannot be a default that happened to already be there, which
  48 |   // is what makes the reload below proof rather than coincidence.
  49 |   await expect(shop.getByText('كل 37 يوماً').first()).toBeVisible({ timeout: 30_000 });
  50 | 
  51 |   const body = await open(shop, '/services');
  52 |   expect(body).toMatch(/كل 37 يوماً/);
  53 |   // AND IT SAYS WHERE IT HAPPENED (§10.8.1): a service holding its own value says so on itself,
  54 |   // never in a distant settings screen he would have to find.
  55 |   expect(body).toMatch(/إعداد خاص/);
  56 | });
  57 | 
  58 | test('nothing on it is an untranslated key', async ({ shop }) => {
  59 |   const body = await open(shop, '/services');
  60 | 
  61 |   expect(body).not.toMatch(/[a-z]+\.[a-z]+\.[a-z]+/);
  62 | });
  63 | 
```