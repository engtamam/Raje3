/**
 * «نقاطي» — the rewards table, and what a visit is worth.
 *
 * IT ARRIVES PRE-FILLED ("100 points = an exterior wash, 300 = polish"). He edits a
 * number, switches one off, or adds one — and never starts from a blank page (§10.8). So the empty
 * state here is not an invitation to build a programme; it is a fault, the same as an empty
 * service catalogue, and it says so.
 *
 * WHAT THIS SCREEN USED TO BE, AND WHY IT WAS WRONG. It listed rewards and nothing else: no edit,
 * no retire, no add, no earning settings — while §9.2, §9.3 and §9.4 describe all four, and every
 * one of the actions was already in the catalogue and simply never called. It also read
 * `cost_points`, a field the API does not have, so the day a reward existed every row would have
 * said «undefined نقطة». A read-only screen over a writable API is not a simpler product; it is a
 * promise the owner cannot act on.
 *
 * TWO TABS, AND THE ORDER IS THE ARGUMENT. «المكافآت» is what he came for — the thing his customer
 * asks about at the counter. «الكسب» is the rarer decision, set once and revisited on a quiet day
 * (§10.8: whoever wants to work fast must be able to, without going deeper).
 *
 * AND THE SECTION IS ABSENT ENTIRELY WITHOUT feature.loyalty rather than shown disabled. The nav
 * decides that from the catalogue, so this file never asks — it is only ever rendered for a shop
 * that has the programme.
 */
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Badge } from '../rj-ui/Badge';
import { Card } from '../rj-ui/Card';
import { halalas } from '../money';
import { KpiCard } from '../rj-ui/KpiCard';
import { AlertTriangle, Coins, Gift, Power, Users } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { Field, Input, Select } from '../rj-ui/Field';
import { PageHeader } from '../rj-ui/PageHeader';
import { Segmented } from '../rj-ui/Segmented';
import { isLoading, isReady } from '../loading';
import { Waiting } from '../Waiting';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import { AssistantHint } from '../AssistantHint';
import './points-i18n';

/** `cost`, NOT `cost_points`. The API's own field name — see the module note. */
interface Reward {
  id: string;
  name: string;
  cost: number;
  type: string;
  service_id?: string;
  discount_halalas?: number;
  active?: boolean;
}

/**
 * `services/loyalty/app/core/report.py::build` — a superset the screen used to read a third of.
 * `expired_share` is the field its own docstring names as "the one indicator that is a warning":
 * how much of everything ever granted died unspent, which means the thresholds sit beyond his
 * customers' reach and the programme is annoying them rather than holding them. Nothing else here
 * reveals that — every other number only counts what already happened.
 */
interface Report {
  redemptions?: number; customers?: number; outstanding?: number;
  granted?: number; consumed?: number; expired_unredeemed?: number;
  /** A fraction 0..1 — `granted ? expired/granted : 0`, straight from the backend. */
  expired_share?: number;
  top_rewards?: [string, number][];
}

interface Service { id: string; name: string }

/** Points per visit, by level. `points` is the only inheriting field (§9.2). */
interface EarnLevel { points?: number }
interface EarnSettings {
  general: EarnLevel;
  services: Record<string, EarnLevel>;
  groups: Record<string, EarnLevel>;
  service_group: Record<string, string>;
  /** `services_priced` — the LAST time this was checked (at the mode switch itself; see the
   *  `points.mode.services` Segmented's own `onChange` below), whether every active service
   *  carried a real price. Not read pre-emptively here: it can go stale the moment a service is
   *  re-priced, so the honest answer is asked live, at the press — this field is read back only
   *  to show the mode that is actually in effect, never to pre-judge a press before it happens. */
  config: { mode?: string; points_per_riyal?: number; services_priced?: boolean };
}

