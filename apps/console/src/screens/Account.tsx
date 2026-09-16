/**
 * «حسابي» — the page every product neglects, because it becomes where everything with no home
 * is dumped.
 *
 * THE RULE THAT KEEPS IT WHOLE: only what concerns the RELATIONSHIP between us and him — his
 * subscription, his channel, his identity, his data. A service price belongs to «خدماتي», a
 * template to «الحملات». Anything proposed here because it "found no place" is refused by that
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
import { KeyRound, MapPin, UserCog } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Field, Input } from '../rj-ui/Field';
import { PageHeader } from '../rj-ui/PageHeader';
import { Card } from '../rj-ui/Card';
import { Segmented } from '../rj-ui/Segmented';
import { TabBar } from '../rj-ui/TabBar';
import { action, call, type Catalog } from '../catalog';
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
 * FOUR TABS, AND FOUR OLD NAMES THAT STILL RESOLVE.
 *
 * `whatsapp`, `team`, `keys` and `invoices` were tabs of their own and are now SECTIONS inside two
 * of these. They stay in the type because they are live URLs: «أضِفه إلى اشتراكي» links, a
 * bookmark, a message somebody sent a colleague. Dropping them would turn every one of those into
 * a page that opens on the wrong thing — which is exactly the failure a deep link exists to
 * prevent.
 */
export type Pane = 'shop' | 'billing' | 'wallet' | 'invoices' | 'data';
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
  return (['shop', 'billing', 'wallet', 'invoices', 'data'] as const).includes(link as Pane)
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
/**
 * A function of `t`, not a module-level constant — this used to be a plain array of Arabic
 * literals, but labels and hints must follow the signed-in account's own operator locale, and a
 * hook can only be called from inside a component.
 */
function tabsFor(t: (key: string) => string): { id: Pane; label: string; hint: string }[] {
  return [
    // ONE TAB FOR THE ESTABLISHMENT, because its five parts answer one question — who and what may
    // act in this shop, and under whose name. They were five separate tabs and a person looking for
    // «who works here» had to guess which of them held it.
    { id: 'shop', label: t('account.tab.shop.label'), hint: t('account.tab.shop.hint') },
    // THE APP AND THE INVOICES ARE ONE ERRAND: money. They were split because choosing an app and
    // fetching a receipt are different acts — which is true, and still leaves both under the one
    // word an owner thinks of when he is here for either.
    // «متجر التطبيقات», WHICH IS WHAT THE REST OF THE PRODUCT ALREADY CALLED IT. The tab said
    // «اشتراكي» and four screens said «متجر التطبيقات» — two names for one place, and the one
    // printed in the sentences that send people here was the one that did not exist.
    { id: 'billing', label: t('account.tab.billing.label'), hint: t('account.tab.billing.hint') },
    // A NEW TAB, DELIBERATELY NOT A NEW RAIL SECTION — nav.ts documents "the nine sections" as a
    // fixed architectural constant (a phone-width limit), so a wallet balance broken down by
    // purpose lives here instead, beside the other money errand. Its own component, its own
    // design — built independently of PlansPane's, which is slated for a full rebuild.
    { id: 'wallet', label: t('account.tab.wallet.label'), hint: t('account.tab.wallet.hint') },
    // THE INVOICES CAME OUT OF THE STORE AND BECAME A TAB. They were the second half of a tab
    // whose first half is a catalogue: a person arriving to buy an app scrolled past his
    // receipts, and a person arriving for a receipt scrolled past the shop. Two errands, and
    // only one of them is browsing.
    { id: 'invoices', label: t('account.tab.invoices.label'), hint: t('account.tab.invoices.hint') },
    { id: 'data', label: t('account.tab.data.label'), hint: t('account.tab.data.hint') },
  ];
}


