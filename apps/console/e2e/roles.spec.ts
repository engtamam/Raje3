/**
 * THREE APPLICATIONS OUT OF ONE LIST, AND NOT ONE `if (role === …)` ANYWHERE.
 *
 * The nav is derived: each section declares the action ids it cannot exist without, the gateway has
 * already filtered the catalogue by the caller's capabilities, and a section whose actions are
 * absent is not rendered. That single rule produces the operator's one screen, the manager's many,
 * and the owner's all nine.
 *
 * WHY THIS FILE IS THE LAST ONE AND THE MOST IMPORTANT. A role check written into the client is a
 * SECOND copy of the permission model, and the copy is the one that goes stale: a capability added
 * to a role next month would need a client release to become visible. This spec is what stops the
 * first `if` from being added — it asserts the derivation itself, by asking the same question of
 * the running system that the sidebar asks.
 *
 * AND HIDING IS NEVER THE SECURITY MEASURE. The server refuses regardless; hiding is a courtesy so
 * a person is not offered what he cannot do (§10.8: "every element he does not use is a tax he
 * pays a hundred times a day"). So the refusal is asserted too, at the API, without a browser.
 */
import { expect, open, test } from './fixtures';

test('the owner reaches all nine sections, and the list is not written in the app', async ({ shop }) => {
  await open(shop, '/');

  const nav = shop.getByRole('navigation');
  for (const label of ['اليوم', 'تسجيل زيارة', 'عملائي', 'محلّي', 'خدماتي',
                       'رسائلي', 'نقاطي', 'فريقي', 'حسابي']) {
    await expect(nav.getByRole('link', { name: label })).toBeVisible();
  }
});

test('every nav entry actually leads somewhere — no link to a screen that does not exist', async ({ shop }) => {
  /**
   * A section derived from an action id whose screen was never built is worse than a missing one:
   * he clicks, gets a blank page, and the product looks broken rather than incomplete. Every
   * entry is opened, and «الصفحة غير موجودة» would be caught here.
   */
  await open(shop, '/');
  const paths = await shop.getByRole('navigation').getByRole('link')
    .evaluateAll((links) => links.map((l) => l.getAttribute('href') ?? ''));

  expect(paths.length).toBe(9);
  for (const path of paths) {
    const body = await open(shop, path);
    expect(body).not.toMatch(/غير موجودة|Not Found|Cannot GET/);
  }
});

test('the sections come from the catalogue, so removing an action removes the section', async ({ shop }) => {
  /**
   * THE DERIVATION ITSELF, asserted by breaking it. `loyalty.rewards.update` is what «نقاطي» is
   * gated on — gated on the WRITE and not the read, because listing rewards is a capability an
   * operator holds and a section whose every control is inert is worse than an absent one.
   *
   * Strip that one action from the catalogue response and the section must disappear. If it
   * survives, somebody has written the list into the app and the whole model is decorative.
   */
  await shop.route('**/api/v1/app/catalog', async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    for (const service of body.services ?? []) {
      service.actions = (service.actions ?? [])
        .filter((a: { id: string }) => a.id !== 'loyalty.rewards.update');
    }
    await route.fulfill({ response: res, json: body });
  });

  // The catalogue is cached per token for the session — a reload with the route in place refetches
  // it only if the cache is cleared, so this starts from a clean context state.
  await shop.evaluate(() => sessionStorage.clear());
  await open(shop, '/');

  await expect(shop.getByRole('navigation').getByRole('link', { name: 'نقاطي' })).toHaveCount(0);
  // And the rest of the application is untouched — this removed one section, not the derivation.
  await expect(shop.getByRole('navigation').getByRole('link', { name: 'اليوم' })).toBeVisible();
});

test('hiding is a courtesy — the server refuses regardless', async ({ shop }) => {
  /**
   * The one assertion in this suite that deliberately leaves the browser's UI behind. If the only
   * thing standing between a role and an action were a missing link, the product would be one
   * typed URL away from having no permissions at all.
   */
  const refused = await shop.evaluate(async () => {
    const res = await fetch('/api/v1/platform/sectors', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: 'x', name: 'x' }),
    });
    return res.status;
  });

  // 401/403/404 are all honest refusals; a 2xx would mean an owner just edited platform data.
  expect(refused).toBeGreaterThanOrEqual(400);
});
