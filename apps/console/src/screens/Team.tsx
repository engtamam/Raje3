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
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Lock } from 'lucide-react';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Operator { id: string; name: string; role?: string; active?: boolean }

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
interface Branch { id: string; name: string }

export function TeamScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [tab, setTab] = useState<'people' | 'branches'>('people');
  const [operators, setOperators] = useState<Operator[] | null>(null);
  const [branches, setBranches] = useState<Branch[] | null>(null);

  // WHAT THIS PERSON MAY DO, FROM THE CATALOGUE. The gateway has already filtered it by
  // capability, so an absent action is a permission fact — and the control simply is not rendered.
  const addOperator = action(catalog, 'operations.create_operator');
  const addBranch = action(catalog, 'operations.create_branch');
  const listBranches = action(catalog, 'operations.list_branches');

  const load = () => {
    const o = action(catalog, 'operations.list_operators');
    if (o) {
      call<{ operators: Operator[] }>(session, o)
        .then((x) => setOperators(x.operators ?? []))
        .catch(() => setOperators([]));
    } else {
      setOperators([]);
    }

    if (listBranches) {
      call<{ branches: Branch[] }>(session, listBranches)
        .then((x) => setBranches(x.branches ?? []))
        .catch(() => setBranches([]));
    } else {
      setBranches(null);
    }
  };

  useEffect(load, [session, catalog]);

  return (
    <div className="flex flex-col gap-4 p-4">
      <Segmented
        options={[
          { value: 'people', label: 'العاملون' },
          // THE LOCK IS ON THE LABEL, so it is visible before he presses and not after. A tab that
          // looks pressable and then refuses is worse than one that says so.
          { value: 'branches', label: listBranches ? 'الفروع' : 'الفروع 🔒' },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === 'people'
        ? <People
            session={session}
            operators={operators}
            add={addOperator}
            onChanged={load}
          />
        : <Branches
            session={session}
            branches={branches}
            add={addBranch}
            available={Boolean(listBranches)}
            onChanged={load}
          />}
    </div>
  );
}

function People({ session, operators, add, onChanged }: {
  session: Session;
  operators: Operator[] | null;
  add: ReturnType<typeof action>;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [pin, setPin] = useState('');
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
      await call(session, add, { name: name.trim(), pin, role });
      setName('');
      setPin('');
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

  if (operators === null) return <Skeleton height={200} />;

  return (
    <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      {operators.length === 0 ? (
        <EmptyState
          title="لا يوجد موظفون بعد"
          description="أضف موظفيك ليسجّلوا الزيارات بحساباتهم."
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {operators.map((o) => (
            <li key={o.id} className="flex items-center justify-between">
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
          {/* FOUR DIGITS, AND THE SERVER SAYS FOUR. A longer PIN is not meaningfully safer for what
              it protects and IS meaningfully slower to type a hundred times a day. */}
          <Field label="رمز الدخول (4 أرقام)" required htmlFor="op-pin">
            <Input
              id="op-pin" value={pin} inputMode="numeric" dir="ltr" maxLength={4}
              onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
            />
          </Field>
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
            <Button type="submit" disabled={busy || name.trim().length === 0 || pin.length !== 4}>
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

function Branches({ session, branches, add, available, onChanged }: {
  session: Session;
  branches: Branch[] | null;
  add: ReturnType<typeof action>;
  available: boolean;
  onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (!available) {
    // LOCKED AND EXPLAINED. Hidden, an owner cannot discover that branches exist — and cannot buy
    // them. The sentence names the plan rather than the capability, because that is what he acts on.
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
    <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      {branches.length === 0 ? (
        <EmptyState title="فرع واحد" description="أضف فرعاً حين تفتح الثاني." />
      ) : (
        <ul className="flex flex-col gap-2">
          {branches.map((b) => <li key={b.id}>{b.name}</li>)}
        </ul>
      )}

      {add && !open ? <Button onClick={() => setOpen(true)}>إضافة فرع</Button> : null}

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
  );
}
