/**
 * The shop every app module seeds INTO — its catalogue, its staff, its branch, and its fifty
 * customers. Not an app: every app needs these to already exist, and none of them owns them.
 *
 * ONE KIND OF SHOP THAT PLAUSIBLY USES EVERY APP. A women's salon and beauty centre: services at
 * the chair (visits, bookings), at the customer's home (mobile requests), beauty products ordered
 * over WhatsApp (delivery orders), chairs rented to freelance stylists (coworking), a freelancer
 * following up after a visit (customer service). A shop that would never touch one of the apps
 * would make that app's screens look staged.
 *
 * FIXED PHONES, NOT RANDOM ONES. The fifty customers are 0570001001…0570001050, every run. The
 * customer door (`/api/v1/field/customers/ensure`) is resolve-or-create, so a re-run finds the same
 * fifty people instead of adding fifty strangers — and every module's own "which of the fifty"
 * choice (a seeded PRNG keyed on the module's name) lands on the same people too, which is what
 * makes re-running a module top up its own history rather than scatter a second one.
 */
import { pool } from '../lib/demo-api.mjs';

// What a real salon sells, in halalas — a smaller catalogue than seed-demo-account.mjs's salon on
// purpose: this shop exists to light up every app's screen, not to fill one screen with volume.
export const SERVICES = [
  { name: 'قص شعر', cycle: 30, duration: 30, price: 6000, points: 20 },
  { name: 'صبغة شعر كاملة', cycle: 60, duration: 120, price: 25000, points: 80 },
  { name: 'صبغة جذور', cycle: 30, duration: 60, price: 12000, points: 40 },
  { name: 'بروتين شعر', cycle: 90, duration: 180, price: 45000, points: 120 },
  { name: 'تسريحة سهرة', cycle: 0, duration: 60, price: 15000, points: 50 },
  { name: 'مانيكير', cycle: 21, duration: 45, price: 8000, points: 25 },
  { name: 'باديكير', cycle: 21, duration: 45, price: 9000, points: 25 },
  { name: 'تنظيف بشرة عميق', cycle: 30, duration: 60, price: 18000, points: 55 },
  { name: 'حمام مغربي', cycle: 45, duration: 90, price: 20000, points: 60 },
  { name: 'مكياج سهرة', cycle: 0, duration: 60, price: 20000, points: 60 },
  { name: 'رموش فردي', cycle: 21, duration: 90, price: 18000, points: 55 },
  { name: 'جلسة تدليك استرخاء', cycle: 30, duration: 60, price: 17000, points: 50 },
];

// Login-based staff — PIN operators are off on this product (seed-demo-account.mjs's own
// ensureOperator note). Three, so every per-staff screen (bookings columns, staff performance,
// mobile-request assignment) has more than one lane to compare.
export const STAFF = [
  { name: 'موظفة الاستقبال', phone: '0570009001' },
  { name: 'أخصائية الشعر', phone: '0570009002' },
  { name: 'أخصائية البشرة', phone: '0570009003' },
];
const STAFF_PASSWORD = 'Raje3-Staff-Passphrase!1';

const FIRST = ['سارة', 'نورة', 'ريم', 'لمى', 'دانة', 'جود', 'العنود', 'شهد', 'غلا', 'رغد',
  'أثير', 'روان', 'جواهر', 'منال', 'هيا', 'وجدان', 'مها', 'عبير', 'ندى', 'أمل', 'لجين', 'بشاير',
  'تهاني', 'حصة', 'خلود'];
const LAST = ['العتيبي', 'القحطاني', 'الشهري', 'الغامدي', 'الدوسري', 'الحربي', 'الزهراني',
  'المطيري', 'السبيعي', 'العنزي'];

export const CUSTOMER_COUNT = 50;
export function customerPhone(i) { return `0570001${String(1 + i).padStart(3, '0')}`; }
function customerName(i) {
  // Two independent strides over the two lists — fifty distinct full names, no two alike.
  return `${FIRST[i % FIRST.length]} ${LAST[(i * 3 + Math.floor(i / FIRST.length)) % LAST.length]}`;
}

