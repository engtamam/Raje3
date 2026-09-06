/**
 * «حسابي» — the page every product neglects, because it becomes where everything with no home
 * is dumped.
 *
 * THE RULE THAT KEEPS IT WHOLE: only what concerns the RELATIONSHIP between us and him — his
 * subscription, his channel, his identity, his data. A service price belongs to «خدماتي», a
 * template to «رسائلي». Anything proposed here because it "found no place" is refused by that
 * sentence, and this comment exists so the refusal has something to point at.
 *
 * TABS ACROSS THE TOP, LIKE EVERY OTHER SECTION — and this replaced an index-and-detail layout
 * that was correct in isolation and wrong in the product. It was the only screen where choosing
 * meant leaving a list and coming back, so it read as a settings menu bolted on rather than as a
 * section of the same application. Sameness of shape is not decoration: a person who has learned
 * one screen has learned all of them.
 *
 * AND THE STATUS IS READ WITHOUT A TAP. Two lines above the tabs answer the only question this
 * page exists for — is the relationship healthy — so the answer never depends on which tab
 * happens to be open.
 *
 * EVERY TAB IS BUILT FROM ITS ACTIONS. A tab whose service the caller cannot reach is not
 * rendered, because the gateway already removed those actions from the catalogue. An operator
 * opening this page gets a short page, never a broken one.
 */
import { useEffect, useState } from 'react';
import { KeyRound } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Field, Input } from '../rj-ui/Field';
import { Segmented } from '../rj-ui/Segmented';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { ConnectByBranch } from './Connect';
import { DataPane, InvoicesPane, KeysPane, ShopPane } from './AccountPanes';
import { PlansPane } from './Plans';
import { TeamScreen } from './Team';
import { type Loading } from '../loading';
import type { Owned } from '../apps';

/**
 * FOUR TABS, AND FOUR OLD NAMES THAT STILL RESOLVE.
 *
 * `whatsapp`, `team`, `keys` and `invoices` were tabs of their own and are now SECTIONS inside two
 * of these. They stay in the type because they are live URLs: «أضِفه إلى اشتراكي» links, a
 * bookmark, a message somebody sent a colleague. Dropping them would turn every one of those into
 * a page that opens on the wrong thing — which is exactly the failure a deep link exists to
 * prevent.
 */
export type Pane = 'shop' | 'billing' | 'invoices' | 'data';
export type PaneLink = Pane | 'login' | 'whatsapp' | 'team' | 'keys';

/**
 * The tab a link opens on. Unknown and absent both land on «منشأتي».
 *
 * NOT ON A HARDCODED 'billing', which is where this opened before: a manager who cannot read
 * billing arrived on a tab that was filtered away and the screen fell back a second time. The
 * establishment is the one tab anybody with any of its permissions holds.
 */
export function resolvePane(link?: string): Pane {
  if (!link) return 'shop';
  // `hasOwn`, NOT a plain lookup. `?tab=` is a string a stranger types, and `MOVED['__proto__']`
  // answers with an object rather than undefined — which would leave `pane` holding something
  // that is not a tab at all.
  if (Object.hasOwn(MOVED, link)) return MOVED[link];
  return (['shop', 'billing', 'invoices', 'data'] as const).includes(link as Pane)
    ? (link as Pane)
    : 'shop';
}

/** Where a name that is no longer a tab now lives. */
export const MOVED: Record<string, Pane> = {
  // «دخولي» IS GONE, AND ONLY ONE THING ON IT WAS EVER USED. Three cards of prose explaining what
  // he cannot change here — that his phone is his login, that a session lasts 31 days, how to
  // reset a password — a page to read rather than a page to use. The switch that WAS used, his
  // weekly report, moved to «بياناتي» first, and then to «منشأتي» (see ShopPane) — where he
  // actually looks for it, next to the rest of what he set up about his establishment.
  login: 'shop',
  whatsapp: 'shop',
  team: 'shop',
  keys: 'shop',
};

/**
 * The tabs, each with the sentence that says what is behind it.
 *
 * THE HINT SURVIVED THE REDESIGN, in the line under the tab strip rather than under a row. It is
 * what stops «دخولي» being a noun somebody has to open to understand — and the tab labels are
 * short precisely because that line carries the meaning.
 */