/**
 * THREE KINDS, CUT WHERE THEY ACTUALLY DIFFER — which is by what the form must still ask for.
 *
 * The old cut was «خدمة» / «منتج» / «خصم», and the first two are the same object: a line in the
 * owner's catalogue. A workshop calls it a service and a coffee shop calls it a product; nothing
 * downstream reads that word, and the reminder interval is a property of the entry he configured,
 * not of the noun. Asking him to choose between them decided nothing and implied a difference in
 * scheduling that does not exist.
 *
 * What is genuinely three is the second question. A catalogue reward needs an entry picked; a
 * discount needs an amount; a gift — a keyring, a voucher, anything not in his catalogue — needs
 * neither, because its name IS the whole of it and the system does nothing with it beyond
 * spending the points.
 */
type T = (key: string) => string;

function typesFor(t: T): { value: string; label: string; hint: string }[] {
  return [
    { value: 'service', label: t('points.type.service.label'), hint: t('points.type.service.hint') },
    { value: 'item', label: t('points.type.item.label'), hint: t('points.type.item.hint') },
    { value: 'discount', label: t('points.type.discount.label'), hint: t('points.type.discount.hint') },
  ];
}

function typeLabel(t: T, types: { value: string; label: string }[], val: string): string {
  return types.find((x) => x.value === val)?.label ?? val;
}

