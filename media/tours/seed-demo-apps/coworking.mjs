/**
 * الاستضافة المهنية — the salon rents chairs and a room to freelance stylists by the hour.
 *
 * Three spaces with real weekly hours and hourly prices; six freelancers who found the shop's
 * public page and asked to join — four approved, one still waiting for the owner, one blocked —
 * and the approved ones' bookings over the past three weeks and the next two, a few of them
 * cancelled by the shop. These freelancers are NOT among the fifty customers: they are the people
 * renting a chair, not the people sitting in one.
 *
 * TWO REAL DOORS, the way the product actually splits it: the owner's admin routes
 * (`/api/v1/coworking/...` — spaces, availability, approving joins, cancelling) and the
 * freelancer's own PUBLIC portal (`/p/coworking/{tenant}/...` — join, book), which identifies a
 * freelancer by phone alone with the owner's approval as the only gate. Nothing is written past
 * either door.
 *
 * RE-RUN SAFE: spaces are matched by name, joins are idempotent by phone on both sides, and a
 * booking already held by the same freelancer, on the same space, at the same Riyadh minute of the
 * day, is not booked again.
 */
import { addDaysStr, epochAtRiyadh, pool, riyadhToday } from '../lib/demo-api.mjs';

export const app = 'feature.coworking';

const SPACES = [
  { name: 'كرسي تصفيف 1', description: 'كرسي تصفيف كامل التجهيز بجانب النافذة، مع مرآة وإضاءة احترافية.', price: 2500 },
  { name: 'كرسي تصفيف 2', description: 'كرسي تصفيف مع مغسلة شعر خاصة.', price: 3000 },
  { name: 'غرفة العناية بالبشرة', description: 'غرفة مغلقة بسرير علاجي وجهاز بخار، مناسبة لجلسات البشرة والتدليك.', price: 4500 },
];

// Saturday-to-Thursday 10:00–22:00, Friday afternoon only — weekday 0 is Monday (Riyadh calendar).
const WEEKLY = Object.fromEntries([0, 1, 2, 3, 5, 6].map((d) => [String(d), [{ start_minute: 600, end_minute: 1320 }]])
  .concat([['4', [{ start_minute: 960, end_minute: 1320 }]]]));

const FREELANCERS = [
  { phone: '0570002001', state: 'approved' }, { phone: '0570002002', state: 'approved' },
  { phone: '0570002003', state: 'approved' }, { phone: '0570002004', state: 'approved' },
  { phone: '0570002005', state: 'pending' }, { phone: '0570002006', state: 'blocked' },
];
const intl = (p) => `+966${p.slice(1)}`;
export const riyadhMinute = (epoch) => Math.floor(((Number(epoch) + 3 * 3600) % 86400) / 60);

/** Bookings decided up front — the same plan for seed() and verify(). Two per space per active
 *  day at most, on the hour, never overlapping within a space, always inside that day's window. */
export function plan({ rng }) {
  const today = riyadhToday();
  const approved = FREELANCERS.filter((f) => f.state === 'approved');
  const out = [];
  for (let d = -21; d <= 14; d++) {
    const date = addDaysStr(today, d);
    const jsDay = new Date(`${date}T00:00:00Z`).getUTCDay();   // 0 = Sunday
    const window = WEEKLY[String((jsDay + 6) % 7)][0];
    for (const [si] of SPACES.entries()) {
      if (rng.next() > 0.45) continue;
      const startHour = rng.int(window.start_minute / 60, window.end_minute / 60 - 4);
      const hours = rng.int(2, 4);
      out.push({
        space: si, freelancer: rng.pick(approved).phone, date,
        starts_at: epochAtRiyadh(date, startHour * 60), ends_at: epochAtRiyadh(date, (startHour + hours) * 60),
        cancel: d < 0 && rng.next() < 0.12,
      });
    }
  }
  return out;
}

async function ensureSpaces(api, branchId) {
  const have = (await api.call(api.act('coworking.list_resources'))).resources ?? [];
  const out = [];
  for (const s of SPACES) {
    let r = have.find((x) => x.name === s.name);
    if (!r) r = await api.call(api.act('coworking.create_resource'), { name: s.name, branch_id: branchId, description: s.description });
    r = r.resource ?? r;
    // The whole schedule is replaced on every call — idempotent by construction.
    await api.call(api.act('coworking.set_availability'), { resource_id: r.id, weekly: WEEKLY, exceptions: {}, hourly_price_minor: s.price });
    out.push(r);
  }
  return out;
}

