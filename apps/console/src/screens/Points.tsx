/**
 * «نقاطي» — the rewards table, and what a visit is worth.
 *
 * IT ARRIVES PRE-FILLED FOR HIS SECTOR ("100 points = an exterior wash, 300 = polish"). He edits a
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
import { useEffect, useState, type FormEvent } from 'react';
import { Badge } from '@base-ui/design-system/Badge';
import { KpiCard } from '@base-ui/design-system/KpiCard';
import { Coins, Gift, Power, Users } from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Field, Input } from '@base-ui/design-system/Field';
import { Segmented } from '@base-ui/design-system/Segmented';
import { isLoading, isReady } from '../loading';
import { Waiting } from '../Waiting';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

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

interface Report { redemptions?: number; customers?: number; outstanding?: number }

interface Service { id: string; name: string }

/** Points per visit, by level. `points` is the only inheriting field (§9.2). */
interface EarnLevel { points?: number }
interface EarnSettings {
  /** The general level also carries the manager-approval threshold — one number for the whole
   *  establishment, not an inheriting field (§9.5). */
  general: EarnLevel & { manager_threshold?: number };
  services: Record<string, EarnLevel>;
  groups: Record<string, EarnLevel>;
  service_group: Record<string, string>;
  /** `integrated` is whether a till is connected — the one thing invoice earning depends on. */
  config: { mode?: string; points_per_riyal?: number; integrated?: boolean };
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
const TYPES: { value: string; label: string; hint: string }[] = [
  { value: 'service', label: 'من خدماتي', hint: 'يختار ما يحصل عليه مما تقدّمه — خدمةً كان أو منتجاً' },
  { value: 'item', label: 'هدية', hint: 'شيء من خارج ما تقدّمه — الاسم يكفي' },
  { value: 'discount', label: 'خصم', hint: 'مبلغ يُخصم من الزيارة' },
];

function typeLabel(t: string): string {
  return TYPES.find((x) => x.value === t)?.label ?? t;
}

export function PointsScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [tab, setTab] = useState<'rewards' | 'earning'>('rewards');
  const [rewards, setRewards] = useState<Reward[] | null | undefined>(undefined);
  const [report, setReport] = useState<Report | null | undefined>(undefined);
  const [services, setServices] = useState<Service[] | null>([]);
  const [earn, setEarn] = useState<EarnSettings | null | undefined>(undefined);
  const [adding, setAdding] = useState(false);
  const [type, setType] = useState(TYPES[0].value);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

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

  const load = () => {
    const r = action(catalog, 'loyalty.rewards.list');
    if (r) {
      // RETIRED ONES INCLUDED, on this screen only. The list defaults to active — right for the
      // redemption sheet, wrong here: without them «إيقاف» made the row vanish, which reads as a
      // delete and leaves «تفعيل» with nothing to act on.
      call<{ rewards: Reward[] }>(session, r, { include_retired: true })
        .then((x) => setRewards(x.rewards ?? []))
        .catch(() => setRewards(null));
    } else {
      setRewards([]);
    }

    const rep = action(catalog, 'loyalty.report');
    if (rep) call<Report>(session, rep).then(setReport).catch(() => setReport(null));

    const s = action(catalog, 'loyalty.settings.read');
    if (s) call<EarnSettings>(session, s).then(setEarn).catch(() => setEarn(null));

    // HIS OWN CATALOGUE, because a service reward must name one of HIS services and the earning
    // tab sets a number per service. Failure leaves the list empty, which removes the service
    // reward type rather than offering one that cannot be bound.
    const list = action(catalog, 'operations.list_services');
    if (list) {
      call<{ services: Service[] }>(session, list)
        .then((x) => setServices(x.services ?? []))
        .catch(() => setServices(null));
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
      setError(e instanceof Error ? e.message : 'تعذّر الحفظ.');
    } finally {
      setSaving(false);
    }
  };

