/**
 * صفقات (insights) — the advice screen, computed from everything the other modules recorded.
 *
 * Insights owns no input of its own to seed: its whole subject is the shop's real activity, which
 * the visit, bookings, home-service and loyalty modules have already written. So this module asks
 * for a fresh computation through the owner's own door (`POST /api/v1/insights/refresh`, the
 * dashboard's «حدّث» — throttled by the service itself to once per quarter hour, and the scheduled
 * insights tick recomputes regardless) and then holds the dashboard to account.
 *
 * VERIFIED AGAINST OPERATIONS, NOT AGAINST ITSELF. Every total the dashboard shows is recounted
 * from the visits on the fifty customers' own records — visits per branch (plus «unknown branch»),
 * per staff member (plus unattributed), per hour of the week, service lines by popularity, and how
 * many distinct customers were active — counting only visits that existed when the snapshot was
 * taken (`as_of`), so a snapshot that predates the latest module is checked as of its own moment.
 */
import { pool } from '../lib/demo-api.mjs';

export const app = 'feature.insights.engine';

export async function seed(ctx) {
  const out = await ctx.api.call(ctx.api.act('insights.refresh'));
  return { refresh: out.ok ? 'recomputed' : `not now (${out.message ?? 'throttled'})` };
}

const sum = (o) => Object.values(o ?? {}).reduce((s, n) => s + Number(n || 0), 0);

export async function verify(ctx) {
  const { api, customers } = ctx;
  let dash = await api.call(api.act('insights.dashboard'));
  for (let i = 0; i < 30 && dash.computing; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    dash = await api.call(api.act('insights.dashboard'));
  }
  const v = dash.values ?? {};
  const asOf = Number(dash.as_of ?? 0);
  if (!asOf) throw new Error(`insights has no computed snapshot yet: ${JSON.stringify(dash).slice(0, 200)}`);

  const visits = [];
  await pool(customers, 6, async (c) => {
    const rec = await api.call(api.act('operations.customer'), { id: c.id });
    if ((rec.visits ?? []).length >= 20) throw new Error(`${c.phone} has 20+ visits — the record page no longer shows them all`);
    for (const x of rec.visits ?? []) if (x.created <= asOf) visits.push({ ...x, customer_id: c.id });
  });

  const problems = [];
  const total = visits.length;
  const byBranch = sum(Object.fromEntries((v.branch_rows ?? []).map((r) => [r.branch_id, r.visits]))) + Number(v.branch_unknown ?? 0);
  if (byBranch !== total) problems.push(`branch rows + unknown = ${byBranch}, visits on record = ${total}`);
  const byOperator = (v.operator_rows ?? []).reduce((s, r) => s + r.visits, 0) + Number(v.operator_unknown ?? 0);
  if (byOperator !== total) problems.push(`operator rows + unattributed = ${byOperator}, visits = ${total}`);
  const attributed = visits.filter((x) => x.operator_id).length;
  if ((v.operator_rows ?? []).reduce((s, r) => s + r.visits, 0) !== attributed) problems.push(`operator rows ≠ ${attributed} attributed visits`);
  if (sum(v.peak_map?.grid) !== total) problems.push(`peak map holds ${sum(v.peak_map?.grid)}, visits = ${total}`);
  const lines = visits.reduce((s, x) => s + x.service_ids.length, 0);
  const popular = (v.service_popularity ?? []).reduce((s, r) => s + r.count, 0);
  if (popular !== lines) problems.push(`service popularity counts ${popular}, service lines = ${lines}`);
  const active = new Set(visits.map((x) => x.customer_id)).size;
  if (Number(v.active_customers) !== active) problems.push(`active customers ${v.active_customers}, distinct visitors = ${active}`);
  if (problems.length) throw new Error(`insights check failed (${problems.length}): ${problems.join(' | ')}`);
  return { as_of_hours_ago: dash.as_of_hours_ago, visits: total, active_customers: active,
    attributed_to_staff: attributed, return_rate: v.return_rate, churn_rate: v.churn_rate,
    at_risk: (v.at_risk ?? []).length, busiest: v.peak_map?.busiest };
}
