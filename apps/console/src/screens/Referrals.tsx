/**
 * «الإحالة والمسوّقين» — the customer-referral program: a shop's own campaigns (a customer refers
 * a friend for a reward, and the friend gets a win-win reward of their own for signing up), and
 * the reporting over what actually got redeemed.
 *
 * TWO SERVICES, ONE SCREEN. Campaign CRUD lives in `services/referrals`
 * (`app/core/{models,campaigns,rewards}.py`, `app/api/v1/admin.py`) — the shop's own configuration,
 * created once and never edited. The real redemption facts and every report here
 * (`referral.report_*`) come from `services/operations`
 * (`app/core/{referral_redemption,referral_reports}.py`) — the only place a grant is actually
 * written, because a till-time redemption needs `EntitlementGateway` and the shop's own customer
 * table, neither of which `services/referrals` holds. Two `action()` lookups per call, same as
 * every other screen that reads more than one service's manifest — never a URL this screen built
 * itself (see catalog.ts's own module docstring).
 *
 * NO branch_id ANYWHERE. Referrals are company-wide by design (confirmed against both services'
 * real code) — never add a branch filter here, the way «الحملات» itself treats a branch as an
 * audience choice, not a scope (see campaigns-are-company-wide.md).
 *
 * A CAMPAIGN'S TERMS ARE IMMUTABLE ONCE CREATED (core/models.py's own module docstring: "a
 * changed mind is a NEW campaign, never a PATCH on an old one"). The only control this screen ever
 * offers on an existing campaign is pause/resume — there is deliberately no "edit terms" button,
 * anywhere, because the backend has no route for it.
 *
 * THE LEADERBOARD IS RANKED BY REVENUE, NOT REDEMPTION COUNT — `referral_reports.py`'s own module
 * docstring calls a raw count "the vanity-metric pattern" and refuses to rank by it alone. This
 * screen preserves that: `redemptions` is shown as a column, never as the sort key.
 *
 * PHONE NUMBERS ARE MASKED HERE, and the leaderboard tab sits behind `operations.affiliates_read`
 * — a narrower capability than the campaign tab's `referrals.manage`/`operations.read`, because a
 * leaderboard is the one surface here that names real people by phone.
 *
 * K-FACTOR, EPC, AND CUSTOMER-LTV UPLIFT ARE NOT COMPUTED ANYWHERE ON THIS SCREEN — the backend
 * deliberately does not report them (`referral_reports.py`'s own docstring: no referral chain, no
 * click event, no longitudinal study). Fabricating them in the UI would be a real number's name on
 * a guess.
 */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import {
  Coins, Gift, Percent, Power, Share2, TrendingUp, UserPlus, Users,
} from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { Card } from '../rj-ui/Card';
import { KpiCard } from '../rj-ui/KpiCard';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { Field, Input, Select } from '../rj-ui/Field';
import { PageHeader } from '../rj-ui/PageHeader';
import { TabBar } from '../rj-ui/TabBar';
import { BarCompare } from '../rj-ui/BarCompare';
import { Table, type TableColumn } from '../rj-ui/Table';
import { riyals, halalas } from '../money';
import { isLoading } from '../loading';
import { Waiting } from '../Waiting';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import { AssistantHint } from '../AssistantHint';
import './referrals-i18n';

// ── the shapes both services actually return ─────────────────────────────────────────────────
interface Campaign {
  id: string;
  created_at: number;
  mode: 'once' | 'x_times' | 'lifetime' | string;
  x_times_limit: number;
  min_spend_minor: number;
  usage_cap_period: string;
  usage_cap_limit: number;
  reward_type: string;
  reward_params: Record<string, unknown>;
  new_customer_reward_type: string;
  new_customer_reward_params: Record<string, unknown>;
  active: boolean;
  cap_scope: 'campaign' | 'lifetime' | string;
}

interface Summary {
  registered_count?: number;
  redeemed_count?: number;
  conversion_rate?: number;
  new_customers_acquired?: number;
  revenue_minor?: number;
  reward_cost_minor?: number;
  cost_ratio?: number;
}

