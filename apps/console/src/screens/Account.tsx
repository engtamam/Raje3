/**
 * «حسابي» — the page every product neglects, because it becomes where everything with no home
 * is dumped.
 *
 * THE RULE THAT KEEPS IT WHOLE: only what concerns the RELATIONSHIP between us and him — his
 * subscription, his channel, his identity, his data. A service price belongs to «خدماتي», a
 * template to «الحملات». Anything proposed here because it "found no place" is refused by that
 * sentence, and this comment exists so the refusal has something to point at.
 *
 * TABS ACROSS THE TOP, LIKE EVERY OTHER SECTION. And BRANCHES GOT A TAB OF ITS OWN (this pass),
 * split out of the old «منشأتي» container it used to share with identity/WhatsApp/keys. The
 * mobile app organises the same domain as a hub with dedicated branch/branch-detail/billing/
 * shop-identity destinations, and burying "who works where, and can I see them" three sub-tabs
 * deep under a generic establishment tab read as a settings menu rather than the second most
 * asked question on this screen. Identity (name/logo/colour, the owner's own name, password,
 * connection keys) stays its own tab too — a different concern from "which branches, and who
 * works in them."
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
import { KeyRound, MapPin, Pencil, UserCog } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Field, Input } from '../rj-ui/Field';
import { PageHeader } from '../rj-ui/PageHeader';
import { Card } from '../rj-ui/Card';
import { Segmented } from '../rj-ui/Segmented';
import { TabBar } from '../rj-ui/TabBar';
import { action, call, type Catalog } from '../catalog';
import { getMyName, setMyName } from '../api';
import type { Session } from '../session';
import { ConnectByBranch } from './Connect';
import { DataPane, InvoicesPane, KeysPane, ShopPane } from './AccountPanes';
import { BillingStatusPane } from './BillingStatusPane';
import { WalletPane } from './Wallet';
import { TeamScreen } from './Team';
import { type BranchGate } from '../branches';
import { type Loading } from '../loading';
import type { Owned } from '../apps';
import { useOperatorI18n } from '../operator-i18n';
import './account-i18n';

/**
 * FIVE TABS, AND FIVE OLD NAMES THAT STILL RESOLVE.
 *
 * `shop`, `whatsapp`, `team` and `keys` were tabs (or a shared sub-tab) of their own and are now
 * split across `identity` and `branches`. `login` never was a tab any more (see MOVED below); it
 * stays in the type only because it is a live URL. Dropping any of these would turn a bookmark,
 * a colleague's message, or an «أضِفه إلى اشتراكي» lock into a page that opens on the wrong thing
 * — exactly the failure a deep link exists to prevent.
 */
export type Pane = 'identity' | 'branches' | 'billing' | 'wallet' | 'invoices' | 'data';
export type PaneLink = Pane | 'login' | 'whatsapp' | 'team' | 'keys' | 'shop';

/**
 * The tab a link opens on. Unknown and absent both land on «الهوية».
 *
 * NOT ON A HARDCODED 'billing', which is where this opened before: a manager who cannot read
 * billing arrived on a tab that was filtered away and the screen fell back a second time. The
 * establishment identity is the one tab anybody with any of its permissions holds.
 */
export function resolvePane(link?: string): Pane {
  if (!link) return 'identity';
  // `hasOwn`, NOT a plain lookup. `?tab=` is a string a stranger types, and `MOVED['__proto__']`
  // answers with an object rather than undefined — which would leave `pane` holding something
  // that is not a tab at all.
  if (Object.hasOwn(MOVED, link)) return MOVED[link];
  return (['identity', 'branches', 'billing', 'wallet', 'invoices', 'data'] as const)
    .includes(link as Pane) ? (link as Pane) : 'identity';
}

