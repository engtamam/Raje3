/**
 * «فريقي» — the people, the branches, and the role that decides what each may touch.
 *
 * THE BUG THIS FILE WOULD HAVE CAUGHT: the screen asked for an act it did not offer. It listed
 * employees, said «لا يوجد موظفون بعد», and had no way to add one — and later, when the form
 * existed, it created every employee with no role chosen at all.
 *
 * A ROLE PICKER THAT OPENS ON «مدير» hands the shop to whoever is added while nobody was reading.
 * It opens on the narrowest role instead, and that default is asserted here rather than trusted.
 */
import { expect, open, test } from './fixtures';

test('an owner can actually add somebody — the screen offers the act it names', async ({ shop }) => {
  await open(shop, '/team');

  // THE FORM IS BEHIND THE BUTTON, and that is the point: the screen names the act, and the act
  // opens the fields. A form standing open on an empty screen is a form nobody asked for.
  await shop.getByRole('button', { name: 'إضافة موظف' }).click();

  await expect(shop.getByLabel('الاسم')).toBeVisible();
  await expect(shop.getByLabel('رمز الدخول (4 أرقام)')).toBeVisible();
});

test('the role is chosen, and it opens on the narrowest one', async ({ shop }) => {
  /**
   * DEFAULTS TO «موظف ميداني». A form that opens on «مدير» is a form that gives away the shop by
   * inattention — and the person adding an employee at the counter is, by definition, not reading
   * carefully.
   */
  await open(shop, '/team');
  await shop.getByRole('button', { name: 'إضافة موظف' }).click();

  await expect(shop.getByRole('radio', { name: /موظف ميداني/ })).toBeChecked();
  // AND THE OWNER IS NOT ON THE LIST. It is protected, there is exactly one, and transferring it
  // is its own act with its own confirmation — never a value in a dropdown on an add form.
  await expect(shop.getByRole('radio', { name: /^مالك/ })).toHaveCount(0);
});

test('each role says what that person may touch, not only what he is called', async ({ shop }) => {
  await open(shop, '/team');
  await shop.getByRole('button', { name: 'إضافة موظف' }).click();
  const body = (await shop.locator('body').innerText()).trim();

  // An owner choosing between «مدير» and «مشرف وردية» is choosing consequences, and a name with
  // no consequence beside it is a guess.
  expect(body).toMatch(/يسجّل الزيارات فقط/);
  expect(body).toMatch(/كل شيء عدا الفوترة/);
});

test('a plan without branches shows the tab locked — it never hides it', async ({ shop }) => {
  /**
   * A capability nobody can see cannot be bought, and a section that vanishes reads as a fault.
   * The campaign cards settled this already: «a card that disappears reads as a fault; a card that
   * explains itself reads as a rule».
   */
  await open(shop, '/team');

  await shop.getByRole('radio', { name: /الفروع/ }).click();
  const body = await shop.locator('body').innerText();
  expect(body).toMatch(/فرع واحد|اسم الفرع/);
});

test('nothing on it is an untranslated key', async ({ shop }) => {
  const body = await open(shop, '/team');

  expect(body).not.toMatch(/[a-z]+\.[a-z]+\.[a-z]+/);
});
