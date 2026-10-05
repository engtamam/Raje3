/**
 * برنامج النقاط — a reward catalogue, and customers who actually spend on it.
 *
 * The points themselves are already there: every visit (walk-in and attended booking) earned them
 * through loyalty's own subscription to `operations.visit.recorded`, at the per-service points the
 * foundation set. What a points screen still lacks then is the other half of the ledger — rewards
 * to spend on, and the spending — so this adds a catalogue covering all three reward kinds, has a
 * spread of customers redeem against it, and gives a couple of them a manual adjustment (a birthday
 * bonus, a correction) the way an owner would.
 *
 * THROUGH THE REAL DOORS ONLY: `POST /api/v1/loyalty/rewards`, `POST /api/v1/loyalty/redeem`,
 * `POST /api/v1/loyalty/adjust`, and the counter's own discount-on-a-visit
 * (`POST /api/v1/field/visits/{id}/points`). A `service` reward redeemed here records a free visit
 * in operations — loyalty's own side effect, kept, because that is what redeeming one does.
 *
 * WHO REDEEMS IS DECIDED FROM LIVE BALANCES, in a fixed order — a customer can only spend what the
 * other modules' visits actually earned. Every spend carries a fixed idempotency key, so a re-run
 * replays it (no second spend) and only tops up customers who could not afford a reward before.
 */
import { addDaysStr, epochAtRiyadh, pool, riyadhToday } from '../lib/demo-api.mjs';

export const app = 'feature.loyalty';

const REWARDS = [
  { name: 'قهوة مجانية', cost: 150, type: 'item' },
  { name: 'خصم 30 ريال', cost: 400, type: 'discount', discount_halalas: 3000 },
  { name: 'قص شعر مجاناً', cost: 300, type: 'service', serviceName: 'قص شعر' },
  { name: 'جلسة تدليك مجانية', cost: 900, type: 'service', serviceName: 'جلسة تدليك استرخاء' },
];
const REDEEMERS = 16;      // how many customers the plan walks, in order, looking for a balance
const ADJUSTED = 3;

async function ensureRewards(api, services) {
  const have = (await api.call(api.act('loyalty.rewards.list'))).rewards ?? [];
  const byName = new Map(have.map((r) => [r.name, r]));
  for (const r of REWARDS) {
    if (byName.has(r.name)) continue;
    const body = { name: r.name, cost: r.cost, type: r.type };
    if (r.type === 'discount') body.discount_halalas = r.discount_halalas;
    if (r.type === 'service') body.service_id = services.find((s) => s.name === r.serviceName)?.id;
    const created = await api.call(api.act('loyalty.rewards.create'), body);
    byName.set(r.name, created);
  }
  return REWARDS.map((r) => byName.get(r.name));
}

async function waitForEarn(api, ref, visitId) {
  for (let i = 0; i < 40; i++) {
    const hist = await api.call(api.act('loyalty.history'), { subject_ref: ref, limit: 10 });
    if ((hist.entries ?? []).some((e) => e.reason === 'earn' && e.source === visitId)) return;
    await new Promise((r) => setTimeout(r, 250));
  }
}

const balanceOf = async (api, ref) => (await api.call(api.act('loyalty.balance'), { subject_ref: ref })).points ?? 0;

