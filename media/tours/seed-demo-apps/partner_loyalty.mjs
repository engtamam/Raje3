/**
 * ولاء الشركاء — the salon gives the perfume shop next door a real discount on ITS subscription.
 *
 * Partner loyalty is shop-to-shop, never shop-to-customer: one shop grants another registered shop
 * a percent off that shop's own subscription with the platform, applied by billing at the next
 * renewal. So the seed is the salon granting its partner (the second real shop, partner-shop.mjs)
 * 10% on the partner's «الحجوزات», plus the two other attempts every grant history really holds:
 * a number with no shop behind it, and a second grant to the same partner in the same month — both
 * refused by the service and recorded as such, which is what that history screen exists to show.
 *
 * THE SHOP'S OWN DOOR (`POST /api/v1/staff/coupons/grant`): operations checks the partner holds the
 * app, then creates the coupon at billing and attaches it to the partner's real subscription.
 *
 * RE-RUN SAFE: the history is read first; an attempt already recorded this month is not repeated.
 */
import { ensurePartnerShop } from './partner-shop.mjs';

export const app = 'feature.partner_loyalty';

const GRANT = { percent: 10, general: false, app_keys: ['feature.bookings'] };
const STRANGER = '0570009999';      // a number no shop signed up with

export async function seed(ctx) {
  const { api } = ctx;
  const partner = await ensurePartnerShop();
  const history = (await api.req('GET', '/api/v1/staff/coupons/history?limit=200')).attempts ?? [];
  const month = new Date().toISOString().slice(0, 7);
  const tried = (phone, granted) => history.some((a) => a.beneficiary_phone_last4 === phone.slice(-4)
    && a.month_key === month && (granted === undefined || (a.outcome === 'granted') === granted));
  const made = [];
  const grant = (phone) => api.req('POST', '/api/v1/staff/coupons/grant', { phone, ...GRANT });
  if (!tried(partner.phone, true)) made.push((await grant(partner.phone)).outcome);
  // The repeat is refused (the partner already holds this coupon) — recorded once, not every run.
  if (!tried(partner.phone, false)) made.push((await grant(partner.phone)).outcome);
  if (!tried(STRANGER)) made.push((await grant(STRANGER)).outcome);
  return { attempts_made_now: made, partner_last4: partner.phone.slice(-4) };
}

/** The salon's history holds the grant and both refusals; its stats count exactly one grant this
 *  month; and on the PARTNER's own side, billing carries the coupon on its «الحجوزات» subscription. */
export async function verify(ctx) {
  const { api } = ctx;
  const partner = await ensurePartnerShop();
  const problems = [];
  const history = (await api.req('GET', '/api/v1/staff/coupons/history?limit=200')).attempts ?? [];
  const forPartner = history.filter((a) => a.beneficiary_phone_last4 === partner.phone.slice(-4));
  if (!forPartner.some((a) => a.outcome === 'granted')) problems.push(`no granted attempt for the partner: ${forPartner.map((a) => a.outcome)}`);
  if (!forPartner.some((a) => a.outcome !== 'granted')) problems.push('the repeat grant this month was not refused');
  if (!history.some((a) => a.beneficiary_phone_last4 === STRANGER.slice(-4) && a.outcome !== 'granted')) problems.push('the stranger attempt is missing or was granted');
  const stats = await api.req('GET', '/api/v1/staff/coupons/stats');
  if (stats.grants_this_month !== 1) problems.push(`stats count ${stats.grants_this_month} grants this month`);
  const subs = (await partner.api.req('GET', '/api/v1/billing/subscriptions')).subscriptions ?? [];
  const plans = (await partner.api.req('GET', '/api/v1/billing/plans')).plans ?? [];
  const bookingsPlan = plans.find((p) => Object.keys(p.limits ?? {}).includes('feature.bookings'));
  const sub = subs.find((s) => s.plan_id === bookingsPlan?.id && s.status !== 'canceled');
  if (!sub?.coupon_code) problems.push(`partner's bookings subscription carries no coupon (${sub ? sub.status : 'none'})`);
  if (problems.length) throw new Error(`partner loyalty check failed (${problems.length}): ${problems.join(' | ')}`);
  return { history: history.map((a) => a.outcome), grants_this_month: stats.grants_this_month,
    cap_percent: stats.current_cap_percent, partner_coupon: sub.coupon_code };
}
