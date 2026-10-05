/**
 * تسجيل زيارة — the walk-in history every other screen reads from.
 *
 * Thirty-four of the fifty have been in, one to six times each over the last twelve weeks, a
 * different mix of services every time — so «عملائي», the customer card's timeline, «اليوم» and
 * insights all have a real past to show. The other sixteen are customers who only ever booked,
 * ordered or were served at home (other modules), which is what a real book of customers looks
 * like: not everyone walks in.
 *
 * THROUGH THE FIELD SCREEN'S OWN DOOR (`POST /api/v1/field/visits`), with the shop's own clock
 * (`occurred_at`) backdated inside operations' 90-day `MAX_BACKDATE_SECONDS` window. Every visit
 * publishes the real `operations.visit.recorded` event, so loyalty earns on it and reminders learns
 * the customer's cycle from it — nothing here touches either service directly.
 *
 * NO STAFF MEMBER ON A WALK-IN VISIT, by product decision: shared-tablet attribution was removed
 * end to end (49465ec4, "no replacement mechanism"), so the field door takes no operator and these
 * visits stay unattributed exactly as the product records them. Per-staff numbers come from the
 * bookings and home-service modules, whose visits do carry their operator.
 *
 * `recorded: false` IS A FAILURE, NOT A 201 TO SHRUG AT. The door answers refusals in the body
 * with a success status (so the sentence survives the platform's error handler); a seed that only
 * checked the status once counted visits the shop never counted.
 *
 * RE-RUN SAFE: each planned visit carries a fixed idempotency key (`apps-visit-<phone>-<n>`), and
 * the visit door answers a replayed key with the visit it already holds — never a second one.
 */
import { addDaysStr, epochAtRiyadh, pool, riyadhToday } from '../lib/demo-api.mjs';

export const app = 'feature.visit';

const CUSTOMERS = 34;
const MAX_DAYS_BACK = 84;   // inside the 90-day backdate window, with room for a slow run

export function riyadhMinute(epoch) { return Math.floor(((Number(epoch) + 3 * 3600) % 86400) / 60); }

/** The whole history, decided up front — the same plan for seed() and verify(). */
export function plan({ customers, shop, rng }) {
  const today = riyadhToday();
  const out = [];
  for (const c of rng.sample(customers, CUSTOMERS)) {
    const n = rng.int(1, 6);
    for (let k = 0; k < n; k++) {
      const services = rng.sample(shop.services, rng.next() < 0.7 ? 1 : 2);
      const daysBack = rng.int(1, MAX_DAYS_BACK);
      const minute = rng.int(10 * 60, 21 * 60);   // the salon's working day, Riyadh time
      out.push({
        customer: c,
        key: `apps-visit-${c.phone}-${k}`,
        service_ids: services.map((s) => s.id),
        points: services.reduce((sum, s) => sum + (s.points ?? 0), 0),
        occurred_at: epochAtRiyadh(addDaysStr(today, -daysBack), minute),
      });
    }
  }
  return out;
}

export async function seed(ctx) {
  const visits = plan(ctx);
  const record = ctx.api.act('operations.record_visit');
  const results = await pool(visits, 6, async (v) => {
    const out = await ctx.api.call(record, {
      phone: v.customer.phone,
      service_ids: v.service_ids,
      idempotency_key: v.key,
      occurred_at: v.occurred_at,
      branch_id: ctx.shop.branchId,
    });
    if (out.recorded === false) throw new Error(`${v.key}: ${out.reason}`);
    return out;
  });
  const failed = results.filter((r) => r?.error);
  if (failed.length) throw new Error(`${failed.length}/${visits.length} visits refused — first: ${failed[0].error}`);
  return { customers: new Set(visits.map((v) => v.customer.id)).size, visits: visits.length };
}

/**
 * Every planned visit is on its customer's real record with the services it was planned with, and
 * the customer's own counters agree with the record: `visit_count` equals the visits listed and
 * `last_visit` is the newest of them. Other modules may ADD visits to the same customers (a
 * completed home service, an attended booking), so this checks the planned ones are all there,
 * never that nothing else is.
 */
export async function verify(ctx) {
  const visits = plan(ctx);
  const byCustomer = new Map();
  for (const v of visits) {
    if (!byCustomer.has(v.customer.id)) byCustomer.set(v.customer.id, []);
    byCustomer.get(v.customer.id).push(v);
  }
  const get = ctx.api.act('operations.customer');
  let found = 0;
  const problems = [];
  await pool(ctx.customers, 6, async (c) => {
    const rec = await ctx.api.call(get, { id: c.id });
    const real = rec.visits ?? [];
    for (const p of byCustomer.get(c.id) ?? []) {
      const want = [...p.service_ids].sort().join(',');
      // MATCHED BY WHAT AND WHEN-IN-THE-DAY, NOT BY DATE — the plan's dates are relative to the day
      // it runs, so a verify on a later day plans them later than they were recorded; the services
      // and the Riyadh minute of the day are what stay fixed.
      const hit = real.find((r) => riyadhMinute(r.occurred_at) === riyadhMinute(p.occurred_at)
        && [...(r.service_ids ?? [])].sort().join(',') === want);
      if (hit) found += 1;
      else problems.push(`${p.customer.phone}: no visit matching ${p.key}`);
    }
    // THE COUNTERS «عملائي» SORTS AND FILTERS BY, against the visits they claim to count.
    // The record lists the newest 20 visits (VisitStore.for_customer's page); past that the list is
    // not the whole history, and the count is only checked to be at least what is listed.
    const newest = Math.max(0, ...real.map((r) => r.occurred_at ?? 0));
    const count = rec.customer?.visit_count ?? 0;
    if (real.length < 20 ? count !== real.length : count < real.length) {
      problems.push(`${c.phone}: visit_count ${rec.customer?.visit_count} but ${real.length} visits on record`);
    }
    if (real.length && rec.customer?.last_visit !== newest) {
      problems.push(`${c.phone}: last_visit ${rec.customer?.last_visit} but newest visit is ${newest}`);
    }
  });
  if (problems.length) throw new Error(`visit check failed (${problems.length}): ${problems.slice(0, 4).join(' | ')}`);
  return { customers: byCustomer.size, visits_found: found, of: visits.length, counters: 'consistent' };
}