export async function seed(ctx) {
  const { api, customers, shop, rng } = ctx;
  const rewards = await ensureRewards(api, shop.services);
  const order = rng.sample(customers, customers.length);
  let redeemed = 0;
  let counterDiscounts = 0;
  const redeemers = new Set();

  // REDEMPTIONS AT THE DESK — each candidate spends on the dearest reward it can afford, at most
  // twice, so balances end up genuinely varied rather than all drained or all untouched.
  //
  // COUNTED FROM THE LEDGER, NOT FROM THIS RUN. An idempotency key is bound to one exact spend —
  // loyalty refuses the same key for a different reward — and which reward is "dearest affordable"
  // changes once a first run has spent. So a customer's next spend is numbered by how many
  // redemptions his real history already holds: a re-run replays nothing, and only adds a spend
  // for someone who could not afford one before.
  for (const c of order.slice(0, REDEEMERS)) {
    const hist = await api.call(api.act('loyalty.history'), { subject_ref: c.subject_ref, limit: 100 });
    const already = (hist.entries ?? []).filter((e) => e.reason === 'redeem').length;
    for (let n = already; n < 2; n++) {
      const bal = await balanceOf(api, c.subject_ref);
      const affordable = rewards.filter((r) => r.cost <= bal && r.type !== 'discount')
        .sort((a, b) => b.cost - a.cost);
      if (!affordable.length) break;
      const reward = n === 0 ? affordable[0] : affordable[affordable.length - 1];
      const out = await api.call(api.act('loyalty.redeem'), {
        subject_ref: c.subject_ref, reward_id: reward.id, idempotency_key: `apps-redeem-${c.phone}-${n}`,
      });
      if (!out.duplicate) redeemed += 1;
      redeemers.add(c.id);
    }
  }

  // THE DISCOUNT REWARD AT THE COUNTER — a real visit, then the visit's own points door, which
  // spends the points and stamps the visit with the discount. Fixed keys: a re-run finds the same
  // visit (its idempotency key) and the visit already carrying its offer, and changes nothing.
  const discount = rewards.find((r) => r.type === 'discount');
  for (const c of order.slice(REDEEMERS, REDEEMERS + 8)) {
    if ((await balanceOf(api, c.subject_ref)) < discount.cost) continue;
    // BACKDATED INTO A WORKING HOUR of the last two weeks — left at "now", every one of these
    // landed in the hour the seed happened to run, and the peak-hours map named that hour busiest.
    const occurredAt = epochAtRiyadh(addDaysStr(riyadhToday(), -rng.int(1, 14)), rng.int(11, 20) * 60);
    const visit = await api.call(api.act('operations.record_visit'), {
      phone: c.phone, service_ids: [rng.pick(shop.services).id], branch_id: shop.branchId,
      idempotency_key: `apps-loyalty-discount-${c.phone}`, occurred_at: occurredAt,
    });
    if (visit.recorded === false) throw new Error(`discount visit for ${c.phone} refused: ${visit.reason}`);
    // THE VISIT'S OWN POINTS LAND FIRST — they arrive over the event bus a moment after the save,
    // and a spend in that same moment holds the customer's balance lock, so the earn is refused and
    // left to loyalty's quarter-hourly recovery. A cashier taps the reward a few seconds after
    // saving anyway; waiting for the earn makes the ledger whole now, not fifteen minutes later.
    await waitForEarn(api, c.subject_ref, visit.visit.id);
    const applied = await api.req('POST', `/api/v1/field/visits/${visit.visit.id}/points`, { reward_id: discount.id });
    if (!applied.applied && !(applied.offer || visit.visit.offer_ref)) {
      throw new Error(`discount for ${c.phone} refused: ${applied.reason}`);
    }
    counterDiscounts += 1;
    redeemers.add(c.id);
  }

  // MANUAL ADJUSTMENTS — what an owner does by hand: a birthday bonus, and one correction down.
  const adjusts = [];
  for (const [i, c] of order.slice(REDEEMERS + 8, REDEEMERS + 8 + ADJUSTED).entries()) {
    const delta = i === ADJUSTED - 1 ? -10 : 75;
    const bal = await balanceOf(api, c.subject_ref);
    if (delta < 0 && bal < -delta) continue;
    const out = await api.call(api.act('loyalty.adjust'), {
      subject_ref: c.subject_ref, delta,
      note: delta > 0 ? 'هدية عيد ميلاد' : 'تصحيح نقاط زيارة مكررة', idempotency_key: `apps-adjust-${c.phone}`,
    });
    if (out.ok === false) throw new Error(`adjust for ${c.phone} refused: ${out.reason ?? JSON.stringify(out)}`);
    adjusts.push(c.id);
  }
  return { rewards: rewards.length, desk_redemptions_new: redeemed, counter_discounts: counterDiscounts,
    customers_redeemed: redeemers.size, adjusted: adjusts.length };
}

/**
 * Every one of the fifty: the balance is exactly the sum of its ledger, and its earn entries are
 * exactly what its visits are worth at the shop's own per-service points (a free visit — a
 * redeemed service reward — earns none). Then the shop-wide report agrees with the ledger summed
 * across customers, and every reward kind has been redeemed at least once.
 */
export async function verify(ctx) {
  const { api, customers } = ctx;
  const settings = await api.call(api.act('loyalty.settings.read'));
  const pointsOf = (sid) => Number(settings.services?.[sid]?.points ?? settings.general?.points ?? 10);
  const problems = [];
  const totals = { earn: 0, redeem: 0, adjust: 0, expire: 0 };
  const touched = new Set();
  await pool(customers, 5, async (c) => {
    const [bal, hist, rec] = await Promise.all([
      balanceOf(api, c.subject_ref),
      api.call(api.act('loyalty.history'), { subject_ref: c.subject_ref, limit: 100 }),
      api.call(api.act('operations.customer'), { id: c.id }),
    ]);
    const entries = hist.entries ?? [];
    const sum = entries.reduce((s, e) => s + e.delta, 0);
    if (entries.length < 100 && sum !== bal) problems.push(`${c.phone}: balance ${bal} ≠ ledger sum ${sum}`);
    // VISIT EARNS ONLY — a gift credited from elsewhere (a freelancer's points reward, a campaign)
    // is also `reason: "earn"`, sourced `award:<key>`, and is no visit's worth.
    const earned = entries.filter((e) => e.reason === 'earn' && !String(e.source).startsWith('award:'))
      .reduce((s, e) => s + e.delta, 0);
    const visits = rec.visits ?? [];
    const worth = visits.filter((v) => !v.free)
      .reduce((s, v) => s + v.service_ids.reduce((a, sid) => a + pointsOf(sid), 0), 0);
    if (visits.length < 20 && earned !== worth) problems.push(`${c.phone}: earned ${earned}, visits are worth ${worth}`);
    for (const e of entries) totals[e.reason] = (totals[e.reason] ?? 0) + e.delta;
    if (entries.some((e) => e.reason !== 'earn')) touched.add(c.id);
  });
  const report = await api.call(api.act('loyalty.report'));
  if (report.granted !== totals.earn) problems.push(`report granted ${report.granted} ≠ ledger earns ${totals.earn}`);
  if (report.consumed !== -totals.redeem) problems.push(`report consumed ${report.consumed} ≠ ledger redeems ${-totals.redeem}`);
  const outstanding = totals.earn + totals.redeem + totals.expire + totals.adjust;
  if (report.outstanding !== outstanding) problems.push(`report outstanding ${report.outstanding} ≠ ${outstanding}`);
  for (const kind of ['item', 'service', 'discount']) {
    if (!(report.by_type?.[kind] > 0)) problems.push(`no ${kind} reward was ever redeemed`);
  }
  if (problems.length) throw new Error(`loyalty check failed (${problems.length}): ${problems.slice(0, 4).join(' | ')}`);
  return { customers_with_spend_or_adjust: touched.size, granted: report.granted, consumed: report.consumed,
    outstanding: report.outstanding, redemptions: report.redemptions, by_type: report.by_type };
}