interface LeaderboardRow {
  referrer_phone: string;
  source: 'referral' | 'affiliate' | string;
  redemptions: number;
  revenue_minor: number;
  reward_cost_minor: number;
  last_redeemed_at: number;
}

/** The backend's own row, plus the rank the screen assigns it — the array already arrives sorted
 *  by revenue (referral_reports.py's own `leaderboard()`), so rank is just the array position. */
interface RankedLeaderboardRow extends LeaderboardRow { rank: number }

interface CampaignBreakdownRow {
  campaign_id: string;
  registered: number;
  redeemed: number;
  revenue_minor: number;
  conversion_rate: number;
}

interface AffiliateRow {
  affiliate_id: string;
  phone: string;
  code: string;
  active: boolean;
  redemptions: number;
  revenue_minor: number;
  last_redeemed_at: number;
  unsettled_points: number;
  total_earned_points: number;
}

type T = (key: string) => string;

const REFERRER_REWARD_TYPES = [
  'fixed_points', 'invoice_percentage', 'points_match', 'milestone_free_item',
  'cashback_points', 'status_multiplier', 'time_boost', 'mystery_box',
] as const;
const NEW_CUSTOMER_REWARD_TYPES = ['discount_percent', 'welcome_points'] as const;
const MODES = ['once', 'x_times', 'lifetime'] as const;

/** The last 4 digits of a phone, and nothing else — this screen never shows a full number
 *  outside the ledger tab (`operations.affiliates_read`, where the code itself already
 *  identifies the person to the shop that onboarded them). */
function maskPhone(phone: string): string {
  const digits = (phone || '').replace(/\D/g, '');
  return digits.slice(-4) || '----';
}

function rewardLine(t: T, type: string, params: Record<string, unknown>): string {
  const p = params || {};
  switch (type) {
    case 'fixed_points': return tf(t, 'referrals.reward.fixed_points', { points: String(p.points ?? 0) });
    case 'invoice_percentage': return tf(t, 'referrals.reward.invoice_percentage', { percent: String(p.percent ?? 0) });
    case 'points_match': return tf(t, 'referrals.reward.points_match', { percent: String(p.percent ?? 0) });
    case 'milestone_free_item': return tf(t, 'referrals.reward.milestone_free_item', {
      referrals_required: String(p.referrals_required ?? 0), service_name: String(p.service_name ?? ''),
    });
    case 'cashback_points': return tf(t, 'referrals.reward.cashback_points', { points: String(p.points ?? 0) });
    case 'status_multiplier': return tf(t, 'referrals.reward.status_multiplier', {
      referrals_required: String(p.referrals_required ?? 0), multiplier: String(p.multiplier ?? 0),
    });
    case 'time_boost': return tf(t, 'referrals.reward.time_boost', { multiplier: String(p.multiplier ?? 0) });
    case 'mystery_box': return tf(t, 'referrals.reward.mystery_box', {
      n: String(Array.isArray(p.outcomes) ? p.outcomes.length : 0),
    });
    case 'discount_percent': return tf(t, 'referrals.reward.discount_percent', { percent: String(p.percent ?? 0) });
    case 'welcome_points': return tf(t, 'referrals.reward.welcome_points', { points: String(p.points ?? 0) });
    default: return type;
  }
}