const TABS: { id: Pane; label: string; hint: string }[] = [
  // ONE TAB FOR THE ESTABLISHMENT, because its five parts answer one question — who and what may
  // act in this shop, and under whose name. They were five separate tabs and a person looking for
  // «who works here» had to guess which of them held it.
  { id: 'shop', label: 'منشأتي', hint: 'هويّتك وفروعك وفريقك وربط واتساب' },
  // THE APP AND THE INVOICES ARE ONE ERRAND: money. They were split because choosing an app and
  // fetching a receipt are different acts — which is true, and still leaves both under the one
  // word an owner thinks of when he is here for either.
  // «متجر التطبيقات», WHICH IS WHAT THE REST OF THE PRODUCT ALREADY CALLED IT. The tab said
  // «اشتراكي» and four screens said «متجر التطبيقات» — two names for one place, and the one
  // printed in the sentences that send people here was the one that did not exist.
  { id: 'billing', label: 'متجر التطبيقات', hint: 'تطبيقاتك ووسيلة الدفع' },
  // THE INVOICES CAME OUT OF THE STORE AND BECAME A TAB. They were the second half of a tab
  // whose first half is a catalogue: a person arriving to buy an app scrolled past his
  // receipts, and a person arriving for a receipt scrolled past the shop. Two errands, and
  // only one of them is browsing.
  { id: 'invoices', label: 'الفواتير', hint: 'فواتيرك وإيصالاتك' },
  { id: 'data', label: 'بياناتي', hint: 'تقريرك الأسبوعي، الاحتفاظ، التصدير، الاتفاقيات' },
];


