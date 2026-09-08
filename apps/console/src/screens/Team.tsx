/**
 * «فريقي» — the people and the branches.
 *
 * TWO LISTS, TWO TABS. They were stacked in one scroll, which is how a screen becomes a wall: the
 * owner scrolls past his employees to reach his branches and back again, and neither list is ever
 * the thing he came for. `Segmented` is the kit's, and the same control the door uses.
 *
 * AND A TAB THE SHOP'S ENABLED APPS DO NOT INCLUDE IS LOCKED, NOT HIDDEN — with the reason on it. This screen
 * hid «الفروع» from a single-branch shop, and that was wrong twice over: a capability nobody can
 * see cannot be bought, and a section that vanishes reads as a fault. The campaign cards already
 * decided this and said why — «a card that disappears reads as a fault; a card that explains
 * itself reads as a rule».
 *
 * THE SEAT LIMIT IS REFUSED AT THE DOOR, BY THE SERVER, with the number in the sentence. A count
 * done here would be a second opinion that disagrees the moment two people add an employee at
 * once — and the one that is wrong is the one the owner is looking at.
 *
 * AND IDENTITY COMES FROM THE SESSION (§3.5). There is no "who is recording this" field anywhere
 * in the product: an operator signs in on his own phone and every visit is attributed to him.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { Field, Input, Select } from '../rj-ui/Field';
import { Segmented } from '../rj-ui/Segmented';
import { Toggle } from '../rj-ui/Toggle';
import { FilterMenu } from '../rj-ui/FilterMenu';
import { hasFailed, isLoading, isReady } from '../loading';
import { Skeleton } from '../rj-ui/Skeleton';
import { Check, Lock, Megaphone, ShieldCheck, UserCog, UserRound } from 'lucide-react';
import { Link } from 'react-router-dom';
import { STORE_PATH } from '../nav';
import { action, call, type Catalog } from '../catalog';
import { branchGate } from '../branches';
import type { Session } from '../session';
import { digitsOnly } from '../digits';
import { isShortGoogleMapsLink, parseGoogleMapsLink } from '../googleMapsLink';
import { AssistantHint } from '../AssistantHint';

interface DayHours { closed?: boolean; start_minute?: number; end_minute?: number }

interface Operator {
  id: string; name: string; role?: string; active?: boolean;
  /** Where he WORKS — one place, and it decides where his visits are counted. */
  branch_id?: string;
  /** What he may SEE, which is a different question and often a wider answer. */
  visible_branch_ids?: string[];
  visible_all?: boolean;
  /** `null`/absent = inherits the shop's own hours in full (the zero-config default — most
   *  shops never touch this). A real object = an explicit manual override for this one person. */
  working_hours?: Record<string, DayHours> | null;
}

// نفس ترتيب العرض وتسمية الأيام في BookingSettingsDialog.tsx — الأحد أولاً، ونفس ترقيم weekday()
// المخزَّن فعلياً بلا أي ترجمة.
const HOURS_DISPLAY_ORDER = [6, 0, 1, 2, 3, 4, 5];
const HOURS_DAY_LABEL: Record<number, string> = {
  6: 'الأحد', 0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت',
};
function hoursMinutesToTime(m: number): string {
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}
function hoursTimeToMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return (h || 0) * 60 + (m || 0);
}

/**
 * The roles an owner may give somebody he is adding.
 *
 * `owner` IS ABSENT, and that is the rule rather than an omission: it is protected, there is
 * exactly one, and transferring it is its own act with its own confirmation — not a value in a
 * dropdown on the add form. `partner` is absent too; a till company is not staff, and it never
 * signs in to a shop's console.
 *
 * THE LINE UNDER EACH ONE IS WHAT HE ACTUALLY DECIDES BY. An owner picking between «مدير» and
 * «مشرف وردية» is not choosing a word, he is choosing what that person may touch — and a name
 * with no consequence beside it is a guess.
 */
const ROLES: { value: string; label: string; can: string; icon: typeof UserRound }[] = [
  // "يسجّل الزيارات فقط" كانت صحيحة قبل الحجوزات — الدور نفسه في roles.json يحمل
  // bookings.read/bookings.write منذ ذلك الحين — الوصف الظاهر لا بد أن يبقى دقيقاً.
  { value: 'operator', label: 'موظف ميداني', can: 'يسجّل الزيارات ويحجز', icon: UserRound },
  { value: 'supervisor', label: 'مشرف وردية', can: 'الزيارات والحجوزات وعملاء ورديته والتقارير', icon: ShieldCheck },
  { value: 'marketer', label: 'مسؤول التسويق', can: 'الحملات والرسائل، بلا تعديل الخدمات', icon: Megaphone },
  { value: 'manager', label: 'مدير', can: 'كل شيء عدا الفوترة وحذف الحساب', icon: UserCog },
];
interface Branch { id: string; name: string; active?: boolean; lat?: number; lng?: number; city?: string }

/** Just enough of a service to list it as a candidate — mirrors Services.tsx's own reading of
 *  `eligible_staff_ids` (empty/absent = every active FIELD-ROLE operator, the zero-config
 *  default — assignment-mode redesign phase 2). `assignment_mode` decides whether this screen
 *  offers the service here at all: an "auto" one is never assigned BY NAME, from either side. */
interface ServiceLite { id: string; name: string; active?: boolean; eligible_staff_ids?: string[];
  assignment_mode?: 'named' | 'auto' }

/** What the branch comparison already computes for the whole shop (insights, spec 10.6.3). */
interface BranchStat { branch_id?: string; visits?: number; customers?: number }

/** The establishment's branch mode, and whether the second one may be chosen at all. */
interface Mode { mode: string; available?: boolean }

/** The one branch every shop has from its first minute. Ours to create, his to rename, and it
 *  cannot be closed — it is where an unrecognised branch lands (services/operations/core/branches.py). */
const MAIN_BRANCH = 'brn-main';

