/**
 * Turns سارة المسوّقة (seed-demo-affiliate.mjs's own account, 0549900110) from the near-empty
 * demo she was left as into a genuinely busy, populated marketer — real referred shops, a real
 * team under her with varying sizes, all through the exact HTTP doors seed-demo-affiliate.mjs and
 * seed-affiliate-team.mjs already established: apply() → admin approve() for every account,
 * POST /api/v1/signup with her (or a team member's) `affiliate_ref` for every referred shop.
 * Never a direct database write — same discipline this whole seed-* family already follows.
 *
 * ONE THING THIS SCRIPT DELIBERATELY DOES NOT SEED, BECAUSE THIS DEV DEPLOYMENT CANNOT HONESTLY
 * PRODUCE IT, checked directly rather than assumed:
 *
 *   COMMISSIONS. CommissionEngine.sync() (core/commission.py) only ever creates a row by reading
 *   billing-service's own paid-invoice history — `BILLING_SERVICE_URL`. That setting is blank in
 *   services/affiliate-service/.env (and in operations/loyalty/bookings/campaigns' own configs
 *   too — checked all of them), and there is no admin route anywhere in this service that grants
 *   a commission by hand. A referred shop can exist for real here; a PAID first invoice for it
 *   cannot, because no billing-service is reachable from this cluster at all. أرباحي's ledger
 *   stays honestly empty for the same reason affiliate-earnings-1-overview.mjs's own header
 *   already documented — this script does not change that fact, only the referred-shops/team/
 *   ticket picture around it.
 *
 *   TICKETS: ATTEMPTED, CONFIRMED BLOCKED, LEFT UNSEEDED — ticket-service itself IS reachable
 *   (`GET /me/shops/{tenant}/tickets` answers `{"tickets":[]}`, a real read grant exists), but
 *   every `POST .../tickets` against a shop this script referred came back
 *   `المحل لم يمنحك صلاحية فتح تذاكر، فقط المشاهدة` (`write_not_granted`). operations'
 *   `core/signup.py::open_shop` only requests a WRITE share (`permissions: ["read","write"]`) in
 *   an `elif self._tickets:` branch nested INSIDE the referral-stamp success branch — so a WRITE
 *   grant depends on both the stamp call and that inner ticket-service call landing cleanly at
 *   the exact moment of signup. Read access exists regardless; write does not, for every shop this
 *   script created. Opening a ticket without a marketer's own write consent would be exactly the
 *   kind of shortcut this whole seed-* family refuses, so none is seeded — a real gap in this dev
 *   deployment, not a missing script.
 *
 * TIMESTAMPS ARE REAL WALL-CLOCK TIME, NOT BACKDATED. Every write below goes through a real API
 * call at the moment this script makes it — there is no `occurred_at`-style parameter on
 * `/api/v1/signup` the way loyalty's `/api/v1/field/visits` has one (seed-demo-account.mjs's own
 * 180-day spread relies on exactly that parameter existing; signup has no equivalent). Running
 * this script's batches with real pauses between them, rather than firing all requests at once,
 * is the most honest spread available without a database write — real minutes apart, not the
 * weeks a hand-edited `created_at` could fake.
 *
 * IDEMPOTENT ON RE-RUN for the team roster (fixed phones, same ensureAffiliate pattern as every
 * other seeder in this family). The referred-shop batch is NOT idempotent by phone reuse — each
 * run mints NEW shops with fresh random phone numbers, so re-running this script grows the
 * roster rather than replaying it. Pass SKIP_SHOPS=1 to add only the team, not another batch of
 * shops, on a re-run.
 *
 * Usage:
 *   node media/tours/seed-affiliate-rich-demo.mjs
 *   SHOP_COUNT=600 CONSOLE=http://localhost:5174 node media/tours/seed-affiliate-rich-demo.mjs
 */
import { setTimeout as sleep } from 'node:timers/promises';