export function PointsScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const TYPES = typesFor(t);
  const [tab, setTab] = useState<'rewards' | 'earning'>('rewards');
  const [rewards, setRewards] = useState<Reward[] | null | undefined>(undefined);
  const [report, setReport] = useState<Report | null | undefined>(undefined);
  const [services, setServices] = useState<Service[] | null>([]);
  const [earn, setEarn] = useState<EarnSettings | null | undefined>(undefined);
  const [adding, setAdding] = useState(false);
  const [type, setType] = useState(TYPES[0].value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  // SET ONLY BY A FAILED SWITCH TO INVOICE MODE, never by the generic `error` path below — the
  // server's refusal there is always the SAME fact the static hint under the card already states
  // (validate() only ever fails a `mode: 'invoice'` write for one reason: unpriced services), so
  // routing it into the shared top banner would put two differently-worded sentences about the
  // same rule on screen at once. This flag colours the ONE existing hint instead of adding a
  // second one — a real screenshot of exactly that duplication is what this was written to fix.
  const [modeBlocked, setModeBlocked] = useState(false);

  // WHAT THIS PERSON MAY DO, FROM THE CATALOGUE. The gateway has already filtered it by
  // capability, so an absent action is a permission fact and the control is simply not rendered —
  // never rendered-and-refused, which teaches him the product is broken.
  const canAdd = action(catalog, 'loyalty.rewards.create');
  const canEdit = action(catalog, 'loyalty.rewards.update');
  const canSetGeneral = action(catalog, 'loyalty.settings.general');
  const canSetService = action(catalog, 'loyalty.settings.service');
  const canSetGroup = action(catalog, 'loyalty.settings.group');
  const canFollow = action(catalog, 'loyalty.settings.follow');
  const canSetMode = action(catalog, 'loyalty.settings.mode');

  // A GENERATION NUMBER, NOT JUST A FUNCTION — every setting on this screen calls `load()` again
  // after its own write, so two edits close together fire two overlapping round-trips. Network
  // order is not request order; without this, an OLDER response landing AFTER a newer one
  // silently overwrites fresh state with stale state — which reads as the screen "reverting to an
  // old update" for no visible reason. Each call captures its own generation and only applies
  // what it fetched if it is still the latest one in flight when the response lands.
  const loadGen = useRef(0);

  const load = () => {
    const gen = ++loadGen.current;
    const current = () => gen === loadGen.current;

    const r = action(catalog, 'loyalty.rewards.list');
    if (r) {
      // RETIRED ONES INCLUDED, on this screen only. The list defaults to active — right for the
      // redemption sheet, wrong here: without them «إيقاف» made the row vanish, which reads as a
      // delete and leaves «تفعيل» with nothing to act on.
      call<{ rewards: Reward[] }>(session, r, { include_retired: true })
        .then((x) => { if (current()) setRewards(x.rewards ?? []); })
        .catch(() => { if (current()) setRewards(null); });
    } else {
      setRewards([]);
    }

    const rep = action(catalog, 'loyalty.report');
    if (rep) {
      call<Report>(session, rep)
        .then((x) => { if (current()) setReport(x); })
        .catch(() => { if (current()) setReport(null); });
    }

    const s = action(catalog, 'loyalty.settings.read');
    if (s) {
      call<EarnSettings>(session, s)
        .then((x) => { if (current()) setEarn(x); })
        .catch(() => { if (current()) setEarn(null); });
    }

    // HIS OWN CATALOGUE, because a service reward must name one of HIS services and the earning
    // tab sets a number per service. Failure leaves the list empty, which removes the service
    // reward type rather than offering one that cannot be bound.
    const list = action(catalog, 'operations.list_services');
    if (list) {
      call<{ services: Service[] }>(session, list)
        .then((x) => { if (current()) setServices(x.services ?? []); })
        .catch(() => { if (current()) setServices(null); });
    }
  };

  useEffect(load, [session, catalog]);

  const patchReward = async (id: string, patch: Partial<Reward>) => {
    if (!canEdit) return;
    setSaving(true);
    setError('');
    try {
      await call(session, canEdit, { reward_id: id, ...patch });
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('points.error.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  const addReward = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!canAdd) return;
    const form = new FormData(e.currentTarget);
    const type = String(form.get('type') || 'item');
    // RIYALS ON THE SCREEN, HALALAS ON THE WIRE — and this line used to say exactly that while
    // doing `Number(riyals) * 100`. `2.3 * 100` is `229.99999999999997`, so a reward priced at
    // 2.30 was stored as 229 halalas and stayed one halala short on every redemption after it.
    // `halalas()` converts the TEXT by integer arithmetic, so no float exists to be wrong.
    const minor = type === 'discount' ? halalas(String(form.get('riyals') || '0')) : 0;
    if (minor === null) {
      // REFUSED WITH A REASON, not rounded for him. «2.305 ريال» is not a price this product can
      // charge, and quietly making it 2.30 spends his money to save him a keystroke.
      setError(t('points.error.discountAmount'));
      return;
    }
    setSaving(true);
    setError('');
    try {
      await call(session, canAdd, {
        name: String(form.get('name') || '').trim(),
        cost: Number(form.get('cost') || 0),
        type,
        service_id: type === 'service' ? String(form.get('service_id') || '') : '',
        discount_halalas: minor,
      });
      setAdding(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('points.error.addFailed'));
    } finally {
      setSaving(false);
    }
  };

  const setEarnFor = async (serviceId: string, points: number) => {
    if (!canSetService) return;
    setSaving(true);
    setError('');
    try {
      await call(session, canSetService, { service_id: serviceId, points });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('points.error.saveFailed'));
    } finally {
      setSaving(false);
    }
  };

  // A PAGE WITH NO KNOWN SHAPE YET WAITS IN OUR OWN MARK, not as one grey rectangle —
  // see Waiting.tsx. The skeletons inside the page stay: there the shape IS known.
  // «NOT YET» IS NOT «IT FAILED» (م · النمط 1). This guard read `=== null`, and the failure
  // handler set `null` too — so a failed read waited here for ever and the «تعذّرت القراءة»
  // sentence below could never be reached. Now the wait is `undefined` and the sentence is live.
  if (isLoading(rewards)) return <Waiting what={t('points.waiting')} />;

  /** A service's effective points, and whether the number is its own (§9.2: inherit, never copy). */
  /** The groups the engine already knows — from his own «خدماتي», never a second list. */
  const groupNames = Array.from(new Set(Object.values(earn?.service_group ?? {})))
    .filter(Boolean)
    .sort();

  const earnFor = (id: string): { points: number; own: boolean } => {
    const own = earn?.services?.[id]?.points;
    if (own !== undefined) return { points: own, own: true };
    const group = earn?.service_group?.[id];
    const fromGroup = group ? earn?.groups?.[group]?.points : undefined;
    return { points: fromGroup ?? earn?.general?.points ?? 0, own: false };
  };

  return (
    <div className="flex flex-col gap-5 p-4">
      <PageHeader icon={Gift} title={t('points.title')} />

      {/* ── what the programme is costing him ────────────────────────────────────────────────
          FOUR NUMBERS NOW, AND TWO OF THEM CARRY COLOUR ON PURPOSE. Points outstanding are a debt
          the shop has already promised and not yet paid (§9.1) — an owner who cannot see its size
          cannot price the programme — so it carries the WARNING tone (a real liability, not the
          brand's own "act on this" accent — corrected 2026-09-07 alongside the theme rebrand's own
          accent-overuse audit).

          THE FOURTH IS THE WARNING THE REPORT WAS BUILT AROUND. `report.py`'s own docstring calls
          `expired_share` "the one indicator that is a warning": a high share means his thresholds
          sit beyond what his customers actually reach, and the programme is reminding people of
          something they will never get. Every OTHER number here only counts what already
          happened; this is the only one that says something is wrong. It was computed on every
          read and never once reached this screen.

          THE OLD ROW WAS THREE IDENTICAL GREY SPANS at one type size, and the eye had no reason
          to stop anywhere. A screen where everything is equally important is a screen where
          nothing is. */}
      {report ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard icon={<Users size={18} />} label={t('points.kpi.customers')}
                   value={String(report.customers ?? 0)} />
          <KpiCard icon={<Gift size={18} />} label={t('points.kpi.redemptions')}
                   value={String(report.redemptions ?? 0)} />
          <KpiCard icon={<Coins size={18} />} label={t('points.kpi.outstanding')} tone="warning"
                   value={String(report.outstanding ?? 0)}
                   hint={t('points.kpi.outstanding.hint')} />
          <KpiCard icon={<AlertTriangle size={18} />} label={t('points.kpi.expiredShare')}
                   tone="warning"
                   value={tf(t, 'points.percentValue', { n: Math.round((report.expired_share ?? 0) * 100) })}
                   hint={t('points.kpi.expiredShare.hint')} />
        </div>
      ) : null}

      {/* «أكثر ما يُستبدل» — the same report, its other half. Rewards a shop never sees redeemed
          are the ones worth re-pricing; a shop cannot know which without this. Shown only once
          there is something to rank — a programme with zero redemptions has nothing here to say
          that the KPI above has not already said. */}
      {report?.top_rewards && report.top_rewards.length > 0 ? (
        <Card className="flex flex-col gap-2 p-4">
          <h2 className="text-sm font-medium text-text-secondary">{t('points.topRewards.title')}</h2>
          <ul className="flex flex-col divide-y divide-border-subtle">
            {report.top_rewards.map(([name, count]) => (
              <li key={name} className="flex items-center justify-between gap-3 py-1.5 text-sm">
                <span className="truncate">{name || t('points.noName')}</span>
                <span className="shrink-0 tabular-nums text-text-secondary">{count}</span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      <Segmented
        // FULL WIDTH, SPLIT EVENLY, NEVER WRAPPED. The kit's Segmented is `inline-flex flex-wrap`,
        // which on a phone stacks two long Arabic labels into a ragged block half the screen wide.
        className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
        ariaLabel={t('points.tabsAriaLabel')}
        value={tab}
        onChange={setTab}
        options={[
          { value: 'rewards', label: t('points.tab.rewards') },
          { value: 'earning', label: t('points.tab.earning') },
        ]}
      />

      {error ? <p className="text-danger">{error}</p> : null}

      {tab === 'rewards' ? (
        <section className="flex flex-col gap-3">
          <Head title={t('points.table.title')}
                said={t('points.table.said')}
                action={canAdd && !adding
                  ? <Button onClick={() => setAdding(true)}>{t('points.addReward')}</Button>
                  : null} />

          {adding ? (
            <form onSubmit={addReward}
                  className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
              <Field label={t('points.form.name.label')} htmlFor="rw-name" hint={t('points.form.name.hint')}>
                <Input id="rw-name" name="name" required maxLength={40} />
              </Field>
              <Field label={t('points.form.cost.label')} htmlFor="rw-cost">
                <Input id="rw-cost" name="cost" type="number" min={1} required dir="ltr" />
              </Field>
              {/* THE HINT IS UNDER THE SELECT, NOT INSIDE IT. A native option list sizes itself to
                  its longest string and is drawn by the OS, outside our layout. */}
              <Field label={t('points.form.type.label')} htmlFor="rw-type" hint={TYPES.find((x) => x.value === type)?.hint}>
                <Select id="rw-type" name="type" value={type}
                        onChange={(e) => setType(e.target.value)}>
                  {TYPES.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
                </Select>
              </Field>
              {/* ONE FIELD AT A TIME. Showing both and labelling each with the case it belongs to
                  asks the owner to do the branching we already know the answer to. */}
              {type === 'discount' ? (
                <Field label={t('points.form.riyals.label')} htmlFor="rw-riyals">
                  {/* STEP IS PART OF THE FIX, NOT DECORATION. A number input with the default
                      step of 1 rejects «2.30» in the browser's own validation, so the halalas
                      the conversion now preserves could never have been typed in the first
                      place. Two decimal places is exactly what a riyal has. */}
                  <Input id="rw-riyals" name="riyals" type="number" min={0} step="0.01"
                         inputMode="decimal" dir="ltr" required />
                </Field>
              ) : type === 'service' ? (
                <Field label={t('points.form.service.label')} htmlFor="rw-service" hint={t('points.form.service.hint')}>
                  <Select id="rw-service" name="service_id" required>
                    <option value="">—</option>
                    {(services ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </Select>
                </Field>
              ) : null}
              <div className="flex gap-2">
                <Button type="submit" disabled={saving}>{t('points.save')}</Button>
                <Button type="button" variant="ghost" onClick={() => setAdding(false)}>{t('points.cancel')}</Button>
              </div>
            </form>
          ) : null}

          {rewards === null ? (
            // «تعذّرت القراءة» AND NOT «جدول فارغ». The sentence below tells the owner his table
            // was never seeded and asks him to call us — a serious claim, and one we may only make
            // once we have actually read the table.
            <EmptyState
              title={t('points.loadFailed.title')}
              description={t('points.loadFailed.description')}
            />
          ) : rewards.length === 0 ? (
            // AN INVITATION, AND IT USED TO BE A FAULT REPORT. The table was seeded from the trade
            // he picked at sign-up, so empty meant the seeding had failed and the sentence told him
            // to contact us. Nothing is seeded now — a rewards table guessed from a trade we have
            // never seen is wrong for most shops — so empty is the true first state of every new
            // shop, and it must read as a beginning rather than as our failure.
            <EmptyState
              title={t('points.empty.title')}
              description={t('points.empty.description')}
            />
          ) : (
            <ul className="flex flex-col gap-2">
              {/* CHEAPEST FIRST, because that is the order his customer meets them in: the first
                  reward within reach is the one that brings him back a fourth time. A list in
                  creation order is a list in OUR order. */}
              {[...rewards].sort((a, b) => a.cost - b.cost).map((r) => (
                <li key={r.id}
                    className={[
                      'flex items-center gap-3 rounded-card border border-border-subtle bg-surface-1 p-3',
                      r.active === false ? 'opacity-60' : '',
                    ].join(' ')}>
                  {/* THE COST AS A COIN, NOT AS A NUMBER IN A ROW OF NUMBERS. It is the one thing
                      the owner compares between rewards and the one thing his customer counts
                      towards, so it is the shape the eye lands on first. GOLD, not accent — this
                      screen has no single aggregate "points total" headline worth a hero gradient
                      (it is a rewards table, not a balance display), so the reward-cost coin is its
                      own genuine premium/reward moment, added 2026-09-07 alongside the theme's own
                      secondary-gold ramp. */}
                  {canEdit ? (
                    <label className="flex shrink-0 flex-col items-center gap-0.5">
                      <input
                        type="number"
                        min={1}
                        defaultValue={r.cost}
                        aria-label={tf(t, 'points.costAriaLabel', { name: r.name })}
                        dir="ltr"
                        // A BLANK FIELD IS NOT A ZERO, and here it would also be a refusal: cost
                        // must be greater than zero.
                        onBlur={(e) => {
                          const raw = e.target.value.trim();
                          if (raw !== '' && Number(raw) !== r.cost) {
                            patchReward(r.id, { cost: Number(raw) });
                          }
                        }}
                        className="h-11 w-20 rounded-xl bg-accent-soft px-1 text-center text-lg font-semibold tabular-nums text-accent-on-soft"
                      />
                      <span className="text-[0.65rem] text-text-secondary">{t('points.pointUnit')}</span>
                    </label>
                  ) : (
                    <span className="grid size-14 shrink-0 place-items-center rounded-xl bg-accent-soft text-lg font-semibold tabular-nums text-accent-on-soft">
                      {r.cost}
                    </span>
                  )}

                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="truncate font-medium">{r.name}</span>
                    <span className="flex flex-wrap items-center gap-2">
                      <Badge tone="neutral">{typeLabel(t, TYPES, r.type)}</Badge>
                      <AssistantHint anchor="points.rewardType" session={session} />
                      {r.active === false ? (
                        <>
                          <Badge tone="warning">{t('points.stoppedBadge')}</Badge>
                          <AssistantHint anchor="points.stoppedBadge" session={session} />
                        </>
                      ) : null}
                    </span>
                  </span>

                  {/* RETIRED, NEVER DELETED. Every redemption in history references a reward, and
                      a receipt must not restate itself when the menu changes. */}
                  {canEdit ? (
                    <button
                      type="button"
                      title={r.active === false ? t('points.activate') : t('points.deactivate')}
                      aria-label={r.active === false ? t('points.activate') : t('points.deactivateShort')}
                      disabled={saving}
                      onClick={() => patchReward(r.id, { active: r.active === false })}
                      className={[
                        'grid size-11 shrink-0 place-items-center rounded-lg transition-colors',
                        'disabled:opacity-40',
                        r.active === false
                          ? 'text-text-secondary hover:bg-surface-2'
                          : 'text-danger hover:bg-danger/10',
                      ].join(' ')}
                    >
                      <Power size={18} aria-hidden />
                    </button>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : !isReady(earn) ? (
        // ── A FAILED SETTINGS READ MUST NOT DRAW RULES AS FACTS (م · قاطع) ───────────────────
        //
        // Every control on this tab defaults to `earn?.…?.points ?? 0`. When the read failed, the
        // whole earning tree therefore rendered as ZERO — presented not as «unknown» but as this
        // shop's configuration. And the first touch on any field WRITES it: the owner corrects a
        // number he was never shown correctly, and the shop starts granting what the screen made
        // up. A programme silently reset to zero is discovered by customers, at the counter.
        <section className="flex flex-col gap-4">
          <EmptyState
            title={isLoading(earn) ? t('points.settingsWaiting.title') : t('points.settingsFailed.title')}
            description={isLoading(earn)
              ? t('points.settingsWaiting.description')
              : t('points.settingsFailed.description')}
          />
        </section>
      ) : (
        <section className="flex flex-col gap-4">
          {/* THE SWITCH, NOT TWO CHECKBOXES (§9.3). A shop granting by invoice AND by service
              grants twice for one transaction — an error that does not show on the screen but at
              the end of the month, as an obligation double what he expected. */}
          {canSetMode ? (
            <Card className="flex flex-col gap-3 p-4">
              <Head title={t('points.mode.title')}
                    said={t('points.mode.said')} />
              <Segmented
                // FULL WIDTH, SPLIT EVENLY, NEVER WRAPPED. The kit's Segmented is
                // `inline-flex flex-wrap`, which on a phone stacks two long Arabic labels into a
                // ragged block half the screen wide. It takes a className and merges with
                // tailwind-merge, so this is a fix at the call site rather than a fork of the kit.
                className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
                ariaLabel={t('points.mode.ariaLabel')}
                value={earn?.config?.mode === 'invoice' ? 'invoice' : 'services'}
                onChange={async (mode) => {
                  setSaving(true);
                  setError('');
                  setModeBlocked(false);
                  try {
                    await call(session, canSetMode, {
                      mode,
                      points_per_riyal: earn?.config?.points_per_riyal ?? 1,
                    });
                    load();
                  } catch (e) {
                    // A SHOP WITH NO TILL CANNOT EARN BY INVOICE — the field screen records no
                    // amounts (§9.3). The service refuses in a sentence the owner can read; the
                    // switch must show it, not swallow it, and must stay where it was.
                    //
                    // A SWITCH TO 'invoice' CAN ONLY EVER FAIL THIS ONE WAY — `validate()` accepts
                    // any mode this control offers and any points_per_riyal already on file, so the
                    // sole failing precondition is unpriced services. That is exactly what the
                    // static hint below already says; showing the server's own wording of the same
                    // fact in the banner above would be the same sentence twice. A switch TO
                    // 'services' has no precondition to fail, so a real (unexpected) error there
                    // still goes through the shared banner.
                    if (mode === 'invoice') {
                      setModeBlocked(true);
                    } else {
                      setError(e instanceof Error ? e.message : t('points.error.modeChangeFailed'));
                    }
                  } finally {
                    setSaving(false);
                  }
                }}
                options={[
                  { value: 'services', label: t('points.mode.services') },
                  { value: 'invoice', label: t('points.mode.invoice') },
                ]}
              />
              {/* SAID BEFORE THE PRESS, NOT AFTER IT — a constant sentence stating the rule,
                  never a conditional read of `earn.config.services_priced`. That field is only
                  ever as fresh as the last time this switch was actually pressed (the real,
                  live check happens server-side, at the press itself — see the `onChange`
                  above), so judging whether to SHOW this hint from it would be showing a
                  possibly-stale verdict as if it were current. Hidden once he is already in
                  invoice mode, where the rule is no longer something he is about to trip over. */}
              {earn?.config?.mode !== 'invoice' ? (
                <p className={`mt-3 text-sm ${modeBlocked ? 'text-danger' : 'text-text-secondary'}`}>
                  {t('points.mode.needsPricedServices')}
                </p>
              ) : null}
            </Card>
          ) : null}

          {canSetGeneral ? (
            <Card className="p-4">
              <label className="flex items-center justify-between gap-3">
                <span className="flex flex-col">
                  <span className="text-sm">{t('points.general.label')}</span>
                  <span className="text-sm text-text-secondary">
                    {t('points.general.hint')}
                  </span>
                </span>
                <input
                  type="number"
                  min={0}
                  defaultValue={earn?.general?.points ?? 0}
                  // NAMED, because the label wraps this input as a sibling of two spans and a
                  // screen reader — or a test — has no way to say which field this is otherwise.
                  aria-label={t('points.general.label')}
                  dir="ltr"
                  onBlur={async (e) => {
                    const raw = e.target.value.trim();
                    if (raw === '' || Number(raw) === (earn?.general?.points ?? 0)) return;
                    setSaving(true);
                    setError('');
                    try {
                      await call(session, canSetGeneral, { points: Number(raw) });
                      load();
                    } catch (err) {
                      setError(err instanceof Error ? err.message : t('points.error.saveFailed'));
                      e.target.value = String(earn?.general?.points ?? 0);
                    } finally {
                      setSaving(false);
                    }
                  }}
                  className="h-10 w-28 rounded-lg bg-surface-2 px-3 text-center tabular-nums"
                />
              </label>
            </Card>
          ) : null}

          {/* ── points for a whole GROUP of services ────────────────────────────────────────
              THE MIDDLE LEVEL, AND NOTHING COULD SET IT. The engine resolves service → group →
              general (§9.2) and `loyalty.settings.group` was declared, served and called by no
              screen: a shop that had organised sixteen services into four groups still had to set
              points sixteen times, and the level built to spare him that was unreachable.

              THE GROUPS COME FROM WHAT HE ALREADY BUILT in «خدماتي» — they are read out of the
              settings the engine returns, so there is no second place to define a group and no way
              for the two to disagree. */}
          {canSetGroup && groupNames.length > 0 ? (
            <Card className="flex flex-col gap-3 p-4">
              <Head title={t('points.group.title')}
                    said={t('points.group.said')} />
              <ul className="flex flex-col gap-2">
                {groupNames.map((g) => (
                  <li key={g} className="flex items-center justify-between gap-3">
                    <span className="text-sm">{g}</span>
                    <input
                      type="number"
                      min={0}
                      dir="ltr"
                      defaultValue={String(earn?.groups?.[g]?.points ?? earn?.general?.points ?? 0)}
                      aria-label={tf(t, 'points.group.ariaLabel', { group: g })}
                      onBlur={async (e) => {
                        const raw = e.target.value.trim();
                        if (raw === '') return;
                        const n = Number(raw);
                        const was = earn?.groups?.[g]?.points ?? -1;
                        if (n === was) return;
                        setSaving(true);
                        setError('');
                        try {
                          // THE MEMBERS COME FROM THE TREE, not from this screen. Sending our own
                          // list would let a group that changed in «خدماتي» be silently rewritten
                          // to whatever this page last saw.
                          await call(session, canSetGroup, {
                            group: g,
                            points: n,
                            service_ids: Object.entries(earn?.service_group ?? {})
                              .filter(([, name]) => name === g)
                              .map(([id]) => id),
                          });
                          load();
                        } catch (err) {
                          setError(err instanceof Error ? err.message : t('points.error.saveFailed'));
                          e.target.value = String(was === -1 ? (earn?.general?.points ?? 0) : was);
                        } finally {
                          setSaving(false);
                        }
                      }}
                      className="h-10 w-28 rounded-lg bg-surface-2 px-3 text-center tabular-nums"
                    />
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {canSetService && (services ?? []).length > 0 ? (
            <Card className="flex flex-col gap-3 p-4">
              <Head title={t('points.perService.title')}
                    said={t('points.perService.said')} />
              <ul className="flex flex-col gap-2">
                {(services ?? []).map((s) => {
                  const { points, own } = earnFor(s.id);
                  return (
                    <li key={s.id} className="flex items-center justify-between gap-3">
                      <span className="flex items-center gap-2">
                        <span>{s.name}</span>
                        {/* SHOWN WHERE IT HAPPENED (§10.8.1), never in a distant settings screen
                            he would have to find. */}
                        {own ? <Badge tone="neutral">{t('points.customSetting')}</Badge> : null}
                      </span>
                      <span className="flex items-center gap-2">
                        <input
                          type="number"
                          min={0}
                          defaultValue={points}
                          aria-label={tf(t, 'points.serviceAriaLabel', { name: s.name })}
                          dir="ltr"
                          onBlur={(e) => {
                            const raw = e.target.value.trim();
                            if (raw !== '' && Number(raw) !== points) {
                              setEarnFor(s.id, Number(raw));
                            }
                          }}
                          className="h-10 w-24 rounded-lg bg-surface-2 px-3 text-center tabular-nums"
                        />
                        {/* A DELETE, NOT A WRITE OF TODAY'S GENERAL VALUE: following means tracking
                            it from now on, and writing the current number would freeze it. */}
                        {own && canFollow ? (
                          <Button
                            variant="ghost"
                            disabled={saving}
                            onClick={async () => {
                              setSaving(true);
                              try {
                                await call(session, canFollow, { service_id: s.id });
                                load();
                              } finally {
                                setSaving(false);
                              }
                            }}
                          >
                            {t('points.returnToGeneral')}
                          </Button>
                        ) : null}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </Card>
          ) : null}
        </section>
      )}
    </div>
  );
}


/**
 * A section's heading: a title, the sentence that says what the section is for, and its one act.
 *
 * WHY THIS EXISTS AS A COMPONENT. Every heading on this screen was «text-sm text-text-secondary» —
 * the same weight, size and colour as the labels inside the cards under it. The owner's own words
 * were that he could not tell a section's head from its branches, and he was right: nothing on the
 * page was drawn as a heading, so the page had no structure to read.
 */
function Head({ title, said, action }:
    { title: string; said?: string; action?: React.ReactNode }) {
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
