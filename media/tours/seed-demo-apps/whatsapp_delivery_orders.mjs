/**
 * طلبات التوصيل عبر الواتساب — the order board's own settings; the orders themselves cannot exist.
 *
 * WHY NO ORDERS, checked in the code rather than assumed:
 *   - an order is CREATED only by operations' internal `POST /internal/operations/whatsapp-orders`,
 *     called by whatsapp-assistant when a customer completes a WhatsApp catalog order and shares a
 *     location — there is no staff or public route that creates one, and this shop has no
 *     connected number to receive a catalog order on;
 *   - and an order that did exist would never leave `received`: it moves on only through
 *     `OrderService.confirm_payment`, reached only from `sync_payment`, which nothing in the
 *     repository calls (no route, no scheduled job, no payment-event subscriber) — so «preparing»,
 *     «out for delivery» and «delivered» are unreachable for every order, everywhere, not just here.
 * Inventing order rows past the API would show a board no real shop can have.
 *
 * WHAT IS SEEDED: the two settings that screen does own — the branch accepting orders (not paused)
 * and sharing each order with the delivery rep switched on — through the staff routes, and the
 * main branch's delivery radius (set by the foundation) that coverage reads.
 */
export const app = 'feature.whatsapp_delivery_orders';

const BASE = '/api/v1/staff/whatsapp-orders';

export async function seed(ctx) {
  const { api, shop } = ctx;
  await api.req('POST', `${BASE}/pause`, { branch_id: shop.branchId, paused: false, reason: '' });
  await api.req('POST', `${BASE}/share-toggle`, { enabled: true });
  return { branch_accepting: true, share_with_rep: true };
}

export async function verify(ctx) {
  const { api, shop } = ctx;
  const problems = [];
  const orders = (await api.req('GET', BASE)).orders;
  if (!Array.isArray(orders)) problems.push('the order board did not answer with a list');
  const share = await api.req('GET', `${BASE}/share-toggle`);
  if (share.enabled !== true) problems.push(`share-with-rep is ${share.enabled}`);
  const pause = await api.req('GET', `${BASE}/pause?branch_id=${encodeURIComponent(shop.branchId)}`);
  const paused = pause.paused ?? pause.branches?.find?.((b) => b.branch_id === shop.branchId)?.paused;
  if (paused) problems.push('the main branch is paused');
  const branch = ((await api.call(api.act('operations.list_branches'))).branches ?? []).find((b) => b.id === shop.branchId);
  if (!(branch?.delivery_radius_km > 0)) problems.push(`the main branch has no delivery radius (${branch?.delivery_radius_km})`);
  if (problems.length) throw new Error(`delivery orders check failed (${problems.length}): ${problems.join(' | ')}`);
  return { orders: orders.length, share_with_rep: true, branch_paused: Boolean(paused), delivery_radius_km: branch.delivery_radius_km };
}