export function AccountScreen(
  { session, catalog, openOn, owned }:
  // `openOn` IS WHERE SOMEBODY ELSE SENT HIM. The locked cards across the product say «أضِفه إلى
  // اشتراكي», and a button that lands on a page and then makes him find the right tab is a button
  // that loses half the people who pressed it. Ignored when he may not read that tab.
  { session: Session; catalog: Catalog; openOn?: PaneLink; owned?: Loading<Owned> },
) {
  // WHICH BRANCH IS HIS — a field operator landing here saw a page that never
  // said who he is or where he works, because every tab that WOULD have said so («منشأتي») is
  // gated on capabilities his role does not hold. This reads independently of any tab, off the
  // SAME two-id read App.tsx's own branch switcher uses (staff.py::_READ_BRANCHES) — an owner/
  // manager/marketer via `operations.list_branches`, a field operator via
  // `operations.list_branches_for_bookings`. Only rendered when it resolves to exactly ONE
  // branch: a multi-branch owner already has the switcher for this, and naming several here would
  // just repeat it worse.
  const [myBranch, setMyBranch] = useState<{ id: string; name?: string } | null | undefined>(undefined);
  // TOLD APART FROM «not applicable» AND «not a single branch» — both of those are `myBranch ===
  // null` and stay silent, same as before. Only an actual failed read sets this, so the line
  // below can finally say so instead of looking identical to a shop with several branches.
  const [myBranchFailed, setMyBranchFailed] = useState(false);

  useEffect(() => {
    const b = action(catalog, 'operations.list_branches')
      || action(catalog, 'operations.list_branches_for_bookings');
    if (!b) { setMyBranch(null); return; }
    call<{ branches?: { id: string; name?: string }[] }>(session, b)
      .then((x) => setMyBranch((x.branches?.length ?? 0) === 1 ? x.branches![0] : null))
      .catch(() => { setMyBranch(null); setMyBranchFailed(true); });
  }, [session, catalog]);

  const tabs = TABS.filter((t) => {
    if (t.id === 'billing') {
      return Boolean(action(catalog, 'billing.plans')
        || action(catalog, 'billing.my_subscriptions'));
    }
    // ITS OWN READ, NOT THE STORE'S. Offering «الفواتير» to somebody whose role cannot list them
    // is a tab that can only ever say «لا يشمل دورك فواتير المحل» — a door with a wall behind it.
    if (t.id === 'invoices') return Boolean(action(catalog, 'billing.my_invoices'));
    // OFFERED IF ANY ONE OF ITS SECTIONS IS. The tab is a container now, and gating it on the
    // identity read alone would hide a manager's team and connection behind a permission he does
    // not need for either.
    if (t.id === 'shop') {
      return Boolean(action(catalog, 'tenant.view_self')
        || action(catalog, 'whatsapp.connect_status')
        || action(catalog, 'operations.create_operator')
        || action(catalog, 'operations.list_branches'));
    }
    return true;
  });

  // OPENS ON THE FIRST TAB HE ACTUALLY HAS, not on a hardcoded 'billing' that a manager cannot
  // read. `tabs` is never empty — «دخولي» and «بياناتي» are everyone's.
  // A LINK MAY NAME A SECTION THAT IS NO LONGER A TAB — see MOVED. It opens the tab that now
  // holds it, and the section itself is on that page.
  const [pane, setPane] = useState<Pane>(() => resolvePane(openOn));
  const active = tabs.some((t) => t.id === pane) ? pane : tabs[0].id;

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-col gap-1">
        <Segmented
          // FULL WIDTH, SPLIT EVENLY, NEVER WRAPPED. The kit's Segmented is
          // `inline-flex flex-wrap`, which on a phone stacks two long Arabic labels into a
          // ragged block half the screen wide. It takes a className and merges with
          // tailwind-merge, so this is a fix at the call site rather than a fork of the kit.
          // AND IT SCROLLS RATHER THAN WRAPS. `flex-1` on five long Arabic labels still folded
          // onto a second row on a phone, which is what «بياناتي وأوراقي» hanging alone under the
          // strip was. One row that slides sideways reads as one control; two ragged rows read as
          // a broken one. The even split comes back at sm, where the labels fit.
          // A GRID, NOT A ROW THAT SLIDES. The strip scrolled sideways, and a control that
          // scrolls hides itself: the last tab arrived cut down the middle, which reads as a
          // rendering fault rather than as "there is more this way". Six equal cells over three
          // columns fit six Arabic labels on the narrowest phone with nothing clipped and nothing
          // ragged — the wrapping the kit does by default is ragged because the cells are not
          // equal, not because wrapping is wrong. One row from sm up, where they all fit.
          className="grid w-full grid-cols-3 gap-1 sm:flex sm:flex-nowrap [&>button]:w-full [&>button]:truncate sm:[&>button]:flex-1"
          ariaLabel="أقسام حسابي"
          value={active}
          onChange={(v) => setPane(v as Pane)}
          options={tabs.map((t) => ({ value: t.id, label: t.label }))}
        />
        {/* The sentence that used to live under each row. Without it the strip is five nouns. */}
        <p className="px-1 text-sm text-text-secondary">
          {TABS.find((t) => t.id === active)?.hint}
        </p>
      </div>

      {active === 'billing' ? (
        <div className="flex flex-col gap-4">
          <PlansPane
            session={session}
            catalog={catalog}
            owned={owned}
            // THE ONE SEAM BETWEEN TWO TABS, and it earns itself: a subscription cannot run without a
            // connected number, so the pane that says so must be able to take him there — which is
            // now a section on another tab rather than a tab of its own.
            onGoConnect={() => setPane('shop')}
          />
        </div>
      ) : null}

      {active === 'invoices' ? <InvoicesPane session={session} catalog={catalog} /> : null}

      {active === 'shop' ? (
        <div className="flex flex-col gap-6">
          {/* ── who he is, and where he works — moved here (was floating above every tab) at the
              product owner's own direction: «منشأتي» is where an owner looks for anything about
              his own identity within the shop, the same reasoning ShopPane's own weekly-digest
              toggle already follows. Depends on no capability, only `session.operatorName` (never
              absent) and the branch read above. */}
          <div className="flex flex-col gap-0.5 rounded-card bg-surface-1 p-4 shadow-sm">
            <span className="text-lg font-semibold">{session.operatorName || session.operator}</span>
            {myBranch ? (
              <span className="text-sm text-text-secondary">
                {myBranch.name || myBranch.id}
              </span>
            ) : myBranchFailed ? (
              <span className="text-sm text-danger">تعذّرت قراءة فرعك</span>
            ) : null}
          </div>

          {/* ── change my own password — moved here from floating above every tab, same reasoning:
              «منشأتي» is where he looks, even though the capability behind it (identity.self) is
              per-person rather than per-establishment (held by every human role). */}
          {action(catalog, 'identity.change_password') ? (
            <ChangePasswordCard session={session} catalog={catalog} />
          ) : null}

          {/* THE ORDER IS THE ORDER HE NEEDS THEM IN, not the order we built them: what the
              customer sees, then where the shop is, then who works there, then what sends in its
              name. Sections rather than nested tabs — a tab inside a tab hides half the page
              behind two taps, and nobody remembers which one they were on. */}
          <ShopPane session={session} catalog={catalog} />
          <TeamScreen session={session} catalog={catalog} />
          {/* PER_BRANCH SHOPS GET ONE CARD A BRANCH — `ConnectByBranch` itself decides between the
              single establishment-wide card (every shop that never left `central` mode, the
              overwhelming default) and a list, by reading `shop_mode`; nothing here needs to know
              which one it is. */}
          <ConnectByBranch session={session} catalog={catalog} />
          <KeysPane session={session} catalog={catalog} />
        </div>
      ) : null}

      {active === 'data' ? <DataPane session={session} catalog={catalog} /> : null}
    </div>
  );
}

