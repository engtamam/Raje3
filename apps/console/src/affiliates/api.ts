/**
 * The affiliate portal's own door — a SEPARATE base URL, a separate token store, deliberately.
 *
 * NOT auth.ts, and not session.ts. Those are the shop's — `tenant`, `operator`, the action
 * catalogue — and a marketer is not a shop: he has no branch, no operator PIN, no subscription.
 * Sharing that module would mean bending its shape until it lied about the second audience it was
 * never written for, which is exactly the failure Door.tsx's own header note describes for the
 * kit's `LoginForm`/`SignupForm` — reused just enough to be wrong. So this is a second, small file
 * rather than a fork of the first.
 */
import { announceExpiry, fresh, renew } from './renew';

const BASE = (import.meta.env.VITE_AFFILIATE_API_BASE ?? '').replace(/\/$/, '');

/** Same shape as auth.ts's own Refused — the console-wide idiom for "a sentence AND a code the
 *  screen can act on", kept identical rather than reinvented per door. */
export class AffiliateRefused extends Error {
  constructor(message: string, readonly reason: string = '') {
    super(message);
  }
}

interface ApiResult {
  ok?: boolean;
  message?: string;
  reason?: string;
  [key: string]: unknown;
}

async function req<T>(path: string, method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE',
                      body?: unknown, token?: string): Promise<T> {
  // RENEW BEFORE SENDING, RENEW AGAIN ON 401 — the exact fix `../api.ts`'s own `call()` already
  // has for the shop console; see ./renew.ts for why the portal never had it until now. `fresh()`
  // only touches a token that is actually about to expire, so a signed-out or never-signed-in
  // caller (token === '') pays nothing extra.
  let bearer = token ? await fresh(token) : token;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (bearer) headers.Authorization = `Bearer ${bearer}`;
  let res = await fetch(`${BASE}${path}`, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && token) {
    bearer = await renew();
    if (bearer) {
      headers.Authorization = `Bearer ${bearer}`;
      res = await fetch(`${BASE}${path}`, {
        method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    }
  }
  // STILL A 401 AFTER RENEWAL WAS TRIED — the session is genuinely over (refresh token dead too),
  // not a screen that fired before a fresh bearer was ready. Announce it ONCE so useAffiliateSession
  // signs him out cleanly, instead of every remaining screen quietly 401ing with no explanation.
  if (res.status === 401 && token) announceExpiry();
  const text = await res.text();
  let parsed: ApiResult | null = null;
  try { parsed = text ? (JSON.parse(text) as ApiResult) : null; } catch { parsed = null; }
  if (!res.ok || parsed?.ok === false) {
    throw new AffiliateRefused(
      parsed?.message ?? 'تعذّر إكمال الطلب. حاول مرة أخرى.', parsed?.reason ?? '');
  }
  return parsed as T;
}

export interface AffiliateSession {
  access_token: string;
  refresh_token?: string;
  tenant?: string;
}

/** «سجّل كمسوّق» — writes a ROW an admin has to look at first. No account, no token comes back;
 *  see services/affiliate-service/app/core/onboarding.py::apply for the whole reasoning. A
 *  referral link's own applicant proves he owns the number via `code` — empty on a deployment
 *  where AFFILIATE_REQUIRE_OTP is still off, which apply() itself accepts either way. */
export async function apply(input: {
  phone: string; name: string; password: string; referralCode?: string; agreed: boolean;
  cvUrl?: string; code?: string;
}): Promise<{ application_id: string; status: string }> {
  return req('/api/v1/affiliates/apply', 'POST', {
    phone: input.phone, name: input.name, password: input.password,
    referral_code: input.referralCode || '', agreed: input.agreed,
    cv_url: input.cvUrl || '', code: input.code || '',
  });
}

/** The phone-ownership code — a no-op refusal (`reason: 'undeliverable'`) on a deployment where
 *  AFFILIATE_OTP_DELIVERABLE is still off, i.e. every deployment today. */
export async function requestApplyOtp(phone: string): Promise<{ sent: boolean; expires_in: number }> {
  return req('/api/v1/affiliates/apply/request-otp', 'POST', { phone });
}

export async function signIn(phone: string, password: string): Promise<AffiliateSession> {
  return req('/api/v1/affiliates/signin', 'POST', { phone, password });
}

/** The referring manager correcting what a person under him submitted — only while there is
 *  still a decision to correct BEFORE (server-enforced; see onboarding.py::update_application). */
export async function updateApplication(session: AffiliateSession, applicationId: string,
    patch: { name?: string; cvUrl?: string }): Promise<{ application_id: string; status: string }> {
  return req(`/api/v1/affiliates/me/applications/${applicationId}`, 'PATCH', {
    name: patch.name, cv_url: patch.cvUrl,
  }, session.access_token);
}

export interface Me {
  id: string; role: string; name: string; parent_id: string; status: string;
}

/** Who I am — and his own `id` doubles as his referral code (spec §1): `?aff=<id>` for a shop,
 *  `?ref=<id>` for another marketer applying under him. */
export async function me(session: AffiliateSession): Promise<Me> {
  return req('/api/v1/affiliates/me', 'GET', undefined, session.access_token);
}

/** Same shape as `services/affiliate-service/app/api/v1/affiliate_self.py::home`'s own response —
 *  ONE call assembling what used to need six to eight, kept a straight mirror of the server's own
 *  dict rather than reshaped here, so the two can never drift apart silently. */
export interface Balance {
  pending_halalas: number; confirmed_available_halalas: number; withdrawn_halalas: number;
  min_withdrawal_halalas: number;
}
export async function balance(session: AffiliateSession): Promise<Balance> {
  return req('/api/v1/affiliates/me/balance', 'GET', undefined, session.access_token);
}
/** `WafaService._aggregate_support_kpis`'s own return shape — real support performance read
 *  through ticket-service's own consent-scoped share, best-effort per shop (`available: false`
 *  is the honest common case before a shop has shared its tickets, never an error). */
export interface SupportKpis {
  available: boolean;
  reason?: string;
  shops_with_shared_tickets?: number;
  ticket_count?: number;
  avg_first_response_seconds?: number | null;
  avg_resolution_seconds?: number | null;
  escalation_rate?: number;
}

export interface WafaEligibility {
  active_shops: number; tier_shops: number; shops_until_next_tier: number; eligible: boolean;
  current_tier_amount_halalas: number; retention_rate: number; refund_rate: number;
  support_kpis: SupportKpis;
  // THE SAMPLE SIZE BEHIND retention_rate/refund_rate — 0 referrals/commissions means the rate is
  // a formula default (100%/0%), not an earned number; PerformanceStats reads these to say "no
  // data yet" instead of a real-looking percentage ("كيف كذا وهو صفر اساس").
  total_referrals: number; total_commissions: number;
  // THE ACTIVITY GATE — how many shops converted trial→paid in the last `conversion_lookback_days`.
  // `eligible` is already false when this is 0 even with enough shops; the screen reads this pair
  // to say WHY, rather than the misleading "N شركة يفتح لك الاستحقاق" a shop-count-only read would.
  recent_conversions: number; min_recent_conversions: number; conversion_lookback_days: number;
}
export interface EmploymentEligibility {
  converted_customers: number; threshold: number; eligible: boolean;
  customers_until_eligible: number;
}
export interface TopTemplate {
  template_id: string; title: string; stage_code: string; kind: string; uses: number;
  advanced: number; no_response: number; rejected: number; pending: number; advance_rate: number;
}
export interface StaleLead {
  id: string; name: string; city: string; status: string; found_at: number;
}
export interface TeamSummary {
  member_count: number; team_confirmed_halalas: number; team_pending_halalas: number;
  pending_wafa_requests_count: number;
}
export interface Home {
  affiliate: { id: string; name: string; role: string };
  balance: Balance;
  payout_method_set: boolean;
  pending_withdrawal?: boolean;
  stale_leads_count: number;
  stale_leads: StaleLead[];
  open_tickets: HomeTicket[];
  wafa_eligibility: WafaEligibility;
  employment_eligibility: EmploymentEligibility;
  top_template_this_period: TopTemplate | null;
  team?: TeamSummary;
  places_api_key_set?: boolean | null;
}

export async function home(session: AffiliateSession): Promise<Home> {
  return req('/api/v1/affiliates/me/home', 'GET', undefined, session.access_token);
}

/**
 * "عملائي المحتملين" — a straight mirror of `Lead.to_dict()`
 * (`services/affiliate-service/app/core/models.py`), field for field, same discipline as `Home`
 * above. `LEAD_MANUAL_STATUSES` is the subset a person may actually set through `setLeadStatus`
 * — `new`/`assigned`/`registered` are reached only by the server itself (ingestion, `assign()`,
 * `link-registration`), never typed in by a screen.
 */
export interface LeadNote {
  at: number; by: string; text: string; status_from: string; status_to: string;
}
export interface Lead {
  id: string; place_id: string; phone: string; name: string; place_type: string;
  sector_code: string; city: string; region: string; address: string; neighborhood: string;
  maps_url: string; rating: number; ratings_count: number; opening_hours: string; website: string;
  lat: number; lng: number; extra_place_ids: string[]; source_manager_id: string;
  assigned_to: string; status: string; converted_tenant: string; notes: LeadNote[];
  found_at: number; outreach_stage_code: string; decision_maker_name: string;
  decision_maker_phone: string; decision_maker_role: string;
}
export const LEAD_MANUAL_STATUSES = ['contacted', 'interested', 'not_interested', 'follow_up'] as const;

export interface LeadsFilter {
  status_eq?: string; stage_code?: string; city?: string; needs_attention?: boolean;
}
export async function leads(session: AffiliateSession, filter: LeadsFilter = {}):
    Promise<{ leads: Lead[] }> {
  const q = new URLSearchParams();
  if (filter.status_eq) q.set('status_eq', filter.status_eq);
  if (filter.stage_code) q.set('stage_code', filter.stage_code);
  if (filter.city) q.set('city', filter.city);
  if (filter.needs_attention) q.set('needs_attention', 'true');
  const qs = q.toString();
  return req(`/api/v1/affiliates/me/leads${qs ? `?${qs}` : ''}`, 'GET', undefined,
             session.access_token);
}

export async function oneLead(session: AffiliateSession, leadId: string): Promise<Lead> {
  return req(`/api/v1/affiliates/me/leads/${leadId}`, 'GET', undefined, session.access_token);
}

export async function setLeadStatus(session: AffiliateSession, leadId: string, newStatus: string,
                                    text = ''): Promise<Lead> {
  return req(`/api/v1/affiliates/me/leads/${leadId}/status`, 'POST', { status: newStatus, text },
             session.access_token);
}

export async function setDecisionMaker(session: AffiliateSession, leadId: string,
                                       input: { name?: string; phone?: string; role?: string }):
    Promise<Lead> {
  return req(`/api/v1/affiliates/me/leads/${leadId}/decision-maker`, 'PATCH', input,
             session.access_token);
}

/** The outbound conversion playbook's own shared library — spec §15, read-only for every
 *  affiliate; a manager's own write routes are a later slice (this screen only ever reads). */
export interface OutreachStage { code: string; name: string; order: number; active: boolean }
export interface MessageTemplate {
  id: string; stage_code: string; kind: string; title: string; body: string; media_url: string;
  objection_type: string; active: boolean;
}
export interface TemplateUse {
  id: string; lead_id: string; template_id: string; stage_code: string; kind: string;
  used_by: string; used_at: number; outcome: string; outcome_at: number; outcome_by: string;
  note: string;
}
export const TEMPLATE_OUTCOMES = ['pending', 'advanced', 'no_response', 'rejected'] as const;

export async function outreachStages(session: AffiliateSession): Promise<{ stages: OutreachStage[] }> {
  return req('/api/v1/affiliates/me/outreach-stages', 'GET', undefined, session.access_token);
}

export async function templates(session: AffiliateSession, stageCode = ''):
    Promise<{ templates: MessageTemplate[] }> {
  const qs = stageCode ? `?stage_code=${encodeURIComponent(stageCode)}` : '';
  return req(`/api/v1/affiliates/me/templates${qs}`, 'GET', undefined, session.access_token);
}

export async function templateUsesForLead(session: AffiliateSession, leadId: string):
    Promise<{ uses: TemplateUse[] }> {
  return req(`/api/v1/affiliates/me/leads/${leadId}/template-uses`, 'GET', undefined,
             session.access_token);
}

export async function logTemplateUse(session: AffiliateSession, leadId: string, templateId: string):
    Promise<TemplateUse> {
  return req(`/api/v1/affiliates/me/leads/${leadId}/template-uses`, 'POST',
             { template_id: templateId }, session.access_token);
}

export async function setOutcome(session: AffiliateSession, useId: string, outcome: string,
                                 opts: { note?: string; newStageCode?: string } = {}):
    Promise<TemplateUse> {
  return req(`/api/v1/affiliates/me/template-uses/${useId}`, 'PATCH',
             { outcome, note: opts.note ?? '', new_stage_code: opts.newStageCode ?? '' },
             session.access_token);
}

/** «حسابي»'s own payout section — a straight mirror of `GET/PUT /me/payout-method`'s own shapes.
 *  `masked_account_ref` is EVERYTHING a read ever returns of the account number on file — never
 *  the full IBAN/account id, which is write-only past the initial save (see the server route's
 *  own docstring). */
export const PAYOUT_CHANNELS = ['bank_iban', 'intermediary'] as const;
export type PayoutMethod =
  | { set: false }
  | { set: true; channel: string; channel_name: string; masked_account_ref: string };

export async function payoutMethod(session: AffiliateSession): Promise<PayoutMethod> {
  return req('/api/v1/affiliates/me/payout-method', 'GET', undefined, session.access_token);
}

export async function setPayoutMethod(session: AffiliateSession, input: {
  channel: string; channelName?: string; accountRef: string;
}): Promise<{ channel: string; channel_name: string; account_ref: string }> {
  return req('/api/v1/affiliates/me/payout-method', 'PUT', {
    channel: input.channel, channel_name: input.channelName ?? '', account_ref: input.accountRef,
  }, session.access_token);
}

/** A pure pass-through to identity-service (see the server route's own docstring) — nothing here
 *  ever holds a password, old or new. */
export async function changePassword(session: AffiliateSession, oldPassword: string,
                                     newPassword: string): Promise<void> {
  await req('/api/v1/affiliates/me/change-password', 'POST',
            { old_password: oldPassword, new_password: newPassword }, session.access_token);
}

/* ── «أدواتي» ──────────────────────────────────────────────────────────────────────────────────
 * The shared playbook (stages/templates/citations) — any affiliate reads; a manager also writes.
 * Every write mirrors the server's own upsert-by-code-or-id / deactivate-never-delete discipline:
 * there is no `deleteTemplate`, only `deactivateTemplate`.
 */
export interface TemplateStat {
  template_id: string; stage_code: string; kind: string; title: string; uses: number;
  pending: number; advanced: number; no_response: number; rejected: number; advance_rate: number;
}
export interface KindStat {
  kind: string; uses: number; pending: number; advanced: number; no_response: number;
  rejected: number; advance_rate: number;
}
export async function templateStats(session: AffiliateSession,
                                    opts: { stageCode?: string; mine?: boolean } = {}):
    Promise<{ stats: TemplateStat[] }> {
  const q = new URLSearchParams();
  if (opts.stageCode) q.set('stage_code', opts.stageCode);
  if (opts.mine) q.set('mine', 'true');
  const qs = q.toString();
  return req(`/api/v1/affiliates/me/template-stats${qs ? `?${qs}` : ''}`, 'GET', undefined,
             session.access_token);
}

/** Which CONTENT TYPE (kind) actually moves a lead forward, across every template sharing it —
 *  a coarser grain than `templateStats`' per-template rows, answering "should I write more
 *  testimonial-style messages" rather than "which exact template". */
export async function templateKindStats(session: AffiliateSession, opts: { mine?: boolean } = {}):
    Promise<{ stats: KindStat[] }> {
  const qs = opts.mine ? '?mine=true' : '';
  return req(`/api/v1/affiliates/me/template-kind-stats${qs}`, 'GET', undefined,
             session.access_token);
}

export async function upsertOutreachStage(session: AffiliateSession, input: {
  code: string; name: string; order?: number;
}): Promise<OutreachStage> {
  return req('/api/v1/affiliates/me/outreach-stages', 'PUT', {
    code: input.code, name: input.name, order: input.order ?? 0,
  }, session.access_token);
}

export async function deactivateOutreachStage(session: AffiliateSession, code: string):
    Promise<{ ok: boolean; changed: boolean }> {
  return req(`/api/v1/affiliates/me/outreach-stages/${code}`, 'DELETE', undefined,
             session.access_token);
}

export interface TemplateInput {
  stageCode: string; kind?: string; title: string; body?: string; mediaUrl?: string;
  objectionType?: string;
}
function templateBody(input: TemplateInput) {
  return {
    stage_code: input.stageCode, kind: input.kind ?? '', title: input.title,
    body: input.body ?? '', media_url: input.mediaUrl ?? '', objection_type: input.objectionType ?? '',
  };
}
export async function createTemplate(session: AffiliateSession, input: TemplateInput):
    Promise<MessageTemplate> {
  return req('/api/v1/affiliates/me/templates', 'POST', templateBody(input), session.access_token);
}
export async function updateTemplate(session: AffiliateSession, templateId: string,
                                     input: TemplateInput): Promise<MessageTemplate> {
  return req(`/api/v1/affiliates/me/templates/${templateId}`, 'PUT', templateBody(input),
             session.access_token);
}
export async function deactivateTemplate(session: AffiliateSession, templateId: string):
    Promise<{ ok: boolean; changed: boolean }> {
  return req(`/api/v1/affiliates/me/templates/${templateId}`, 'DELETE', undefined,
             session.access_token);
}

/** The evidence library — real, sourced financial facts a template can cite. */
export interface StatCitation {
  id: string; title: string; body: string; source_label: string; source_url: string;
  stage_code: string; active: boolean;
}
export async function statCitations(session: AffiliateSession, stageCode = ''):
    Promise<{ citations: StatCitation[] }> {
  const qs = stageCode ? `?stage_code=${encodeURIComponent(stageCode)}` : '';
  return req(`/api/v1/affiliates/me/stat-citations${qs}`, 'GET', undefined, session.access_token);
}
export interface StatCitationInput {
  title: string; body: string; sourceLabel?: string; sourceUrl?: string; stageCode?: string;
}
function citationBody(input: StatCitationInput) {
  return {
    title: input.title, body: input.body, source_label: input.sourceLabel ?? '',
    source_url: input.sourceUrl ?? '', stage_code: input.stageCode ?? '',
  };
}
export async function createStatCitation(session: AffiliateSession, input: StatCitationInput):
    Promise<StatCitation> {
  return req('/api/v1/affiliates/me/stat-citations', 'POST', citationBody(input),
             session.access_token);
}
export async function updateStatCitation(session: AffiliateSession, citationId: string,
                                         input: StatCitationInput): Promise<StatCitation> {
  return req(`/api/v1/affiliates/me/stat-citations/${citationId}`, 'PUT', citationBody(input),
             session.access_token);
}
export async function deactivateStatCitation(session: AffiliateSession, citationId: string):
    Promise<{ ok: boolean; changed: boolean }> {
  return req(`/api/v1/affiliates/me/stat-citations/${citationId}`, 'DELETE', undefined,
             session.access_token);
}

/* ── أداة البحث عن عملاء محتملين — مدير فقط (BYOK Google Places key + مهمة بحث بالخلفية) ───────── */
export interface PlacesApiKeyInfo {
  set: boolean; hint?: string; set_at?: number;
}
export async function placesApiKey(session: AffiliateSession): Promise<PlacesApiKeyInfo> {
  return req('/api/v1/affiliates/me/places-api-key', 'GET', undefined, session.access_token);
}
export async function setPlacesApiKey(session: AffiliateSession, apiKey: string):
    Promise<{ ok: boolean; hint: string; set_at: number }> {
  return req('/api/v1/affiliates/me/places-api-key', 'PUT', { api_key: apiKey },
             session.access_token);
}
export async function clearPlacesApiKey(session: AffiliateSession):
    Promise<{ ok: boolean; cleared: boolean }> {
  return req('/api/v1/affiliates/me/places-api-key', 'DELETE', undefined, session.access_token);
}

export interface City { name: string; region?: string; lat: number; lng: number; w_km: number; h_km: number }
export interface LeadSearchJob {
  id: string; affiliate_id: string; place_type: string; sector_code: string; keywords: string[];
  radius_km: number; cities: City[]; status: string; cursor: { city: number; point: number; keyword: number };
  found_count: number; duplicate_count: number; created_at: number; started_at: number;
  finished_at: number; error: string;
}
export async function startLeadSearch(session: AffiliateSession, input: {
  sectorCode: string; keywords: string[]; cities: City[]; placeType?: string; radiusKm?: number;
}): Promise<LeadSearchJob> {
  return req('/api/v1/affiliates/me/leads/search', 'POST', {
    place_type: input.placeType ?? '', sector_code: input.sectorCode, keywords: input.keywords,
    radius_km: input.radiusKm ?? 5, cities: input.cities,
  }, session.access_token);
}
export async function myLeadSearches(session: AffiliateSession): Promise<{ jobs: LeadSearchJob[] }> {
  return req('/api/v1/affiliates/me/leads/search', 'GET', undefined, session.access_token);
}
export async function leadSearchStatus(session: AffiliateSession, jobId: string):
    Promise<LeadSearchJob> {
  return req(`/api/v1/affiliates/me/leads/search/${jobId}`, 'GET', undefined, session.access_token);
}

/* ── «أرباحي» — the money deep-dive: commissions, withdrawals, receipts, team earnings, Wafa ───── */
export interface Commission {
  id: string; tenant: string; affiliate_id: string; kind: string; amount_halalas: number;
  status: string; earned_at: string; confirms_at: number; created_at: number; withdrawal_id: string;
}
export async function commissions(session: AffiliateSession): Promise<{ commissions: Commission[] }> {
  return req('/api/v1/affiliates/me/commissions', 'GET', undefined, session.access_token);
}

export const WITHDRAWAL_STATUS = ['requested', 'completed', 'rejected'] as const;
export interface WithdrawalRequest {
  id: string; affiliate_id: string; amount_halalas: number; commission_ids: string[];
  status: string; payout_channel: string; payout_channel_name: string; payout_account_ref: string;
  requested_at: number; decided_at: number; decided_by: string; receipt_reference: string;
  receipt_content_type: string; reason: string;
}
export async function requestWithdrawal(session: AffiliateSession): Promise<WithdrawalRequest> {
  return req('/api/v1/affiliates/me/withdrawals', 'POST', undefined, session.access_token);
}
export async function myWithdrawals(session: AffiliateSession):
    Promise<{ withdrawals: WithdrawalRequest[] }> {
  return req('/api/v1/affiliates/me/withdrawals', 'GET', undefined, session.access_token);
}
/** A binary response, unlike every other call here — `req<T>` assumes JSON, so this fetches
 *  directly and hands back an object URL the caller opens/revokes itself. */
export async function withdrawalReceiptUrl(session: AffiliateSession, withdrawalId: string):
    Promise<string> {
  const res = await fetch(`${BASE}/api/v1/affiliates/me/withdrawals/${withdrawalId}/receipt`,
    { headers: { Authorization: `Bearer ${session.access_token}` } });
  if (!res.ok) throw new AffiliateRefused('تعذّر فتح الإيصال.');
  return URL.createObjectURL(await res.blob());
}

/** The manager's own team-earnings view — richer than `Home`'s `TeamSummary` teaser, one member
 *  row at a time. */
export interface TeamMember {
  id: string; name: string; status: string; confirmed_halalas: number; pending_halalas: number;
  commission_count: number; shops: number; total_net_revenue_minor: number; revenue_partial: boolean;
  // `GET /me/team` merges the SAME `performance_for()` dict `/me/wafa-eligibility` returns for
  // the manager himself — sent all along, just never typed or rendered until now.
  active_shops?: number; retention_rate?: number; refund_rate?: number; support_kpis?: SupportKpis;
  total_referrals?: number; total_commissions?: number;
}
export interface Team {
  my_shops: number; my_net_revenue_minor: number; my_revenue_partial: boolean;
  members: TeamMember[]; team_confirmed_halalas: number; team_pending_halalas: number;
  team_net_revenue_minor: number; team_revenue_partial: boolean; platform_revenue_enabled: boolean;
  platform_net_revenue_minor?: number; platform_revenue_partial?: boolean;
}
export async function team(session: AffiliateSession): Promise<Team> {
  return req('/api/v1/affiliates/me/team', 'GET', undefined, session.access_token);
}

/** برنامج دعم الوفاء — الاستحقاق الذاتي، منفصل تمامًا عن سجل العمولات (بطاقة حالة، لا صف بجدول).
 *  `manager_decision` استشاري فقط؛ `status` هو قرار المنصة الملزِم — لا يُخلَط بينهما بالواجهة. */
export const WAFA_STATUSES = ['requested', 'granted', 'rejected'] as const;
export interface WafaRequest {
  id: string; affiliate_id: string; active_shops: number; tier_amount_halalas: number;
  status: string; requested_at: number; system_recommendation: string;
  system_retention_rate: number; system_refund_rate: number; manager_decision: string;
  manager_decided_by: string; manager_decided_at: number; manager_reason: string;
  decided_by: string; decided_at: number; reason: string; granted_at: number;
}
export async function wafaEligibility(session: AffiliateSession): Promise<WafaEligibility> {
  return req('/api/v1/affiliates/me/wafa-eligibility', 'GET', undefined, session.access_token);
}
export async function requestWafa(session: AffiliateSession): Promise<WafaRequest> {
  return req('/api/v1/affiliates/me/wafa-requests', 'POST', undefined, session.access_token);
}
export async function myWafaRequests(session: AffiliateSession):
    Promise<{ wafa_requests: WafaRequest[] }> {
  return req('/api/v1/affiliates/me/wafa-requests', 'GET', undefined, session.access_token);
}
export async function teamWafaRequests(session: AffiliateSession):
    Promise<{ wafa_requests: WafaRequest[] }> {
  return req('/api/v1/affiliates/me/team/wafa-requests', 'GET', undefined, session.access_token);
}
export async function decideTeamWafaRequest(session: AffiliateSession, requestId: string,
                                            decision: 'approve' | 'reject', reason = ''):
    Promise<WafaRequest> {
  return req(`/api/v1/affiliates/me/team/wafa-requests/${requestId}/decision`, 'POST',
             { decision, reason }, session.access_token);
}

/** «رشّح نفسك لوظيفة» — نفس نمط دعم الوفاء بالضبط، بطاقة حالة مستقلة. */
export const EMPLOYMENT_STATUSES = ['requested', 'approved', 'rejected'] as const;
export interface EmploymentRequest {
  id: string; affiliate_id: string; converted_customers: number; status: string;
  requested_at: number; decided_by: string; decided_at: number; reason: string;
}
export async function employmentEligibility(session: AffiliateSession) {
  return req<{
    converted_customers: number; threshold: number; eligible: boolean;
    customers_until_eligible: number;
  }>('/api/v1/affiliates/me/employment-eligibility', 'GET', undefined, session.access_token);
}
export async function requestEmployment(session: AffiliateSession): Promise<EmploymentRequest> {
  return req('/api/v1/affiliates/me/employment-requests', 'POST', undefined, session.access_token);
}
export async function myEmploymentRequests(session: AffiliateSession):
    Promise<{ employment_requests: EmploymentRequest[] }> {
  return req('/api/v1/affiliates/me/employment-requests', 'GET', undefined, session.access_token);
}

/** إحصائيات القطاعات — بيانات محرّك البحث، مدير فقط، من `LeadSourcingService.sector_stats`. */
export interface SectorStat {
  sector_code: string; city: string; lead_count: number; by_status: Record<string, number>;
  registered_count: number;
}
export async function sectorStats(session: AffiliateSession): Promise<{ stats: SectorStat[] }> {
  return req('/api/v1/affiliates/me/leads/sector-stats', 'GET', undefined, session.access_token);
}

/* ── §13 تذاكر المحلات — أي مسوّق أحال محلًا فعليًا، لا مدير فقط ─────────────────────────────────── */
export interface ReferredShop {
  tenant: string; shop_name: string; status: string; stamped_at: number;
}
export async function referredShops(session: AffiliateSession): Promise<{ shops: ReferredShop[] }> {
  return req('/api/v1/affiliates/me/referred-shops', 'GET', undefined, session.access_token);
}

/** شكل التذكرة نفسه يملكه ticket-service (خدمة خارجية) — يبقى مفتوحًا هنا عمدًا بدل تخمين حقوله؛
 *  الحقول الشائعة اختيارية للاستخدام المباشر بالواجهة. */
export interface ShopTicket extends Record<string, unknown> {
  id?: string; subject?: string; body?: string; status?: string; type?: string;
  priority?: string; created_at?: number;
}
/** A `ShopTicket` as `/me/home`'s own carousel feed returns it — the same row, with the shop it
 *  belongs to attached (a marketer's ticket list is per-shop everywhere else; the carousel is the
 *  one place several shops' tickets sit side by side, so it has to say whose is whose). */
export interface HomeTicket extends ShopTicket {
  tenant: string; shop_name: string;
}
export async function shopTickets(session: AffiliateSession, tenant: string):
    Promise<{ tickets: ShopTicket[] }> {
  return req(`/api/v1/affiliates/me/shops/${tenant}/tickets`, 'GET', undefined, session.access_token);
}
export async function shopTicket(session: AffiliateSession, tenant: string, ticketId: string):
    Promise<ShopTicket> {
  return req(`/api/v1/affiliates/me/shops/${tenant}/tickets/${ticketId}`, 'GET', undefined,
             session.access_token);
}
export async function openShopTicket(session: AffiliateSession, tenant: string, input: {
  type: string; subject?: string; body?: string; priority?: string;
}): Promise<ShopTicket> {
  return req(`/api/v1/affiliates/me/shops/${tenant}/tickets`, 'POST', {
    type: input.type, subject: input.subject ?? '', body: input.body ?? '',
    priority: input.priority ?? 'normal',
  }, session.access_token);
}
export async function replyShopTicket(session: AffiliateSession, tenant: string, ticketId: string,
                                      body: string): Promise<ShopTicket> {
  return req(`/api/v1/affiliates/me/shops/${tenant}/tickets/${ticketId}/replies`, 'POST',
             { body }, session.access_token);
}
