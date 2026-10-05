/**
 * الحجوزات — eight weeks of appointments behind today and two weeks ahead, across all three staff.
 *
 * About thirty of the fifty book (some of them also walk in — the visit module's customers overlap
 * on purpose): the past is closed the way a real day closes — mostly attended, a no-show now and
 * then, a few cancelled — and the next fourteen days are open bookings with a real mix of «بدون»,
 * «عربون» and «مدفوع». One customer has a run of no-shows, so the risk badge has someone real to
 * point at rather than nobody.
 *
 * THE REAL DOORS, AND THEIR REAL SIDE EFFECTS. `POST /api/v1/bookings` creates; attend/no-show/
 * cancel close. Attending is what turns a booking into a VISIT — bookings calls operations'
 * record_visit with the booking's own operator and branch — so these are the visits that carry a
 * staff member (walk-in visits carry none, by product decision), and they earn loyalty points
 * through the same event as any other visit. `occurred_at = starts_at` on attend, or a backdated
 * appointment would be stamped "now".
 *
 * NO COLLISIONS BY CONSTRUCTION. Each operator's day is a fixed set of start times spaced wider
 * than the longest service placed in them, and a slot is either used or not — the server's own
 * overlap lock would refuse a clash, and a seed that silently came up short is the worse outcome.
 *
 * RE-RUN SAFE: every booking carries a fixed idempotency key, so a re-run gets the booking it
 * already made; it is only closed (attended/no-show/cancelled) if it is still `booked`.
 */
import { addDaysStr, epochAtRiyadh, pool, riyadhToday } from '../lib/demo-api.mjs';

export const app = 'feature.bookings';

const CUSTOMERS = 30;
const DAYS_BACK = 56;          // attended visits must stay inside operations' 90-day backdate window
const DAYS_AHEAD = 14;
// Start times per operator column — 3h apart, so nothing up to 180 minutes can overlap the next.
const SLOTS = [600, 780, 960, 1140];   // 10:00 · 13:00 · 16:00 · 19:00
const LATE_SLOT_MAX_MINUTES = 150;     // the 19:00 slot only takes what ends by the 22:00 close

/** Everything decided up front — the same plan for seed() and verify(). */
export function plan({ customers, shop, rng }) {
  const today = riyadhToday();
  const nowEpoch = Math.floor(Date.now() / 1000);
  const people = rng.sample(customers, CUSTOMERS);
  const risky = people[0];
  const out = [];
  for (let d = -DAYS_BACK; d <= DAYS_AHEAD; d++) {
    const date = addDaysStr(today, d);
    for (const [oi, operator] of shop.operators.entries()) {
      for (const [si, minute] of SLOTS.entries()) {
        // About one slot in three filled — a believable book, not a wall.
        if (rng.next() > 0.32) continue;
        const pool = si === SLOTS.length - 1
          ? shop.services.filter((s) => s.duration_minutes <= LATE_SLOT_MAX_MINUTES) : shop.services;
        const service = rng.pick(pool);
        const startsAt = epochAtRiyadh(date, minute);
        const customer = rng.pick(people.slice(1));
        const past = startsAt + service.duration_minutes * 60 < nowEpoch;
        const roll = rng.next();
        const outcome = !past ? 'booked' : roll < 0.78 ? 'attended' : roll < 0.9 ? 'no_show' : 'cancelled';
        const payRoll = rng.next();
        const pay = payRoll < 0.55 ? 'none' : payRoll < 0.8 ? 'deposit' : 'paid';
        out.push({
          key: `apps-bkg-${date}-${oi}-${si}`, customer, operator_id: operator.id, service,
          starts_at: startsAt, outcome, payment_status: pay,
          deposit_amount_minor: pay === 'deposit' ? (rng.next() < 0.5 ? 5000 : 10000) : undefined,
        });
      }
    }
  }
  // THE RISKY CUSTOMER — five weekly mornings at 09:00 (outside every SLOT above, so it never
  // collides), four of them missed: past the risk rule's own bar (≥60% of the last 5 closed).
  for (let w = 1; w <= 5; w++) {
    const date = addDaysStr(today, -7 * w);
    const service = shop.services.find((s) => s.duration_minutes <= 60) ?? shop.services[0];
    out.push({
      key: `apps-bkg-risky-${w}`, customer: risky, operator_id: shop.operators[w % shop.operators.length].id,
      service, starts_at: epochAtRiyadh(date, 540), outcome: w === 3 ? 'attended' : 'no_show',
      payment_status: 'none', risky: true,
    });
  }
  return { bookings: out, risky };
}