/** Where a name that is no longer a tab now lives. */
export const MOVED: Record<string, Pane> = {
  // «دخولي» IS GONE, AND ONLY ONE THING ON IT WAS EVER USED. Three cards of prose explaining what
  // he cannot change here — that his phone is his login, that a session lasts 31 days, how to
  // reset a password — a page to read rather than a page to use. The switch that WAS used, his
  // weekly report, has since been removed with the feature itself; nothing on this tab is left
  // to carry, so the name simply resolves to the identity tab like every other unknown name.
  login: 'identity',
  // «منشأتي» SPLIT IN TWO. The four things it held (shop identity, staff, branches, WhatsApp
  // connection) are now on two tabs: identity keeps the establishment's own facts, password, and
  // connection keys; branches keeps the team and the branch list together, since "who works
  // where" is one question, not two.
  shop: 'identity',
  keys: 'identity',
  whatsapp: 'branches',
  team: 'branches',
};

/**
 * The tabs, each with the sentence that says what is behind it.
 *
 * THE HINT SURVIVED THE REDESIGN, in the line under the tab strip rather than under a row. It is
 * what stops a tab being a noun somebody has to open to understand — and the tab labels are
 * short precisely because that line carries the meaning.
 */
/**
 * A function of `t`, not a module-level constant — this used to be a plain array of Arabic
 * literals, but labels and hints must follow the signed-in account's own operator locale, and a
 * hook can only be called from inside a component.
 */
function tabsFor(t: (key: string) => string): { id: Pane; label: string; hint: string }[] {
  return [
    // WHAT THE ESTABLISHMENT IS, AND WHO HE IS — name/logo/colour, his own name, his password,
    // and the machine keys that can act in his name. All per-person or per-establishment facts,
    // none of them "which branch, which staff member".
    { id: 'identity', label: t('account.tab.identity.label'), hint: t('account.tab.identity.hint') },
    // A TAB OF ITS OWN, SPLIT OUT OF «منشأتي» — branches and the staff inside them, plus the
    // WhatsApp number connection (itself a per-branch fact, `ConnectByBranch` renders one card a
    // branch). "Who works where, and how do customers reach this branch" is one coherent errand.
    { id: 'branches', label: t('account.tab.branches.label'), hint: t('account.tab.branches.hint') },
    // RENAMED, 2026-09-19 — «متجر التطبيقات» WAS RIGHT ONCE, AND STOPPED BEING RIGHT. This
    // tab used to BE the store (subscribe/cancel/discounts/capacity add-ons all lived here), so
    // calling it that matched what the rest of the product already said. Then the whole store
    // moved to the launcher (`AppLauncher.tsx`, [[task-app-store-redesign-7-phases]]) and
    // `BillingStatusPane.tsx` is what remained: a failing charge, and the one control that fixes
    // it — no apps, no subscribing, no browsing. Renamed to «الفوترة» — what is actually behind
    // this tab now.
    { id: 'billing', label: t('account.tab.billing.label'), hint: t('account.tab.billing.hint') },
    // «محفظتي» TAB HIDDEN (2026-09-22, owner's own call) — the wallet balance it showed has no
    // real use left in the product; kept out of the visible tab list rather than deleted
    // (WalletPane/Wallet.tsx, the 'wallet' Pane id) in case it earns a real purpose again.
    // THE INVOICES CAME OUT OF THE STORE AND BECAME A TAB. They were the second half of a tab
    // whose first half is a catalogue: a person arriving to buy an app scrolled past his
    // receipts, and a person arriving for a receipt scrolled past the shop.
    { id: 'invoices', label: t('account.tab.invoices.label'), hint: t('account.tab.invoices.hint') },
    // «حقوقك في بياناتك» TAB HIDDEN (2026-09-22, owner's own call) — the DSAR buttons it showed
    // are replaced with one line in the privacy policy itself: every request, including deletion,
    // goes to the same DPO email already named there. Kept out of the visible tab list rather
    // than deleted (DataPane/AccountPanes.tsx, the 'data' Pane id) in case it earns a real purpose
    // again.
  ];
}