const rawBase = process.env.CONSOLE ?? 'http://localhost:5174';
const withSlash = rawBase.endsWith('/') ? rawBase : `${rawBase}/`;
const API = withSlash.replace(/\/app\/?$/, '').replace(/\/$/, '');

const ADMIN_PHONE = '0500000902';
const ADMIN_PASSWORD = 'HomeTour2026Demo!';
const PLATFORM_TENANT = '_platform';

const SARA = { phone: '0549900110', password: 'Raje3-Affiliate-Tour!1', name: 'مسوّق العرض' };

// A REAL TEAM, VARYING SIZE ON PURPOSE — Team.tsx (فريقي) sums across every member; a roster
// where every row performs identically teaches nothing about what "some active, some less" looks
// like on the real screen. shopCount below is each member's OWN referred-shop target, seeded the
// exact same way سارة's own are (a real /api/v1/signup per shop, her team member's own id as
// affiliate_ref).
const TEAM = [
  { phone: '0549900201', password: 'Sara2026$Team1!', name: 'منى — مسوّقة نشطة', shopCount: 42 },
  { phone: '0549900202', password: 'Sara2026$Team2!', name: 'فيصل — مسوّق نشط', shopCount: 27 },
  { phone: '0549900203', password: 'Sara2026$Team3!', name: 'عبدالله — مسوّق متوسط', shopCount: 9 },
  { phone: '0549900204', password: 'Sara2026$Team4!', name: 'لمى — مسوّقة جديدة', shopCount: 1 },
];

const SHOP_COUNT = Number(process.env.SHOP_COUNT || 600);
const SKIP_SHOPS = process.env.SKIP_SHOPS === '1';
// SEQUENTIAL, NOT PARALLEL — a real /api/v1/signup call provisions a whole new tenant (schema,
// trial, default rows); firing several at once against this dev deployment was tried and made
// EVERY call in the batch fail with a generic refusal, not just slow one down. One at a time is
// slower but actually works.
const CONCURRENCY = 1;
const BATCH_PAUSE_MS = 800; // gentle — this dev cluster's identity-service was found crash-looping
                            // under sustained load partway through this script's own first run

const SHOP_KINDS = ['صالون', 'عيادة تجميل', 'مركز عناية', 'استوديو تجميل', 'مقص وموس', 'بيوتي سنتر'];
const CITY_TAGS = ['الرياض', 'جدة', 'الدمام', 'الخبر', 'مكة', 'المدينة', 'أبها', 'تبوك', 'بريدة', 'حائل'];

function randomShopName(i) {
  const kind = SHOP_KINDS[i % SHOP_KINDS.length];
  const city = CITY_TAGS[Math.floor(i / SHOP_KINDS.length) % CITY_TAGS.length];
  return `${kind} ${city} ${i + 1}`;
}

function randomPhone(seed) {
  // 059xxxxxxx range, offset from the fixed team/admin numbers above so nothing collides.
  const n = 20000000 + seed;
  return `059${String(n).slice(-7)}`;
}

async function reqOnce(path, method, body, token) {
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
    const err = new Error(`${message}${parsed?.reason ? ` (${parsed.reason})` : ''}`);
    err.status = res.status;
    throw err;
  }
  return parsed;
}

