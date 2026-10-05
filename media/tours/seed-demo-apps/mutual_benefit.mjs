/**
 * تبادل منافع — the salon and the perfume shop next door send each other customers.
 *
 * Two real agreements, both directions, each proposed by one shop and accepted by the other's own
 * session: a salon customer whose visit comes to 200 SAR or more earns 15% off at the perfume shop;
 * a perfume customer who buys a custom 50 ml perfume earns a free manicure at the salon. Then the
 * customers move: grants are earned by real visits at the referring shop, and some of them are
 * redeemed by real visits at the other shop, through that shop's own offer door — so the salon's
 * KPI card shows real numbers on BOTH sides (customers it sent, customers it received).
 *
 * EVERY STEP IS A REAL DOOR: propose/accept (`/api/v1/staff/mutual-benefit/agreements`), visits
 * (`/api/v1/field/visits` — the grant is created by operations' own `on_visit_recorded` hook), and
 * the redemption (`/api/v1/field/visits/{id}/offer`, ranked and finalised by operations'
 * entitlement gateway). The partner is a second real signed-up shop (partner-shop.mjs).
 *
 * RE-RUN SAFE: agreements are matched before proposing, every visit carries a fixed idempotency
 * key, and an offer is only applied to a visit that does not carry one yet.
 */
import { addDaysStr, epochAtRiyadh, pool, riyadhToday } from '../lib/demo-api.mjs';
import { readDemoCredentials } from '../lib/demo-session.mjs';
import { ensurePartnerShop } from './partner-shop.mjs';

export const app = 'feature.mutual_benefit';

const SALON_TRIGGER = 'صبغة شعر كاملة';     // 250 SAR — clears the 200 SAR condition
const SALON_GIFT = 'مانيكير';
const PERFUME_TRIGGER = 'عطر مخصص 50 مل';
const PERFUME_REDEEM = 'تغليف هدية';

/** Which customers trigger and redeem, in each direction — the same plan for seed() and verify(). */
export function plan({ customers, rng }) {
  const people = rng.sample(customers, 14);
  return {
    toPerfume: { triggers: people.slice(0, 8), redeemers: people.slice(0, 5) },
    toSalon: { triggers: people.slice(8, 14), redeemers: people.slice(8, 11) },
  };
}

const LIST = '/api/v1/staff/mutual-benefit/agreements';

async function ensureAgreement(fromApi, toApi, toPhone, terms, key) {
  const live = ((await fromApi.req('GET', LIST)).agreements ?? [])
    .find((a) => a.idempotency_key === key && ['proposed', 'active'].includes(a.status));
  let agreement = live;
  if (!agreement) {
    const out = await fromApi.req('POST', LIST, { shop_b_phone: toPhone, idempotency_key: key, ...terms });
    agreement = out.agreement ?? out;
  }
  if (agreement.status === 'proposed') {
    const out = await toApi.req('POST', `${LIST}/${agreement.id}/accept`);
    agreement = out.agreement ?? out;
  }
  if (agreement.status !== 'active') throw new Error(`agreement ${key} is ${agreement.status}`);
  return agreement;
}

async function visit(api, branchId, phone, serviceId, key, occurredAt) {
  const out = await api.call(api.act('operations.record_visit'), {
    phone, service_ids: [serviceId], branch_id: branchId, idempotency_key: key, occurred_at: occurredAt,
  });
  if (out.recorded === false) throw new Error(`${key}: ${out.reason}`);
  return out;
}

async function redeemAt(api, branchId, phone, serviceId, key, occurredAt) {
  const v = await visit(api, branchId, phone, serviceId, key, occurredAt);
  if (v.visit.offer_ref) return v.visit;                       // already redeemed on a prior run
  const ensured = await api.call(api.act('operations.ensure_customer'), { phone });
  const subject = (ensured.customer ?? ensured).subject_ref;
  const out = await api.req('POST', `/api/v1/field/visits/${v.visit.id}/offer`, { subject_ref: subject });
  if (out.applied === false) throw new Error(`${key}: offer not applied — ${out.reason ?? JSON.stringify(out).slice(0, 160)}`);
  return v.visit;
}

