/**
 * الحملات — the salon's marketing campaigns, one of each behaviour the screen has.
 *
 * A standing win-back for customers late for their usual visit; a loyal-customer reward (paused by
 * the owner); a scheduled occasion campaign ten days out; a one-off offer on «حمام مغربي» that runs
 * the moment it is created; and the automatic service-due reminder switched on. Through the
 * campaigns service's own doors: create, pause, the service-due setting.
 *
 * READ THIS BEFORE TRUSTING THE NUMBERS ON THIS SCREEN. A campaign is a WhatsApp send, and this
 * demo shop has no connected number (no local stack can — that is Meta). Two consequences, both
 * the product's own behaviour rather than anything this script fakes:
 *   - creation passes the "approved template" gate only because notification-service is not run
 *     locally: reminders cannot learn the approval state, and by its own outage rule treats it as
 *     unknown rather than refusing (the goal cards say `template_status: unknown`). In production a
 *     shop with no Meta-approved template is refused at that gate.
 *   - every run reaches its audience and sends nothing: the runs report shows who matched and that
 *     no message left, exactly what an unconnected shop's run is.
 *
 * RE-RUN SAFE: one campaign per goal — a goal already on the list is not created again.
 */
import { addDaysStr, epochAtRiyadh, riyadhToday } from '../lib/demo-api.mjs';

export const app = 'feature.campaigns';

function planned(shop) {
  const today = riyadhToday();
  const at = (days, minute = 600) => epochAtRiyadh(addDaysStr(today, days), minute);
  const svc = (name) => shop.services.find((s) => s.name === name)?.id;
  return [
    { goal: 'win_back', state: 'active', body: { reward_kind: 'percent', reward_amount: 20, expires_at: at(60) } },
    { goal: 'reward_loyal', state: 'paused', body: { reward_kind: 'percent', reward_amount: 10, service_id: svc('قص شعر'),
      loyalty_window_days: 90, loyalty_min_visits: 3, expires_at: at(45) } },
    { goal: 'occasion', state: 'active', body: { reward_kind: 'percent', reward_amount: 15, fire_at: at(10),
      expires_at: at(17), owner_text: 'بمناسبة افتتاح فرعنا الجديد' } },
    { goal: 'service_offer', state: null, body: { reward_kind: 'fixed_halalas', reward_amount: 3000,
      service_id: svc('حمام مغربي'), expires_at: at(14) } },
  ];
}

export async function seed(ctx) {
  const { api, shop } = ctx;
  const existing = (await api.call(api.act('campaigns.list'))).campaigns ?? [];
  let created = 0;
  for (const c of planned(shop)) {
    let row = existing.find((r) => r.goal === c.goal);
    if (!row) {
      const out = await api.call(api.act('campaigns.create'), { goal: c.goal, ...c.body });
      row = out.campaign ?? out;
      created += 1;
    }
    if (c.state === 'paused' && row.state !== 'paused') await api.call(api.act('campaigns.pause'), { campaign_id: row.id });
  }
  await api.call(api.act('campaigns.service_due_settings_write'), { active: true });
  return { campaigns: planned(shop).length + 1, created };
}

/** Each campaign is on the list in its planned state (the one-off offer may have run to done), the
 *  service-due reminder is on, and the one-off offer has a real run report: it matched an audience
 *  and — the shop being unconnected — delivered nothing. */
export async function verify(ctx) {
  const { api, shop } = ctx;
  const problems = [];
  const rows = (await api.call(api.act('campaigns.list'))).campaigns ?? [];
  for (const c of planned(shop)) {
    const row = rows.find((r) => r.goal === c.goal);
    if (!row) { problems.push(`${c.goal} missing`); continue; }
    if (c.state && row.state !== c.state) problems.push(`${c.goal} is ${row.state}, planned ${c.state}`);
  }
  if (!rows.some((r) => r.goal === 'service_due' && r.state === 'active')) problems.push('service-due reminder not active');
  const offer = rows.find((r) => r.goal === 'service_offer');
  const runs = offer ? await api.call(api.act('campaigns.runs'), { campaign_id: offer.id }) : null;
  const totals = runs?.totals ?? {};
  if (!(totals.runs >= 1)) problems.push(`the one-off offer never ran: ${JSON.stringify(totals)}`);
  if (totals.sent > 0) problems.push(`${totals.sent} messages "sent" from a shop with no connected number`);
  if (problems.length) throw new Error(`campaigns check failed (${problems.length}): ${problems.join(' | ')}`);
  return { campaigns: rows.map((r) => `${r.goal}:${r.state}`), offer_run: totals };
}