export function AccountScreen(
  { session, catalog, openOn, owned, notice: incomingNotice }:
  // `openOn` IS WHERE SOMEBODY ELSE SENT HIM. The locked cards across the product say «أضِفه إلى
  // اشتراكي», and a button that lands on a page and then makes him find the right tab is a button
  // that loses half the people who pressed it. Ignored when he may not read that tab.
  //
  // `notice` IS THE ONE SENTENCE THE SUBSCRIBE ATTEMPT ITSELF ALREADY WROTE — carried through
  // react-router's own navigation `state` (subscribeFlow.ts's own WHATSAPP_CONNECTION_REQUIRED
  // handling), never a URL query param: it is the server's exact refusal sentence, arbitrary
  // length and free text, not a fixed enum a query string should carry.
  {
    session: Session; catalog: Catalog; openOn?: PaneLink; owned?: Loading<Owned>;
    notice?: string;
  },
) {
  const { t } = useOperatorI18n();
  const TABS = tabsFor(t);
  // WHICH BRANCH IS HIS — a field operator landing here saw a page that never
  // said who he is or where he works, because every tab that WOULD have said so («الفروع») is
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

  // HIS OWN NAME, WHEN HE IS NOT AN OPERATOR — `session.operatorName` already carries a real name
  // for staff (`Operator.name`, minted straight into the token); the owner holds no Operator row
  // at all (staff.py's own docstring) and so had no name anywhere in the product until this. Read
  // and edited through the platform-wide, capability-free `/account/me/name` door — same reasoning
  // `getMyLocale`/`setMyLocale` already established for the language switch (api.ts's own note).
  const [myName, setMyNameState] = useState<string | undefined>(undefined);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState('');
  const [savingName, setSavingName] = useState(false);

  useEffect(() => {
    if (session.operatorName) return; // he already has a real name — nothing to fetch
    getMyName(session).then((row) => setMyNameState(row.name || '')).catch(() => setMyNameState(''));
  }, [session]);

  async function saveName() {
    setSavingName(true);
    try {
      await setMyName(session, nameDraft.trim());
      setMyNameState(nameDraft.trim());
      setEditingName(false);
    } finally {
      setSavingName(false);
    }
  }

  const tabs = TABS.filter((tab) => {
    if (tab.id === 'billing') {
      return Boolean(action(catalog, 'billing.plans')
        || action(catalog, 'billing.my_subscriptions'));
    }
    // ITS OWN READ, NOT THE STORE'S. Offering «الفواتير» to somebody whose role cannot list them
    // is a tab that can only ever say «لا يشمل دورك فواتير المحل» — a door with a wall behind it.
    if (tab.id === 'invoices') return Boolean(action(catalog, 'billing.my_invoices'));
    // THE ESTABLISHMENT'S OWN FACTS AND PERSONAL SECURITY — gated on whichever of the three
    // identity-shaped reads his role actually holds. `identity.change_password` is held by every
    // human role (identity-service grants it per-person, not per-establishment), so in practice
    // this tab is never hidden — which is correct: everyone can at least change their own password.
    if (tab.id === 'identity') {
      return Boolean(action(catalog, 'tenant.view_self')
        || action(catalog, 'identity.change_password')
        || action(catalog, 'identity.list_service_accounts'));
    }
    // WHO WORKS WHERE, AND HOW CUSTOMERS REACH THAT BRANCH. Offered if any one of its three
    // sections is — a container tab gated on staff-management alone would hide WhatsApp
    // connection from a role that manages neither hiring nor branches.
    if (tab.id === 'branches') {
      return Boolean(action(catalog, 'whatsapp.connect_status')
        || action(catalog, 'operations.create_operator')
        || action(catalog, 'operations.list_branches'));
    }
    return true;
  });

  // OPENS ON THE FIRST TAB HE ACTUALLY HAS, not on a hardcoded 'billing' that a manager cannot
  // read. `tabs` is never empty — «الهوية» is everyone's.
  // A LINK MAY NAME A SECTION THAT IS NO LONGER A TAB — see MOVED. It opens the tab that now
  // holds it, and the section itself is on that page.
  const [pane, setPane] = useState<Pane>(() => resolvePane(openOn));
  const active = tabs.some((tab) => tab.id === pane) ? pane : tabs[0].id;

  /** «الفروع» ITSELF HOLDS THREE SECTIONS — staff, the branch list/detail, and the WhatsApp
   *  number connection. Same Segmented-under-TabBar pattern the old «منشأتي» used, kept for the
   *  same reason: the owner ruled out ever stacking two tab strips directly on top of each other
   *  ("ممنوع اطلاقاً يطلع شريطين تحت بعض"). `TeamScreen` renders in CONTROLLED mode here (a
   *  `tab`/`onChangeTab` pair) so it draws no switcher of its own — see its own comment. */
  // OPENS ON THE WHATSAPP SUB-TAB DIRECTLY when `openOn === 'whatsapp'` — the deep link
  // subscribeFlow.ts's own WHATSAPP_CONNECTION_REQUIRED handling now sends (`/account?tab=
  // whatsapp`), the one still missing half of "أضِفه إلى اشتراكي" already lands on the right TOP
  // tab: without this it stopped one level short, on «العاملون» inside «الفروع».
  const [branchesSub, setBranchesSub] = useState<'people' | 'branches' | 'whatsapp'>(
    openOn === 'whatsapp' ? 'whatsapp' : 'people');
  // THE BRANCH TAB'S OWN LOCK (هـ-3, branchGate) — reported by `TeamScreen` once the branches
  // read resolves, since this file has no read of its own to compute it from. `'open'` is the
  // exact same "never lock on an unknown" default `branchGate` itself returns before that.
  const [branchGateState, setBranchGateState] = useState<BranchGate>('open');
  const BRANCHES_SUBTABS = [
    { value: 'people' as const, label: t('account.subtab.people') },
    // THE LOCK IS VISIBLE BEFORE HE PRESSES, not after — same reasoning as always, now through
    // Segmented's own `badge`/`badgeTone` (its 2026-09-07 redesign exists for exactly this: a
    // status baked into the label as raw text/emoji, with zero colour, is what that redesign
    // replaced everywhere else — this raw "🔒" was the one spot still doing it the old way).
    { value: 'branches' as const, label: t('account.subtab.branches'),
     ...(branchGateState !== 'open' ? { badge: t('account.subtab.branchesLocked'), badgeTone: 'partial' as const } : {}) },
    { value: 'whatsapp' as const, label: t('account.subtab.whatsapp') },
  ];

  return (
    <div className="flex flex-col gap-5 p-4">
      <PageHeader icon={UserCog} title={t('account.pageTitle')} />

      {/* ── who he is, and where he works — ALWAYS shown, regardless of tab. A field operator's
          role often cannot reach «الفروع» at all (it is gated on capabilities his role does not
          hold), so this cannot live behind that tab, let alone a sub-tab of it. Depends on no
          capability, only `session.operatorName` (never absent) and the branch read above.
          A COLOURED ICON CIRCLE, not a bare text block — the same "identity card" language every
          other screen in this redesign pass now uses (Wallet.tsx's own KpiCard icons), so the
          person reading it recognises the pattern instead of meeting a fifth flat gray box. */}
      <Card className="flex items-center gap-3 p-4">
        <span aria-hidden
             className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-soft text-accent-on-soft">
          <UserCog size={20} />
        </span>
        <div className="flex flex-1 flex-col gap-0.5">
          {editingName ? (
            <div className="flex items-center gap-2">
              <Input autoFocus value={nameDraft} onChange={(e) => setNameDraft(e.target.value)}
                     onKeyDown={(e) => { if (e.key === 'Enter') void saveName(); }}
                     className="h-8 max-w-56 text-sm" />
              <Button size="sm" disabled={savingName} onClick={() => void saveName()}>
                {savingName ? t('account.savingName') : t('account.saveNameCta')}
              </Button>
              <Button size="sm" variant="ghost" disabled={savingName} onClick={() => setEditingName(false)}>
                {t('account.cancelNameCta')}
              </Button>
            </div>
          ) : (
            <span className="flex items-center gap-1.5 text-lg font-semibold">
              {session.operatorName || myName || session.operator}
              {!session.operatorName && myName !== undefined ? (
                <button type="button" aria-label={t('account.editNameCta')}
                        onClick={() => { setNameDraft(myName); setEditingName(true); }}
                        className="grid size-6 place-items-center rounded-full text-text-secondary transition hover:bg-surface-2 hover:text-text-primary focus-ring">
                  <Pencil size={13} aria-hidden />
                </button>
              ) : null}
            </span>
          )}
          {myBranch ? (
            <span className="flex items-center gap-1 text-sm text-text-secondary">
              <MapPin size={13} aria-hidden /> {myBranch.name || myBranch.id}
            </span>
          ) : myBranchFailed ? (
            <span className="text-sm text-danger">{t('account.myBranchReadFailed')}</span>
          ) : null}
        </div>
      </Card>

      <div className="flex flex-col gap-1.5">
        {/* THE TOP-LEVEL SWITCHER FOR THE WHOLE PAGE — TabBar (rj-ui/TabBar.tsx), never Segmented:
            the page's own «الفروع» sub-tabs below are ALSO a Segmented strip, and two pill-track
            rows stacked directly on each other is exactly "شريطين تحت بعض", the shape the owner
            ruled out entirely (Segmented's own module docstring, TabBar's own docstring). TabBar's
            underline shape reads as real navigation into a different section of the page; the
            nested «الفروع» row stays Segmented precisely because IT is a filter within one
            section, not a second copy of this row. */}
        <TabBar
          fullWidth
          ariaLabel={t('account.tabsAriaLabel')}
          value={active}
          onChange={(v) => setPane(v)}
          options={tabs.map((tab) => ({ value: tab.id, label: tab.label }))}
        />
        {/* The sentence that used to live under each row. Without it the strip is five nouns. */}
        <p className="px-1 text-sm text-text-secondary">
          {TABS.find((tab) => tab.id === active)?.hint}
        </p>
      </div>

      {active === 'billing' ? (
        <div className="flex flex-col gap-4">
          <BillingStatusPane session={session} catalog={catalog} />
        </div>
      ) : null}

      {active === 'wallet' ? <WalletPane session={session} catalog={catalog} /> : null}

      {active === 'invoices' ? <InvoicesPane session={session} catalog={catalog} /> : null}

      {active === 'identity' ? (
        <div className="flex flex-col gap-4">
          {/* ── change my own password — the capability behind it (identity.self) is
              per-person rather than per-establishment, held by every human role. */}
          {action(catalog, 'identity.change_password') ? (
            <ChangePasswordCard session={session} catalog={catalog} />
          ) : null}

          <ShopPane session={session} catalog={catalog} />
          <KeysPane session={session} catalog={catalog} />
        </div>
      ) : null}

      {active === 'branches' ? (
        <div className="flex flex-col gap-4">
          {/* «الفروع» split into three, one level down from the top-level tab — same Segmented
              pattern the top-level tabs use, `size="sm"` marking it as nested rather than a second
              copy of the top-level row (Segmented's own module docstring). */}
          <Segmented
            size="sm"
            className="grid w-full grid-cols-3 gap-1 sm:flex sm:flex-nowrap [&>button]:w-full [&>button]:truncate sm:[&>button]:flex-1"
            ariaLabel={t('account.branchesSubtabsAriaLabel')}
            value={branchesSub}
            onChange={(v) => setBranchesSub(v as typeof branchesSub)}
            options={BRANCHES_SUBTABS}
          />

          {branchesSub === 'people' || branchesSub === 'branches' ? (
            <div className="flex flex-col gap-6">
              <TeamScreen session={session} catalog={catalog} tab={branchesSub}
                        onChangeTab={setBranchesSub} onBranchGateChange={setBranchGateState} />
            </div>
          ) : null}

          {branchesSub === 'whatsapp' ? (
            <div className="flex flex-col gap-6">
              {/* THE REFUSAL SENTENCE ITSELF, CARRIED FROM THE ATTEMPT THAT SENT HIM HERE — see
                  `notice` prop's own comment above. Absent on every ordinary visit to this tab. */}
              {incomingNotice ? (
                <p role="alert" className="text-sm text-warning">{incomingNotice}</p>
              ) : null}
              {/* PER_BRANCH SHOPS GET ONE CARD A BRANCH — `ConnectByBranch` itself decides between
                  the single establishment-wide card (every shop that never left `central` mode,
                  the overwhelming default) and a list, by reading `shop_mode`; nothing here needs
                  to know which one it is.
                  THIS IS THE ONLY WHATSAPP CARD LEFT HERE, ON PURPOSE (2026-09-16, the owner's own
                  instruction) — connecting the number itself is a GENERAL establishment fact, not
                  something specific to the assistant bot (a shop could in principle connect the
                  number for a future, non-AI use of the channel). Everything that configures the
                  ASSISTANT's own behaviour moved to its own dedicated app screen —
                  `WhatsAppAssistant.tsx`, reached from متجر التطبيقات like any other app, not
                  buried three tabs deep in «حسابي». */}
              <ConnectByBranch session={session} catalog={catalog} />
            </div>
          ) : null}
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
  const { t } = useOperatorI18n();
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
        <KeyRound size={16} className="text-text-secondary" /> {t('account.changePassword.title')}
      </button>
    );
  }

  async function submit() {
    if (!newPassword) return;
    if (newPassword !== confirm) { setError(t('account.changePassword.mismatch')); return; }
    const a = action(catalog, 'identity.change_password');
    if (!a) return;
    setBusy(true); setError(''); setDone(false);
    try {
      await call(session, a, { old_password: oldPassword, new_password: newPassword });
      setDone(true);
      setOldPassword(''); setNewPassword(''); setConfirm('');
    } catch (err) {
      setError(err instanceof Error ? err.message : t('account.changePassword.failed'));
    } finally { setBusy(false); }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-center gap-2 text-sm font-medium text-text-secondary">
        <KeyRound size={16} /> {t('account.changePassword.title')}
      </div>
      <Field label={t('account.changePassword.currentLabel')} htmlFor="acct-cp-old">
        <Input id="acct-cp-old" type="password" autoComplete="current-password" dir="ltr"
              value={oldPassword}
              onChange={(e) => { setOldPassword(e.target.value); setDone(false); }} />
      </Field>
      <Field label={t('account.changePassword.newLabel')} htmlFor="acct-cp-new">
        <Input id="acct-cp-new" type="password" autoComplete="new-password" dir="ltr"
              value={newPassword}
              onChange={(e) => { setNewPassword(e.target.value); setDone(false); }} />
      </Field>
      <Field label={t('account.changePassword.confirmLabel')} htmlFor="acct-cp-confirm">
        <Input id="acct-cp-confirm" type="password" autoComplete="new-password" dir="ltr"
              value={confirm}
              onChange={(e) => { setConfirm(e.target.value); setDone(false); }} />
      </Field>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      {done ? <p className="text-sm text-success">{t('account.changePassword.success')}</p> : null}
      <div className="flex items-center gap-2">
        <Button type="button" disabled={busy || !oldPassword || !newPassword} onClick={submit}>
          {t('account.changePassword.save')}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setOpen(false)}>{t('account.changePassword.cancel')}</Button>
      </div>
    </Card>
  );
}