export function TeamScreen({ session, catalog, tab: controlledTab, onChangeTab, onBranchGateChange }: {
  session: Session;
  catalog: Catalog;
  /** CONTROLLED MODE — for a parent that has already folded «العاملون»/«الفروع» into its OWN
   *  single-level tab switcher (Account.tsx's SHOP_SUBTABS) rather than nesting a second one
   *  under a "الفروع والفريق" wrapper tab. When given, this screen renders NO switcher of its
   *  own — the "never two tab strips stacked" rule (see the owner's own instruction and
   *  ci/check_no_two_tab_strips_stack_in_one_view.py). Omit both for the standalone `/team`
   *  route (TeamRoute.tsx), which has no switcher above it and needs this screen's own. */
  tab?: 'people' | 'branches';
  onChangeTab?: (tab: 'people' | 'branches') => void;
  /** Reports the branch tab's own lock state (`branchGate`, هـ-3) as soon as it is known, so a
   *  parent rendering the label itself (Account.tsx, controlled mode) can put the same 🔒 on it
   *  this screen would otherwise draw on its own internal tab. Fires with `'open'` before the
   *  branches read resolves — the exact same "never lock on an unknown" default `branchGate`
   *  itself already returns for an unresolved limit. */
  onBranchGateChange?: (gate: ReturnType<typeof branchGate>) => void;
}) {
  const [internalTab, setInternalTab] = useState<'people' | 'branches'>('people');
  const tab = controlledTab ?? internalTab;
  const setTab = onChangeTab ?? setInternalTab;
  const [operators, setOperators] = useState<Operator[] | null | undefined>(undefined);
  const [branches, setBranches] = useState<Branch[] | null | undefined>(undefined);
  /**
   * HOW MANY BRANCHES HIS APP ENTITLEMENT ALLOWS — the entitlement, which is not the capability.
   *
   * `undefined` while the read is out or was never made, and `-1` for «no known ceiling»: an
   * unlimited entitlement and a billing we could not reach are both that, and neither may draw a lock.
   * Only a stated limit of 1 is the base entitlement, and only that draws the sentence about the app store.
   */
  const [branchLimit, setBranchLimit] = useState<number | undefined>(undefined);
  // WHETHER ONE MORE FITS RIGHT NOW — a different question from the ceiling, and the only one
  // the «إضافة فرع» button can answer honestly. `undefined` is an answer that did not arrive,
  // and it never hides the button: an outage must not read as an app entitlement he has outgrown.
  const [mayAddBranch, setMayAddBranch] = useState<boolean | undefined>(undefined);
  /**
   * WHETHER «رمز على الجهاز» EXISTS ON THIS DEPLOYMENT.
   *
   * The whole path is built and switched off (`PIN_OPERATORS_ENABLED`), and the door refuses it
   * while it is — so the form offers ONE way of adding somebody rather than two, one of which
   * answers with an error by design.
   *
   * FALSE UNTIL THE SERVER SAYS OTHERWISE, including on a failed read: hiding a path we could not
   * ask about costs an owner one form; showing one the door refuses costs him a failure he cannot
   * explain.
   */
  const [pinKind, setPinKind] = useState(false);
  // FOR THE SAME EDIT «تخصيص دوام» ALREADY OFFERS, ON THE OTHER SIDE OF THE SAME FACT — an owner
  // asking "what does HE do" is the mirror of Services.tsx's own "who does THIS", and the answer
  // lives in the exact same field (`Service.eligible_staff_ids`), just read from the operator's
  // row instead of the service's.
  const [services, setServices] = useState<ServiceLite[] | null | undefined>(undefined);

  // WHAT THIS PERSON MAY DO, FROM THE CATALOGUE. The gateway has already filtered it by
  // capability, so an absent action is a permission fact — and the control simply is not rendered.
  const addOperator = action(catalog, 'operations.create_operator');
  const addBranch = action(catalog, 'operations.create_branch');
  const editBranch = action(catalog, 'operations.update_branch');
  const listBranches = action(catalog, 'operations.list_branches');
  const setHours = action(catalog, 'operations.set_staff_hours');
  const clearHours = action(catalog, 'operations.clear_staff_hours');
  // SAME ACTION SERVICES.TSX PATCHES SERVICES WITH — no new route, no new capability; this pane
  // just calls the same PATCH from the operator's side of the same field.
  const updateService = action(catalog, 'operations.update_service');

  const load = () => {
    const svc = action(catalog, 'operations.manage_services') ?? action(catalog, 'operations.list_services');
    if (svc) {
      call<{ services: ServiceLite[] }>(session, svc)
        .then((x) => setServices(x.services ?? []))
        .catch(() => setServices(null));
    } else {
      setServices(null);
    }

    const o = action(catalog, 'operations.list_operators');
    if (o) {
      call<{ operators: Operator[]; pin_operators_enabled?: boolean }>(session, o)
        .then((x) => {
          setOperators(x.operators ?? []);
          // THE DEPLOYMENT'S ANSWER, NOT OURS. «رمز على الجهاز» is built end to end and switched
          // off (`PIN_OPERATORS_ENABLED`), and the door refuses it while it is — so offering the
          // choice here would be a control that returns an error by design. `undefined` on a
          // failed read stays false: hiding a path we could not ask about costs one owner one
          // form; showing one the server refuses costs him a confusing failure.
          setPinKind(x.pin_operators_enabled === true);
        })
        .catch(() => setOperators(null));
    } else {
      setOperators([]);
    }

    if (listBranches) {
      call<{ branches: Branch[]; branch_limit?: number; may_add_branch?: boolean }>(session, listBranches)
        .then((x) => {
          setBranches(x.branches ?? []);
          // NOT COERCED TO A NUMBER. An answer that did not carry the limit has told us nothing
          // about his app entitlement, and `?? 0` there would lock every shop out of a tab it may own.
          setBranchLimit(typeof x.branch_limit === 'number' ? x.branch_limit : undefined);
          setMayAddBranch(typeof x.may_add_branch === 'boolean' ? x.may_add_branch : undefined);
        })
        .catch(() => setBranches(null));
    } else {
      setBranches(null);
    }
  };

  useEffect(load, [session, catalog]);

  // REPORT THE LOCK STATE AS SOON AS IT'S KNOWN, controlled mode or not — a parent rendering the
  // label itself needs the exact same answer this screen's own (uncontrolled) label below draws
  // from, not a second, possibly-stale copy of the same computation.
  useEffect(() => {
    onBranchGateChange?.(branchGate(Boolean(listBranches), branchLimit));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onBranchGateChange is a per-render
    // callback the parent owns; it is not a dependency of "did the gate itself change".
  }, [Boolean(listBranches), branchLimit]);

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* NO SWITCHER OF ITS OWN IN CONTROLLED MODE — Account.tsx already renders one strip
          (SHOP_SUBTABS) that includes «العاملون»/«الفروع» directly as two of its own options, so
          a second strip here would stack right under it (the "شريطين تحت بعض" the owner ruled
          out entirely, whichever level it's at). The standalone `/team` route has no switcher
          above it at all, so it still gets this one. */}
      {controlledTab === undefined ? (
        <Segmented
          // FULL WIDTH, SPLIT EVENLY, NEVER WRAPPED. The kit's Segmented is
          // `inline-flex flex-wrap`, which on a phone stacks two long Arabic labels into a
          // ragged block half the screen wide. It takes a className and merges with
          // tailwind-merge, so this is a fix at the call site rather than a fork of the kit.
          className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
          options={[
            { value: 'people', label: 'العاملون' },
            // THE LOCK IS ON THE LABEL, so it is visible before he presses and not after. A tab that
            // looks pressable and then refuses is worse than one that says so. It marks BOTH kinds
            // of closed door — «not yours» and «not in your enabled apps» — and the panel says which.
            { value: 'branches',
              label: branchGate(Boolean(listBranches), branchLimit) === 'open'
                ? 'الفروع' : 'الفروع 🔒' },
          ]}
          value={tab}
          onChange={setTab}
        />
      ) : null}

      {tab === 'people'
        ? <People
            session={session}
            operators={operators}
            branches={branches}
            add={addOperator}
            edit={action(catalog, 'operations.update_operator')}
            hire={action(catalog, 'operations.hire_member')}
            setHours={setHours}
            clearHours={clearHours}
            services={services}
            updateService={updateService}
            pinKind={pinKind}
            onChanged={load}
          />
        : <Branches
            session={session}
            catalog={catalog}
            branches={branches}
            operators={operators}
            add={addBranch}
            edit={editBranch}
            mayRead={Boolean(listBranches)}
            limit={branchLimit}
            mayAdd={mayAddBranch}
            onChanged={load}
          />}
    </div>
  );
}