export function AccountScreen(
  { session, catalog, openOn, owned }:
  // `openOn` IS WHERE SOMEBODY ELSE SENT HIM. The locked cards across the product say «أضِفه إلى
  // اشتراكي», and a button that lands on a page and then makes him find the right tab is a button
  // that loses half the people who pressed it. Ignored when he may not read that tab.
  { session: Session; catalog: Catalog; openOn?: PaneLink; owned?: Loading<Owned> },
) {
  const { t } = useOperatorI18n();
  const TABS = tabsFor(t);
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

  const tabs = TABS.filter((tab) => {
    if (tab.id === 'billing') {
      return Boolean(action(catalog, 'billing.plans')
        || action(catalog, 'billing.my_subscriptions'));
    }
    // ITS OWN READ, NOT THE STORE'S. Offering «الفواتير» to somebody whose role cannot list them
    // is a tab that can only ever say «لا يشمل دورك فواتير المحل» — a door with a wall behind it.
    if (tab.id === 'invoices') return Boolean(action(catalog, 'billing.my_invoices'));
    // OFFERED IF ANY ONE OF ITS SECTIONS IS. The tab is a container now, and gating it on the
    // identity read alone would hide a manager's team and connection behind a permission he does
    // not need for either.
    if (tab.id === 'shop') {
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
  const active = tabs.some((tab) => tab.id === pane) ? pane : tabs[0].id;

  /** «منشأتي» ITSELF SPLIT, at the product owner's own direction: it had grown into five sections
   *  stacked in one long scroll, which is the same "everything with no home" problem this file's
   *  own header comment warns the WHOLE page against, just one level down.
   *
   *  «العاملون»/«الفروع» ARE TWO OF THESE OPTIONS DIRECTLY, not a "الفروع والفريق" tab that then
   *  nests `TeamScreen`'s own switcher under it — that nested a second tab strip directly under
   *  this one, which the owner ruled out entirely regardless of level ("ممنوع اطلاقاً يطلع
   *  شريطين تحت بعض"). `TeamScreen` renders in CONTROLLED mode here (a `tab`/`onChangeTab` pair)
   *  so it draws no switcher of its own — see its own comment. */
  const [shopSub, setShopSub] = useState<'people' | 'branches' | 'whatsapp' | 'identity'>('people');
  // THE BRANCH TAB'S OWN LOCK (هـ-3, branchGate) — reported by `TeamScreen` once the branches
  // read resolves, since this file has no read of its own to compute it from. `'open'` is the
  // exact same "never lock on an unknown" default `branchGate` itself returns before that.
  const [branchGateState, setBranchGateState] = useState<BranchGate>('open');
  const SHOP_SUBTABS = [
    { value: 'people' as const, label: t('account.subtab.people') },
    // THE LOCK IS VISIBLE BEFORE HE PRESSES, not after — same reasoning as always, now through
    // Segmented's own `badge`/`badgeTone` (its 2026-09-07 redesign exists for exactly this: a
    // status baked into the label as raw text/emoji, with zero colour, is what that redesign
    // replaced everywhere else — this raw "🔒" was the one spot still doing it the old way).
    { value: 'branches' as const, label: t('account.subtab.branches'),
     ...(branchGateState !== 'open' ? { badge: t('account.subtab.branchesLocked'), badgeTone: 'partial' as const } : {}) },
    { value: 'whatsapp' as const, label: t('account.subtab.whatsapp') },
    { value: 'identity' as const, label: t('account.subtab.identity') },
  ];

  return (
    <div className="flex flex-col gap-5 p-4">
      <PageHeader icon={UserCog} title={t('account.pageTitle')} />

      {/* ── who he is, and where he works — ALWAYS shown, regardless of tab. A field operator's
          role often cannot reach «منشأتي» at all (it is gated on capabilities his role does not
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
        <div className="flex flex-col gap-0.5">
          <span className="text-lg font-semibold">{session.operatorName || session.operator}</span>
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
            the page's own «منشأتي» sub-tabs below are ALSO a Segmented strip, and two pill-track
            rows stacked directly on each other is exactly "شريطين تحت بعض", the shape the owner
            ruled out entirely (Segmented's own module docstring, TabBar's own docstring). TabBar's
            underline shape reads as real navigation into a different section of the page; the
            nested «منشأتي» row stays Segmented precisely because IT is a filter within one
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

      {active === 'shop' ? (
        <div className="flex flex-col gap-4">
          {/* «منشأتي» split into four, at the product owner's own direction — it had grown into
              five sections stacked in one long scroll. Same Segmented pattern as the top-level
              tabs, one level down — `size="sm"` now marks it as exactly that: nested, not a
              second copy of the top-level row (Segmented's own module docstring). FOUR options
              now (was three): «العاملون»/«الفروع» joined directly instead of sitting behind one
              "الفروع والفريق" tab — see the `shopSub` state's own comment above. */}
          <Segmented
            size="sm"
            className="grid w-full grid-cols-2 gap-1 sm:flex sm:flex-nowrap [&>button]:w-full [&>button]:truncate sm:[&>button]:flex-1"
            ariaLabel={t('account.shopSubtabsAriaLabel')}
            value={shopSub}
            onChange={(v) => setShopSub(v as typeof shopSub)}
            options={SHOP_SUBTABS}
          />

          {shopSub === 'people' || shopSub === 'branches' ? (
            <div className="flex flex-col gap-6">
              <TeamScreen session={session} catalog={catalog} tab={shopSub}
                        onChangeTab={setShopSub} onBranchGateChange={setBranchGateState} />
            </div>
          ) : null}

          {shopSub === 'whatsapp' ? (
            <div className="flex flex-col gap-6">
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

          {shopSub === 'identity' ? (
            <div className="flex flex-col gap-6">
              {/* ── change my own password — the capability behind it (identity.self) is
                  per-person rather than per-establishment, held by every human role. */}
              {action(catalog, 'identity.change_password') ? (
                <ChangePasswordCard session={session} catalog={catalog} />
              ) : null}

              <ShopPane session={session} catalog={catalog} />
              <KeysPane session={session} catalog={catalog} />
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
