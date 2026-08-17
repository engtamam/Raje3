/**
 * «فريقي» — the people and the branches.
 *
 * TWO LISTS, TWO TABS. They were stacked in one scroll, which is how a screen becomes a wall: the
 * owner scrolls past his employees to reach his branches and back again, and neither list is ever
 * the thing he came for. `Segmented` is the kit's, and the same control the door uses.
 *
 * AND A TAB THE PLAN DOES NOT INCLUDE IS LOCKED, NOT HIDDEN — with the reason on it. This screen
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
import { Button } from '@base-ui/design-system/Button';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Field, Input } from '@base-ui/design-system/Field';
import { Segmented } from '@base-ui/design-system/Segmented';
import { hasFailed, isLoading, isReady } from '../loading';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Lock } from 'lucide-react';
import { action, call, type Catalog } from '../catalog';
import { branchGate } from '../branches';
import type { Session } from '../session';
import { digitsOnly } from '../digits';

interface Operator {
  id: string; name: string; role?: string; active?: boolean;
  /** Where he WORKS — one place, and it decides where his visits are counted. */
  branch_id?: string;
  /** What he may SEE, which is a different question and often a wider answer. */
  visible_branch_ids?: string[];
  visible_all?: boolean;
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
const ROLES: { value: string; label: string; can: string }[] = [
  { value: 'operator', label: 'موظف ميداني', can: 'يسجّل الزيارات فقط' },
  { value: 'supervisor', label: 'مشرف وردية', can: 'الزيارات وعملاء وردیته والتقارير' },
  { value: 'marketer', label: 'مسؤول التسويق', can: 'الحملات والرسائل، بلا تعديل الخدمات' },
  { value: 'manager', label: 'مدير', can: 'كل شيء عدا الفوترة وحذف الحساب' },
];
interface Branch { id: string; name: string; active?: boolean }

/** What the branch comparison already computes for the whole shop (insights, spec 10.6.3). */
interface BranchStat { branch_id?: string; visits?: number; customers?: number }

/** The establishment's branch mode, and whether the second one may be chosen at all. */
interface Mode { mode: string; available?: boolean }

/** The one branch every shop has from its first minute. Ours to create, his to rename, and it
 *  cannot be closed — it is where an unrecognised branch lands (services/operations/core/branches.py). */
const MAIN_BRANCH = 'brn-main';