/** Collapsed by default — a control this sensitive earns the extra tap rather than sitting open on
 *  a page loaded a dozen times a day (same balance apps/console/src/affiliates/AffiliateAccount.tsx's
 *  own ChangePasswordCard already struck for the affiliate side of this product). The three-field
 *  pattern (current + new + confirm) rather than a reset flow: this is an AUTHENTICATED change made
 *  while he already holds a session, never the unauthenticated "forgot password" screen. */
function ChangePasswordCard({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [open, setOpen] = useState(false);
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)}
             className="flex items-center gap-2 rounded-card bg-surface-1 p-4 text-sm shadow-sm">
        <KeyRound size={16} className="text-text-secondary" /> تغيير كلمة المرور
      </button>
    );
  }

  async function submit() {
    if (!newPassword) return;
    if (newPassword !== confirm) { setError('كلمتا المرور الجديدتان غير متطابقتين.'); return; }
    const a = action(catalog, 'identity.change_password');
    if (!a) return;
    setBusy(true); setError(''); setDone(false);
    try {
      await call(session, a, { old_password: oldPassword, new_password: newPassword });
      setDone(true);
      setOldPassword(''); setNewPassword(''); setConfirm('');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر تغيير كلمة المرور.');
    } finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex items-center gap-2 text-sm font-medium text-text-secondary">
        <KeyRound size={16} /> تغيير كلمة المرور
      </div>
      <Field label="كلمة المرور الحالية" htmlFor="acct-cp-old">
        <Input id="acct-cp-old" type="password" autoComplete="current-password" dir="ltr"
              value={oldPassword}
              onChange={(e) => { setOldPassword(e.target.value); setDone(false); }} />
      </Field>
      <Field label="كلمة المرور الجديدة" htmlFor="acct-cp-new">
        <Input id="acct-cp-new" type="password" autoComplete="new-password" dir="ltr"
              value={newPassword}
              onChange={(e) => { setNewPassword(e.target.value); setDone(false); }} />
      </Field>
      <Field label="تأكيد كلمة المرور الجديدة" htmlFor="acct-cp-confirm">
        <Input id="acct-cp-confirm" type="password" autoComplete="new-password" dir="ltr"
              value={confirm}
              onChange={(e) => { setConfirm(e.target.value); setDone(false); }} />
      </Field>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      {done ? <p className="text-sm text-success">تم تغيير كلمة المرور.</p> : null}
      <div className="flex items-center gap-2">
        <Button type="button" disabled={busy || !oldPassword || !newPassword} onClick={submit}>
          حفظ
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>إلغاء</Button>
      </div>
    </div>
  );
}