// WHO THE SHOP IS. The browser signup opens it with the e2e fixture's own shop name (a tyre shop,
// «بنشر الاختبار»), which every screen and every insight then repeats — wrong for a salon. Renamed
// through the owner's own settings, and the main branch given a real Riyadh location and a delivery
// radius (what WhatsApp ordering's coverage reads), the way an owner completing setup would.
export const SHOP = { name: 'صالون لمسة الجمال', branch: 'الفرع الرئيسي — حي الملقا', city: 'الرياض',
  lat: 24.8105, lng: 46.6345, delivery_radius_km: 15 };

export async function ensureShop(api, log) {
  await api.call(api.act('operations.set_shop_name'), { name: SHOP.name });
  const services = await ensureServices(api);
  log(`services: ${services.length}`);
  const branches = await api.call(api.act('operations.list_branches'));
  const branchId = branches.branches?.[0]?.id;
  if (!branchId) throw new Error('the shop has no branch — signup should have seeded its main one');
  await api.call(api.act('operations.update_branch'), { id: branchId, name: SHOP.branch, city: SHOP.city,
    lat: SHOP.lat, lng: SHOP.lng, delivery_radius_km: SHOP.delivery_radius_km });
  const operators = await ensureStaff(api, branchId);
  log(`staff: ${operators.map((o) => o.name).join('، ')} · branch ${branchId}`);
  return { services, branchId, operators };
}

async function ensureServices(api) {
  const listed = await api.call(api.act('operations.list_services'));
  const have = new Map((listed.services ?? []).map((s) => [s.name, s]));
  const create = api.act('operations.create_service');
  const points = api.tryAct('loyalty.settings.service');
  for (const svc of SERVICES) {
    if (have.has(svc.name)) continue;
    const created = await api.call(create, {
      name: svc.name, cycle_days: svc.cycle, duration_minutes: svc.duration, price_minor: svc.price,
    });
    // Points per service are loyalty's own setting, written through loyalty's own action the way
    // Services.tsx's addService does — a refusal is printed, never swallowed, so a catalogue that
    // silently earns nothing cannot pass for a seeded one.
    if (points && created?.id) {
      await api.call(points, { service_id: created.id, points: svc.points })
        .catch((e) => console.log(`  ⚠ points for "${svc.name}" refused: ${e.message}`));
    }
  }
  const after = await api.call(api.act('operations.list_services'));
  const byName = new Map((after.services ?? []).map((s) => [s.name, s]));
  return SERVICES.map((s) => ({ ...s, ...byName.get(s.name) })).filter((s) => s.id);
}

async function ensureStaff(api, branchId) {
  const listed = await api.call(api.act('operations.list_operators'));
  const have = new Map((listed.operators ?? []).map((o) => [o.name, o]));
  for (const member of STAFF) {
    if (have.has(member.name)) continue;
    const hired = await api.call(api.act('operations.hire_member'), {
      name: member.name, phone: member.phone, password: STAFF_PASSWORD, role: 'operator', branch_id: branchId,
    });
    if (hired?.id) have.set(member.name, hired);
  }
  const after = await api.call(api.act('operations.list_operators'));
  const byName = new Map((after.operators ?? []).map((o) => [o.name, o]));
  return STAFF.map((s) => byName.get(s.name)).filter(Boolean);
}

/** The fifty, resolved through the same door the booking dialog and «جهات الاتصال» use. Each
 *  comes back with its real id and `subject_ref` (the pseudonym loyalty/reminders know it by). */
export async function ensureCustomers(api) {
  const ensure = api.act('operations.ensure_customer');
  // THREE AT A TIME, NOT EIGHT. Each registration also writes the customer's search document, and
  // platform search-service's built-in index updates one shared counter row per write under a
  // compare-and-set that gives up under contention ("CAS exhausted", seen live at eight wide) —
  // leaving that customer unfindable by the keypad, with no later visit seam to repair it yet.
  const rows = await pool(Array.from({ length: CUSTOMER_COUNT }, (_, i) => i), 3, async (i) => {
    const out = await api.call(ensure, { phone: customerPhone(i), name: customerName(i) });
    const c = out.customer ?? out;
    if (!c?.id) throw new Error(`customer ${customerPhone(i)} did not resolve: ${JSON.stringify(out).slice(0, 200)}`);
    return { index: i, id: c.id, phone: customerPhone(i), name: customerName(i), subject_ref: c.subject_ref ?? '' };
  });
  const failed = rows.filter((r) => r?.error);
  if (failed.length) throw new Error(`${failed.length} customers failed to resolve: ${failed[0].error}`);
  return rows;
}