export function TeamScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [tab, setTab] = useState<'people' | 'branches'>('people');
  const [operators, setOperators] = useState<Operator[] | null | undefined>(undefined);
  const [branches, setBranches] = useState<Branch[] | null | undefined>(undefined);
  /**
   * HOW MANY BRANCHES HIS PLAN ALLOWS — the entitlement, which is not the capability.
   *
   * `undefined` while the read is out or was never made, and `-1` for «no known ceiling»: an
   * unlimited plan and a billing we could not reach are both that, and neither may draw a lock.
   * Only a stated limit of 1 is the base plan, and only that draws the sentence about a package.
   */
  const [branchLimit, setBranchLimit] = useState<number | undefined>(undefined);
  // WHETHER ONE MORE FITS RIGHT NOW — a different question from the ceiling, and the only one
  // the «إضافة فرع» button can answer honestly. `undefined` is an answer that did not arrive,
  // and it never hides the button: an outage must not read as a plan he has outgrown.
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

  // WHAT THIS PERSON MAY DO, FROM THE CATALOGUE. The gateway has already filtered it by
  // capability, so an absent action is a permission fact — and the control simply is not rendered.
  const addOperator = action(catalog, 'operations.create_operator');
  const addBranch = action(catalog, 'operations.create_branch');
  const editBranch = action(catalog, 'operations.update_branch');
  const listBranches = action(catalog, 'operations.list_branches');

  const load = () => {
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
          // about his plan, and `?? 0` there would lock every shop out of a tab it may own.
          setBranchLimit(typeof x.branch_limit === 'number' ? x.branch_limit : undefined);
          setMayAddBranch(typeof x.may_add_branch === 'boolean' ? x.may_add_branch : undefined);
        })
        .catch(() => setBranches(null));
    } else {
      setBranches(null);
    }
  };

  useEffect(load, [session, catalog]);

  return (
    <div className="flex flex-col gap-4 p-4">
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
          // of closed door — «not yours» and «not in your plan» — and the panel says which.
          { value: 'branches',
            label: branchGate(Boolean(listBranches), branchLimit) === 'open'
              ? 'الفروع' : 'الفروع 🔒' },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === 'people'
        ? <People
            session={session}
            operators={operators}
            branches={branches}
            add={addOperator}
            edit={action(catalog, 'operations.update_operator')}
            hire={action(catalog, 'operations.hire_member')}
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

function People({ session, operators, branches, add, edit, hire, pinKind, onChanged }: {
  session: Session;
  operators: Operator[] | null | undefined;
  branches: Branch[] | null | undefined;
  add: ReturnType<typeof action>;
  edit: ReturnType<typeof action>;
  hire: ReturnType<typeof action>;
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
      if (kind === 'login') {
        if (!hire) return;
        await call(session, hire, {
          name: name.trim(), phone: phone.trim(), password, role, branch_id: branchId,
        });
      } else {
        // AND THE BRANCH, WHICH THIS CALL USED TO OMIT. The server has always accepted it
        // (`staff.py` create_operator) — the screen simply never offered it, so the field that
        // decides where a visit happened was left empty for the majority of a workshop's staff.
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
      // written here would be a second copy of a plan we do not hold.
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
            <li key={o.id} className="flex items-center justify-between gap-3">
              <span className="flex flex-col">
                <span>{o.name}</span>
                {/* SHOWN IN THE LIST TOO. A team screen that hides what each person may do is a
                    screen an owner cannot audit — and the question he asks is always "who can
                    touch the billing", never "how many employees do I have". */}
                <span className="text-sm text-text-secondary">
                  {ROLES.find((r) => r.value === o.role)?.label ?? o.role ?? ''}
                </span>
              </span>
              {o.active === false ? (
                <span className="text-sm text-text-secondary">موقوف</span>
              ) : (
                /* HIS BRANCH, CHANGEABLE IN PLACE — and it decides something: a visit he saves is
                   filed under HIS branch, whatever the device sends (services/operations/core/
                   operations.py). Hidden for a shop with one place, where the question is noise. */
                (branches ?? []).length > 1 && edit ? (
                  <label className="flex items-center gap-2 text-sm">
                    <span className="text-text-secondary">فرعه</span>
                    <select
                      className="min-h-11 rounded-xl bg-surface-2 px-3 text-sm"
                      value={o.branch_id ?? ''}
                      aria-label={`فرع ${o.name}`}
                      onChange={async (e) => {
                        await call(session, edit, { id: o.id, branch_id: e.target.value })
                          .catch(() => undefined);
                        onChanged();
                      }}
                    >
                      <option value="">كل الفروع</option>
                      {(branches ?? []).filter((b) => b.active !== false).map((b) => (
                        <option key={b.id} value={b.id}>{b.name}</option>
                      ))}
                    </select>
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
            </li>
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

              SHOWN ONLY TO A SHOP WITH MORE THAN ONE PLACE — for everyone else the answer is «كل
              الفروع» and the question is noise. */}
          {(branches ?? []).length > 1 ? (
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-text-secondary">فرعه</span>
              <select className="min-h-11 rounded-xl bg-surface-2 px-3 text-sm"
                      value={branchId} aria-label="فرع الموظف"
                      onChange={(e) => setBranchId(e.target.value)}>
                <option value="">كل الفروع</option>
                {(branches ?? []).filter((b) => b.active !== false).map((b) => (
                  <option key={b.id} value={b.id}>{b.name}</option>
                ))}
              </select>
              <span className="text-xs text-text-secondary">
                {kind === 'pin'
                  ? 'الزيارات التي يسجّلها تُنسب لهذا الفرع.'
                  : 'من له فرع يرى بيانات فرعه وحده، وزياراته تُنسب إليه.'}
              </span>
            </label>
          ) : null}
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
            <legend className="mb-1 text-sm text-text-secondary">الدور</legend>
            {ROLES.map((r) => (
              <label
                key={r.value}
                className={[
                  'flex cursor-pointer items-start gap-3 rounded-card border px-3 py-2',
                  role === r.value
                    ? 'border-accent bg-accent-soft text-accent-on-soft'
                    : 'border-border-subtle hover:border-border-strong',
                ].join(' ')}
              >
                <input
                  type="radio" name="op-role" value={r.value} checked={role === r.value}
                  onChange={() => setRole(r.value)} className="sr-only"
                />
                <span className="flex flex-col">
                  <span className="text-sm">{r.label}</span>
                  <span className="text-xs opacity-80">{r.can}</span>
                </span>
              </label>
            ))}
          </fieldset>

          {error ? <p role="alert" className="text-danger">{error}</p> : null}
          <div className="flex gap-2">
            <Button
              type="submit"
              disabled={busy || name.trim().length === 0
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

function Branches({ session, catalog, branches, operators, add, edit, mayRead, limit, mayAdd,
                   onChanged }: {
  session: Session;
  catalog: Catalog;
  branches: Branch[] | null | undefined;
  operators: Operator[] | null | undefined;
  add: ReturnType<typeof action>;
  edit: ReturnType<typeof action>;
  /** Whether this PERSON may read the branch list — a role fact, from the catalogue. */
  mayRead: boolean;
  /** How many branches his SHOP may have — a plan fact, from the read. `-1` is no known
   *  ceiling (unlimited, or a billing we could not ask) and `undefined` is «not answered». */
  limit: number | undefined;
  mayAdd: boolean | undefined;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
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
    // THE PLAN, AND ONLY WHEN BILLING SAID SO. Hidden, an owner cannot discover that branches
    // exist — and cannot buy them. The sentence names the plan because that is what he acts on.
    return (
      <section className="rounded-card bg-surface-1 p-6 text-center shadow-sm">
        <Lock size={20} className="mx-auto mb-3 text-text-secondary" aria-hidden />
        <p className="text-text-primary">الفروع متاحة في باقة أعلى</p>
        <p className="mt-1 text-sm text-text-secondary">
          افتح فرعاً ثانياً وتابع كل فرع على حدة.
        </p>
      </section>
    );
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!add) return;
    setBusy(true);
    setError('');
    try {
      await call(session, add, { name: name.trim() });
      setName('');
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
          the role — may this person create branches at all. `mayAdd` is the plan, counted against
          what the shop already holds: a shop allowed three and holding three used to see this
          button, type a name, and read the refusal only after pressing save. `=== false` on
          purpose, so an answer that never came leaves the button where it was. */}
      {add && mayAdd !== false && !open
        ? <Button onClick={() => setOpen(true)}>إضافة فرع</Button> : null}
      {add && mayAdd === false ? (
        <p className="text-sm text-text-secondary">
          بلغت عدد الفروع المتاحة في باقتك. للمزيد، رقِّ باقتك من «متجر التطبيقات».
        </p>
      ) : null}

      {add && open ? (
        <form onSubmit={submit} className="flex flex-col gap-3 border-t border-border-subtle pt-3">
          <Field label="اسم الفرع" required htmlFor="br-name">
            <Input id="br-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </Field>
          {error ? <p role="alert" className="text-danger">{error}</p> : null}
          <div className="flex gap-2">
            <Button type="submit" disabled={busy || name.trim().length === 0}>
              {busy ? 'جارٍ الحفظ…' : 'حفظ'}
            </Button>
            <Button type="button" variant="ghost" onClick={() => { setOpen(false); setError(''); }}>
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
      <h3 className="font-medium">العمل على السيارات</h3>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="size-5"
          checked={tracks === true}
          disabled={busy || !write}
          onChange={(e) => flip(e.target.checked)}
        />
        <span>عملي يتم على السيارات</span>
      </label>
      <p className="text-sm text-text-secondary">
        إن فعّلته ظهرت صفحة رقم اللوحة والعدّاد في «تسجيل زيارة»، وارتبطت الدورة بالسيارة لا
        بصاحبها وحده. غيّره متى تغيّر عملك.
      </p>
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
 * AND REOPENING IS REFUSED BY THE SERVER when the plan is full, with the number in the sentence:
 * putting a place back into service is an addition, and a plan of one branch must not be passed
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
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const main = branch.id === MAIN_BRANCH;
  const live = branch.active !== false;

  async function save(patch: Record<string, unknown>) {
    if (!edit) return;
    setBusy(true);
    setError('');
    try {
      await call(session, edit, { id: branch.id, ...patch });
      setRenaming(false);
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
          onSubmit={(e: FormEvent) => { e.preventDefault(); save({ name: name.trim() }); }}
        >
          <Field label="اسم الفرع" required htmlFor={`br-${branch.id}`}>
            <Input id={`br-${branch.id}`} value={name} autoFocus
                   onChange={(e) => setName(e.target.value)} />
          </Field>
          <div className="flex gap-2">
            <Button type="submit" disabled={busy || name.trim().length === 0}>
              {busy ? 'جارٍ الحفظ…' : 'حفظ'}
            </Button>
            <Button type="button" variant="ghost"
                    onClick={() => { setRenaming(false); setName(branch.name); setError(''); }}>
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