// A DEV-CLUSTER-ONLY RETRY, NOT A PRODUCT CONCERN — provisioning a whole tenant per shop signup
// is heavy enough that a long sequential run occasionally hits a transient 5xx/timeout on this
// single-instance dev deployment under sustained load. Retried with backoff rather than aborting
// the whole batch on one hiccup; a real 4xx refusal (bad password, duplicate phone) is never
// retried — only load-shaped failures are.
async function req(path, method, body, token, attempts = 4) {
  let lastErr;
  for (let i = 0; i < attempts; i++) {
    try {
      return await reqOnce(path, method, body, token);
    } catch (e) {
      lastErr = e;
      const transient = !e.status || e.status >= 500;
      if (!transient || i === attempts - 1) throw e;
      await sleep(1500 * (i + 1));
    }
  }
  throw lastErr;
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

async function ensureAffiliate(adminToken, { phone, password, name, referralCode = '' }) {
  try {
    const session = await affiliateSignIn(phone, password);
    console.log(`  · ${name} — already active, signed in`);
    return session;
  } catch { /* falls through to apply()+approve() below */ }

  let applicationId;
  try {
    const applied = await req('/api/v1/affiliates/apply', 'POST', {
      phone, name, password, referral_code: referralCode, agreed: true,
    });
    applicationId = applied.application_id;
  } catch (e) {
    if (!/قيد المراجعة|already_pending/.test(e.message)) throw e;
    const pending = await req('/api/v1/admin/affiliates', 'GET', undefined, adminToken);
    const rows = pending.applications || pending.rows || [];
    applicationId = rows.find((a) => a.name === name)?.id;
    if (!applicationId) throw new Error(`"${name}" is pending but not found in the admin queue`);
  }
  await req(`/api/v1/admin/affiliates/${applicationId}/approve`, 'POST', undefined, adminToken);
  console.log(`  ✔ ${name} — applied and approved`);
  return affiliateSignIn(phone, password);
}

/** One real shop signup, referred by `affiliateId`. `seed` picks its phone/name deterministically
 *  so re-runs are traceable, never colliding with the fixed team/admin numbers above. */
async function seedReferredShop(affiliateId, seed) {
  const phone = randomPhone(seed);
  const shopName = randomShopName(seed);
  try {
    await req('/api/v1/signup', 'POST', {
      phone, password: `Demo${seed}Pass!1`, shop_name: shopName, affiliate_ref: affiliateId,
    });
    return 'created';
  } catch (e) {
    if (/مسجّل|already|registered/i.test(e.message)) return 'exists';
    throw e;
  }
}

/** Seeds shops until `affiliateId` has at least `target` referred shops — resumable across
 *  crashed/restarted runs (checks the real count first, rather than always minting `target` more
 *  new ones), with a RANDOM per-run phone-seed base so a resumed run never collides with phones a
 *  previous, unfinished run already claimed. */
async function seedShopsUpTo(affiliateId, target, label, token) {
  const before = await req('/api/v1/affiliates/me/referred-shops', 'GET', undefined, token).catch(() => ({ shops: [] }));
  const existing = (before.shops || []).length;
  if (existing >= target) {
    console.log(`  · ${label}: already has ${existing}/${target} referred shops`);
    return 0;
  }
  const toCreate = target - existing;
  console.log(`  ▸ ${label}: ${existing}/${target} so far, creating ${toCreate} more`);
  const base = 1000 + Math.floor(Math.random() * 900000);
  let created = 0;
  for (let i = 0; i < toCreate; i++) {
    try {
      const result = await seedReferredShop(affiliateId, base + i);
      if (result === 'created') created++;
    } catch (e) {
      console.log(`    ⚠ shop seed failed: ${e.message}`);
    }
    if ((existing + i + 1) % 25 === 0) console.log(`  ▸ ${label}: ${existing + i + 1}/${target}`);
    await sleep(BATCH_PAUSE_MS);
  }
  return created;
}

const TICKET_TOPICS = [
  { type: 'استفسار عن الحساب', subject: 'صعوبة بربط واتساب', body: 'صاحب المحل يقول رقم الواتساب ما يقبل الربط من أول محاولة — يحتاج مساعدة.' },
  { type: 'استفسار عن الحساب', subject: 'سؤال عن باقة الاشتراك', body: 'يسأل عن الفرق بين الباقات قبل ما تنتهي فترته التجريبية.' },
  { type: 'استفسار عن الحساب', subject: 'تعديل بيانات المحل', body: 'يبي يغيّر اسم المحل ورقم التواصل الظاهر للعملاء.' },
  { type: 'استفسار عن الحساب', subject: 'استفسار عن نقاط الولاء', body: 'ما فاهم كيف يحسب نظام النقاط، يبي شرح مبسّط.' },
];

/** A handful of real tickets on a few of سارة's own referred shops — real POST calls against
 *  `/me/shops/{tenant}/tickets`, some then replied to for real too. See this file's own header
 *  on why status stays wherever `open()` starts it (no transition capability is exposed here). */
async function seedTickets(token, count = 4) {
  const shopsResp = await req('/api/v1/affiliates/me/referred-shops', 'GET', undefined, token).catch(() => ({ shops: [] }));
  const shops = shopsResp.shops || [];
  if (!shops.length) {
    console.log('  · no referred shops yet — skipping tickets this run');
    return 0;
  }
  let opened = 0;
  for (let i = 0; i < Math.min(count, shops.length); i++) {
    const shop = shops[i];
    const topic = TICKET_TOPICS[i % TICKET_TOPICS.length];
    try {
      const existing = await req(`/api/v1/affiliates/me/shops/${shop.tenant}/tickets`, 'GET', undefined, token);
      if ((existing.tickets || []).length > 0) {
        console.log(`  · ${shop.shop_name} already has a ticket — skipping`);
        continue;
      }
      const created = await req(`/api/v1/affiliates/me/shops/${shop.tenant}/tickets`, 'POST', topic, token);
      opened++;
      // Reply to every other one, so the seeded set shows a raised-but-unanswered ticket next to
      // one the marketer already engaged with — real variety within what this door allows.
      if (i % 2 === 1 && created?.id) {
        await req(`/api/v1/affiliates/me/shops/${shop.tenant}/tickets/${created.id}/replies`, 'POST',
          { body: 'تابعت مع صاحب المحل — بنحل الموضوع خلال يوم.' }, token);
      }
      console.log(`  ✔ ticket opened on ${shop.shop_name}${i % 2 === 1 ? ' (and replied to)' : ''}`);
    } catch (e) {
      console.log(`    ⚠ ticket seed failed for ${shop.shop_name}: ${e.message}`);
    }
    await sleep(500);
  }
  return opened;
}

async function main() {
  console.log(`▸ signing in as the platform admin (${ADMIN_PHONE})`);
  const adminToken = await adminSignIn();

  console.log(`▸ ${SARA.name} (سارة المسوّقة)`);
  const saraSession = await ensureAffiliate(adminToken, SARA);
  const saraMe = await req('/api/v1/affiliates/me', 'GET', undefined, saraSession.access_token);
  console.log(`  id / referral code: ${saraMe.id}`);

  console.log(`▸ ${TEAM.length} team members under her, varying performance`);
  const teamSessions = [];
  for (const member of TEAM) {
    const session = await ensureAffiliate(adminToken, { ...member, referralCode: saraMe.id });
    teamSessions.push({ ...member, session });
  }

  if (!SKIP_SHOPS) {
    console.log(`▸ seeding up to ${SHOP_COUNT} real referred shops directly under سارة (resumable — this takes a while)`);
    const created = await seedShopsUpTo(saraMe.id, SHOP_COUNT, 'سارة', saraSession.access_token);
    console.log(`  ✔ ${created} new shops referred directly to سارة this run`);

    for (const member of teamSessions) {
      if (!member.shopCount) continue;
      const memberMe = await req('/api/v1/affiliates/me', 'GET', undefined, member.session.access_token);
      const createdForMember = await seedShopsUpTo(memberMe.id, member.shopCount, member.name, member.session.access_token);
      console.log(`  ✔ ${createdForMember} new shops referred to ${member.name} this run`);
    }
  } else {
    console.log('▸ SKIP_SHOPS=1 — team roster ensured, no new shops seeded this run');
  }

  console.log('▸ real support tickets on a few of سارة\'s referred shops');
  await seedTickets(saraSession.access_token);

  console.log('✔ rich affiliate demo ready.');
  console.log(`  سارة: ${SARA.phone} / ${SARA.password}`);
  for (const m of TEAM) console.log(`  ${m.name}: ${m.phone} / ${m.password}`);
  console.log('  (commissions and ticket-state variety NOT seeded — see this file\'s own header on why)');
}

main().catch((e) => { console.error(e.message); process.exit(1); });