export function ReferralsScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const [tab, setTab] = useState<'campaigns' | 'leaderboard' | 'compare' | 'affiliates'>('campaigns');

  const [campaigns, setCampaigns] = useState<Campaign[] | null | undefined>(undefined);
  const [summary, setSummary] = useState<Summary | null | undefined>(undefined);
  const [leaderboard, setLeaderboard] = useState<LeaderboardRow[] | null | undefined>(undefined);
  const [campaignBreakdown, setCampaignBreakdown] = useState<CampaignBreakdownRow[] | null | undefined>(undefined);
  const [affiliates, setAffiliates] = useState<AffiliateRow[] | null | undefined>(undefined);

  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const [mode, setMode] = useState<string>('once');
  const [rewardType, setRewardType] = useState<string>('fixed_points');
  const [ncRewardType, setNcRewardType] = useState<string>('discount_percent');

  // WHAT THIS PERSON MAY DO. An absent action is a permission fact — the control simply is not
  // rendered, exactly the convention Points.tsx and Coupons.tsx already use.
  const canCreate = action(catalog, 'referrals.create_campaign');
  const canList = action(catalog, 'referrals.list_campaigns');
  const canSetActive = action(catalog, 'referrals.set_campaign_active');
  const canSummary = action(catalog, 'referral.report_summary');
  const canLeaderboard = action(catalog, 'referral.report_leaderboard');
  const canCampaignReport = action(catalog, 'referral.report_campaigns');
  const canAffiliateReport = action(catalog, 'referral.report_affiliates');

  // A GENERATION NUMBER, same reasoning as Points.tsx's own `loadGen` — two overlapping loads
  // (a tab switch right after a save) must not let an older response overwrite a newer one.
  const loadGen = useRef(0);

  const load = () => {
    const gen = ++loadGen.current;
    const current = () => gen === loadGen.current;

    if (canList) {
      call<{ campaigns: Campaign[] }>(session, canList, {})
        .then((x) => { if (current()) setCampaigns(x.campaigns ?? []); })
        .catch(() => { if (current()) setCampaigns(null); });
    } else {
      setCampaigns([]);
    }

    if (canSummary) {
      call<Summary>(session, canSummary, {})
        .then((x) => { if (current()) setSummary(x); })
        .catch(() => { if (current()) setSummary(null); });
    }

    if (canLeaderboard) {
      // THE ROUTE WRAPS THE ARRAY (`{"leaderboard": [...]}`) — see
      // services/operations/app/api/v1/referral_reports.py's own `referral_leaderboard`, verified
      // against the real running service, not assumed from the report SERVICE's own return type.
      call<{ leaderboard: LeaderboardRow[] }>(session, canLeaderboard, {})
        .then((x) => { if (current()) setLeaderboard(x.leaderboard ?? []); })
        .catch(() => { if (current()) setLeaderboard(null); });
    }

    if (canCampaignReport) {
      call<{ campaigns: CampaignBreakdownRow[] }>(session, canCampaignReport, {})
        .then((x) => { if (current()) setCampaignBreakdown(x.campaigns ?? []); })
        .catch(() => { if (current()) setCampaignBreakdown(null); });
    }

    if (canAffiliateReport) {
      call<{ affiliates: AffiliateRow[] }>(session, canAffiliateReport, {})
        .then((x) => { if (current()) setAffiliates(x.affiliates ?? []); })
        .catch(() => { if (current()) setAffiliates(null); });
    }
  };

  useEffect(load, [session, catalog]);

  const toggleActive = async (c: Campaign) => {
    if (!canSetActive) return;
    setSaving(true);
    setError('');
    try {
      await call(session, canSetActive, { campaign_id: c.id, active: !c.active });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('referrals.error.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const createCampaign = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!canCreate) return;
    const form = new FormData(e.currentTarget);
    const num = (name: string, fallback = 0): number => {
      const raw = String(form.get(name) ?? '').trim();
      return raw === '' ? fallback : Number(raw);
    };

    const rewardParams: Record<string, unknown> = {};
    if (rewardType === 'fixed_points' || rewardType === 'cashback_points') {
      rewardParams.points = num('reward_points');
    } else if (rewardType === 'invoice_percentage' || rewardType === 'points_match') {
      rewardParams.percent = num('reward_percent');
    } else if (rewardType === 'milestone_free_item') {
      rewardParams.referrals_required = num('reward_referrals_required', 1);
      rewardParams.service_id = String(form.get('reward_service_id') || '').trim();
      rewardParams.service_name = String(form.get('reward_service_name') || '').trim();
    } else if (rewardType === 'status_multiplier') {
      rewardParams.referrals_required = num('reward_referrals_required', 1);
      rewardParams.multiplier = num('reward_multiplier', 1.5);
    } else if (rewardType === 'time_boost') {
      rewardParams.multiplier = num('reward_multiplier', 1.5);
      // ONE WINDOW IS ENOUGH FOR THIS SCREEN'S OWN BUILDER — the backend accepts any number of
      // windows, but a wizard asking an owner to define a whole weekly schedule for a first
      // campaign is its own separate feature. Sat-Thu, all day, is a safe single default window.
      rewardParams.windows = [{ weekday: num('reward_weekday', 0), start_minute: 0, end_minute: 1440 }];
    } else if (rewardType === 'mystery_box') {
      // TWO OUTCOMES, THE VALIDATOR'S OWN MINIMUM — a fuller box-outcome editor is future work;
      // this is the smallest real, honest mystery box the API accepts.
      rewardParams.outcomes = [
        { points: num('reward_points_a', 50), weight: num('reward_weight_a', 1) },
        { points: num('reward_points_b', 150), weight: num('reward_weight_b', 1) },
      ];
    }

    const ncParams: Record<string, unknown> = ncRewardType === 'discount_percent'
      ? { percent: num('nc_percent', 10) }
      : { points: num('nc_points', 100) };

    setSaving(true);
    setError('');
    try {
      await call(session, canCreate, {
        mode,
        reward_type: rewardType,
        reward_params: rewardParams,
        new_customer_reward_type: ncRewardType,
        new_customer_reward_params: ncParams,
        x_times_limit: mode === 'x_times' ? num('x_times_limit', 1) : 0,
        min_spend_minor: form.get('min_spend_riyals')
          ? (halalas(String(form.get('min_spend_riyals'))) ?? 0) : 0,
        usage_cap_period: String(form.get('cap_period') || ''),
        usage_cap_limit: num('cap_limit', 0),
        cap_scope: String(form.get('cap_scope') || 'campaign'),
      });
      setAdding(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('referrals.error.addFailed'));
    } finally {
      setSaving(false);
    }
  };

  if (isLoading(campaigns)) return <Waiting what={t('referrals.waiting')} />;

  const campaignTitle = (id: string): string => `#${id.slice(0, 8)}`;

  return (
    <div className="flex flex-col gap-5 p-4">
      <PageHeader icon={Share2} title={t('referrals.title')} />

      {/* ── the four/five numbers this programme is judged by ─────────────────────────────────
          `cost_ratio` IS THE ONE THAT CAN TURN WARNING, and never danger — an expensive campaign
          is a pricing decision to revisit, not a fraud signal (referral_reports.py's own module
          docstring: every count here is paired with a currency figure so a raw count is never
          read alone). */}
      {summary ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <KpiCard icon={<UserPlus size={18} />} label={t('referrals.kpi.registered')}
                   value={String(summary.registered_count ?? 0)} />
          <KpiCard icon={<Gift size={18} />} label={t('referrals.kpi.redeemed')}
                   value={String(summary.redeemed_count ?? 0)} />
          <KpiCard icon={<Percent size={18} />} label={t('referrals.kpi.conversion')}
                   value={tf(t, 'referrals.percentValue', { n: Math.round((summary.conversion_rate ?? 0) * 100) })} />
          <KpiCard icon={<Users size={18} />} label={t('referrals.kpi.newCustomers')}
                   value={String(summary.new_customers_acquired ?? 0)} />
          <KpiCard icon={<TrendingUp size={18} />} label={t('referrals.kpi.revenue')}
                   value={riyals(summary.revenue_minor ?? 0)} />
          <KpiCard icon={<Coins size={18} />} label={t('referrals.kpi.costRatio')}
                   tone={(summary.cost_ratio ?? 0) > 0.5 ? 'warning' : 'neutral'}
                   value={tf(t, 'referrals.percentValue', { n: Math.round((summary.cost_ratio ?? 0) * 100) })}
                   hint={(summary.cost_ratio ?? 0) > 0.5 ? t('referrals.kpi.costRatio.hint') : undefined} />
        </div>
      ) : null}

      <TabBar
        fullWidth
        value={tab}
        onChange={setTab}
        options={[
          { value: 'campaigns', label: t('referrals.tab.campaigns') },
          { value: 'leaderboard', label: t('referrals.tab.leaderboard') },
          { value: 'compare', label: t('referrals.tab.compare') },
          { value: 'affiliates', label: t('referrals.tab.affiliates') },
        ]}
      />

      {error ? <p className="text-danger">{error}</p> : null}

      {tab === 'campaigns' ? (
        <section className="flex flex-col gap-3">
          <Head title={t('referrals.campaigns.title')} said={t('referrals.campaigns.said')}
                action={canCreate && !adding
                  ? <Button onClick={() => setAdding(true)}>{t('referrals.campaigns.new')}</Button>
                  : null} />

          {/* A PERMANENT, NON-EDITABLE CALLOUT — never a bug report waiting to happen. The two
              rules below are deliberate policy (core/referral_redemption.py's own module notes,
              lines ~239-307), so this stays on screen whether or not the builder is open. */}
          <Card className="flex flex-col gap-2 p-4">
            <h2 className="text-sm font-semibold">{t('referrals.hint.title')}</h2>
            <p className="text-sm text-text-secondary">{t('referrals.hint.priorDealing')}</p>
            <p className="text-sm text-text-secondary">{t('referrals.hint.newCustomer')}</p>
            <p className="text-sm text-text-secondary">{t('referrals.hint.selfReferral')}</p>
            <AssistantHint anchor="referrals.priorDealing" session={session} />
          </Card>

          {adding ? (
            <form onSubmit={createCampaign}
                  className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
              <Field label={t('referrals.form.mode.label')} htmlFor="rf-mode" hint={t('referrals.form.mode.hint')}>
                <Select id="rf-mode" name="mode" value={mode} onChange={(e) => setMode(e.target.value)}>
                  {MODES.map((m) => <option key={m} value={m}>{modeLabel(t, m)}</option>)}
                </Select>
              </Field>
              {mode === 'x_times' ? (
                <Field label={t('referrals.form.xTimesLimit.label')} htmlFor="rf-xtimes">
                  <Input id="rf-xtimes" name="x_times_limit" type="number" min={1} required dir="ltr" defaultValue={3} />
                </Field>
              ) : null}

              <Field label={t('referrals.form.rewardType.label')} htmlFor="rf-reward">
                <Select id="rf-reward" name="reward_type" value={rewardType}
                        onChange={(e) => setRewardType(e.target.value)}>
                  {REFERRER_REWARD_TYPES.map((r) => <option key={r} value={r}>{rewardTypeLabel(t, r)}</option>)}
                </Select>
              </Field>
              <RewardFields t={t} kind={rewardType} prefix="reward" />

              <Field label={t('referrals.form.newCustomerRewardType.label')} htmlFor="rf-nc-reward">
                <Select id="rf-nc-reward" name="new_customer_reward_type" value={ncRewardType}
                        onChange={(e) => setNcRewardType(e.target.value)}>
                  {NEW_CUSTOMER_REWARD_TYPES.map((r) => <option key={r} value={r}>{rewardTypeLabel(t, r)}</option>)}
                </Select>
              </Field>
              {ncRewardType === 'discount_percent' ? (
                <Field label={t('referrals.form.percent.label')} htmlFor="rf-nc-percent">
                  <Input id="rf-nc-percent" name="nc_percent" type="number" min={1} max={99} required dir="ltr" defaultValue={10} />
                </Field>
              ) : (
                <Field label={t('referrals.form.points.label')} htmlFor="rf-nc-points">
                  <Input id="rf-nc-points" name="nc_points" type="number" min={1} required dir="ltr" defaultValue={100} />
                </Field>
              )}

              <Field label={t('referrals.form.minSpend.label')} htmlFor="rf-minspend">
                <Input id="rf-minspend" name="min_spend_riyals" type="number" min={0} step="0.01" dir="ltr" inputMode="decimal" />
              </Field>

              <Field label={t('referrals.form.capPeriod.label')} htmlFor="rf-capperiod">
                <Select id="rf-capperiod" name="cap_period" defaultValue="">
                  <option value="">—</option>
                  <option value="day">يوم</option>
                  <option value="week">أسبوع</option>
                  <option value="month">شهر</option>
                </Select>
              </Field>
              <Field label={t('referrals.form.capLimit.label')} htmlFor="rf-caplimit">
                <Input id="rf-caplimit" name="cap_limit" type="number" min={0} dir="ltr" defaultValue={0} />
              </Field>
              <Field label={t('referrals.form.capScope.label')} htmlFor="rf-capscope">
                <Select id="rf-capscope" name="cap_scope" defaultValue="campaign">
                  <option value="campaign">{t('referrals.form.capScope.campaign')}</option>
                  <option value="lifetime">{t('referrals.form.capScope.lifetime')}</option>
                </Select>
              </Field>

              <div className="flex gap-2">
                <Button type="submit" disabled={saving}>{t('referrals.form.save')}</Button>
                <Button type="button" variant="ghost" onClick={() => setAdding(false)}>{t('referrals.form.cancel')}</Button>
              </div>
            </form>
          ) : null}

          {campaigns === null ? (
            <EmptyState title={t('referrals.campaigns.loadFailed.title')}
                        description={t('referrals.campaigns.loadFailed.description')} />
          ) : campaigns.length === 0 ? (
            <EmptyState title={t('referrals.campaigns.empty.title')}
                        description={t('referrals.campaigns.empty.description')} />
          ) : (
            <ul className="flex flex-col gap-2">
              {[...campaigns].sort((a, b) => b.created_at - a.created_at).map((c) => (
                <li key={c.id}
                    className={[
                      'flex flex-col gap-2 rounded-card border border-border-subtle bg-surface-1 p-4',
                      c.active ? '' : 'opacity-70',
                    ].join(' ')}>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="flex items-center gap-2">
                      <span className="font-medium">{campaignTitle(c.id)}</span>
                      <Badge tone={c.active ? 'success' : 'warning'}>
                        {c.active ? t('referrals.campaign.active') : t('referrals.campaign.paused')}
                      </Badge>
                    </span>
                    {canSetActive ? (
                      <Button variant="ghost" disabled={saving} onClick={() => toggleActive(c)}>
                        <Power size={16} aria-hidden />
                        {c.active ? t('referrals.campaign.deactivate') : t('referrals.campaign.activate')}
                      </Button>
                    ) : null}
                  </div>

                  <div className="grid gap-1 text-sm text-text-secondary sm:grid-cols-2">
                    <span>{modeLine(t, c)}</span>
                    <span>{t('referrals.campaign.reward')}: {rewardLine(t, c.reward_type, c.reward_params)}</span>
                    <span>{t('referrals.campaign.newCustomerReward')}: {rewardLine(t, c.new_customer_reward_type, c.new_customer_reward_params)}</span>
                    {c.min_spend_minor > 0 ? (
                      <span>{tf(t, 'referrals.campaign.minSpend', { amount: riyals(c.min_spend_minor) })}</span>
                    ) : null}
                    {c.usage_cap_period && c.usage_cap_limit > 0 ? (
                      <span className="flex items-center gap-1">
                        {t('referrals.campaign.cap')}: {tf(t, 'referrals.campaign.cap.value', {
                          limit: String(c.usage_cap_limit), period: periodLabel(c.usage_cap_period),
                        })}
                        <Badge tone="neutral">
                          {c.cap_scope === 'lifetime'
                            ? t('referrals.campaign.cap.scope.lifetime')
                            : t('referrals.campaign.cap.scope.campaign')}
                        </Badge>
                      </span>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : tab === 'leaderboard' ? (
        <section className="flex flex-col gap-3">
          <Head title={t('referrals.leaderboard.title')} said={t('referrals.leaderboard.said')} />
          {!canLeaderboard ? null
            : leaderboard === null || leaderboard === undefined || leaderboard.length === 0 ? (
            <EmptyState title={t('referrals.leaderboard.empty.title')}
                        description={t('referrals.leaderboard.empty.description')} />
          ) : (
            <Table<RankedLeaderboardRow>
              rows={leaderboard.map((r, i) => ({ ...r, rank: i + 1 }))}
              getRowId={(r) => `${r.referrer_phone}-${r.source}`}
              columns={leaderboardColumns(t)}
            />
          )}
        </section>
      ) : tab === 'compare' ? (
        <section className="flex flex-col gap-3">
          <Head title={t('referrals.compare.title')} said={t('referrals.compare.said')} />
          {!canCampaignReport ? null : (
            <Card className="p-4">
              <BarCompare
                items={(campaignBreakdown ?? []).map((c) => ({
                  label: campaignTitle(c.campaign_id), value: c.revenue_minor,
                }))}
                formatValue={(v) => riyals(v)}
              />
            </Card>
          )}
        </section>
      ) : (
        <section className="flex flex-col gap-3">
          <Head title={t('referrals.affiliates.title')} said={t('referrals.affiliates.said')} />
          {!canAffiliateReport ? null
            : affiliates === null || affiliates === undefined || affiliates.length === 0 ? (
            <EmptyState title={t('referrals.affiliates.empty.title')}
                        description={t('referrals.affiliates.empty.description')} />
          ) : (
            <Table<AffiliateRow>
              rows={affiliates}
              getRowId={(r) => r.affiliate_id}
              columns={affiliateColumns(t)}
            />
          )}
        </section>
      )}
    </div>
  );
}

function modeLabel(t: T, m: string): string {
  if (m === 'x_times') return t('referrals.form.xTimesLimit.label');
  return t(`referrals.campaign.mode.${m}`);
}

function modeLine(t: T, c: Campaign): string {
  if (c.mode === 'x_times') return tf(t, 'referrals.campaign.mode.x_times', { n: String(c.x_times_limit) });
  return t(`referrals.campaign.mode.${c.mode}`);
}

function rewardTypeLabel(t: T, r: string): string {
  // NAMED FROM THE SAME LINE THE CARD ALREADY RENDERS, so the select in the builder and the
  // finished campaign's own summary never say the reward differently.
  const sample: Record<string, Record<string, unknown>> = {
    fixed_points: { points: 'ن' }, invoice_percentage: { percent: '٪' }, points_match: { percent: '٪' },
    milestone_free_item: { referrals_required: 'ن', service_name: '' }, cashback_points: { points: 'ن' },
    status_multiplier: { referrals_required: 'ن', multiplier: 'x' }, time_boost: { multiplier: 'x' },
    mystery_box: { outcomes: [] }, discount_percent: { percent: '٪' }, welcome_points: { points: 'ن' },
  };
  return rewardLine(t, r, sample[r] ?? {});
}

function periodLabel(period: string): string {
  return period === 'day' ? 'يوم' : period === 'week' ? 'أسبوع' : period === 'month' ? 'شهر' : period;
}

/** The reward-type-specific inputs, shared by the referrer reward form. */
function RewardFields({ t, kind, prefix }: { t: T; kind: string; prefix: string }) {
  if (kind === 'fixed_points' || kind === 'cashback_points') {
    return (
      <Field label={t('referrals.form.points.label')} htmlFor={`${prefix}-points`}>
        <Input id={`${prefix}-points`} name={`${prefix}_points`} type="number" min={1} required dir="ltr" defaultValue={100} />
      </Field>
    );
  }
  if (kind === 'invoice_percentage' || kind === 'points_match') {
    return (
      <Field label={t('referrals.form.percent.label')} htmlFor={`${prefix}-percent`}>
        <Input id={`${prefix}-percent`} name={`${prefix}_percent`} type="number" min={1} max={99} required dir="ltr" defaultValue={10} />
      </Field>
    );
  }
  if (kind === 'milestone_free_item') {
    return (
      <>
        <Field label={t('referrals.form.referralsRequired.label')} htmlFor={`${prefix}-req`}>
          <Input id={`${prefix}-req`} name={`${prefix}_referrals_required`} type="number" min={1} required dir="ltr" defaultValue={3} />
        </Field>
        <Field label={t('referrals.form.serviceId.label')} htmlFor={`${prefix}-sid`}>
          <Input id={`${prefix}-sid`} name={`${prefix}_service_id`} required />
        </Field>
        <Field label={t('referrals.form.serviceName.label')} htmlFor={`${prefix}-sname`}>
          <Input id={`${prefix}-sname`} name={`${prefix}_service_name`} required />
        </Field>
      </>
    );
  }
  if (kind === 'status_multiplier' || kind === 'time_boost') {
    return (
      <>
        {kind === 'status_multiplier' ? (
          <Field label={t('referrals.form.referralsRequired.label')} htmlFor={`${prefix}-req`}>
            <Input id={`${prefix}-req`} name={`${prefix}_referrals_required`} type="number" min={1} required dir="ltr" defaultValue={5} />
          </Field>
        ) : null}
        <Field label={t('referrals.form.multiplier.label')} htmlFor={`${prefix}-mult`}>
          <Input id={`${prefix}-mult`} name={`${prefix}_multiplier`} type="number" min={1.01} max={10} step="0.1" required dir="ltr" defaultValue={1.5} />
        </Field>
      </>
    );
  }
  // mystery_box: two fixed outcomes — see createCampaign's own note on why this stays minimal.
  return (
    <p className="text-sm text-text-secondary">
      {rewardLine(t, 'mystery_box', { outcomes: [{}, {}] })}
    </p>
  );
}

function leaderboardColumns(t: T): TableColumn<RankedLeaderboardRow>[] {
  return [
    {
      key: 'rank', header: t('referrals.leaderboard.col.rank'),
      render: (r) => `#${r.rank}`, hideOnCard: true, width: '48px',
    },
    {
      key: 'referrer', header: t('referrals.leaderboard.col.referrer'),
      render: (r) => (
        // TOP PERFORMER, IN THE CONSOLE'S OWN CELEBRATORY/GIFT ACCENT — the same `gift` token
        // `theme.config.ts` reserves for exactly this kind of "something to be pleased about"
        // moment, never the ordinary accent.
        <span className="flex items-center gap-2">
          {r.rank === 1 ? (
            <Badge className="bg-gift-soft text-gift-on-soft">{t('referrals.leaderboard.top')}</Badge>
          ) : null}
          {tf(t, 'referrals.leaderboard.phoneMasked', { last4: maskPhone(r.referrer_phone) })}
        </span>
      ),
    },
    {
      key: 'source', header: t('referrals.leaderboard.col.source'),
      render: (r) => (
        <Badge tone="neutral">
          {r.source === 'affiliate' ? t('referrals.leaderboard.source.affiliate') : t('referrals.leaderboard.source.referral')}
        </Badge>
      ),
    },
    { key: 'redemptions', header: t('referrals.leaderboard.col.redemptions'), render: (r) => String(r.redemptions) },
    { key: 'revenue', header: t('referrals.leaderboard.col.revenue'), render: (r) => riyals(r.revenue_minor) },
  ];
}

function affiliateColumns(t: T): TableColumn<AffiliateRow>[] {
  return [
    { key: 'code', header: t('referrals.affiliates.col.code'), render: (r) => r.code },
    {
      key: 'phone', header: t('referrals.affiliates.col.phone'),
      render: (r) => tf(t, 'referrals.leaderboard.phoneMasked', { last4: maskPhone(r.phone) }),
    },
    {
      key: 'status', header: t('referrals.affiliates.col.status'),
      render: (r) => (
        <Badge tone={r.active ? 'success' : 'warning'}>
          {r.active ? t('referrals.affiliates.active') : t('referrals.affiliates.inactive')}
        </Badge>
      ),
    },
    { key: 'redemptions', header: t('referrals.affiliates.col.redemptions'), render: (r) => String(r.redemptions) },
    { key: 'revenue', header: t('referrals.affiliates.col.revenue'), render: (r) => riyals(r.revenue_minor) },
    { key: 'unsettled', header: t('referrals.affiliates.col.unsettled'), render: (r) => String(r.unsettled_points) },
    { key: 'lifetime', header: t('referrals.affiliates.col.lifetime'), render: (r) => String(r.total_earned_points), hideOnCard: true },
  ];
}

/** A section's heading — same component Points.tsx already defines locally; kept as a copy here
 *  rather than a shared export since neither screen imports the other. */
function Head({ title, said, action }: { title: string; said?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-2 px-1">
      <span className="flex min-w-0 flex-col gap-0.5">
        <h2 className="text-base font-semibold">{title}</h2>
        {said ? <span className="text-sm text-text-secondary">{said}</span> : null}
      </span>
      {action}
    </div>
  );
}