export async function seed(ctx) {
  const { api, session, shop } = ctx;
  const spaces = await ensureSpaces(api, shop.branchId);
  const portal = `/p/coworking/${session.tenant}`;

  for (const f of FREELANCERS) {
    await api.req('POST', `${portal}/join`, { phone: f.phone });
    const enc = encodeURIComponent(intl(f.phone));
    if (f.state === 'approved') await api.call(api.act('coworking.approve_join'), { phone: intl(f.phone) }).catch(() => {});
    if (f.state === 'blocked') await api.req('POST', `/api/v1/coworking/joins/${enc}/block`);
  }

  const planned = plan(ctx);
  const mine = new Map();
  for (const f of FREELANCERS.filter((x) => x.state === 'approved')) {
    mine.set(f.phone, ((await api.req('GET', `${portal}/my-bookings?phone=${encodeURIComponent(f.phone)}`)).bookings ?? []));
  }
  let created = 0;
  let cancelled = 0;
  const results = await pool(planned, 3, async (p) => {
    const space = spaces[p.space];
    let b = (mine.get(p.freelancer) ?? []).find((x) => x.resource_id === space.id
      && riyadhMinute(x.starts_at) === riyadhMinute(p.starts_at) && x.ends_at - x.starts_at === p.ends_at - p.starts_at);
    if (!b) {
      b = await api.req('POST', `${portal}/bookings`, { phone: p.freelancer, resource_id: space.id, starts_at: p.starts_at, ends_at: p.ends_at });
      if (!b?.id) throw new Error(`booking for ${p.freelancer} on ${p.date} not made: ${JSON.stringify(b).slice(0, 160)}`);
      created += 1;
    }
    if (p.cancel && b.status !== 'cancelled') {
      await api.call(api.act('coworking.cancel_booking'), { booking_id: b.id });
      cancelled += 1;
    }
    return b;
  });
  const failed = results.filter((r) => r?.error);
  if (failed.length) throw new Error(`${failed.length}/${planned.length} coworking bookings failed — first: ${failed[0].error}`);
  return { spaces: spaces.length, freelancers: FREELANCERS.length, bookings: planned.length, created, cancelled };
}

/** The spaces carry their schedule and price; each freelancer's join is in its planned state; and
 *  every planned booking is on the owner's own bookings list, held by the right freelancer, on the
 *  right space, at the right time — cancelled exactly when the plan cancelled it. */
export async function verify(ctx) {
  const { api } = ctx;
  const problems = [];
  const spaces = (await api.call(api.act('coworking.list_resources'))).resources ?? [];
  const byName = new Map(spaces.map((s) => [s.name, s]));
  for (const s of SPACES) {
    const r = byName.get(s.name);
    if (!r) { problems.push(`space ${s.name} missing`); continue; }
    if (r.hourly_price_minor !== s.price) problems.push(`${s.name}: price ${r.hourly_price_minor}`);
    if (Object.keys(r.weekly ?? {}).length !== 7) problems.push(`${s.name}: schedule covers ${Object.keys(r.weekly ?? {}).length} days`);
  }
  const joins = (await api.call(api.act('coworking.list_joins'))).joins ?? [];
  for (const f of FREELANCERS) {
    const j = joins.find((x) => x.phone === intl(f.phone));
    if ((j?.status ?? 'missing') !== f.state) problems.push(`${f.phone}: join ${j?.status ?? 'missing'}, planned ${f.state}`);
  }
  const all = (await api.call(api.act('coworking.list_bookings'))).bookings ?? [];
  const planned = plan(ctx);
  for (const p of planned) {
    const space = byName.get(SPACES[p.space].name);
    const hits = all.filter((b) => b.resource_id === space?.id && b.freelancer_phone === intl(p.freelancer)
      && riyadhMinute(b.starts_at) === riyadhMinute(p.starts_at) && b.ends_at - b.starts_at === p.ends_at - p.starts_at);
    if (hits.length < 1) { problems.push(`${p.freelancer} ${p.date}: not on the bookings list`); continue; }
    const want = p.cancel ? 'cancelled' : 'confirmed';
    if (!hits.some((b) => b.status === want)) problems.push(`${p.freelancer} ${p.date}: ${hits.map((b) => b.status)} not ${want}`);
    if (hits.some((b) => b.hourly_price_minor !== SPACES[p.space].price)) problems.push(`${p.freelancer} ${p.date}: price not copied`);
  }
  if (problems.length) throw new Error(`coworking check failed (${problems.length}): ${problems.slice(0, 4).join(' | ')}`);
  return { spaces: spaces.length, joins: joins.reduce((t, j) => ({ ...t, [j.status]: (t[j.status] ?? 0) + 1 }), {}),
    bookings: all.length, confirmed: all.filter((b) => b.status === 'confirmed').length,
    cancelled: all.filter((b) => b.status === 'cancelled').length };
}
