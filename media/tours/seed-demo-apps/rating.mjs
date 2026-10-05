/**
 * التقييم — the rating settings, and the staff-performance report the rating app carries.
 *
 * WHAT CANNOT BE SEEDED, AND WHY: the ratings themselves. A rating is the customer's answer to a
 * WhatsApp message — reminders sends it after the visit, and only that send mints the single-use
 * link (`/r/rate:<visit>`) the customer's public rating page accepts. There is no user-facing route
 * that sets a rating (only operations' internal one, called by reminders), and this shop has no
 * connected number to send from, so «التقييمات» stays honestly empty here. Writing ratings past the
 * API would invent customer opinions nobody gave.
 *
 * WHAT IS SEEDED: the owner's own rating settings (`PUT /api/v1/reminders/rating_settings` — ask
 * half an hour after the visit, 20 points for answering), so the settings screen shows a shop that
 * set them up.
 *
 * WHAT IS VERIFIED: the settings read back, the ratings list answers (empty), and the rating app's
 * staff-performance report counts exactly the visits each staff member served over the last 90
 * days — recounted from the customers' own visit records (the attributed visits come from attended
 * bookings; walk-in visits carry no staff member by product decision).
 */
import { pool } from '../lib/demo-api.mjs';

export const app = 'feature.rating';

const SETTINGS = { enabled: true, delay_minutes: 30, points: 20 };

export async function seed(ctx) {
  await ctx.api.call(ctx.api.act('reminders.set_rating_settings'), SETTINGS);
  return { settings: SETTINGS };
}

export async function verify(ctx) {
  const { api, customers } = ctx;
  const problems = [];
  const s = await api.call(api.act('reminders.rating_settings'));
  for (const [k, v] of Object.entries(SETTINGS)) if (s[k] !== v) problems.push(`setting ${k} = ${s[k]}, planned ${v}`);
  const ratings = (await api.call(api.act('operations.ratings'))).ratings ?? [];
  if (ratings.length) problems.push(`${ratings.length} ratings exist with no WhatsApp send behind them`);

  const until = Math.floor(Date.now() / 1000);
  const since = until - 90 * 86400;
  const perf = (await api.call(api.act('operations.staff_performance'), { since, until })).staff ?? [];
  const served = new Map();
  await pool(customers, 6, async (c) => {
    const rec = await api.call(api.act('operations.customer'), { id: c.id });
    for (const v of rec.visits ?? []) {
      if (v.operator_id && v.occurred_at >= since && v.occurred_at <= until) {
        served.set(v.operator_id, (served.get(v.operator_id) ?? 0) + 1);
      }
    }
  });
  // THE NO-SHOW COLUMN, recounted from the bookings themselves with bookings' own rule: every
  // booking whose day falls in the window (any status) is the denominator, the no-shows the
  // numerator, per staff member.
  const booked = new Map();
  const firstDay = new Date((since + 3 * 3600) * 1000).toISOString().slice(0, 10);
  const lastDay = new Date((until + 3 * 3600) * 1000).toISOString().slice(0, 10);
  await pool(customers, 6, async (c) => {
    for (const b of (await api.req('GET', `/api/v1/bookings/for-customer?customer_id=${c.id}`)).bookings ?? []) {
      const day = new Date((b.starts_at + 3 * 3600) * 1000).toISOString().slice(0, 10);
      if (day < firstDay || day > lastDay) continue;
      const t = booked.get(b.operator_id) ?? { total: 0, no_show: 0 };
      t.total += 1;
      if (b.status === 'no_show') t.no_show += 1;
      booked.set(b.operator_id, t);
    }
  });
  for (const row of perf) {
    if (row.visits !== (served.get(row.operator_id) ?? 0)) problems.push(`${row.operator_name}: report ${row.visits}, records ${served.get(row.operator_id) ?? 0}`);
    const t = booked.get(row.operator_id);
    const rate = t && t.total ? Math.round((t.no_show / t.total) * 100) / 100 : 0;
    if (row.no_show_rate !== rate) problems.push(`${row.operator_name}: no-show ${row.no_show_rate}, bookings say ${rate}`);
  }
  if (perf.length !== served.size) problems.push(`report names ${perf.length} staff, records ${served.size}`);
  if (problems.length) throw new Error(`rating check failed (${problems.length}): ${problems.join(' | ')}`);
  return { settings: SETTINGS, ratings: 0, staff_report: perf.map((r) => `${r.operator_name}: ${r.visits} visits, no-show ${r.no_show_rate}`) };
}
