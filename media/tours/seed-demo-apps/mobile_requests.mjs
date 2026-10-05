/**
 * خدمات متنقلة — the salon's home-service book: requests at every stage of their life.
 *
 * Sixteen of the fifty asked for a stylist at home: some are still waiting for the owner's
 * decision (pending), some are accepted and assigned to a staff member for the coming days, some
 * were done (completed — a real visit), turned down (rejected, with the reason the owner gave), or
 * nobody was home (no-show). Locations are real Riyadh districts, so every map pin opens somewhere
 * a salon would actually send someone.
 *
 * THE STAFF DOORS ONLY (`/api/v1/staff/mobile-requests` and its accept/reject/assign/complete/
 * no-show actions), within the shop's real working hours — the create door checks the requested
 * minute against them. Completing a request is what records its visit (operations' own
 * `record_visit`), so loyalty earns on it like any other visit. Noted while seeding: that visit is
 * stamped at the moment of completion and carries no staff member or branch even when the request
 * was assigned — so a completed request counts in no one's staff numbers.
 *
 * RE-RUN SAFE WITHOUT AN IDEMPOTENCY KEY (the create door takes none): a planned request already
 * on the list — same customer, same services, same Riyadh minute of the day — is not created
 * again, and a request already past its planned state is not moved again.
 */
import { addDaysStr, epochAtRiyadh, pool, riyadhToday } from '../lib/demo-api.mjs';

export const app = 'feature.mobile_requests';

const CUSTOMERS = 16;
// Riyadh districts the salon serves — [lat, lng].
const PLACES = [[24.7743, 46.7386], [24.6911, 46.6853], [24.8105, 46.6345], [24.7136, 46.6753],
  [24.7561, 46.6292], [24.6560, 46.7105], [24.8302, 46.7180], [24.7259, 46.7779]];
const REJECT_REASONS = ['خارج نطاق التغطية', 'لا يوجد موظفة متاحة في هذا الوقت', 'الطلب مكرر'];

export const riyadhMinute = (epoch) => Math.floor(((Number(epoch) + 3 * 3600) % 86400) / 60);

/** The whole book, decided up front — the same plan for seed() and verify(). */
export function plan({ customers, shop, rng }) {
  const today = riyadhToday();
  const out = [];
  const outcomes = ['pending', 'pending', 'pending', 'pending', 'pending',
    'accepted', 'accepted', 'accepted', 'accepted', 'accepted',
    'completed', 'completed', 'completed', 'completed', 'completed', 'completed', 'completed',
    'rejected', 'rejected', 'rejected', 'no_show', 'no_show'];
  const people = rng.sample(customers, CUSTOMERS);
  for (const [i, outcome] of outcomes.entries()) {
    const future = outcome === 'pending' || outcome === 'accepted' || (outcome === 'rejected' && i % 2);
    const daysOut = future ? rng.int(1, 10) : -rng.int(1, 30);
    const minute = rng.int(10, 20) * 60 + (rng.next() < 0.5 ? 0 : 30);   // on the hour or half past
    const services = rng.sample(shop.services.filter((s) => s.duration_minutes <= 120), rng.next() < 0.75 ? 1 : 2);
    const [lat, lng] = rng.pick(PLACES);
    out.push({
      customer: people[i % people.length], outcome,
      service_ids: services.map((s) => s.id),
      requested_time: epochAtRiyadh(addDaysStr(today, daysOut), minute),
      lat: lat + (rng.next() - 0.5) * 0.01, lng: lng + (rng.next() - 0.5) * 0.01,
      // Accepted ones are assigned (most of them), completed/no-show ones were assigned before the
      // day; a pending one has nobody yet, by definition of waiting for a decision.
      operator_id: outcome === 'pending' || outcome === 'rejected' ? '' :
        (outcome === 'accepted' && i % 5 === 4 ? '' : rng.pick(shop.operators).id),
      reason: outcome === 'rejected' ? rng.pick(REJECT_REASONS) : '',
    });
  }
  return out;
}

const same = (r, p) => r.phone.endsWith(p.customer.phone.slice(1))
  && riyadhMinute(r.requested_time) === riyadhMinute(p.requested_time)
  && [...r.service_ids].sort().join(',') === [...p.service_ids].sort().join(',');

const base = '/api/v1/staff/mobile-requests';

export async function seed(ctx) {
  const { api } = ctx;
  const planned = plan(ctx);
  const existing = (await api.req('GET', base)).requests ?? [];
  const results = await pool(planned, 4, async (p) => {
    let row = existing.find((r) => same(r, p));
    if (!row) {
      row = await api.req('POST', base, {
        phone: p.customer.phone, customer_name: p.customer.name, service_ids: p.service_ids,
        requested_time: p.requested_time, lat: p.lat, lng: p.lng, operator_id: p.operator_id,
      });
      row = row.request ?? row;
    }
    if (row.status === 'pending' && p.outcome !== 'pending') {
      if (p.outcome === 'rejected') {
        await api.req('POST', `${base}/${row.id}/reject`, { reason: p.reason });
        return row;
      }
      await api.req('POST', `${base}/${row.id}/accept`);
      row.status = 'accepted';
    }
    if (row.status === 'accepted' && p.outcome === 'completed') await api.req('POST', `${base}/${row.id}/complete`);
    if (row.status === 'accepted' && p.outcome === 'no_show') await api.req('POST', `${base}/${row.id}/no-show`);
    return row;
  });
  const failed = results.filter((r) => r?.error);
  if (failed.length) throw new Error(`${failed.length}/${planned.length} requests failed — first: ${failed[0].error}`);
  const tally = planned.reduce((t, p) => ({ ...t, [p.outcome]: (t[p.outcome] ?? 0) + 1 }), {});
  return { customers: new Set(planned.map((p) => p.customer.id)).size, requests: planned.length, ...tally };
}

/** Every planned request is on the real list in its planned state, assigned as planned, with the
 *  rejection reason kept; every completed one points at a real visit on its customer's record. */
export async function verify(ctx) {
  const { api } = ctx;
  const planned = plan(ctx);
  const rows = (await api.req('GET', base)).requests ?? [];
  const problems = [];
  let visits = 0;
  for (const p of planned) {
    const hits = rows.filter((r) => same(r, p));
    if (hits.length !== 1) { problems.push(`${p.customer.phone}: ${hits.length} requests match the plan`); continue; }
    const r = hits[0];
    if (r.status !== p.outcome) problems.push(`${p.customer.phone}: status ${r.status}, planned ${p.outcome}`);
    if ((r.assigned_to || '') !== p.operator_id) problems.push(`${p.customer.phone}: assigned ${r.assigned_to}`);
    if (p.outcome === 'rejected' && r.reject_reason !== p.reason) problems.push(`${p.customer.phone}: reason ${r.reject_reason}`);
    if (p.outcome === 'completed') {
      const rec = await api.call(api.act('operations.customer'), { id: p.customer.id });
      if (!r.visit_id || !(rec.visits ?? []).some((v) => v.id === r.visit_id)) {
        problems.push(`${p.customer.phone}: completed with no visit on record`);
      } else visits += 1;
    }
  }
  if (problems.length) throw new Error(`mobile requests check failed (${problems.length}): ${problems.slice(0, 4).join(' | ')}`);
  return { requests_matched: planned.length, completed_visits: visits,
    by_status: rows.reduce((t, r) => ({ ...t, [r.status]: (t[r.status] ?? 0) + 1 }), {}) };
}
