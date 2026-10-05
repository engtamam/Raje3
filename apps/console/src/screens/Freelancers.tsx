/**
 * «خدمات ما بعد البيع» — core/freelancer_service.py + core/freelancer_crm.py's own module
 * docstrings. A shop hands post-visit customer follow-up to an EXTERNAL freelancer it brought in
 * itself (max 3 linked, deactivate never delete, no marketplace, no ranking).
 *
 * TWO TABS, ONE DATA MODEL — never two screens. «المستقلون» is link management (add/deactivate,
 * the business rules, the reward catalog, the escalation inbox): shop-staff-only actions, gated on
 * `operations.freelancer_manage`. «سجل العمل» is the SAME customer roster/actions a freelancer's
 * own phone screen would show (api/v1/freelancer_portal.py's own module docstring: "ONE engine,
 * two doors") — built here so staff can do everything a freelancer can, from the console, without
 * a second implementation anywhere. Both tabs reach the same backend action set; the split is
 * purely "who manages the arrangement" vs "who does the daily follow-up work", not a permission
 * split a `require_any_capability` route cares about.
 *
 * EASIEST POSSIBLE DAILY LOOP, BY DESIGN (owner's own instruction, 2026-10-05: "اسهل ما يمكن"):
 * - The cooldown filter is INVISIBLE — a customer who should not be called today never appears;
 *   nobody has to remember the rule or compute it by hand.
 * - Every action (rate / escalate / grant / note) lives ON the customer's own card — no second
 *   screen per action, no navigating away and losing the list's scroll position.
 * - The daily-reward counter is shown BEFORE a grant is attempted, not after it is refused — a
 *   quiet "تبقى 2 ترضيات اليوم" line, never a surprise 400 at the worst moment.
 * - Open escalations surface in a dedicated, always-visible box at the top of «سجل العمل» — never
 *   buried in a tab the shop has to remember to check.
 *
 * SMART FILTERS (owner's own request) — one search box (name OR phone, server-side, case-
 * insensitive) plus a last-contact-status filter («جديد لم يُتَّصل به» / راضٍ / محايد / غير راضٍ),
 * both read straight off `filtered_customers`'s own `search`/`status_filter` params
 * (core/freelancer_crm.py) — never client-side guessing over a partial page, since the roster is
 * already server-filtered by cooldown before anything else happens to it.
 */
import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle, ChevronDown, Gift, Headphones, Percent, Phone, Plus, Search, Settings2,
  ThumbsDown, ThumbsUp, UserX,
} from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { PageHeader } from '../rj-ui/PageHeader';
import { Card } from '../rj-ui/Card';
import { TabBar } from '../rj-ui/TabBar';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { Modal } from '../rj-ui/Modal';
import { Field, Input } from '../rj-ui/Field';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import './freelancers-i18n';

interface FreelancerLink {
  id: string; tenant: string; phone: string; display_name: string; active: boolean; created: number;
}
interface Rules {
  cooldown_days: number; daily_cap: number; quiet_start_minute: number; quiet_end_minute: number;
}
interface RewardOption {
  id: string; kind: 'discount' | 'points' | 'gift'; label: string; percent: number; points: number;
  active: boolean;
}
interface Escalation {
  id: string; customer_id: string; freelancer_phone: string; note: string; status: string;
  created: number; resolution_note?: string;
}
interface CustomerRow {
  customer_id: string; name: string; phone: string; last_visit: number; last_status: string;
}

const RATINGS = ['satisfied', 'neutral', 'unsatisfied'] as const;
const RATING_TONE: Record<string, 'success' | 'neutral' | 'danger'> = {
  satisfied: 'success', neutral: 'neutral', unsatisfied: 'danger',
};
const RATING_ICON: Record<string, typeof ThumbsUp> = {
  satisfied: ThumbsUp, neutral: AlertTriangle, unsatisfied: ThumbsDown,
};

function formatDate(ts: number, locale: string): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleDateString(locale === 'ar' ? 'ar-SA' : locale, {
    day: 'numeric', month: 'short', year: 'numeric',
  });
}