const CLOSE = {
  attended: (b) => ({ method: 'PATCH', path: `/api/v1/bookings/${b.id}/attend` }),
  no_show: (b) => ({ method: 'PATCH', path: `/api/v1/bookings/${b.id}/no-show` }),
  cancelled: (b) => ({ method: 'PATCH', path: `/api/v1/bookings/${b.id}/cancel` }),
};

export async function seed(ctx) {
  const { bookings } = plan(ctx);
  const results = await pool(bookings, 6, async (p) => {
    const booking = await ctx.api.req('POST', '/api/v1/bookings', {
      branch_id: ctx.shop.branchId, operator_id: p.operator_id, customer_id: p.customer.id,
      service_ids: [p.service.id], starts_at: p.starts_at, idempotency_key: p.key,
      payment_status: p.payment_status, deposit_amount_minor: p.deposit_amount_minor,
    });
    if (p.outcome !== 'booked' && booking.status === 'booked') {
      const body = p.outcome === 'attended' ? { occurred_at: p.starts_at }
        : p.outcome === 'cancelled' ? { reason: 'اعتذرت العميلة' } : { reason: '' };
      await ctx.api.call(CLOSE[p.outcome](booking), body);
    }
    return booking;
  });
  const failed = results.filter((r) => r?.error);
  if (failed.length) throw new Error(`${failed.length}/${bookings.length} bookings failed — first: ${failed[0].error}`);
  const tally = bookings.reduce((t, b) => ({ ...t, [b.outcome]: (t[b.outcome] ?? 0) + 1 }), {});
  return { customers: new Set(bookings.map((b) => b.customer.id)).size, bookings: bookings.length, ...tally };
}

/**
 * Every planned booking is on its customer's real history in the planned state, at the planned
 * time with the planned staff member; every attended one produced a real visit attributed to that
 * staff member; and the risky customer reads risky through the real risk route.
 */
export async function verify(ctx) {
  const { bookings, risky } = plan(ctx);
  const byCustomer = new Map();
  for (const b of bookings) {
    if (!byCustomer.has(b.customer.id)) byCustomer.set(b.customer.id, []);
    byCustomer.get(b.customer.id).push(b);
  }
  const problems = [];
  let matched = 0;
  let visitsChecked = 0;
  await pool([...byCustomer.entries()], 4, async ([customerId, planned]) => {
    const real = (await ctx.api.req('GET', `/api/v1/bookings/for-customer?customer_id=${customerId}`)).bookings ?? [];
    const rec = await ctx.api.call(ctx.api.act('operations.customer'), { id: customerId });
    const visitIds = new Map((rec.visits ?? []).map((v) => [v.id, v]));
    for (const p of planned) {
      // MATCHED BY ITS OWN IDEMPOTENCY KEY, which a booking returns on every read — unlike a visit,
      // so no time-of-day matching is needed here.
      const hit = real.find((r) => r.idempotency_key === p.key);
      if (!hit) { problems.push(`${p.key}: not in ${p.customer.phone}'s bookings`); continue; }
      if (hit.status !== p.outcome) problems.push(`${p.key}: status ${hit.status}, planned ${p.outcome}`);
      if (hit.operator_id !== p.operator_id) problems.push(`${p.key}: operator ${hit.operator_id}`);
      if (p.outcome === 'attended') {
        const v = visitIds.get(hit.visit_id);
        // `for_customer` lists the newest 20 visits; an older attended visit is checked by id only.
        if (!hit.visit_id) problems.push(`${p.key}: attended with no visit`);
        else if (v) {
          visitsChecked += 1;
          if (v.operator_id !== p.operator_id) problems.push(`${p.key}: visit operator ${v.operator_id}`);
          if (Math.abs(v.occurred_at - hit.starts_at) > 60) problems.push(`${p.key}: visit at ${v.occurred_at}, booking ${hit.starts_at}`);
        }
      }
      matched += 1;
    }
  });
  if (problems.length) throw new Error(`bookings check failed (${problems.length}): ${problems.slice(0, 4).join(' | ')}`);
  const risk = await ctx.api.req('GET', `/api/v1/bookings/risk?customer_id=${risky.id}`);
  if (!risk.risky) throw new Error(`risky customer ${risky.phone} reads ${JSON.stringify(risk)}`);
  return { bookings_matched: matched, of: bookings.length, attended_visits_checked: visitsChecked,
    risky_customer: `${risky.phone} (${risk.no_shows}/${risk.considered} no-shows)` };
}
