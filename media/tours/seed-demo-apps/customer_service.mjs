/**
 * خدمات ما بعد البيع — the follow-up desk: who was called after their visit, how they felt, what
 * was done about it.
 *
 * Two freelancers on the shop's follow-up team, the shop's contact rules and reward options, and
 * fourteen of the fifty actually followed up: a note on each call, a satisfaction status (mostly
 * happy, some neutral, a few not), a thank-you reward for some (points, a discount, a gift), the
 * unhappy ones escalated to the owner — one of them already resolved — and one customer who asked
 * not to be contacted again.
 *
 * THE SHOP'S OWN DOORS (`/api/v1/staff/freelancers/...` and `/api/v1/staff/freelancer-portal/...`).
 * A freelancer cannot sign in yet (the token step was never built), so the portal is driven the way
 * the console's own internal tab drives it today: from the shop's session. A points reward with the
 * customer's pseudonym is credited by loyalty for real (`award:<key>` on their ledger).
 *
 * RE-RUN SAFE BY THE PRODUCT'S OWN RULE: the portal lists only customers not contacted within the
 * shop's cooldown, so a customer this module already followed up is simply not on the list on the
 * next run, and nothing is done to them twice. Escalations are matched by customer, reward options
 * by label, freelancers by phone.
 */
import { pool } from '../lib/demo-api.mjs';

export const app = 'feature.customer_service';

const FREELANCERS = [{ phone: '0570003001', display_name: 'أ. هند — متابعة العملاء' },
  { phone: '0570003002', display_name: 'أ. مريم — خدمة ما بعد البيع' }];
const RULES = { cooldown_days: 30, daily_cap: 10, quiet_start_minute: 22 * 60, quiet_end_minute: 9 * 60 };
const OPTIONS = [
  { kind: 'points', label: '50 نقطة شكر', points: 50 },
  { kind: 'discount', label: 'خصم 15% على الزيارة القادمة', percent: 15 },
  { kind: 'gift', label: 'عينة سيروم شعر مجانية' },
];
const NOTES = {
  satisfied: ['ممتنة جداً للخدمة، وتنوي تحجز الشهر القادم.', 'أعجبتها النتيجة وطلبت نفس الأخصائية مرة ثانية.',
    'راضية، وسألت عن عروض الباقات.'],
  neutral: ['الخدمة جيدة لكن الانتظار كان طويلاً.', 'تقول السعر أعلى من توقعها لكن النتيجة مقبولة.'],
  unsatisfied: ['اللون طلع مختلف عن المتفق عليه.', 'تأخر موعدها نصف ساعة ولم يُعتذر لها.'],
};

const PORTAL = '/api/v1/staff/freelancer-portal/customers';

/** Who is followed up, and how — decided up front, the same plan for seed() and verify(). */
export function plan({ customers, rng }) {
  const people = rng.sample(customers, 15);
  const moods = ['satisfied', 'satisfied', 'satisfied', 'satisfied', 'satisfied', 'satisfied', 'satisfied',
    'satisfied', 'neutral', 'neutral', 'neutral', 'unsatisfied', 'unsatisfied', 'unsatisfied'];
  const calls = moods.map((mood, i) => ({
    customer: people[i], mood, note: rng.pick(NOTES[mood]),
    reward: mood === 'satisfied' ? [OPTIONS[0], OPTIONS[0], OPTIONS[1], OPTIONS[2]][i] ?? null : null,
    escalate: mood === 'unsatisfied', resolve: mood === 'unsatisfied' && i === 11,
  }));
  return { calls, dnd: people[14] };
}

async function ensureSetup(api) {
  const have = (await api.call(api.act('operations.freelancer_list'))).freelancers ?? [];
  for (const f of FREELANCERS) {
    if (!have.some((x) => x.phone.endsWith(f.phone.slice(1)))) await api.call(api.act('operations.freelancer_add'), f);
  }
  await api.call(api.act('operations.freelancer_rules_set'), RULES);
  const opts = (await api.call(api.act('operations.freelancer_reward_options_list'))).options ?? [];
  const byLabel = new Map(opts.map((o) => [o.label, o]));
  for (const o of OPTIONS) {
    if (!byLabel.has(o.label)) byLabel.set(o.label, await api.call(api.act('operations.freelancer_reward_option_add'), o));
  }
  return byLabel;
}