export function FreelancersScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t, locale } = useOperatorI18n();
  const [tab, setTab] = useState<'roster' | 'workbench'>('roster');

  const listAction = action(catalog, 'operations.freelancer_list');
  if (!listAction) return null;

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <PageHeader icon={Headphones} title={t('fl.title')} />
          <p className="mt-1 text-sm text-text-secondary">{t('fl.subtitle')}</p>
        </div>
        <TabBar
          value={tab} onChange={setTab} ariaLabel={t('fl.title')}
          options={[
            { value: 'roster', label: t('fl.tab.roster') },
            { value: 'workbench', label: t('fl.tab.workbench') },
          ]}
        />
      </div>

      {tab === 'roster' ? (
        <RosterTab session={session} catalog={catalog} listAction={listAction} t={t} locale={locale} />
      ) : (
        <WorkbenchTab session={session} catalog={catalog} t={t} locale={locale} />
      )}
    </div>
  );
}

// ── «المستقلون» — link management, rules, reward catalog, escalation inbox ────────────────────
function RosterTab({ session, catalog, listAction, t, locale }: {
  session: Session; catalog: Catalog; listAction: NonNullable<ReturnType<typeof action>>;
  t: (k: string) => string; locale: string;
}) {
  const addAction = action(catalog, 'operations.freelancer_add');
  const deactivateAction = action(catalog, 'operations.freelancer_deactivate');
  const rulesGetAction = action(catalog, 'operations.freelancer_rules_get');
  const rulesSetAction = action(catalog, 'operations.freelancer_rules_set');
  const optionsListAction = action(catalog, 'operations.freelancer_reward_options_list');
  const optionAddAction = action(catalog, 'operations.freelancer_reward_option_add');
  const escalationsAction = action(catalog, 'operations.freelancer_escalations_list');
  const resolveAction = action(catalog, 'operations.freelancer_escalation_resolve');
  const exportAction = action(catalog, 'operations.freelancer_notes_export');

  const [rows, setRows] = useState<FreelancerLink[] | 'loading' | 'failed'>('loading');
  const [rules, setRules] = useState<Rules | null>(null);
  const [options, setOptions] = useState<RewardOption[]>([]);
  const [escalations, setEscalations] = useState<Escalation[] | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [showRules, setShowRules] = useState(false);
  const [showOptions, setShowOptions] = useState(false);
  const [showExport, setShowExport] = useState(false);

  const reload = () => {
    setRows('loading');
    call<{ freelancers: FreelancerLink[] }>(session, listAction)
      .then((x) => setRows(x.freelancers)).catch(() => setRows('failed'));
  };
  useEffect(reload, [session, catalog]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!rulesGetAction) return;
    call<Rules>(session, rulesGetAction).then(setRules).catch(() => setRules(null));
  }, [session, catalog, rulesGetAction]);

  useEffect(() => {
    if (!optionsListAction) return;
    call<{ options: RewardOption[] }>(session, optionsListAction)
      .then((x) => setOptions(x.options)).catch(() => setOptions([]));
  }, [session, catalog, optionsListAction]);

  useEffect(() => {
    if (!escalationsAction) { setEscalations(null); return; }
    call<{ escalations: Escalation[] }>(session, escalationsAction, { status_filter: 'open' })
      .then((x) => setEscalations(x.escalations)).catch(() => setEscalations(null));
  }, [session, catalog, escalationsAction]);

  const active = Array.isArray(rows) ? rows.filter((r) => r.active) : [];
  const slotsOpen = Math.max(0, 3 - active.length);

  async function deactivate(id: string) {
    if (!deactivateAction) return;
    // eslint-disable-next-line no-alert -- same window.confirm idiom MutualBenefit.tsx uses
    if (!window.confirm(t('fl.roster.confirmDeactivate'))) return;
    await call(session, deactivateAction, { link_id: id });
    reload();
  }

  return (
    <div className="flex flex-col gap-4">
      {escalations && escalations.length > 0 ? (
        <Card className="flex flex-col gap-2 border-danger/30 bg-danger-soft p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-danger" />
            <p className="text-sm font-bold text-danger">
              {tf(t, 'fl.escalations.open', { n: escalations.length })}
            </p>
          </div>
          <div className="flex flex-col gap-2">
            {escalations.map((e) => (
              <div key={e.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-surface-1 p-3">
                <div>
                  <p className="text-sm">{e.note}</p>
                  <p className="text-xs text-text-tertiary">{formatDate(e.created, locale)}</p>
                </div>
                {resolveAction ? (
                  <Button size="sm" onClick={async () => {
                    await call(session, resolveAction, { escalation_id: e.id });
                    setEscalations((cur) => cur ? cur.filter((x) => x.id !== e.id) : cur);
                  }}>
                    {t('fl.escalations.resolve')}
                  </Button>
                ) : null}
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {rulesGetAction ? (
          <Button variant="ghost" size="sm" onClick={() => setShowRules(true)}>
            <Settings2 size={14} /> {t('fl.roster.rulesButton')}
          </Button>
        ) : null}
        {optionsListAction ? (
          <Button variant="ghost" size="sm" onClick={() => setShowOptions(true)}>
            <Gift size={14} /> {t('fl.roster.optionsButton')}
          </Button>
        ) : null}
        {exportAction ? (
          <Button variant="ghost" size="sm" onClick={() => setShowExport(true)}>
            {t('fl.roster.exportButton')}
          </Button>
        ) : null}
      </div>

      {rows === 'failed' ? (
        <EmptyState title={t('fl.roster.failedTitle')} />
      ) : rows === 'loading' ? null : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {active.map((f) => (
            <Card key={f.id} className="flex flex-col gap-2 p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-bold">{f.display_name}</p>
                <Badge tone="success">{t('fl.roster.active')}</Badge>
              </div>
              <p className="flex items-center gap-1.5 text-xs text-text-secondary">
                <Phone size={12} /> {f.phone}
              </p>
              {deactivateAction ? (
                <Button variant="ghost" size="sm" onClick={() => deactivate(f.id)} className="mt-1 self-start">
                  <UserX size={14} /> {t('fl.roster.deactivate')}
                </Button>
              ) : null}
            </Card>
          ))}

          {slotsOpen > 0 && addAction ? (
            <button type="button" onClick={() => setShowAdd(true)}
                   className="flex min-h-32 flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed border-border-subtle p-4 text-text-tertiary transition-colors hover:border-accent hover:text-accent">
              <Plus size={20} />
              <span className="text-sm font-medium">{t('fl.roster.addButton')}</span>
            </button>
          ) : null}
        </div>
      )}

      {Array.isArray(rows) && active.length === 0 ? (
        <EmptyState title={t('fl.roster.emptyTitle')} description={t('fl.roster.emptyDesc')} />
      ) : null}

      {addAction ? (
        <AddFreelancerModal open={showAdd} onClose={() => setShowAdd(false)} session={session}
                            addAction={addAction} onAdded={reload} t={t} />
      ) : null}
      {rulesSetAction && rules ? (
        <RulesModal open={showRules} onClose={() => setShowRules(false)} session={session}
                   rules={rules} setRulesAction={rulesSetAction}
                   onSaved={(r) => { setRules(r); setShowRules(false); }} t={t} />
      ) : null}
      {optionAddAction ? (
        <RewardOptionsModal open={showOptions} onClose={() => setShowOptions(false)} session={session}
                            options={options} addAction={optionAddAction}
                            onAdded={(o) => setOptions((cur) => [...cur, o])} t={t} />
      ) : null}
      {exportAction ? (
        <ExportModal open={showExport} onClose={() => setShowExport(false)} session={session}
                    exportAction={exportAction} t={t} />
      ) : null}
    </div>
  );
}

function AddFreelancerModal({ open, onClose, session, addAction, onAdded, t }: {
  open: boolean; onClose: () => void; session: Session;
  addAction: NonNullable<ReturnType<typeof action>>; onAdded: () => void; t: (k: string) => string;
}) {
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const valid = phone.trim().length >= 9 && name.trim().length > 0;

  async function onSubmit() {
    if (!valid || busy) return;
    setBusy(true); setError('');
    try {
      await call(session, addAction, { phone: phone.trim(), display_name: name.trim() });
      setPhone(''); setName(''); onAdded(); onClose();
    } catch {
      setError(t('fl.add.failed'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={t('fl.add.title')}
          footer={<Button onClick={onSubmit} disabled={!valid || busy} className="w-full">
            {busy ? t('fl.add.submitting') : t('fl.add.submit')}
          </Button>}>
      <div className="flex flex-col gap-3">
        <Field label={t('fl.add.nameLabel')}>
          <Input value={name} onChange={(e) => setName(e.target.value)}
                placeholder={t('fl.add.namePlaceholder')} />
        </Field>
        <Field label={t('fl.add.phoneLabel')}>
          <Input type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
                placeholder={t('fl.add.phonePlaceholder')} />
        </Field>
        <p className="text-xs text-text-tertiary">{t('fl.add.note')}</p>
        {error ? <p className="text-xs text-danger">{error}</p> : null}
      </div>
    </Modal>
  );
}

function RulesModal({ open, onClose, session, rules, setRulesAction, onSaved, t }: {
  open: boolean; onClose: () => void; session: Session; rules: Rules;
  setRulesAction: NonNullable<ReturnType<typeof action>>; onSaved: (r: Rules) => void;
  t: (k: string) => string;
}) {
  const [cooldown, setCooldown] = useState(rules.cooldown_days);
  const [cap, setCap] = useState(rules.daily_cap);
  const [busy, setBusy] = useState(false);

  async function onSave() {
    setBusy(true);
    try {
      const r = await call<Rules>(session, setRulesAction, { cooldown_days: cooldown, daily_cap: cap });
      onSaved(r);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={t('fl.rules.title')}
          footer={<Button onClick={onSave} disabled={busy} className="w-full">
            {busy ? t('fl.rules.saving') : t('fl.rules.save')}
          </Button>}>
      <div className="flex flex-col gap-4">
        <Field label={t('fl.rules.cooldownLabel')}>
          <Input type="number" min={0} value={cooldown}
                onChange={(e) => setCooldown(Math.max(0, Number(e.target.value) || 0))}
                className="tabular-nums" />
          <p className="mt-1 text-xs text-text-tertiary">{t('fl.rules.cooldownHelp')}</p>
        </Field>
        <Field label={t('fl.rules.capLabel')}>
          <Input type="number" min={0} value={cap}
                onChange={(e) => setCap(Math.max(0, Number(e.target.value) || 0))}
                className="tabular-nums" />
          <p className="mt-1 text-xs text-text-tertiary">{t('fl.rules.capHelp')}</p>
        </Field>
      </div>
    </Modal>
  );
}

function RewardOptionsModal({ open, onClose, session, options, addAction, onAdded, t }: {
  open: boolean; onClose: () => void; session: Session; options: RewardOption[];
  addAction: NonNullable<ReturnType<typeof action>>; onAdded: (o: RewardOption) => void;
  t: (k: string) => string;
}) {
  const [kind, setKind] = useState<RewardOption['kind']>('gift');
  const [label, setLabel] = useState('');
  const [percent, setPercent] = useState(10);
  const [points, setPoints] = useState(50);
  const [busy, setBusy] = useState(false);
  const valid = label.trim().length > 0
    && (kind !== 'discount' || (percent > 0 && percent <= 100))
    && (kind !== 'points' || points > 0);

  async function onSubmit() {
    if (!valid || busy) return;
    setBusy(true);
    try {
      const o = await call<RewardOption>(session, addAction, {
        kind, label: label.trim(), percent: kind === 'discount' ? percent : 0,
        points: kind === 'points' ? points : 0,
      });
      onAdded(o); setLabel('');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={t('fl.options.title')} size="lg">
      <div className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          {options.map((o) => (
            <div key={o.id} className="flex items-center gap-2 rounded-lg border border-border-subtle p-2.5 text-sm">
              {o.kind === 'gift' ? <Gift size={14} className="text-success" />
               : o.kind === 'points' ? <Badge tone="accent">{o.points}</Badge>
               : <Percent size={14} className="text-warning" />}
              <span>{o.label}</span>
            </div>
          ))}
          {options.length === 0 ? <p className="text-xs text-text-tertiary">{t('fl.options.empty')}</p> : null}
        </div>

        <div className="flex flex-wrap items-end gap-3 border-t border-border-subtle pt-4">
          <Field label={t('fl.options.kindLabel')}>
            <select value={kind} onChange={(e) => setKind(e.target.value as RewardOption['kind'])}
                   className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
              <option value="gift">{t('fl.options.kind.gift')}</option>
              <option value="points">{t('fl.options.kind.points')}</option>
              <option value="discount">{t('fl.options.kind.discount')}</option>
            </select>
          </Field>
          <Field label={t('fl.options.labelLabel')}>
            <Input value={label} onChange={(e) => setLabel(e.target.value)}
                  placeholder={t('fl.options.labelPlaceholder')} className="w-40" />
          </Field>
          {kind === 'discount' ? (
            <Field label={t('fl.options.percentLabel')}>
              <Input type="number" min={1} max={100} value={percent}
                    onChange={(e) => setPercent(Number(e.target.value) || 0)} className="w-20 tabular-nums" />
            </Field>
          ) : null}
          {kind === 'points' ? (
            <Field label={t('fl.options.pointsLabel')}>
              <Input type="number" min={1} value={points}
                    onChange={(e) => setPoints(Number(e.target.value) || 0)} className="w-24 tabular-nums" />
            </Field>
          ) : null}
          <Button onClick={onSubmit} disabled={!valid || busy}>
            {busy ? t('fl.options.submitting') : t('fl.options.submit')}
          </Button>
        </div>
      </div>
    </Modal>
  );
}

const EXPORT_PRESETS = [
  { value: 'week', days: 7 }, { value: 'month', days: 30 },
  { value: '90d', days: 90 }, { value: 'year', days: 365 },
] as const;

function ExportModal({ open, onClose, session, exportAction, t }: {
  open: boolean; onClose: () => void; session: Session;
  exportAction: NonNullable<ReturnType<typeof action>>; t: (k: string) => string;
}) {
  const [preset, setPreset] = useState<string>('month');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');
  const [includePii, setIncludePii] = useState(false);
  const [text, setText] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onRun() {
    setBusy(true); setText(null);
    try {
      const now = Math.floor(Date.now() / 1000);
      let since: number, until: number;
      if (preset === 'custom') {
        since = customStart ? Math.floor(new Date(customStart).getTime() / 1000) : 0;
        until = customEnd ? Math.floor(new Date(customEnd).getTime() / 1000) + 86400 : now;
      } else {
        const p = EXPORT_PRESETS.find((x) => x.value === preset)!;
        since = now - p.days * 86400; until = now;
      }
      const r = await call<{ text: string }>(session, exportAction, { since, until, include_pii: includePii });
      setText(r.text);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={t('fl.export.title')} size="lg">
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2">
          {EXPORT_PRESETS.map((p) => (
            <button key={p.value} type="button" onClick={() => setPreset(p.value)}
                   className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                     preset === p.value ? 'bg-accent text-accent-contrast' : 'bg-surface-2 text-text-secondary'
                   }`}>
              {t(`fl.export.preset.${p.value}`)}
            </button>
          ))}
          <button type="button" onClick={() => setPreset('custom')}
                 className={`rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                   preset === 'custom' ? 'bg-accent text-accent-contrast' : 'bg-surface-2 text-text-secondary'
                 }`}>
            {t('fl.export.preset.custom')}
          </button>
        </div>

        {preset === 'custom' ? (
          <div className="flex flex-wrap items-end gap-3">
            <Field label={t('fl.export.fromLabel')}>
              <Input type="date" value={customStart} onChange={(e) => setCustomStart(e.target.value)} />
            </Field>
            <Field label={t('fl.export.toLabel')}>
              <Input type="date" value={customEnd} onChange={(e) => setCustomEnd(e.target.value)} />
            </Field>
          </div>
        ) : null}

        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={includePii} onChange={(e) => setIncludePii(e.target.checked)} />
          {t('fl.export.includePii')}
        </label>

        <Button onClick={onRun} disabled={busy}>{busy ? t('fl.export.running') : t('fl.export.run')}</Button>

        {text !== null ? (
          text ? (
            <textarea readOnly value={text} rows={10}
                     className="w-full rounded-lg border border-border-subtle bg-surface-2 p-3 text-xs" />
          ) : (
            <p className="text-xs text-text-tertiary">{t('fl.export.empty')}</p>
          )
        ) : null}
      </div>
    </Modal>
  );
}

// ── «سجل العمل» — the internal mirror of the freelancer's own screen ──────────────────────────
function WorkbenchTab({ session, catalog, t, locale }: {
  session: Session; catalog: Catalog; t: (k: string) => string; locale: string;
}) {
  const customersAction = action(catalog, 'operations.freelancer_portal_customers');
  const rateAction = action(catalog, 'operations.freelancer_portal_rate');
  const dndAction = action(catalog, 'operations.freelancer_portal_dnd');
  const rewardAction = action(catalog, 'operations.freelancer_portal_reward');
  const escalateAction = action(catalog, 'operations.freelancer_portal_escalate');
  const noteAction = action(catalog, 'operations.freelancer_portal_note_add');
  const optionsListAction = action(catalog, 'operations.freelancer_reward_options_list');
  const rulesGetAction = action(catalog, 'operations.freelancer_rules_get');

  const [rows, setRows] = useState<CustomerRow[] | 'loading' | 'failed'>('loading');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [options, setOptions] = useState<RewardOption[]>([]);
  const [rules, setRules] = useState<Rules | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!customersAction) return null;

  const reload = () => {
    setRows('loading');
    call<{ customers: CustomerRow[] }>(session, customersAction, {
      search, status_filter: statusFilter,
    }).then((x) => setRows(x.customers)).catch(() => setRows('failed'));
  };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(reload, [session, catalog, search, statusFilter]);

  useEffect(() => {
    if (!optionsListAction) return;
    call<{ options: RewardOption[] }>(session, optionsListAction)
      .then((x) => setOptions(x.options)).catch(() => setOptions([]));
  }, [session, catalog, optionsListAction]);

  useEffect(() => {
    if (!rulesGetAction) return;
    call<Rules>(session, rulesGetAction).then(setRules).catch(() => setRules(null));
  }, [session, catalog, rulesGetAction]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1">
          <Search size={16} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-text-tertiary" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)}
                placeholder={t('fl.work.searchPlaceholder')} className="ps-9" />
        </div>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
               className="rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
          <option value="">{t('fl.work.filter.all')}</option>
          <option value="new">{t('fl.work.filter.new')}</option>
          {RATINGS.map((r) => <option key={r} value={r}>{t(`fl.rating.${r}`)}</option>)}
        </select>
      </div>

      {rows === 'failed' ? (
        <EmptyState title={t('fl.work.failedTitle')} />
      ) : rows === 'loading' ? null : rows.length === 0 ? (
        <EmptyState title={t('fl.work.emptyTitle')} description={t('fl.work.emptyDesc')} />
      ) : (
        <motion.div initial="hidden" animate="show"
                   variants={{ show: { transition: { staggerChildren: 0.04 } } }}
                   className="flex flex-col gap-2">
          {rows.map((c) => (
            <motion.div key={c.customer_id}
                       variants={{ hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0 } }}>
              <CustomerCard
                session={session} customer={c} options={options} rules={rules}
                expanded={expanded === c.customer_id}
                onToggle={() => setExpanded((cur) => (cur === c.customer_id ? null : c.customer_id))}
                rateAction={rateAction} dndAction={dndAction} rewardAction={rewardAction}
                escalateAction={escalateAction} noteAction={noteAction}
                onActed={reload} t={t} locale={locale}
              />
            </motion.div>
          ))}
        </motion.div>
      )}
    </div>
  );
}

function CustomerCard({
  session, customer, options, rules, expanded, onToggle,
  rateAction, dndAction, rewardAction, escalateAction, noteAction, onActed, t, locale,
}: {
  session: Session; customer: CustomerRow; options: RewardOption[]; rules: Rules | null;
  expanded: boolean; onToggle: () => void;
  rateAction: ReturnType<typeof action>; dndAction: ReturnType<typeof action>;
  rewardAction: ReturnType<typeof action>; escalateAction: ReturnType<typeof action>;
  noteAction: ReturnType<typeof action>; onActed: () => void;
  t: (k: string) => string; locale: string;
}) {
  const [busy, setBusy] = useState(false);
  const [noteText, setNoteText] = useState('');
  const [escalateText, setEscalateText] = useState('');
  const [error, setError] = useState('');

  async function rate(status: string) {
    if (!rateAction || busy) return;
    setBusy(true); setError('');
    try { await call(session, rateAction, { customer_id: customer.customer_id, status }); onActed(); }
    catch { setError(t('fl.work.actionFailed')); } finally { setBusy(false); }
  }

  async function dnd() {
    if (!dndAction || busy) return;
    // eslint-disable-next-line no-alert -- same window.confirm idiom MutualBenefit.tsx uses
    if (!window.confirm(t('fl.work.confirmDnd'))) return;
    setBusy(true);
    try { await call(session, dndAction, { customer_id: customer.customer_id }); onActed(); }
    finally { setBusy(false); }
  }

  async function grant(optionId: string) {
    if (!rewardAction || busy) return;
    setBusy(true); setError('');
    try {
      await call(session, rewardAction, { customer_id: customer.customer_id, option_id: optionId });
      onActed();
    } catch { setError(t('fl.work.capReached')); } finally { setBusy(false); }
  }

  async function escalate() {
    if (!escalateAction || !escalateText.trim() || busy) return;
    setBusy(true);
    try {
      await call(session, escalateAction, { customer_id: customer.customer_id, note: escalateText.trim() });
      setEscalateText(''); onActed();
    } finally { setBusy(false); }
  }

  async function addNote() {
    if (!noteAction || !noteText.trim() || busy) return;
    setBusy(true);
    try {
      await call(session, noteAction, {
        customer_id: customer.customer_id, text: noteText.trim(), status: customer.last_status || 'neutral',
      });
      setNoteText('');
    } finally { setBusy(false); }
  }

  return (
    <Card interactive={false} className="flex flex-col gap-0 overflow-hidden p-0">
      <button type="button" onClick={onToggle}
             className="flex w-full items-center justify-between gap-3 p-3.5 text-start transition-colors hover:bg-surface-2">
        <div>
          <p className="text-sm font-bold">{customer.name || customer.phone}</p>
          <p className="text-xs text-text-secondary">
            {tf(t, 'fl.work.lastVisit', { date: formatDate(customer.last_visit, locale) })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {customer.last_status ? (
            <Badge tone={RATING_TONE[customer.last_status] ?? 'neutral'}>
              {t(`fl.rating.${customer.last_status}`)}
            </Badge>
          ) : (
            <Badge tone="neutral">{t('fl.work.filter.new')}</Badge>
          )}
          <motion.span animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.18 }}>
            <ChevronDown size={16} className="text-text-tertiary" />
          </motion.span>
        </div>
      </button>

      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }}
                     exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2, ease: 'easeOut' }}
                     className="overflow-hidden border-t border-border-subtle">
            <div className="flex flex-col gap-3 p-4">
              <div className="flex flex-wrap items-center gap-2">
                {RATINGS.map((r) => {
                  const Icon = RATING_ICON[r];
                  return (
                    <Button key={r} size="sm" variant={customer.last_status === r ? 'solid' : 'ghost'}
                           disabled={busy} onClick={() => rate(r)}>
                      <Icon size={14} /> {t(`fl.rating.${r}`)}
                    </Button>
                  );
                })}
                {dndAction ? (
                  <Button size="sm" variant="ghost" disabled={busy} onClick={dnd}>
                    <UserX size={14} /> {t('fl.work.dnd')}
                  </Button>
                ) : null}
              </div>

              {rewardAction && options.length > 0 ? (
                <div className="flex flex-col gap-1.5">
                  <p className="text-xs font-bold text-text-secondary">{t('fl.work.rewardTitle')}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {options.map((o) => (
                      <Button key={o.id} size="sm" variant="ghost" disabled={busy} onClick={() => grant(o.id)}>
                        {o.kind === 'gift' ? <Gift size={13} /> : o.kind === 'points' ? null : <Percent size={13} />}
                        {o.label}
                      </Button>
                    ))}
                  </div>
                </div>
              ) : null}

              {noteAction ? (
                <div className="flex gap-2">
                  <Input value={noteText} onChange={(e) => setNoteText(e.target.value)}
                        placeholder={t('fl.work.notePlaceholder')} className="flex-1" />
                  <Button size="sm" disabled={!noteText.trim() || busy} onClick={addNote}>
                    {t('fl.work.noteSave')}
                  </Button>
                </div>
              ) : null}

              {escalateAction ? (
                <div className="flex gap-2 border-t border-border-subtle pt-3">
                  <Input value={escalateText} onChange={(e) => setEscalateText(e.target.value)}
                        placeholder={t('fl.work.escalatePlaceholder')} className="flex-1" />
                  <Button size="sm" variant="danger" disabled={!escalateText.trim() || busy} onClick={escalate}>
                    <AlertTriangle size={13} /> {t('fl.work.escalate')}
                  </Button>
                </div>
              ) : null}

              {error ? <p className="text-xs text-danger">{error}</p> : null}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </Card>
  );
}