// EXPORTED FOR THE SAME REASON `Branches` IS BELOW: its own test needs it directly rather than
// driving the whole `TeamScreen` (catalogue, both reads, both tabs) to reach one form.
export function People({ session, operators, branches, add, edit, hire, setHours, clearHours,
                        services, updateService, pinKind, onChanged }: {
  session: Session;
  operators: Operator[] | null | undefined;
  branches: Branch[] | null | undefined;
  add: ReturnType<typeof action>;
  edit: ReturnType<typeof action>;
  hire: ReturnType<typeof action>;
  setHours?: ReturnType<typeof action>;
  clearHours?: ReturnType<typeof action>;
  services?: ServiceLite[] | null;
  updateService?: ReturnType<typeof action>;
  /** Whether this deployment offers «رمز على الجهاز» at all — the server's answer, not a guess. */
  pinKind: boolean;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [pin, setPin] = useState('');
  /**
   * TWO KINDS OF PERSON, AND THE SHOP DECIDES WHICH IT IS ADDING.
   *
   * A PIN is attribution on a shared tablet: it answers «which of the three of us saved that
   * visit» and protects nothing. A LOGIN is authentication: his own phone and password, his own
   * role, and — the reason this exists — a branch he is scoped to, so a manager in Jeddah does
   * not read Riyadh's customers (§12.4).
   *
   * Both were impossible to tell apart on this screen until now, because only one existed.
   */
  // THE DEFAULT FOLLOWS WHAT EXISTS. «رمز على الجهاز» is switched off on this deployment, and
  // opening the form on a kind the door refuses would make the commonest act fail by design.
  const [kind, setKind] = useState<'pin' | 'login'>(pinKind ? 'pin' : 'login');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [branchId, setBranchId] = useState('');
  // DEFAULTS TO THE NARROWEST. Adding somebody is a routine act done in a hurry, and a form that
  // opens on «مدير» hands out the shop to whoever is added while nobody was reading.
  const [role, setRole] = useState('operator');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!add) return;
    setBusy(true);
    setError('');
    try {
      // EXPLICIT, ALWAYS — NEVER GUESSED. A shop with one place used to skip
      // the picker entirely and send branch_id="", which api/scope.py reads as «unassigned =
      // sees the WHOLE establishment», never «works at the one branch that exists». Harmless the
      // day he is hired — one branch either way — and wrong the day the owner opens a second
      // one: every employee hired before it silently starts seeing BOTH, because nobody ever
      // chose to widen them. The server itself now refuses an empty branch_id outright
      // (`staff.py`'s own BRANCH_REQUIRED) — this form just makes sure he never reaches that
      // refusal: the picker is always shown, and submit stays disabled until he has actually
      // chosen «الفرع الرئيسي» or another real branch himself.
      if (kind === 'login') {
        if (!hire) return;
        await call(session, hire, {
          name: name.trim(), phone: phone.trim(), password, role, branch_id: branchId,
        });
      } else {
        await call(session, add, { name: name.trim(), pin, role, branch_id: branchId });
      }
      setName('');
      setPin('');
      setPhone('');
      setPassword('');
      setBranchId('');
      setRole('operator');
      setOpen(false);
      onChanged();
    } catch (err) {
      // THE SERVER'S SENTENCE, WHICH IS WHERE THE SEAT LIMIT LIVES. It names the number; a message
      // written here would be a second copy of an entitlement we do not hold.
      setError(err instanceof Error ? err.message : 'تعذّر إضافة الموظف.');
    } finally {
      setBusy(false);
    }
  }

  if (isLoading(operators)) return <Skeleton height={200} />;

  return (
    <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      {hasFailed(operators) ? (
        // «لا يوجد موظفون بعد» INVITES HIM TO ADD PEOPLE HE ALREADY HAS. Said after a failed read
        // it is an instruction to redo work, on the screen that decides who sees whose data.
        <EmptyState
          title="تعذّرت قراءة فريقك"
          description="لم نستطع جلبه الآن، والخلل عندنا. أعد المحاولة بعد قليل."
        />
      ) : operators.length === 0 ? (
        <EmptyState
          title="لا يوجد موظفون بعد"
          description="أضف موظفيك ليسجّلوا الزيارات بحساباتهم."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {operators.map((o) => (
            <OperatorRow key={o.id} session={session} o={o} allOperators={operators} branches={branches}
                        edit={edit} setHours={setHours} clearHours={clearHours}
                        services={services} updateService={updateService} onChanged={onChanged} />
          ))}
        </ul>
      )}

      {/* THE BUTTON THE SCREEN WAS MISSING. It said «أضف موظفيك» and offered no way to — a screen
          that asks for an action it does not provide, found by using it. */}
      {add && !open ? (
        <Button onClick={() => setOpen(true)}>إضافة موظف</Button>
      ) : null}

      {add && open ? (
        <form onSubmit={submit} className="flex flex-col gap-3 border-t border-border-subtle pt-3">
          <Field label="الاسم" required htmlFor="op-name">
            <Input id="op-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </Field>

          {/* THE CHOICE IS NAMED BY WHAT IT GIVES HIM, not by our words for it. «رمز على الجهاز»
              and «حساب يدخل به» are the two things a shop owner actually decides between. */}
          {/* THE CHOICE ONLY EXISTS WHERE BOTH KINDS DO. With the shared-tablet employee switched
              off there is one way of adding somebody, and a two-option control whose second option
              is refused at the door is worse than no control at all. */}
          {hire && pinKind ? (
            <div className="flex items-center gap-2">
              <Segmented
                className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
                ariaLabel="نوع الإضافة"
                value={kind}
                onChange={(v) => setKind(v as 'pin' | 'login')}
                options={[
                  { value: 'pin', label: 'رمز على الجهاز' },
                  { value: 'login', label: 'حساب يدخل به' },
                ]}
              />
              <AssistantHint anchor="team.add_kind" session={session} />
            </div>
          ) : null}

          {kind === 'login' ? (
            <>
              <Field label="جوّاله" required htmlFor="op-phone">
                <Input id="op-phone" value={phone} inputMode="tel" dir="ltr"
                       onChange={(e) => setPhone(e.target.value)} />
              </Field>
              {/* HE CHANGES IT LATER; THE OWNER CHOOSES IT NOW. A temporary password the manager
                  says out loud beats an invite link a shop employee never opens. */}
              <Field label="كلمة مرور مؤقتة" required htmlFor="op-pw">
                <Input id="op-pw" value={password} type="password"
                       onChange={(e) => setPassword(e.target.value)} />
              </Field>
            </>
          ) : null}

          {/* THE BRANCH BELONGS TO BOTH KINDS OF EMPLOYEE, AND IT USED TO BE INSIDE THE LOGIN BLOCK.
              So a PIN operator — the man on the shared tablet, which is most of a workshop's staff
              — could never be given one from any screen. And a visit takes its branch from the
              person recording it, so every visit he took landed in «غير محدَّد». An owner with three
              branches opened his comparison table and read three empty rows and one huge unnamed
              one, with nothing on any screen to tell him why.

              ALWAYS SHOWN NOW, EVEN FOR ONE PLACE — «كل الفروع» is gone as an
              option entirely. A single-branch shop still picks «الفرع الرئيسي» explicitly: the
              choice is a fact he made, not a silent default nobody asked him about. Opens on NO
              selection (`branchId` starts empty) so submit stays disabled until he has actually
              touched it — a pre-selected first option would be the same silent default in a
              different shape. */}
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-text-secondary">فرعه</span>
            <Select value={branchId} aria-label="فرع الموظف" required
                   onChange={(e) => setBranchId(e.target.value)}>
              <option value="" disabled>اختر الفرع…</option>
              {(branches ?? []).filter((b) => b.active !== false).map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </Select>
            <span className="text-xs text-text-secondary">
              {kind === 'pin'
                ? 'الزيارات التي يسجّلها تُنسب لهذا الفرع.'
                : 'من له فرع يرى بيانات فرعه وحده، وزياراته تُنسب إليه.'}
            </span>
          </label>
          {/* FOUR DIGITS, AND THE SERVER SAYS FOUR. A longer PIN is not meaningfully safer for what
              it protects and IS meaningfully slower to type a hundred times a day. */}
          {kind === 'pin' ? (
          <Field label="رمز الدخول (4 أرقام)" required htmlFor="op-pin">
            <Input
              id="op-pin" value={pin} inputMode="numeric" dir="ltr" maxLength={4}
              onChange={(e) => setPin(digitsOnly(e.target.value).slice(0, 4))}
            />
          </Field>
          ) : null}
          {/* THE ROLE, ASKED RATHER THAN ASSUMED. The form sent `operator` silently — so a shop
              that wanted a manager had no way to say so, and «فريقي» could only ever produce one
              kind of person. */}
          <fieldset className="flex flex-col gap-2">
            {/* `<legend>` only ever accepts phrasing content — AssistantHint's opened state is a
                block-level `<p>`, and browsers do not agree on what to do with one nested inside a
                legend (observed live: the fieldset's layout box breaks and the whole page grows
                tall with a deep scroll the moment the hint opens). The label and the hint sit in an
                ordinary `<div>` right above the fieldset instead — same visual placement, valid
                nesting either way. */}
            <div className="mb-1 flex items-center gap-1 text-sm text-text-secondary">
              الدور
              <AssistantHint anchor="team.roles" session={session} />
            </div>
            <legend className="sr-only">الدور</legend>
            <div className="grid gap-2 sm:grid-cols-2">
              {ROLES.map((r) => {
                const selected = role === r.value;
                const Icon = r.icon;
                return (
                  <label
                    key={r.value}
                    className={[
                      'flex cursor-pointer items-center gap-3 rounded-card border px-3 py-3 shadow-sm transition-colors',
                      selected
                        ? 'border-accent bg-accent-soft text-accent-on-soft'
                        : 'border-border-subtle hover:border-border-strong hover:bg-surface-2',
                    ].join(' ')}
                  >
                    <input
                      type="radio" name="op-role" value={r.value} checked={selected}
                      onChange={() => setRole(r.value)} className="sr-only"
                    />
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-surface-2 text-text-primary">
                      <Icon size={18} aria-hidden />
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="truncate text-sm font-semibold">{r.label}</span>
                      <span className="truncate text-xs opacity-80">{r.can}</span>
                    </span>
                    {selected ? <Check size={16} aria-hidden className="shrink-0" /> : null}
                  </label>
                );
              })}
            </div>
          </fieldset>

          {error ? <p role="alert" className="text-danger">{error}</p> : null}
          <div className="flex gap-2">
            <Button
              type="submit"
              disabled={busy || name.trim().length === 0 || branchId.length === 0
                || (kind === 'pin' ? pin.length !== 4
                    : phone.trim().length < 6 || password.length < 8)}
            >
              {busy ? 'جارٍ الحفظ…' : 'حفظ'}
            </Button>
            <Button type="button" variant="ghost" onClick={() => { setOpen(false); setError(''); }}>
              إلغاء
            </Button>
          </div>
        </form>
      ) : null}
    </section>
  );
}