export async function seed(ctx) {
  const { api } = ctx;
  const options = await ensureSetup(api);
  const { calls, dnd } = plan(ctx);
  const listed = new Set(((await api.req('GET', `${PORTAL}?limit=200`)).customers ?? []).map((c) => c.customer_id));
  const escalations = (await api.call(api.act('operations.freelancer_escalations_list'))).escalations ?? [];
  let done = 0;
  for (const call of calls) {
    const id = call.customer.id;
    if (!listed.has(id)) continue;            // already followed up (or never eligible) — nothing twice
    const rec = await api.call(api.act('operations.customer'), { id });
    const services = (rec.visits?.[0]?.services ?? '').split('، ').filter(Boolean);
    await api.req('POST', `${PORTAL}/${id}/notes`, { text: call.note, status: call.mood, services });
    await api.req('POST', `${PORTAL}/${id}/rate`, { status: call.mood });
    if (call.reward) {
      await api.req('POST', `${PORTAL}/${id}/reward`, {
        option_id: options.get(call.reward.label).id, subject_ref: call.customer.subject_ref,
      });
    }
    if (call.escalate && !escalations.some((e) => e.customer_id === id)) {
      const esc = await api.req('POST', `${PORTAL}/${id}/escalate`, { note: `تحتاج اتصالاً من المالكة: ${call.note}` });
      if (call.resolve) {
        await api.req('POST', `/api/v1/staff/freelancers/escalations/${esc.id}/resolve`, {
          resolution_note: 'اتصلت المالكة واعتذرت، وحُجز لها موعد تصحيح مجاني.', new_status: 'neutral',
        });
      }
    }
    done += 1;
  }
  if (listed.has(dnd.id)) await api.req('POST', `${PORTAL}/${dnd.id}/do-not-disturb`);
  return { freelancers: FREELANCERS.length, reward_options: OPTIONS.length, followed_up_now: done,
    planned: calls.length, do_not_disturb: 1 };
}

/** Each planned call is in the shop's notes export with its customer and status; none of the
 *  followed-up or do-not-disturb customers is still on the to-contact list; the unhappy ones are
 *  escalated (one resolved); and every points reward reached the customer's loyalty ledger. */
export async function verify(ctx) {
  const { api } = ctx;
  const { calls, dnd } = plan(ctx);
  const problems = [];
  const freelancers = (await api.call(api.act('operations.freelancer_list'))).freelancers ?? [];
  if (freelancers.length !== FREELANCERS.length) problems.push(`${freelancers.length} freelancers`);
  const exp = await api.req('GET', `/api/v1/staff/freelancers/notes/export?since=0&until=${Math.floor(Date.now() / 1000) + 60}&include_pii=true`);
  const text = exp.text ?? '';
  const listed = new Set(((await api.req('GET', `${PORTAL}?limit=200`)).customers ?? []).map((c) => c.customer_id));
  const open = (await api.req('GET', '/api/v1/staff/freelancers/escalations?status_filter=open')).escalations ?? [];
  const resolved = (await api.req('GET', '/api/v1/staff/freelancers/escalations?status_filter=resolved')).escalations ?? [];
  let rewardsCredited = 0;
  await pool(calls, 4, async (call) => {
    const c = call.customer;
    if (!text.includes(call.note) || !text.includes(c.name)) problems.push(`${c.phone}: note not in the export`);
    if (listed.has(c.id)) problems.push(`${c.phone}: followed up but still on the to-contact list`);
    if (call.escalate) {
      const inOpen = open.some((e) => e.customer_id === c.id);
      const inResolved = resolved.some((e) => e.customer_id === c.id);
      if (call.resolve ? !inResolved : !inOpen) problems.push(`${c.phone}: escalation not ${call.resolve ? 'resolved' : 'open'}`);
    }
    if (call.reward?.kind === 'points') {
      const hist = await api.call(api.act('loyalty.history'), { subject_ref: c.subject_ref, limit: 100 });
      if ((hist.entries ?? []).some((e) => String(e.source).startsWith('award:') && e.delta === call.reward.points)) rewardsCredited += 1;
      else problems.push(`${c.phone}: points reward never reached the ledger`);
    }
  });
  if (listed.has(dnd.id)) problems.push(`${dnd.phone}: do-not-disturb but still listed`);
  if (problems.length) throw new Error(`customer service check failed (${problems.length}): ${problems.slice(0, 4).join(' | ')}`);
  return { notes_in_export: calls.length, escalations_open: open.length, escalations_resolved: resolved.length,
    points_rewards_credited: rewardsCredited, still_to_contact: listed.size };
}