  const addReward = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!canAdd) return;
    const form = new FormData(e.currentTarget);
    const type = String(form.get('type') || 'item');
    setSaving(true);
    setError('');
    try {
      await call(session, canAdd, {
        name: String(form.get('name') || '').trim(),
        cost: Number(form.get('cost') || 0),
        type,
        service_id: type === 'service' ? String(form.get('service_id') || '') : '',
        // Riyals on the screen, halalas on the wire — no float ever touches money.
        discount_halalas: type === 'discount' ? Number(form.get('riyals') || 0) * 100 : 0,
      });
      setAdding(false);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر إضافة المكافأة.');
    } finally {
      setSaving(false);
    }
  };

  const setEarnFor = async (serviceId: string, points: number) => {
    if (!canSetService) return;
    setSaving(true);
    try {
      await call(session, canSetService, { service_id: serviceId, points });
      load();
    } finally {
      setSaving(false);
    }
  };

  // A PAGE WITH NO KNOWN SHAPE YET WAITS IN OUR OWN MARK, not as one grey rectangle —
  // see Waiting.tsx. The skeletons inside the page stay: there the shape IS known.
  // «NOT YET» IS NOT «IT FAILED» (م · النمط 1). This guard read `=== null`, and the failure
  // handler set `null` too — so a failed read waited here for ever and the «تعذّرت القراءة»
  // sentence below could never be reached. Now the wait is `undefined` and the sentence is live.
  if (isLoading(rewards)) return <Waiting what="نقرأ نقاطك وجوائزك" />;

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
      {/* ── what the programme is costing him ────────────────────────────────────────────────
          THREE NUMBERS, AND ONLY THE LAST ONE IS MONEY. Points outstanding are a debt the shop
          has already promised and not yet paid (§9.1) — an owner who cannot see its size cannot
          price the programme — so it carries the accent and the other two are context for it.

          THE OLD ROW WAS THREE IDENTICAL GREY SPANS at one type size, and the eye had no reason
          to stop anywhere. A screen where everything is equally important is a screen where
          nothing is. */}
      {report ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <KpiCard icon={<Users size={18} />} label="عميل يجمع نقاطاً"
                   value={String(report.customers ?? 0)} />
          <KpiCard icon={<Gift size={18} />} label="استبدال"
                   value={String(report.redemptions ?? 0)} />
          <KpiCard icon={<Coins size={18} />} label="نقطة لم تُستبدل بعد"
                   value={String(report.outstanding ?? 0)}
                   hint="ما وعدت به ولم يُصرف — وهو التزام على محلّك." />
        </div>
      ) : null}

      <Segmented
        // FULL WIDTH, SPLIT EVENLY, NEVER WRAPPED. The kit's Segmented is `inline-flex flex-wrap`,
        // which on a phone stacks two long Arabic labels into a ragged block half the screen wide.
        className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
        ariaLabel="أقسام النقاط"
        value={tab}
        onChange={setTab}
        options={[
          { value: 'rewards', label: 'المكافآت' },
          { value: 'earning', label: 'الكسب' },
        ]}
      />

      {error ? <p className="text-danger">{error}</p> : null}

      {tab === 'rewards' ? (
        <section className="flex flex-col gap-3">
          <Head title="جدول المكافآت"
                said="ما يستبدله عميلك بنقاطه — ويصل معبّأً لقطاعك."
                action={canAdd && !adding
                  ? <Button onClick={() => setAdding(true)}>إضافة مكافأة</Button>
                  : null} />

          {adding ? (
            <form onSubmit={addReward}
                  className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
              <Field label="اسم المكافأة" htmlFor="rw-name" hint="يظهر في رسالة واتساب للعميل — اجعله قصيراً">
                <Input id="rw-name" name="name" required maxLength={40} />
              </Field>
              <Field label="التكلفة بالنقاط" htmlFor="rw-cost">
                <Input id="rw-cost" name="cost" type="number" min={1} required dir="ltr" />
              </Field>
              {/* THE HINT IS UNDER THE SELECT, NOT INSIDE IT. A native option list sizes itself to
                  its longest string and is drawn by the OS, outside our layout. */}
              <Field label="النوع" htmlFor="rw-type" hint={TYPES.find((t) => t.value === type)?.hint}>
                <select id="rw-type" name="type" value={type}
                        onChange={(e) => setType(e.target.value)}
                        className="h-10 rounded-lg bg-surface-2 px-3">
                  {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </Field>
              {/* ONE FIELD AT A TIME. Showing both and labelling each with the case it belongs to
                  asks the owner to do the branching we already know the answer to. */}
              {type === 'discount' ? (
                <Field label="مبلغ الخصم بالريال" htmlFor="rw-riyals">
                  <Input id="rw-riyals" name="riyals" type="number" min={0} dir="ltr" required />
                </Field>
              ) : type === 'service' ? (
                <Field label="ما يحصل عليه" htmlFor="rw-service" hint="مما تقدّمه — خدمةً كان أو منتجاً">
                  <select id="rw-service" name="service_id" required
                          className="h-10 rounded-lg bg-surface-2 px-3">
                    <option value="">—</option>
                    {(services ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </Field>
              ) : null}
              <div className="flex gap-2">
                <Button type="submit" disabled={saving}>حفظ</Button>
                <Button type="button" variant="ghost" onClick={() => setAdding(false)}>إلغاء</Button>
              </div>
            </form>
          ) : null}

          {rewards === null ? (
            // «تعذّرت القراءة» AND NOT «جدول فارغ». The sentence below tells the owner his table
            // was never seeded and asks him to call us — a serious claim, and one we may only make
            // once we have actually read the table.
            <EmptyState
              title="تعذّرت قراءة جدول المكافآت"
              description="لم نستطع جلبه الآن، والخلل عندنا. أعد المحاولة بعد قليل."
            />
          ) : rewards.length === 0 ? (
            // A FAULT, NOT AN INVITATION. The table is seeded for his sector at creation, so empty
            // means the seeding did not run.
            <EmptyState
              title="جدول المكافآت فارغ"
              description="يصل معبّأً لقطاعك عند إنشاء الحساب — تواصل معنا إن بقي فارغاً."
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
                      towards, so it is the shape the eye lands on first. */}
                  {canEdit ? (
                    <label className="flex shrink-0 flex-col items-center gap-0.5">
                      <input
                        type="number"
                        min={1}
                        defaultValue={r.cost}
                        aria-label={`تكلفة ${r.name} بالنقاط`}
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
                      <span className="text-[0.65rem] text-text-secondary">نقطة</span>
                    </label>
                  ) : (
                    <span className="grid size-14 shrink-0 place-items-center rounded-xl bg-accent-soft text-lg font-semibold tabular-nums text-accent-on-soft">
                      {r.cost}
                    </span>
                  )}

                  <span className="flex min-w-0 flex-1 flex-col gap-1">
                    <span className="truncate font-medium">{r.name}</span>
                    <span className="flex items-center gap-2">
                      <Badge tone="neutral">{typeLabel(r.type)}</Badge>
                      {r.active === false ? <Badge tone="warning">موقوفة</Badge> : null}
                    </span>
                  </span>

                  {/* RETIRED, NEVER DELETED. Every redemption in history references a reward, and
                      a receipt must not restate itself when the menu changes. */}
                  {canEdit ? (
                    <button
                      type="button"
                      title={r.active === false ? 'تفعيل' : 'إيقاف — يختفي من قائمة الاستبدال'}
                      aria-label={r.active === false ? 'تفعيل' : 'إيقاف'}
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
            title={isLoading(earn) ? 'نقرأ إعدادات النقاط' : 'تعذّرت قراءة إعدادات النقاط'}
            description={isLoading(earn)
              ? 'لحظة واحدة.'
              : 'لم نعرضها كي لا تُعدّل رقماً على غير أصله — قواعد محلك كما هي. أعد المحاولة.'}
          />
        </section>
      ) : (
        <section className="flex flex-col gap-4">
          {/* THE SWITCH, NOT TWO CHECKBOXES (§9.3). A shop granting by invoice AND by service
              grants twice for one transaction — an error that does not show on the screen but at
              the end of the month, as an obligation double what he expected. */}
          {canSetMode ? (
            <div className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
              <Head title="طريقة الاحتساب"
                    said="بالخدمات: كل خدمة نقاطها. بقيمة الفاتورة: نقطة لكل ريال." />
              <Segmented
                // FULL WIDTH, SPLIT EVENLY, NEVER WRAPPED. The kit's Segmented is
                // `inline-flex flex-wrap`, which on a phone stacks two long Arabic labels into a
                // ragged block half the screen wide. It takes a className and merges with
                // tailwind-merge, so this is a fix at the call site rather than a fork of the kit.
                className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
                ariaLabel="طريقة احتساب النقاط"
                value={earn?.config?.mode === 'invoice' ? 'invoice' : 'services'}
                onChange={async (mode) => {
                  setSaving(true);
                  setError('');
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
                    setError(e instanceof Error ? e.message : 'تعذّر تغيير طريقة الاحتساب');
                  } finally {
                    setSaving(false);
                  }
                }}
                options={[
                  { value: 'services', label: 'بالخدمات' },
                  { value: 'invoice', label: 'بقيمة الفاتورة' },
                ]}
              />
              {/* SAID BEFORE THE PRESS, NOT AFTER IT. The service refuses invoice earning without a
                  till and says why, and that refusal now reaches the screen — but a rule the owner
                  only meets by tripping over it is a rule the screen kept from him. The option
                  stays visible and pressable: it is a capability he can buy by connecting a till,
                  and a choice that vanishes reads as a fault (§ui 11). */}
              {earn?.config?.integrated === false ? (
                <p className="mt-3 text-sm text-text-secondary">
                  الاحتساب بقيمة الفاتورة يحتاج ربطاً بالكاشير — الشاشة الميدانية تسجّل زيارة، لا مبلغاً.
                </p>
              ) : null}
            </div>
          ) : null}

          {canSetGeneral ? (
            <div className="rounded-card border border-border-subtle bg-surface-1 p-4">
              <label className="flex items-center justify-between gap-3">
                <span className="flex flex-col">
                  <span className="text-sm">نقاط لكل زيارة (عام)</span>
                  <span className="text-sm text-text-secondary">
                    كل خدمة بلا رقم خاص تأخذ هذا الرقم.
                  </span>
                </span>
                <input
                  type="number"
                  min={0}
                  defaultValue={earn?.general?.points ?? 0}
                  // NAMED, because the label wraps this input as a sibling of two spans and a
                  // screen reader — or a test — has no way to say which field this is otherwise.
                  aria-label="نقاط لكل زيارة (عام)"
                  dir="ltr"
                  onBlur={async (e) => {
                    const raw = e.target.value.trim();
                    if (raw === '' || Number(raw) === (earn?.general?.points ?? 0)) return;
                    setSaving(true);
                    try {
                      await call(session, canSetGeneral, { points: Number(raw) });
                      load();
                    } finally {
                      setSaving(false);
                    }
                  }}
                  className="h-10 w-28 rounded-lg bg-surface-2 px-3 text-center tabular-nums"
                />
              </label>

              {/* ── THE APPROVAL THRESHOLD, WHICH NO SCREEN COULD SET (د-14) ─────────────────
                  loyalty has always refused a reward at or above this number without a manager's
                  name, and the number lived only in the database: there was no field anywhere in
                  this app, so it was 0 for every shop and the control simply did not exist. The
                  owner sets it here, on the same row as the general rule, because it is one
                  number for the whole establishment (§9.5). */}
              <label className="mt-4 flex items-center justify-between gap-3 border-t border-border-subtle pt-4">
                <span className="flex flex-col">
                  <span className="text-sm">مكافأة تحتاج اعتماد المدير من</span>
                  <span className="text-sm text-text-secondary">
                    أي مكافأة بهذه النقاط فأكثر تحتاج اسم المدير عند الاستبدال. 0 يعني لا اعتماد.
                  </span>
                </span>
                <input
                  type="number"
                  min={0}
                  defaultValue={Number(earn?.general?.manager_threshold ?? 0)}
                  aria-label="مكافأة تحتاج اعتماد المدير من"
                  dir="ltr"
                  onBlur={async (e) => {
                    const raw = e.target.value.trim();
                    const was = Number(earn?.general?.manager_threshold ?? 0);
                    if (raw === '' || Number(raw) === was) return;
                    setSaving(true);
                    try {
                      // BOTH FIELDS, because the route rewrites the general row from what it is
                      // sent: posting the threshold alone would set the shop's points-per-visit
                      // to whatever the model defaults to and nobody would notice until the end
                      // of the month.
                      await call(session, canSetGeneral, {
                        points: earn?.general?.points ?? 0,
                        manager_threshold: Number(raw),
                      });
                      load();
                    } finally {
                      setSaving(false);
                    }
                  }}
                  className="h-10 w-28 rounded-lg bg-surface-2 px-3 text-center tabular-nums"
                />
              </label>
            </div>
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
            <div className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
              <Head title="نقاط مجموعة"
                    said="تسري على كل خدمة في المجموعة لم تُخصَّص وحدها." />
              <ul className="flex flex-col gap-2">
                {groupNames.map((g) => (
                  <li key={g} className="flex items-center justify-between gap-3">
                    <span className="text-sm">{g}</span>
                    <input
                      type="number"
                      min={0}
                      dir="ltr"
                      defaultValue={String(earn?.groups?.[g]?.points ?? earn?.general?.points ?? 0)}
                      aria-label={`نقاط مجموعة ${g}`}
                      onBlur={async (e) => {
                        const raw = e.target.value.trim();
                        if (raw === '') return;
                        const n = Number(raw);
                        if (n === (earn?.groups?.[g]?.points ?? -1)) return;
                        setSaving(true);
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
                        } finally {
                          setSaving(false);
                        }
                      }}
                      className="h-10 w-28 rounded-lg bg-surface-2 px-3 text-center tabular-nums"
                    />
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {canSetService && (services ?? []).length > 0 ? (
            <div className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
              <Head title="نقاط خدمة بعينها"
                    said="رقمٌ خاص يتقدّم على المجموعة وعلى العام." />
              <ul className="flex flex-col gap-2">
                {(services ?? []).map((s) => {
                  const { points, own } = earnFor(s.id);
                  return (
                    <li key={s.id} className="flex items-center justify-between gap-3">
                      <span className="flex items-center gap-2">
                        <span>{s.name}</span>
                        {/* SHOWN WHERE IT HAPPENED (§10.8.1), never in a distant settings screen
                            he would have to find. */}
                        {own ? <Badge tone="accent">إعداد خاص</Badge> : null}
                      </span>
                      <span className="flex items-center gap-2">
                        <input
                          type="number"
                          min={0}
                          defaultValue={points}
                          aria-label={`نقاط ${s.name}`}
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
                            العودة إلى العام
                          </Button>
                        ) : null}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
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
