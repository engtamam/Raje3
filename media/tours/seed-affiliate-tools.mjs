/**
 * Builds the ONE affiliate account «أدواتي» needs and every other affiliate tour deliberately does
 * not: a manager with real templates, real citations, a saved Places API key, and a real referred
 * shop to open a ticket against. affiliate-earnings-1-overview.mjs's own header explains why ITS
 * account (0549900110) must stay at zero forever — this is the opposite case: AffiliateTools.tsx
 * has nothing honest left to show a viewer on an empty account (a template library with zero
 * templates, a ticket screen with zero shops, teaches nothing about the screen itself), so this is
 * its own dedicated manager, seeded exactly like seed-affiliate-team.mjs's own manager: apply()
 * then the same platform-owner admin's approve() — never a direct database write.
 *
 * WHY A SEPARATE SHOP SIGNUP TOO, NOT A REFERRAL ONTO AN EXISTING DEMO SHOP. `referredShops()`
 * only ever lists shops whose OWN signup carried this manager's `affiliate_ref` — the tie is
 * stamped once, at signup, and nothing later can retrofit it onto seed-demo-account.mjs's own hero
 * shop without changing which marketer that account belongs to. A second, small shop — real, but
 * otherwise unused — is the only honest way to give «تذاكر المحلات» a real row to open.
 *
 * IDEMPOTENT ON RE-RUN, same discipline as every seeder in this family: signing in first and only
 * falling through to apply()/approve()/create when the fixed phone doesn't already work, and
 * counting existing templates/citations/shops before adding more rather than piling up duplicates
 * run after run.
 *
 * Usage:
 *   node media/tours/seed-affiliate-tools.mjs
 *   CONSOLE=http://localhost:5174 node media/tours/seed-affiliate-tools.mjs
 */
import { writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const SESSION_FILE = join(HERE, '.demo-affiliate-tools-session.json');

const rawBase = process.env.CONSOLE ?? 'http://localhost:5174';
const withSlash = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;
const API = withSlash.replace(/\/app\/?$/, '').replace(/\/$/, '');

// SAME PLATFORM-OWNER ACCOUNT EVERY OTHER SEEDER IN THIS FAMILY USES — seeded once by
// deploy/seed/seed-admin.sh, not by this file. Reused rather than re-described here.
const ADMIN_PHONE = '0500000902';
const ADMIN_PASSWORD = 'HomeTour2026Demo!';
const PLATFORM_TENANT = '_platform';

export const MANAGER = { phone: '0501234567', password: 'ToolsTour2026Demo!', name: 'مدير المسوّقين التجريبي' };
export const REFERRED_SHOP = { phone: '0509876543', password: 'ReferredShop2026!', shopName: 'صالون تجريبي — أدواتي' };
// A REAL-LOOKING KEY, NEVER A REAL ONE — the endpoint only ever stores it encrypted
// (SECRETS_KEK) and never validates the format against Google at save time (checked in
// api/v1/affiliate_self.py before writing this). A lead-search job started against it will run and
// genuinely fail from Google's own 4xx, which is the honest thing for a demo key to show, not a
// staged success.
export const PLACES_DEMO_KEY = 'AIzaSyDEMO0000000000000000000000000';

async function req(path, method, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API}${path}`, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  let parsed = null;
  try { parsed = text ? JSON.parse(text) : null; } catch { /* non-JSON error body */ }
  if (!res.ok || parsed?.ok === false) {
    const message = parsed?.message ?? parsed?.detail ?? `${method} ${path} → ${res.status}`;
    throw new Error(`${message}${parsed?.reason ? ` (${parsed.reason})` : ''}`);
  }
  return parsed;
}

async function adminSignIn() {
  const out = await req('/api/v1/auth/tenant', 'POST',
    { tenant: PLATFORM_TENANT, username: ADMIN_PHONE, password: ADMIN_PASSWORD });
  if (!out?.access_token) throw new Error('admin sign-in answered with no access_token');
  return out.access_token;
}

async function affiliateSignIn(phone, password) {
  return req('/api/v1/affiliates/signin', 'POST', { phone, password });
}

async function ensureAffiliate(adminToken, { phone, password, name }) {
  try {
    const session = await affiliateSignIn(phone, password);
    console.log(`  · ${name} — already active, signed in`);
    return session;
  } catch { /* falls through to apply()+approve() below */ }

  let applicationId;
  try {
    const applied = await req('/api/v1/affiliates/apply', 'POST', { phone, name, password, agreed: true });
    applicationId = applied.application_id;
  } catch (e) {
    if (!/قيد المراجعة|already_pending/.test(e.message)) throw e;
    const pending = await req('/api/v1/admin/affiliates', 'GET', undefined, adminToken);
    applicationId = pending.applications?.find((a) => a.name === name)?.id;
    if (!applicationId) throw new Error(`"${name}" is pending but not found in the admin queue`);
  }
  await req(`/api/v1/admin/affiliates/${applicationId}/approve`, 'POST', undefined, adminToken);
  console.log(`  ✔ ${name} — applied and approved`);
  return affiliateSignIn(phone, password);
}

async function ensureReferredShop(managerId) {
  try {
    await req('/api/v1/signup', 'POST', {
      phone: REFERRED_SHOP.phone, password: REFERRED_SHOP.password,
      shop_name: REFERRED_SHOP.shopName, affiliate_ref: managerId,
    });
    console.log(`  ✔ ${REFERRED_SHOP.shopName} — signed up, referred by this manager`);
  } catch (e) {
    // ALREADY SIGNED UP FROM A PRIOR RUN — the phone is fixed on purpose, same reasoning as
    // every other fixed phone in this file. A duplicate-phone refusal here just means the shop
    // (and its referral stamp) already exists; nothing left to do.
    if (!/مسجّل|already|registered/i.test(e.message)) throw e;
    console.log(`  · ${REFERRED_SHOP.shopName} — already signed up`);
  }
}

async function main() {
  console.log(`▸ signing in as the platform admin (${ADMIN_PHONE})`);
  const adminToken = await adminSignIn();

  console.log(`▸ ${MANAGER.name}`);
  const session = await ensureAffiliate(adminToken, MANAGER);
  const token = session.access_token;
  writeFileSync(SESSION_FILE, JSON.stringify({
    access_token: session.access_token, refresh_token: session.refresh_token, tenant: session.tenant,
  }, null, 2), 'utf8');

  const me = await req('/api/v1/affiliates/me', 'GET', undefined, token);
  console.log(`  affiliate id (his own referral code): ${me.id}`);

  console.log('▸ message templates');
  const stages = await req('/api/v1/affiliates/me/outreach-stages', 'GET', undefined, token);
  const stageCode = stages.stages?.[0]?.code || 'gatekeeper';
  const existingTemplates = await req(`/api/v1/affiliates/me/templates?stage_code=${stageCode}`, 'GET', undefined, token);
  if (!existingTemplates.templates?.length) {
    await req('/api/v1/affiliates/me/templates', 'POST', {
      stage_code: stageCode, title: 'أول تواصل — سلام وتعريف', kind: 'ترحيب',
      body: 'السلام عليكم، معك [اسمك] من راجِع — نساعد المحلات ترجّع عملائها بذكاء عبر واتساب ونقاط ولاء. عندك دقيقتين أشرح لك الفكرة؟',
    }, token);
    await req('/api/v1/affiliates/me/templates', 'POST', {
      stage_code: stageCode, title: 'متابعة بعد يومين', kind: 'متابعة',
      body: 'هلا، تذكرت أرسل لك تفاصيل راجِع قبل يومين — حابب أعطيك نبذة سريعة أو أرسل لك فيديو دقيقتين؟',
    }, token);
    console.log('  ✔ 2 templates created');
  } else {
    console.log(`  · ${existingTemplates.templates.length} template(s) already there`);
  }

  console.log('▸ stat citations');
  const existingCitations = await req('/api/v1/affiliates/me/stat-citations', 'GET', undefined, token);
  if (!existingCitations.citations?.length) {
    await req('/api/v1/affiliates/me/stat-citations', 'POST', {
      title: 'العميل العائد أرخص من عميل جديد',
      body: 'استقطاب عميل جديد يكلّف الصالونات والعيادات أضعاف تكلفة إرجاع عميل قديم — راجِع مبني على هذا بالضبط.',
      source_label: 'تحليل داخلي — راجِع', source_url: '',
    }, token);
    await req('/api/v1/affiliates/me/stat-citations', 'POST', {
      title: 'رسالة تذكير واحدة كافية غالباً',
      body: 'أغلب العملاء المنقطعين يحتاجون رسالة تذكير واحدة بوقتها الصحيح ليعودوا لا حملة كاملة.',
      source_label: 'بيانات استخدام راجِع', source_url: '',
    }, token);
    console.log('  ✔ 2 citations created');
  } else {
    console.log(`  · ${existingCitations.citations.length} citation(s) already there`);
  }

  console.log('▸ Places API key');
  const keyInfo = await req('/api/v1/affiliates/me/places-api-key', 'GET', undefined, token);
  if (!keyInfo.set) {
    await req('/api/v1/affiliates/me/places-api-key', 'PUT', { api_key: PLACES_DEMO_KEY }, token);
    console.log('  ✔ demo key saved');
  } else {
    console.log(`  · key already set (${keyInfo.hint})`);
  }

  console.log('▸ a referred shop for «تذاكر المحلات»');
  const shops = await req('/api/v1/affiliates/me/referred-shops', 'GET', undefined, token);
  if (!shops.shops?.length) {
    await ensureReferredShop(me.id);
  } else {
    console.log(`  · ${shops.shops.length} referred shop(s) already there (${shops.shops[0].shop_name})`);
  }

  console.log('✔ affiliate tools demo account ready — manager phone/password:');
  console.log(`    ${MANAGER.phone} / ${MANAGER.password}`);
}

main().catch((e) => { console.error(e.message); process.exit(1); });
