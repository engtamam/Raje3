/**
 * The demo salon's partner — a second real shop, for the two apps whose whole subject is another
 * shop: ولاء الشركاء (a discount on the partner's own subscription) and تبادل منافع (customers sent
 * between the two). Not an app module; the modules that need a partner import this.
 *
 * A REAL SIGNUP, the same browser door the salon came through (lib/demo-api.mjs's
 * signUpFreshDemoShop), under its own session profile ("apps-partner"), so it is reused on every
 * run instead of a new partner each time. It is a perfume shop on the same street — the kind of
 * neighbour a salon would actually trade customers with — with a small catalogue of its own: a
 * mutual-benefit gift has to name one of the partner's real services.
 */
import { API, makeApi, signUpFreshDemoShop } from '../lib/demo-api.mjs';
import { ensureFreshDemoSession, readDemoCredentials, readDemoSession } from '../lib/demo-session.mjs';

const PROFILE = 'apps-partner';
export const PARTNER = { name: 'عطور الياسمين', branch: 'فرع حي الملقا', city: 'الرياض', lat: 24.8121, lng: 46.6318 };
const CATALOGUE = [
  { name: 'تغليف هدية', duration: 15, price: 1500 },
  { name: 'استشارة عطر شخصي', duration: 30, price: 5000 },
  { name: 'عطر مخصص 50 مل', duration: 30, price: 28000 },
];

let cached = null;

/** { api, session, phone, services } for the partner shop — signed up on first use, reused after. */
export async function ensurePartnerShop() {
  if (cached) return cached;
  let session = readDemoSession(PROFILE) ? await ensureFreshDemoSession(API, PROFILE) : null;
  if (!session) session = await signUpFreshDemoShop(PROFILE);
  const { phone } = readDemoCredentials(PROFILE);
  const api = await makeApi(session, PROFILE);
  await api.call(api.act('operations.set_shop_name'), { name: PARTNER.name });
  const branch = (await api.call(api.act('operations.list_branches'))).branches?.[0];
  await api.call(api.act('operations.update_branch'), { id: branch.id, name: PARTNER.branch, city: PARTNER.city,
    lat: PARTNER.lat, lng: PARTNER.lng });
  const have = new Set(((await api.call(api.act('operations.list_services'))).services ?? []).map((s) => s.name));
  for (const s of CATALOGUE) {
    if (!have.has(s.name)) {
      await api.call(api.act('operations.create_service'), { name: s.name, cycle_days: 0, duration_minutes: s.duration, price_minor: s.price });
    }
  }
  const services = (await api.call(api.act('operations.list_services'))).services ?? [];
  cached = { api, session: api.session, phone, branchId: branch.id,
    services: CATALOGUE.map((s) => services.find((x) => x.name === s.name)).filter(Boolean) };
  return cached;
}
