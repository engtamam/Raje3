/**
 * الإحالة والمسوقين — the salon's referral programmes.
 *
 * Two real campaigns through the referrals service's own door (`POST /api/v1/referrals/campaigns`):
 * a standing one — a customer who brings a new one earns 100 points, the newcomer gets 15% off a
 * first visit of 100 SAR or more — and a three-times mystery-box campaign the owner tried and then
 * switched off. That is what the programme list and its settings screens show.
 *
 * WHAT THIS DELIBERATELY DOES NOT SEED, AND WHY: referral REDEMPTIONS. A redemption needs a code,
 * and no user-facing route can produce one today — a customer's global code is minted only by the
 * referrals service's internal route (nothing calls it), and the shop-affiliate codes live on
 * operations' `/api/v1/affiliates`, which the gateway hands to affiliate-service instead (the same
 * shadowing that hid `/api/v1/referrals/reports` until the gateway learned a narrower prefix for
 * it). Faking either would mean writing past the API, so the reports stay honestly at zero, and
 * this module checks that they are reachable and say so.
 *
 * RE-RUN SAFE: a campaign is matched by its mode and reward kind before one is created.
 */
export const app = 'feature.referrals';

const CAMPAIGNS = [
  { key: 'standing', active: true, body: {
    mode: 'lifetime', reward_type: 'fixed_points', reward_params: { points: 100 },
    new_customer_reward_type: 'discount_percent', new_customer_reward_params: { percent: 15 },
    min_spend_minor: 10000, usage_cap_period: 'month', usage_cap_limit: 20, cap_scope: 'campaign',
    beneficiary_eligibility: 'new' } },
  { key: 'mystery', active: false, body: {
    mode: 'x_times', x_times_limit: 3, reward_type: 'mystery_box',
    reward_params: { outcomes: [{ weight: 3, points: 50 }, { weight: 1, points: 200 }] },
    new_customer_reward_type: 'welcome_points', new_customer_reward_params: { points: 50 },
    beneficiary_eligibility: 'new' } },
];

const find = (rows, c) => rows.find((r) => r.mode === c.body.mode && r.reward_type === c.body.reward_type);

export async function seed(ctx) {
  const { api } = ctx;
  const rows = (await api.call(api.act('referrals.list_campaigns'))).campaigns ?? [];
  let created = 0;
  for (const c of CAMPAIGNS) {
    let row = find(rows, c);
    if (!row) {
      const out = await api.call(api.act('referrals.create_campaign'), c.body);
      row = out.campaign ?? out;
      created += 1;
    }
    if (Boolean(row.active) !== c.active) {
      await api.call(api.act('referrals.set_campaign_active'), { campaign_id: row.id, active: c.active });
    }
  }
  return { campaigns: CAMPAIGNS.length, created };
}

export async function verify(ctx) {
  const { api } = ctx;
  const problems = [];
  const rows = (await api.call(api.act('referrals.list_campaigns'))).campaigns ?? [];
  for (const c of CAMPAIGNS) {
    const row = find(rows, c);
    if (!row) problems.push(`${c.key} campaign missing`);
    else if (Boolean(row.active) !== c.active) problems.push(`${c.key} active=${row.active}, planned ${c.active}`);
  }
  // REACHABLE THROUGH THE GATEWAY, and honestly empty — see the module note on redemptions.
  const summary = await api.req('GET', '/api/v1/referrals/reports/summary');
  if (typeof summary.registered_count !== 'number') problems.push(`reports unreachable: ${JSON.stringify(summary).slice(0, 120)}`);
  const perCampaign = (await api.req('GET', '/api/v1/referrals/reports/campaigns')).campaigns ?? [];
  if (problems.length) throw new Error(`referrals check failed (${problems.length}): ${problems.join(' | ')}`);
  return { campaigns: rows.length, active: rows.filter((r) => r.active).length,
    registered: summary.registered_count, redeemed: summary.redeemed_count, report_rows: perCampaign.length };
}
