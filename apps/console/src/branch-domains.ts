/**
 * The console's own copy of `services/operations/app/core/branch_domains.py`'s classification —
 * which of this product's domains a branch actually means something to, and which are shop-wide.
 *
 * A HAND-WRITTEN MIRROR, NEVER GENERATED. This repo has no Python→TypeScript codegen step, and
 * building one just for this one file would be a bigger, separate decision than this project's own
 * scope — see the Python file's own module docstring for the full reasoning behind the
 * classification itself; this file only restates it in the language the console reads.
 *
 * KEEP THIS IN SYNC WITH THE PYTHON FILE BY HAND. Both files carry a one-line pointer at the top to
 * the other as the same source of truth — a future edit to one (a domain added, renamed, or
 * reclassified) is expected to update the other in the same change, the same way this repo already
 * expects `apps.ts`/`nav.ts` and their own backend counterparts to move together.
 *
 * NOT WIRED TO ANY SCREEN YET, ON PURPOSE. This file exists so the classification has a real,
 * reviewable TypeScript home — enforcing it (a build-time check that a screen reading a
 * branch-scoped domain's data calls `scopeQuery`) is deliberately later work, done together with
 * the mobile app's own equivalent for parity between the two clients rather than console-only.
 */

export interface BranchDomainInfo {
  id: string;
  /** The Arabic name already used for this domain elsewhere in this console (apps.ts / nav.ts),
   *  reused verbatim so this file never invents a second name for the same thing. */
  labelAr: string;
  branchScoped: boolean;
  /** Set ONLY for `mobile_requests` — see that entry's own comment below. `null` for every other
   *  domain, including every platform-level one. */
  derivedFrom: 'assigned_operator_branch' | null;
}

// ── branch-scoped: a manager at one branch must not see another branch's records ────────────────
const BRANCH_SCOPED: readonly BranchDomainInfo[] = [
  { id: 'visit', labelAr: 'تسجيل زيارة', branchScoped: true, derivedFrom: null },
  { id: 'customers', labelAr: 'جهات الاتصال', branchScoped: true, derivedFrom: null },
  { id: 'rating', labelAr: 'التقييم', branchScoped: true, derivedFrom: null },
  { id: 'bookings', labelAr: 'الحجوزات', branchScoped: true, derivedFrom: null },
  { id: 'shop_insights', labelAr: 'محلّي', branchScoped: true, derivedFrom: null },
  { id: 'team', labelAr: 'فريقي', branchScoped: true, derivedFrom: null },
  { id: 'whatsapp_connect', labelAr: 'ربط واتساب', branchScoped: true, derivedFrom: null },
  { id: 'campaigns_send_log', labelAr: 'الحملات', branchScoped: true, derivedFrom: null },
  // Scoped INDIRECTLY, through whoever the request is currently ASSIGNED to — a mobile-service
  // request carries no branch_id of its own (the technician travels to the customer, not to a
  // shop branch). See services/operations/app/api/v1/mobile_requests.py's own module docstring
  // and `_operator_branch`/`_branch_allowed` for how the backend derives and applies this.
  { id: 'mobile_requests', labelAr: 'خدمات متنقلة', branchScoped: true,
   derivedFrom: 'assigned_operator_branch' },
];

// ── platform-level: shop-wide, branch has no meaning here at all ────────────────────────────────
const PLATFORM_LEVEL: readonly BranchDomainInfo[] = [
  { id: 'services_catalogue', labelAr: 'خدماتي ومنتجاتي', branchScoped: false, derivedFrom: null },
  { id: 'loyalty_points', labelAr: 'نقاط الولاء', branchScoped: false, derivedFrom: null },
  { id: 'partner_loyalty', labelAr: 'ولاء الشركاء', branchScoped: false, derivedFrom: null },
  { id: 'referral_partnership', labelAr: 'شراكة استراتيجية', branchScoped: false, derivedFrom: null },
  { id: 'whatsapp_assistant', labelAr: 'المساعد الذكي عبر واتساب', branchScoped: false, derivedFrom: null },
  { id: 'mobile_ai_assistant', labelAr: 'المساعد الذكي (تطبيق الجوال)', branchScoped: false, derivedFrom: null },
  { id: 'support', labelAr: 'الدعم الفني', branchScoped: false, derivedFrom: null },
  { id: 'billing_account', labelAr: 'حسابي', branchScoped: false, derivedFrom: null },
  { id: 'campaigns_authoring', labelAr: 'الحملات', branchScoped: false, derivedFrom: null },
];

/** The full registry — the only thing outside this file should ever iterate. */
export const BRANCH_DOMAINS: readonly BranchDomainInfo[] = [...BRANCH_SCOPED, ...PLATFORM_LEVEL];

/** Lookup by id, built once at module load — mirrors the Python file's own `BRANCH_DOMAINS_BY_ID`. */
export const BRANCH_DOMAINS_BY_ID: Readonly<Record<string, BranchDomainInfo>> =
  Object.fromEntries(BRANCH_DOMAINS.map((d) => [d.id, d]));

/** Whether `domainId` should be filtered/restricted by branch. Throws on an unknown id on purpose
 *  — a typo here must fail loudly, not silently read as platform-level (same posture the Python
 *  file's own `is_branch_scoped` takes). */
export function isBranchScoped(domainId: string): boolean {
  const d = BRANCH_DOMAINS_BY_ID[domainId];
  if (!d) throw new Error(`branch-domains.ts: unknown domain id "${domainId}"`);
  return d.branchScoped;
}
