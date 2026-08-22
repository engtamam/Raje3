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

async function req<T>(path: string, method: 'GET' | 'POST' | 'PATCH' | 'PUT', body?: unknown,
                      token?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${BASE}${path}`, {
    method, headers, body: body !== undefined ? JSON.stringify(body) : undefined,
  });
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
 *  see services/affiliate-service/app/core/onboarding.py::apply for the whole reasoning. */
export async function apply(input: {
  phone: string; name: string; password: string; referralCode?: string; agreed: boolean;
}): Promise<{ application_id: string; status: string }> {
  return req('/api/v1/affiliates/apply', 'POST', {
    phone: input.phone, name: input.name, password: input.password,
    referral_code: input.referralCode || '', agreed: input.agreed,
  });
}

export async function signIn(phone: string, password: string): Promise<AffiliateSession> {
  return req('/api/v1/affiliates/signin', 'POST', { phone, password });
}

/** The other half of a manager's invite — no token yet, same reason `apply` has none. */
export async function acceptInvite(token: string, password: string, agreed: boolean):
    Promise<{ affiliate_id: string }> {
  return req('/api/v1/affiliates/accept-invite', 'POST', { token, password, agreed });
}

/** A manager naming somebody for his own team. Needs a signed-in manager's own token; the server
 *  is the one place that actually decides whether the caller may (see api/v1/affiliate_self.py). */
export async function invite(session: AffiliateSession, phone: string, name: string):
    Promise<{ application_id: string; status: string }> {
  return req('/api/v1/affiliates/me/invite', 'POST', { phone, name }, session.access_token);
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
}
export interface WafaEligibility {
  active_shops: number; tier_shops: number; shops_until_next_tier: number; eligible: boolean;
  current_tier_amount_halalas: number; retention_rate: number; refund_rate: number;
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