export async function seed(ctx) {
  const { api, shop, rng } = ctx;
  const partner = await ensurePartnerShop();
  const salonPhone = readDemoCredentials('apps').phone;   // the salon owner's own signup number
  const perfumeTrigger = partner.services.find((s) => s.name === PERFUME_TRIGGER);
  const perfumeRedeem = partner.services.find((s) => s.name === PERFUME_REDEEM);
  const salonTrigger = shop.services.find((s) => s.name === SALON_TRIGGER);
  const salonGift = shop.services.find((s) => s.name === SALON_GIFT);

  await ensureAgreement(api, partner.api, partner.phone, {
    condition_type: 'min_total_minor', condition_value: '20000', grant_validity_days: 30,
    agreement_duration_days: 180, per_period_cap: 0, grant_type: 'discount',
    discount_kind: 'percent', discount_amount: 15, discount_scope: 'blanket',
  }, 'apps-mb-salon-to-perfume');
  await ensureAgreement(partner.api, api, salonPhone, {
    condition_type: 'service_id', condition_value: perfumeTrigger.id, grant_validity_days: 30,
    agreement_duration_days: 180, per_period_cap: 0, grant_type: 'gift', gift_service_id: salonGift.id,
  }, 'apps-mb-perfume-to-salon');

  const p = plan(ctx);
  const today = riyadhToday();
  // Recent days, working hours — grants last 30 days, so every one of these is still live.
  const when = () => epochAtRiyadh(addDaysStr(today, -rng.int(1, 10)), rng.int(11, 20) * 60);
  await pool(p.toPerfume.triggers, 3, (c) => visit(api, shop.branchId, c.phone, salonTrigger.id, `apps-mb-trigger-${c.phone}`, when()));
  await pool(p.toSalon.triggers, 3, (c) => visit(partner.api, partner.branchId, c.phone, perfumeTrigger.id, `apps-mb-trigger-${c.phone}`, when()));
  // Redemptions after the triggers, a day or so later — the customer walked next door.
  await pool(p.toPerfume.redeemers, 2, (c) => redeemAt(partner.api, partner.branchId, c.phone, perfumeRedeem.id, `apps-mb-redeem-${c.phone}`, Math.floor(Date.now() / 1000) - 3600));
  await pool(p.toSalon.redeemers, 2, (c) => redeemAt(api, shop.branchId, c.phone, salonGift.id, `apps-mb-redeem-${c.phone}`, Math.floor(Date.now() / 1000) - 3600));
  return { agreements: 2, grants_sent: p.toPerfume.triggers.length, redeemed_at_partner: p.toPerfume.redeemers.length,
    grants_received: p.toSalon.triggers.length, redeemed_here: p.toSalon.redeemers.length };
}

/** Both agreements active from the salon's own list; the salon's KPIs count exactly the grants
 *  each direction's planned visits earned and the redemptions planned; and every redeemed visit
 *  carries the offer the grant gave it. */
export async function verify(ctx) {
  const { api } = ctx;
  const p = plan(ctx);
  const problems = [];
  const agreements = (await api.req('GET', LIST)).agreements ?? [];
  for (const key of ['apps-mb-salon-to-perfume', 'apps-mb-perfume-to-salon']) {
    if (!agreements.some((a) => a.idempotency_key === key && a.status === 'active')) problems.push(`${key} not active`);
  }
  const k = await api.call(api.act('operations.mutual_benefit_kpis'));
  const sent = k.as_referrer ?? {};
  const got = k.as_beneficiary ?? {};
  if (sent.referrals_sent !== p.toPerfume.triggers.length) problems.push(`sent ${sent.referrals_sent}, planned ${p.toPerfume.triggers.length}`);
  if (sent.redeemed !== p.toPerfume.redeemers.length) problems.push(`redeemed at partner ${sent.redeemed}, planned ${p.toPerfume.redeemers.length}`);
  if (got.referrals_sent !== p.toSalon.triggers.length) problems.push(`received ${got.referrals_sent}, planned ${p.toSalon.triggers.length}`);
  if (got.redeemed !== p.toSalon.redeemers.length) problems.push(`redeemed here ${got.redeemed}, planned ${p.toSalon.redeemers.length}`);
  for (const c of p.toSalon.redeemers) {
    const rec = await api.call(api.act('operations.customer'), { id: c.id });
    if (!(rec.visits ?? []).some((v) => v.offer_ref && v.services?.includes(SALON_GIFT))) problems.push(`${c.phone}: gift visit carries no offer`);
  }
  if (problems.length) throw new Error(`mutual benefit check failed (${problems.length}): ${problems.join(' | ')}`);
  return { agreements_active: 2, as_referrer: { sent: sent.referrals_sent, redeemed: sent.redeemed, rate: sent.redemption_rate },
    as_beneficiary: { received: got.referrals_sent, redeemed: got.redeemed, rate: got.redemption_rate } };
}