/**
 * ONE EMPLOYEE'S ROW — rename, role, and stop/reactivate, ALWAYS available (never behind the
 * branch count). Found from a screenshot: a single-branch shop's «فريقي» showed a name and a
 * role and NOTHING ELSE — the branch/visibility controls below were the only management this
 * screen ever offered, and both are gated on `branches.length > 1`. The backend
 * (`operations/api/v1/staff.py::update_operator`) has always accepted name, role and active —
 * an owner just never had a control that called it for any of the three, on any shop, branch
 * count irrelevant. An employee who left could not be stopped from this screen at all.
 */
function OperatorRow({ session, o, allOperators, branches, edit, setHours, clearHours,
                       services, updateService, onChanged }: {
  session: Session;
  o: Operator;
  allOperators: Operator[] | null | undefined;
  branches: Branch[] | null | undefined;
  edit: ReturnType<typeof action>;
  setHours?: ReturnType<typeof action>;
  clearHours?: ReturnType<typeof action>;
  services?: ServiceLite[] | null;
  updateService?: ReturnType<typeof action>;
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(o.name);
  const [role, setRole] = useState(o.role ?? 'operator');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // مطوي افتراضياً دائماً — «تخصيص دوام» لا يُرى إطلاقاً من محل ما لمسه أبداً (§3 من الخطة).
  const [hoursOpen, setHoursOpen] = useState(false);
  const [hoursDraft, setHoursDraft] = useState<Record<string, DayHours>>(o.working_hours ?? {});
  const [hoursBusy, setHoursBusy] = useState(false);
  const [hoursError, setHoursError] = useState('');
  const customised = Boolean(o.working_hours);

  function setDay(day: number, patch: Partial<DayHours>) {
    setHoursDraft((cur) => ({
      ...cur,
      [day]: { ...(cur[day] ?? { closed: false, start_minute: 480, end_minute: 1320 }), ...patch },
    }));
  }

  async function saveHours() {
    if (!setHours) return;
    setHoursBusy(true);
    setHoursError('');
    try {
      const weekly: Record<string, DayHours> = {};
      for (let d = 0; d < 7; d++) {
        weekly[String(d)] = hoursDraft[String(d)]
          ?? { closed: false, start_minute: 480, end_minute: 1320 };
      }
      await call(session, setHours, { id: o.id, weekly });
      setHoursOpen(false);
      onChanged();
    } catch (err) {
      setHoursError(err instanceof Error ? err.message : 'تعذّر حفظ الدوام.');
    } finally {
      setHoursBusy(false);
    }
  }

  async function resetHours() {
    if (!clearHours) return;
    setHoursBusy(true);
    setHoursError('');
    try {
      await call(session, clearHours, { id: o.id });
      setHoursOpen(false);
      onChanged();
    } catch (err) {
      setHoursError(err instanceof Error ? err.message : 'تعذّر إعادة الدوام.');
    } finally {
      setHoursBusy(false);
    }
  }

  // «أي خدمات يسوّيها» — الوجه الآخر لنفس الحقل اللي «خدماتي» تُخصّصه من جهة الخدمة (§3 من خطة
  // الحجوزات الذكية). نفس منيو الفلترة المستخدمة في كل مكان آخر بالكونسول (`rj-ui/FilterMenu`) —
  // زر بعدّاد + منيو بمربعات اختيار، لا صف خام من checkbox مبعثرة.
  const [servicesBusy, setServicesBusy] = useState(false);
  const [servicesError, setServicesError] = useState('');

  // الافتراضي بلا قيد يطابق الخادم الآن: كل موظف نشط بدور ميداني، لا كل موظف نشط بأي دور
  // (assignment-mode redesign phase 2) — نفس تصحيح Services.tsx بالضبط.
  const fieldActiveIds = (allOperators ?? [])
    .filter((op) => op.active !== false && op.role === 'operator').map((op) => op.id);

  async function toggleService(svc: ServiceLite) {
    if (!updateService) return;
    const current = svc.eligible_staff_ids && svc.eligible_staff_ids.length > 0
      ? new Set(svc.eligible_staff_ids)
      : new Set(fieldActiveIds);   // «الافتراضي بلا قيد» — الموظفون الميدانيون فقط
    if (current.has(o.id)) current.delete(o.id); else current.add(o.id);
    // لا نخزّن «الافتراضي بالاسم» أبداً — نفس قاعدة Services.tsx بالضبط: الموظف الميداني السادس
    // المُضاف مستقبلاً لازم يبقى مؤهلاً تلقائياً لخدمة لم يقيّدها أحد، لا مستبعداً بصمت من قائمة جامدة.
    const isExactlyTheDefault = current.size === fieldActiveIds.length
      && fieldActiveIds.every((id) => current.has(id));
    const eligible_staff_ids = isExactlyTheDefault ? [] : [...current];
    setServicesBusy(true);
    setServicesError('');
    try {
      await call(session, updateService, { id: svc.id, eligible_staff_ids });
      onChanged();
    } catch (err) {
      setServicesError(err instanceof Error ? err.message : 'تعذّر حفظ التعديل.');
    } finally {
      setServicesBusy(false);
    }
  }

  // FilterMenu ONLY KNOWS "the new full selection", NOT which box(es) changed — eligibility is
  // stored per SERVICE, not per operator, so the actual write is a diff against what was selected
  // a moment ago, applied to EVERY service that changed (one call each — "مسح الكل" alone can
  // change every box at once, not just the first one a naive single-diff would catch).
  function isEligible(svc: ServiceLite): boolean {
    return svc.eligible_staff_ids && svc.eligible_staff_ids.length > 0
      ? svc.eligible_staff_ids.includes(o.id)
      : true;   // «الافتراضي بلا قيد» — الموظفون الميدانيون فقط؛ هذي القائمة أصلاً services
                // مصفّاة بـ assignment_mode !== 'auto' تحت، فكل خدمة هنا «بالاسم» بالتعريف.
  }
  // خدمات «تلقائي» غير معروضة هنا إطلاقاً — لا معنى لسؤال "هل هذا الموظف مؤهَّل بالاسم" لخدمة
  // لا تُسأل بالاسم أصلاً؛ يبقى تخصيصها ممكناً من «خدماتي» فقط (القائمة نفسها، بس تحت الخدمة).
  const activeServices = (services ?? [])
    .filter((s) => s.active !== false && s.assignment_mode !== 'auto');
  const eligibleServiceIds = activeServices.filter(isEligible).map((s) => s.id);
  async function onServicesChange(next: string[]) {
    const changedIds = [
      ...next.filter((id) => !eligibleServiceIds.includes(id)),
      ...eligibleServiceIds.filter((id) => !next.includes(id)),
    ];
    for (const id of changedIds) {
      const svc = activeServices.find((s) => s.id === id);
      if (svc) await toggleService(svc);
    }
  }

  async function save() {
    if (!edit) return;
    setBusy(true);
    setError('');
    try {
      const patch: Record<string, unknown> = {};
      if (name.trim() && name.trim() !== o.name) patch.name = name.trim();
      if (role !== o.role) patch.role = role;
      if (Object.keys(patch).length) await call(session, edit, { id: o.id, ...patch });
      setEditing(false);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر الحفظ.');
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive() {
    if (!edit) return;
    setBusy(true);
    setError('');
    try {
      // DEACTIVATE, NEVER DELETE (staff.py's own words) — his history stays his. Reactivating
      // somebody who was stopped needs a fresh login (server refuses REHIRE_REQUIRED otherwise);
      // that sentence comes back through `call`'s own error and is shown as-is, same as every
      // other refusal on this screen.
      await call(session, edit, { id: o.id, active: o.active === false });
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر الحفظ.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="flex flex-col gap-2 border-b border-border-subtle pb-2 last:border-0 last:pb-0">
      <div className="flex items-center justify-between gap-3">
        <span className="flex flex-col">
          <span>{o.name}</span>
          {/* SHOWN IN THE LIST TOO. A team screen that hides what each person may do is a
              screen an owner cannot audit — and the question he asks is always "who can
              touch the billing", never "how many employees do I have". */}
          <span className="text-sm text-text-secondary">
            {ROLES.find((r) => r.value === o.role)?.label ?? o.role ?? ''}
            {o.active === false ? ' · موقوف' : ''}
          </span>
        </span>

        {edit ? (
          <div className="flex items-center gap-2">
            <Button type="button" variant="ghost" className="text-sm"
                    onClick={() => { setName(o.name); setRole(o.role ?? 'operator'); setEditing((v) => !v); }}>
              تعديل
            </Button>
            <Button type="button" variant="ghost" className="text-sm text-danger"
                    disabled={busy} onClick={toggleActive}>
              {o.active === false ? 'إعادة تفعيل' : 'إيقاف'}
            </Button>
          </div>
        ) : null}
      </div>

      {editing ? (
        <div className="flex flex-wrap items-end gap-2 rounded-xl bg-surface-2 p-2">
          <Field label="الاسم" htmlFor={`op-name-${o.id}`}>
            <Input id={`op-name-${o.id}`} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-text-secondary">الدور</span>
            <Select value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </Select>
          </label>
          <Button type="button" disabled={busy} onClick={save}>حفظ</Button>
          <Button type="button" variant="ghost" onClick={() => setEditing(false)}>إلغاء</Button>
        </div>
      ) : null}

      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}

      {o.active === false ? null : (
        /* HIS BRANCH, CHANGEABLE IN PLACE — and it decides something: a visit he saves is filed
           under HIS branch, whatever the device sends (services/operations/core/operations.py).
           ALWAYS SHOWN NOW, even for one place — a single-branch shop still
           gets to see and confirm «الفرع الرئيسي», not a hidden control. «كل الفروع» is gone as
           a choice: an owner cannot put somebody back into it, matching the server's own refusal
           (staff.py's BRANCH_REQUIRED). A row still carrying the old empty state (hired before
           this rule) shows a disabled placeholder rather than a false selection — he has to pick
           a real branch to clear it, same as adding somebody new. */
        edit ? (
          <label className="flex items-center gap-2 text-sm">
            <span className="shrink-0 text-text-secondary">فرعه</span>
            <Select
              className="w-auto"
              value={o.branch_id ?? ''}
              aria-label={`فرع ${o.name}`}
              onChange={async (e) => {
                if (!e.target.value) return;
                await call(session, edit, { id: o.id, branch_id: e.target.value })
                  .catch(() => undefined);
                onChanged();
              }}
            >
              {o.branch_id ? null : <option value="" disabled>فرع غير محدَّد — اختره الآن</option>}
              {(branches ?? []).filter((b) => b.active !== false).map((b) => (
                <option key={b.id} value={b.id}>{b.name}</option>
              ))}
            </Select>
          </label>
        ) : null
      )}
      {/* AND WHAT HE MAY SEE, which is NOT where he works — the two were one field until
          now, so an owner could say «this branch» or «everything» and nothing between, and
          a supervisor over three had to be handed the whole chain to be given his three.
          Beside the station rather than instead of it: a man works in one place and may
          watch several, and both facts have to be readable at a glance or nobody can audit
          a grant. */}
      {o.active !== false && (branches ?? []).length > 1 && edit ? (
        <fieldset className="flex flex-wrap items-center gap-2 text-sm">
          <legend className="sr-only">{`ما يراه ${o.name}`}</legend>
          <span className="text-text-secondary">يرى</span>
          <AssistantHint anchor="team.branch_visibility" session={session} />
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              className="size-5"
              checked={o.visible_all === true}
              onChange={async (e) => {
                await call(session, edit, { id: o.id, visible_all: e.target.checked })
                  .catch(() => undefined);
                onChanged();
              }}
            />
            <span>كل الفروع</span>
          </label>
          {o.visible_all === true ? null : (branches ?? [])
            .filter((b) => b.active !== false)
            .map((b) => {
              // HIS OWN BRANCH IS ALWAYS AMONG THEM, granted or not: a man sees where he
              // works, and a screen that let an owner take that away would produce an
              // employee who cannot read his own counter.
              const granted = (o.visible_branch_ids ?? []).includes(b.id) || o.branch_id === b.id;
              return (
                <label key={b.id} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    className="size-5"
                    checked={granted}
                    disabled={o.branch_id === b.id}
                    onChange={async (e) => {
                      const now = new Set(o.visible_branch_ids ?? []);
                      if (e.target.checked) now.add(b.id); else now.delete(b.id);
                      await call(session, edit,
                        { id: o.id, visible_branch_ids: [...now] }).catch(() => undefined);
                      onChanged();
                    }}
                  />
                  <span>{b.name}</span>
                </label>
              );
            })}
        </fieldset>
      ) : null}

      {/* دوام مخصص — مطويّ افتراضياً بالكامل، ولا يظهر إطلاقاً لمن لا صلاحية له. محل لا يفتحه
          أبداً لا يرى منه غير هذا الزر، ودوام الموظف يبقى دوام المحل بلا أي تغيير محسوس. */}
      {o.active !== false && setHours && clearHours ? (
        <div className="text-sm">
          <span className="inline-flex items-center gap-1">
            <button type="button" className="text-text-secondary underline underline-offset-2"
                    onClick={() => { setHoursDraft(o.working_hours ?? {}); setHoursOpen((v) => !v); }}>
              {customised ? 'دوام مخصص لهذا الموظف' : 'تخصيص دوام'}
            </button>
            <AssistantHint anchor="team.custom_hours" session={session} />
          </span>

          {hoursOpen ? (
            <div className="mt-2 flex flex-col gap-2 rounded-xl bg-surface-2 p-2">
              {HOURS_DISPLAY_ORDER.map((day) => {
                const d = hoursDraft[String(day)]
                  ?? { closed: false, start_minute: 480, end_minute: 1320 };
                return (
                  <div key={day} className="flex items-center gap-3">
                    <span className="w-16 shrink-0 text-xs font-semibold">
                      {HOURS_DAY_LABEL[day]}
                    </span>
                    <label className="flex shrink-0 items-center gap-1.5 text-xs text-text-secondary">
                      <input type="checkbox" checked={!d.closed}
                            onChange={(e) => setDay(day, { closed: !e.target.checked })} />
                      مفتوح
                    </label>
                    {!d.closed ? (
                      <div className="flex flex-1 items-center gap-2">
                        <input type="time" value={hoursMinutesToTime(d.start_minute ?? 480)}
                              onChange={(e) => setDay(day, { start_minute: hoursTimeToMinutes(e.target.value) })}
                              className="h-9 rounded-lg bg-surface-1 px-2 text-xs" dir="ltr" />
                        <span className="text-text-secondary">إلى</span>
                        <input type="time" value={hoursMinutesToTime(d.end_minute ?? 1320)}
                              onChange={(e) => setDay(day, { end_minute: hoursTimeToMinutes(e.target.value) })}
                              className="h-9 rounded-lg bg-surface-1 px-2 text-xs" dir="ltr" />
                      </div>
                    ) : (
                      <span className="flex-1 text-xs text-text-muted">مغلق</span>
                    )}
                  </div>
                );
              })}

              {hoursError ? <p role="alert" className="text-danger text-xs">{hoursError}</p> : null}

              <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-2">
                {customised ? (
                  <Button type="button" variant="ghost" className="text-xs" disabled={hoursBusy}
                          onClick={resetHours}>
                    الرجوع لدوام المحل
                  </Button>
                ) : null}
                <Button type="button" variant="ghost" className="text-xs"
                        onClick={() => setHoursOpen(false)}>
                  إلغاء
                </Button>
                <Button type="button" className="text-xs" disabled={hoursBusy} onClick={saveHours}>
                  حفظ
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* «أي خدمات يسوّيها» — نفس شرط ظهور «من يقدر يسوّيها» في «خدماتي»: لا معنى له إن كان
          عندك موظف نشط واحد فقط، فلا يظهر إطلاقاً في تلك الحالة. */}
      {o.active !== false && updateService
          && (allOperators ?? []).filter((op) => op.active !== false).length > 1
          && activeServices.length > 0 ? (
        <div>
          <div className="flex items-center gap-1">
            <FilterMenu
              label="أي خدمات يسوّيها"
              options={activeServices.map((s) => ({ value: s.id, label: s.name }))}
              selected={eligibleServiceIds}
              onChange={onServicesChange}
            />
            <AssistantHint anchor="team.eligible_services" session={session} />
          </div>
          {servicesBusy ? <p className="mt-1 text-xs text-text-secondary">جارٍ الحفظ…</p> : null}
          {servicesError ? <p role="alert" className="mt-1 text-xs text-danger">{servicesError}</p> : null}
        </div>
      ) : null}
    </li>
  );
}

// EXPORTED FOR ONE REASON: the cap. Whether a full app entitlement REMOVES the button or turns it into an
// offer is a decision, and a decision nothing renders in a test is a decision that quietly
// reverts. Nothing outside this file and its test imports it.
export function Branches({ session, catalog, branches, operators, add, edit, mayRead, limit, mayAdd,
                   onChanged }: {
  session: Session;
  catalog: Catalog;
  branches: Branch[] | null | undefined;
  operators: Operator[] | null | undefined;
  add: ReturnType<typeof action>;
  edit: ReturnType<typeof action>;
  /** Whether this PERSON may read the branch list — a role fact, from the catalogue. */
  mayRead: boolean;
  /** How many branches his SHOP may have — an app entitlement fact, from the read. `-1` is no known
   *  ceiling (unlimited, or a billing we could not ask) and `undefined` is «not answered». */
  limit: number | undefined;
  mayAdd: boolean | undefined;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  // HE PRESSED THE BUTTON AND THE OFFER ANSWERED. The cap used to REMOVE the button and leave
  // a grey sentence in its place, which reads as «this shop cannot have another branch» — and
  // it can, for money we would like to be paid. The decision: يعطيه الخيار، ولما يضغط
  // عليه يطلع له الرسالة مع رابط لبطاقة الترقية.
  const [capped, setCapped] = useState(false);
  const [name, setName] = useState('');
  // THE LINK, NOT A LAT/LNG THE OWNER TYPES BY HAND — see src/googleMapsLink.ts's own docstring
  // on why: no mapping library exists in this product, and a shop's owner already has his branch
  // open in Google Maps on his phone. Parsed on every keystroke so the "الموقع محدَّد ✓" line
  // below reacts immediately rather than waiting for blur/submit.
  const [mapsLink, setMapsLink] = useState('');
  const [city, setCity] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const parsedLocation = parseGoogleMapsLink(mapsLink);
  // REQUIRED FROM THE SECOND LIVE BRANCH ON, NEVER THE FIRST — mirrors the backend's own rule
  // exactly (services/operations/app/api/v1/staff.py::create_branch): `branches` here already
  // includes the auto-created main branch, so one or more existing LIVE rows means the branch
  // this form is about to add will be the establishment's second (or later) one.
  const locationRequired = isReady(branches)
    && branches.filter((b) => b.active !== false).length >= 1;
  // THE FIGURES ARE BORROWED, NOT COMPUTED. The branch comparison already counts visits and
  // customers per branch for «محلّي», and a second count here would be a second opinion that
  // disagrees. `null` means we could not ask - and the card then shows no figure at all rather
  // than a zero, because «لا أعرف» is not «صفر».
  const [stats, setStats] = useState<BranchStat[] | null | undefined>(undefined);

  useEffect(() => {
    const a = action(catalog, 'insights.branches');
    if (!a) { setStats(null); return; }
    call<{ rows?: BranchStat[] }>(session, a)
      .then((x) => setStats(x.rows ?? []))
      .catch(() => setStats(null));
  }, [session, catalog]);

  // TWO CLOSED DOORS, AND THEY ARE NOT THE SAME DOOR (هـ-3) — see `branchGate` above.
  const gate = branchGate(mayRead, limit);
  if (gate === 'role') {
    // NOTHING TO SELL HIM HERE. The shop may own branches already; this is one person's role.
    return (
      <section className="rounded-card bg-surface-1 p-6 text-center shadow-sm">
        <Lock size={20} className="mx-auto mb-3 text-text-secondary" aria-hidden />
        <p className="text-text-primary">الفروع ليست من صلاحياتك</p>
        <p className="mt-1 text-sm text-text-secondary">اطلب من المالك أن يفتحها لك.</p>
      </section>
    );
  }
  if (gate === 'plan') {
    // THE ENTITLEMENT, AND ONLY WHEN BILLING SAID SO. Hidden, an owner cannot discover that branches
    // exist — and cannot buy them. The sentence names the app store because that is what he acts on.
    return (
      <section className="rounded-card bg-surface-1 p-6 text-center shadow-sm">
        <Lock size={20} className="mx-auto mb-3 text-text-secondary" aria-hidden />
        <p className="text-text-primary">الفروع متاحة كتطبيق إضافي من متجر التطبيقات</p>
        <p className="mt-1 text-sm text-text-secondary">
          افتح فرعاً ثانياً وتابع كل فرع على حدة.
        </p>
        {/* THE SAME DOOR AS THE CAP BELOW. This screen sold branches and left him to find where
            they are sold — and the name it would have printed did not exist in the console until
            the store became a place. */}
        <Link
          to={STORE_PATH}
          className="mt-3 inline-block rounded-control bg-surface-3 px-3 py-1.5 text-sm text-text-primary"
        >
          افتح متجر التطبيقات
        </Link>
      </section>
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!add) return;
    // CHECKED HERE TOO, NOT ONLY ON THE SERVER. The server's own refusal (LOCATION_REQUIRED) is
    // what actually protects the data — this is only so a shop that skipped straight to "حفظ"
    // reads a specific sentence about a link instead of the generic catch-all below.
    if (locationRequired && !parsedLocation) {
      setError(mapsLink.trim()
        ? (isShortGoogleMapsLink(mapsLink)
          ? 'هذا رابط مختصر — الصق الرابط الكامل من خرائط جوجل (بعد فتحه بالمتصفح).'
          : 'ما قدرنا نحدد الموقع من هذا الرابط — تأكد إنه رابط خرائط جوجل صحيح.')
        : 'حدّد موقع الفرع على خرائط جوجل — لازم من الفرع الثاني فأكثر.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await call(session, add, {
        name: name.trim(),
        ...(parsedLocation ? { lat: parsedLocation.lat, lng: parsedLocation.lng } : {}),
        ...(city.trim() ? { city: city.trim() } : {}),
      });
      setName('');
      setMapsLink('');
      setCity('');
      setOpen(false);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر إضافة الفرع.');
    } finally {
      setBusy(false);
    }
  }

  if (branches === null) return <Skeleton height={160} />;

  return (
    <div className="flex flex-col gap-4">
      <ModeCard session={session} catalog={catalog} />
      {/* «العمل على السيارات» MOVED TO «حسابي ← منشأتي». It stood among the branch settings, which
          made it read as a per-branch switch — and it is not one: `operations.shop_vehicles` is a
          fact about the WHOLE establishment, and a shop cannot work on cars in one branch and not
          another. It belongs with the shop's identity, which is where it now is. */}
      <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      {isLoading(branches) ? (
        <Skeleton height={120} />
      ) : hasFailed(branches) || branches.length === 0 ? (
        // AN EMPTY LIST IS NOW A FAILURE, NOT A STATE. Every establishment owns its main branch
        // from signup, and the read repairs a shop that somehow has none — so nothing left here
        // means the request did not answer, and «أضف فرعاً حين تفتح الثاني» would be us blaming
        // his shop for our outage.
        <EmptyState title="تعذّر قراءة الفروع" description="حاول بعد قليل." />
      ) : (
        <ul className="flex flex-col gap-2">
          {branches.map((b) => (
            <BranchRow
              key={b.id}
              session={session}
              branch={b}
              edit={edit}
              staff={isReady(operators)
                ? operators.filter((o) => o.active !== false && o.branch_id === b.id).length
                : null}
              stat={isReady(stats) ? stats.find((r) => r.branch_id === b.id) ?? {} : null}
              onChanged={onChanged}
            />
          ))}
        </ul>
      )}

      {/* THE BUTTON ASKS THE SERVER'S QUESTION, NOT THE SCREEN'S (هـ-3, second half). `add` is
          the role — may this person create branches at all. `mayAdd` is the app entitlement, counted against
          what the shop already holds: a shop allowed three and holding three used to see this
          button, type a name, and read the refusal only after pressing save. `=== false` on
          purpose, so an answer that never came leaves the button where it was. */}
      {add && !open && !capped ? (
        // THE BUTTON STAYS AT THE CAP. `mayAdd === false` is «your app entitlement is full», not «you may
        // not» — and a control that disappears teaches him the product cannot do it. Pressing
        // it at the cap opens the offer instead of the form; `=== false` on purpose, so an
        // answer that never came still opens the form rather than selling him something.
        <Button onClick={() => (mayAdd === false ? setCapped(true) : setOpen(true))}>
          إضافة فرع
        </Button>
      ) : null}
      {add && capped ? (
        // AN OFFER, WITH THE DOOR IN IT. The sentence named «متجر التطبيقات» and left him to
        // find it — and until this cycle that name existed nowhere in the product: no row, no
        // tab, no address. Now it is a place, and this is a link to it rather than an
        // instruction.
        <div className="flex flex-col items-start gap-2 rounded-card bg-surface-2 p-3">
          <p className="text-sm">
            وصلت إلى عدد الفروع في اشتراكك الحالي. أضِف فروعاً أكثر من متجر التطبيقات.
          </p>
          <div className="flex items-center gap-2">
            <Link
              to={STORE_PATH}
              className="rounded-control bg-surface-3 px-3 py-1.5 text-sm text-text-primary"
            >
              افتح متجر التطبيقات
            </Link>
            <Button type="button" variant="ghost" onClick={() => setCapped(false)}>
              ليس الآن
            </Button>
          </div>
        </div>
      ) : null}

      {add && open ? (
        <form onSubmit={submit} className="flex flex-col gap-3 border-t border-border-subtle pt-3">
          <Field label="اسم الفرع" required htmlFor="br-name">
            <Input id="br-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </Field>
          {/* OPTIONAL ON THE FIRST BRANCH (a one-branch shop has no ambiguity), REQUIRED FROM THE
              SECOND — the `required` prop is only cosmetic (a red asterisk); the real gate is
              `locationRequired` in `submit()` above and, regardless of what this form does, the
              server's own refusal. */}
          <Field label="رابط الموقع من خرائط جوجل" required={locationRequired} htmlFor="br-maps">
            <Input id="br-maps" dir="ltr" placeholder="https://maps.google.com/…"
                  value={mapsLink} onChange={(e) => setMapsLink(e.target.value)} />
          </Field>
          {mapsLink.trim() ? (
            parsedLocation ? (
              <p className="text-sm text-success">
                ✓ الموقع محدَّد ({parsedLocation.lat.toFixed(4)}, {parsedLocation.lng.toFixed(4)})
              </p>
            ) : (
              <p className="text-sm text-text-secondary">
                {isShortGoogleMapsLink(mapsLink)
                  ? 'رابط مختصر — افتحه بالمتصفح والصق الرابط الكامل من شريط العنوان.'
                  : 'لسه ما قدرنا نحدد الموقع من هذا الرابط.'}
              </p>
            )
          ) : null}
          <Field label="المدينة (اختياري)" htmlFor="br-city">
            <Input id="br-city" value={city} onChange={(e) => setCity(e.target.value)} />
          </Field>
          {error ? <p role="alert" className="text-danger">{error}</p> : null}
          <div className="flex gap-2">
            <Button type="submit" disabled={busy || name.trim().length === 0}>
              {busy ? 'جارٍ الحفظ…' : 'حفظ'}
            </Button>
            <Button type="button" variant="ghost"
                   onClick={() => { setOpen(false); setError(''); setMapsLink(''); setCity(''); }}>
              إلغاء
            </Button>
          </div>
        </form>
      ) : null}
      </section>
    </div>
  );
}

/**
 * Does this shop work on cars — the one question «تسجيل زيارة» changes shape for.
 *
 * IT REPLACED A TRADE. Sign-up used to ask «نوع النشاط» and that single answer decided four things
 * at once: the services we seeded, the rewards we seeded, the plate page and the meter. The owner
 * answering it could not see any of that, and could never change it — so the tyre shop that added
 * detailing, and the car wash that stopped, both kept a screen that was wrong about them.
 *
 * NOW IT IS ONE CHECKBOX AND IT IS HIS. The rest a shop writes itself, because a catalogue guessed
 * from a trade we have never seen is wrong on its first day, and correcting a guess is more work
 * than writing the truth once.
 */
export function VehiclesCard({ session, catalog }: { session: Session; catalog: Catalog }) {
  const read = action(catalog, 'operations.shop_vehicles');
  const write = action(catalog, 'operations.set_shop_vehicles');
  const [tracks, setTracks] = useState<boolean | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!read) { setTracks(null); return; }
    call<{ tracks_vehicle?: boolean }>(session, read)
      .then((x) => setTracks(x.tracks_vehicle === true))
      .catch(() => setTracks(null));
  }, [session, catalog]);

  async function flip(next: boolean) {
    if (!write) return;
    setBusy(true);
    setError('');
    try {
      const row = await call<{ tracks_vehicle?: boolean }>(
        session, write, { tracks_vehicle: next });
      setTracks(row.tracks_vehicle === true);
    } catch (err) {
      // THE OLD VALUE STAYS ON THE SCREEN. A checkbox that moves on a failed write tells him the
      // plate page is on when the server still says off.
      setError(err instanceof Error ? err.message : 'تعذّر حفظ الاختيار. حاول بعد قليل.');
    } finally {
      setBusy(false);
    }
  }

  if (!read || tracks === null) return null;

  return (
    <section className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <span className="flex flex-col">
          <span className="text-sm font-medium">العمل على السيارات</span>
          <span className="text-xs text-text-secondary">
            إن فعّلته ظهرت صفحة رقم اللوحة والعدّاد في «تسجيل زيارة»، وارتبطت الدورة بالسيارة لا
            بصاحبها وحده. غيّره متى تغيّر عملك.
          </span>
        </span>
        <Toggle checked={tracks === true} disabled={busy || !write} onChange={flip}
               ariaLabel="عملي يتم على السيارات" testId="vehicles-toggle" />
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}
    </section>
  );
}

/**
 * How this establishment runs its branches - one sentence, and a choice that goes one way.
 *
 * BOTH MODES ARE SHOWN AND ONLY ONE IS OFFERED, which is the whole point of `available` travelling
 * with the read (services/operations/core/shop_mode.py). An owner cannot ask for what he cannot
 * see; a control that pretends to work is the defect this product keeps finding. So the locked one
 * is named, explained, and inert.
 *
 * AND THE MOVE IS CONFIRMED BEFORE IT IS SENT, because it does not come back from this screen. The
 * server refuses the reverse with the sentence that says what to do instead - but a refusal read
 * after the fact is a worse place to learn that than the button itself.
 */
function ModeCard({ session, catalog }: { session: Session; catalog: Catalog }) {
  const read = action(catalog, 'operations.shop_mode');
  const write = action(catalog, 'operations.set_shop_mode');
  const [mode, setMode] = useState<Mode | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    if (!read) { setMode(null); return; }
    call<Mode>(session, read).then(setMode).catch(() => setMode(null));
  }, [session, catalog]);

  async function move() {
    if (!write) return;
    setBusy(true);
    setError('');
    try {
      setMode(await call<Mode>(session, write, { mode: 'per_branch' }));
      setAsking(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر تغيير نظام الفروع.');
    } finally {
      setBusy(false);
    }
  }

  if (!read || !mode) return null;

  const per = mode.mode === 'per_branch';

  return (
    <section className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
      <h3 className="font-medium">نظام إدارة الفروع</h3>
      <p className="text-sm text-text-secondary">
        {per
          ? 'لكلّ فرع رقمه الخاص، والعميل يراسل فرعه. والإدارة تبقى مركزية: القوالب والخدمات والحملات والعملاء والنقاط تُعدّ مرة وترثها الفروع.'
          : 'رقم واحد للمنشأة كلها. والفروع أماكن يُسجَّل فيها العمل، وكل رسالة تخرج من الرقم الذي يعرفه عميلك.'}
      </p>
      {per || !write ? null : mode.available ? (
        asking ? (
          <div className="flex flex-col gap-2 border-t border-border-subtle pt-2">
            <p className="text-sm">
              بعد التحوّل لا يمكن الرجوع من الشاشة: أرقام الفروع وقوالبها المعتمدة وعملاؤها لا
              تُلغى بضغطة. متأكد؟
            </p>
            <div className="flex gap-2">
              <Button onClick={move} disabled={busy}>
                {busy ? 'جارٍ التحويل…' : 'نعم، رقم لكل فرع'}
              </Button>
              <Button variant="ghost" onClick={() => { setAsking(false); setError(''); }}>
                إلغاء
              </Button>
            </div>
          </div>
        ) : (
          <Button variant="ghost" onClick={() => setAsking(true)}>
            التحوّل إلى رقم لكل فرع
          </Button>
        )
      ) : (
        <p className="flex items-center gap-2 text-sm text-text-secondary">
          <Lock size={14} aria-hidden />
          «رقم لكل فرع» قيد التجهيز. سنبلغك حين تجهز.
        </p>
      )}
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    </section>
  );
}

/**
 * One branch, and the two things an owner may do to it.
 *
 * RENAME AND CLOSE — NEVER DELETE. Visits, points movements and reminder schedules all carry a
 * branch id as a plain string, so a deleted branch would leave a year of records pointing at a
 * place with no name, and the comparison table would report them under an id nobody recognises.
 * The server refuses a delete by not having one; this screen offers what exists.
 *
 * THE MAIN BRANCH HAS NO CLOSE BUTTON, and the reason is written where he can read it: it is
 * where a visit with an unrecognised branch lands, so a shop that closed it would be recording
 * visits against nothing. Renaming it is his — «الفرع الرئيسي» is our word, not his shop's.
 *
 * AND REOPENING IS REFUSED BY THE SERVER when the app entitlement is full, with the number in the sentence:
 * putting a place back into service is an addition, and an entitlement of one branch must not be passed
 * by closing and reopening.
 */
function BranchRow({ session, branch, edit, staff, stat, onChanged }: {
  session: Session;
  branch: Branch;
  edit: ReturnType<typeof action>;
  /** Active employees assigned to this branch, or null when the list could not be read. */
  staff: number | null;
  /** Its row in the branch comparison, `{}` when it has none yet, null when unreadable. */
  stat: BranchStat | null;
  onChanged: () => void;
}) {
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(branch.name);
  const [mapsLink, setMapsLink] = useState('');
  const [city, setCity] = useState(branch.city ?? '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const main = branch.id === MAIN_BRANCH;
  const live = branch.active !== false;
  const hasLocation = !!(branch.lat || branch.lng);
  const parsedLocation = parseGoogleMapsLink(mapsLink);

  async function save(patch: Record<string, unknown>) {
    if (!edit) return;
    setBusy(true);
    setError('');
    try {
      await call(session, edit, { id: branch.id, ...patch });
      setRenaming(false);
      setMapsLink('');
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر حفظ التعديل.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <li className="flex flex-col gap-2 border-t border-border-subtle pt-2 first:border-0 first:pt-0">
      {renaming ? (
        <form
          className="flex flex-col gap-2"
          onSubmit={(e: FormEvent) => {
            e.preventDefault();
            save({
              name: name.trim(),
              ...(parsedLocation ? { lat: parsedLocation.lat, lng: parsedLocation.lng } : {}),
              ...(city.trim() !== (branch.city ?? '') ? { city: city.trim() } : {}),
            });
          }}
        >
          <Field label="اسم الفرع" required htmlFor={`br-${branch.id}`}>
            <Input id={`br-${branch.id}`} value={name} autoFocus
                   onChange={(e) => setName(e.target.value)} />
          </Field>
          {/* SET OR CORRECT — never required here (only opening a SECOND branch is gated; an
              already-open branch's location is a fix an owner makes when he gets to it, never a
              form he is blocked from saving without). Leaving the link blank keeps whatever
              location the branch already has (or still has none) — this never clears one. */}
          <Field label={hasLocation ? 'تحديث رابط الموقع (اختياري)' : 'رابط الموقع من خرائط جوجل (اختياري)'}
                htmlFor={`br-maps-${branch.id}`}>
            <Input id={`br-maps-${branch.id}`} dir="ltr" placeholder="https://maps.google.com/…"
                  value={mapsLink} onChange={(e) => setMapsLink(e.target.value)} />
          </Field>
          {mapsLink.trim() && !parsedLocation ? (
            <p className="text-sm text-text-secondary">
              {isShortGoogleMapsLink(mapsLink)
                ? 'رابط مختصر — افتحه بالمتصفح والصق الرابط الكامل من شريط العنوان.'
                : 'لسه ما قدرنا نحدد الموقع من هذا الرابط.'}
            </p>
          ) : null}
          <Field label="المدينة (اختياري)" htmlFor={`br-city-${branch.id}`}>
            <Input id={`br-city-${branch.id}`} value={city} onChange={(e) => setCity(e.target.value)} />
          </Field>
          <div className="flex gap-2">
            <Button type="submit" disabled={busy || name.trim().length === 0}>
              {busy ? 'جارٍ الحفظ…' : 'حفظ'}
            </Button>
            <Button type="button" variant="ghost"
                    onClick={() => {
                      setRenaming(false); setName(branch.name); setError('');
                      setMapsLink(''); setCity(branch.city ?? '');
                    }}>
              إلغاء
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex items-center justify-between gap-3">
          <span className="flex flex-col">
            <span>{branch.name}</span>
            {/* CLOSED IS SAID, NOT GREYED. A branch that only looks faint reads as a rendering
                accident; the word is what tells him why it is absent from the pickers. */}
            {!live ? <span className="text-xs text-text-secondary">مغلق</span> : null}
            {main ? <span className="text-xs text-text-secondary">الفرع الرئيسي — لا يُغلق</span> : null}
            {/* THE FIGURES, AND ONLY THE ONES WE HAVE. Each is dropped on its own when its read
                failed - a card saying «0 زيارة» about a branch we could not count is a lie that
                looks like a report. */}
            <span className="flex flex-wrap gap-x-3 text-xs text-text-secondary">
              {staff === null ? null : <span>{staff} موظفاً</span>}
              {stat === null ? null : <span>{stat.visits ?? 0} زيارة</span>}
              {stat === null ? null : <span>{stat.customers ?? 0} عميلاً</span>}
            </span>
          </span>
          {edit ? (
            <span className="flex gap-2">
              <Button variant="ghost" onClick={() => setRenaming(true)}>تسمية</Button>
              {main ? null : (
                <Button variant="ghost" disabled={busy}
                        onClick={() => save({ active: !live })}>
                  {live ? 'إغلاق' : 'إعادة فتح'}
                </Button>
              )}
            </span>
          ) : null}
        </div>
      )}
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    </li>
  );
}
