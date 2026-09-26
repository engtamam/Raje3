/**
 * «حسابي» — the page every product neglects, because it becomes where everything with no home
 * is dumped.
 *
 * THE RULE THAT KEEPS IT WHOLE: only what concerns the RELATIONSHIP between us and him — his
 * subscription, his channel, his identity, his data. A service price belongs to «خدماتي», a
 * template to «الحملات». Anything proposed here because it "found no place" is refused by that
 * sentence, and this comment exists so the refusal has something to point at.
 *
 * REBUILT AS A DIRECTORY OF FOCUSED SCREENS, not one file holding every pane. The old
 * AccountPanes.tsx grew to over a thousand lines because every concern this page touches —
 * establishment identity, connection keys, branches/team/WhatsApp, invoices, PDPL — landed in the
 * same file with no boundary between them. This mirrors how the mobile app organises the exact
 * same domain: apps/mobile/lib/features/account/account_screen.dart is a thin hub, and
 * shop_identity_screen.dart / billing_screen.dart / branches_screen.dart / branch_detail_screen.dart
 * each own one concern. The console stays a wide desktop page with tabs across the top — that
 * part is NOT copied from mobile, which uses a grouped list instead, because a horizontal tab
 * strip is correct on this layout and a scrollable settings list is correct on a phone. What IS
 * copied is the organisational discipline: this file is the hub (identity-card header, tab shell,
 * routing between panes) and every pane below lives in its own file under `account/`
 * (IdentityPane.tsx, BranchesPane.tsx, InvoicesPane.tsx, DataPane.tsx), with BillingStatusPane.tsx
 * and Wallet.tsx already their own files before this pass.
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
import { MapPin, Pencil, UserCog } from 'lucide-react';
import { Button } from '../../rj-ui/Button';
import { Input } from '../../rj-ui/Field';
import { PageHeader } from '../../rj-ui/PageHeader';
import { Card } from '../../rj-ui/Card';
import { TabBar } from '../../rj-ui/TabBar';
import { action, call, type Catalog } from '../../catalog';
import { getMyName, setMyName } from '../../api';
import type { Session } from '../../session';
import { BillingStatusPane } from '../BillingStatusPane';
import { WalletPane } from '../Wallet';
import { type Loading } from '../../loading';
import type { Owned } from '../../apps';
import { useOperatorI18n } from '../../operator-i18n';
import { ChangePasswordCard, KeysPane, ShopPane } from './IdentityPane';
import { BranchesPane, branchesTabVisible } from './BranchesPane';
import { InvoicesPane } from './InvoicesPane';
import { DataPane } from './DataPane';
import '../account-i18n';

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
  // «دخولي» IS GONE, AND ONLY ONE THING ON IT WAS EVER USED — nothing on that tab is left to
  // carry, so the name simply resolves to the identity tab like every other unknown name.
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
 * A function of `t`, not a module-level constant — labels and hints must follow the signed-in
 * account's own operator locale, and a hook can only be called from inside a component.
 */
function tabsFor(t: (key: string) => string): { id: Pane; label: string; hint: string }[] {
  return [
    { id: 'identity', label: t('account.tab.identity.label'), hint: t('account.tab.identity.hint') },
    { id: 'branches', label: t('account.tab.branches.label'), hint: t('account.tab.branches.hint') },
    { id: 'billing', label: t('account.tab.billing.label'), hint: t('account.tab.billing.hint') },
    // «محفظتي» TAB HIDDEN (owner's own call) — kept out of the visible tab list rather than
    // deleted (Wallet.tsx, the 'wallet' Pane id) in case it earns a real purpose again.
    { id: 'invoices', label: t('account.tab.invoices.label'), hint: t('account.tab.invoices.hint') },
    // «حقوقك في بياناتك» TAB HIDDEN (owner's own call) — kept out of the visible tab list rather
    // than deleted (DataPane.tsx, the 'data' Pane id) in case it earns a real purpose again.
  ];
}

export function AccountScreen(
  { session, catalog, openOn, owned: _owned, notice: incomingNotice }:
  // `openOn` IS WHERE SOMEBODY ELSE SENT HIM — the locked cards across the product say «أضِفه إلى
  // اشتراكي», and a button that lands on a page and then makes him find the right tab is a button
  // that loses half the people who pressed it. Ignored when he may not read that tab.
  //
  // `notice` IS THE ONE SENTENCE THE SUBSCRIBE ATTEMPT ITSELF ALREADY WROTE — carried through
  // react-router's own navigation `state`, never a URL query param.
  {
    session: Session; catalog: Catalog; openOn?: PaneLink; owned?: Loading<Owned>;
    notice?: string;
  },
) {
  const { t } = useOperatorI18n();
  const TABS = tabsFor(t);
  // WHICH BRANCH IS HIS — a field operator landing here saw a page that never said who he is or
  // where he works, because every tab that WOULD have said so («الفروع») is gated on capabilities
  // his role does not hold. This reads independently of any tab, off the SAME two-id read
  // App.tsx's own branch switcher uses. Only rendered when it resolves to exactly ONE branch: a
  // multi-branch owner already has the switcher for this.
  const [myBranch, setMyBranch] = useState<{ id: string; name?: string } | null | undefined>(undefined);
  // TOLD APART FROM «not applicable» AND «not a single branch» — both of those are `myBranch ===
  // null` and stay silent. Only an actual failed read sets this.
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
  // for staff; the owner holds no Operator row at all and so had no name anywhere in the product
  // until this. Read and edited through the platform-wide, capability-free `/account/me/name` door.
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
    // human role, so in practice this tab is never hidden.
    if (tab.id === 'identity') {
      return Boolean(action(catalog, 'tenant.view_self')
        || action(catalog, 'identity.change_password')
        || action(catalog, 'identity.list_service_accounts'));
    }
    if (tab.id === 'branches') return branchesTabVisible(catalog);
    return true;
  });

  // OPENS ON THE FIRST TAB HE ACTUALLY HAS, not on a hardcoded 'billing' that a manager cannot
  // read. `tabs` is never empty — «الهوية» is everyone's.
  const [pane, setPane] = useState<Pane>(() => resolvePane(openOn));
  const active = tabs.some((tab) => tab.id === pane) ? pane : tabs[0].id;

  return (
    <div className="flex flex-col gap-5 p-4">
      <PageHeader icon={UserCog} title={t('account.pageTitle')} />

      {/* ── who he is, and where he works — ALWAYS shown, regardless of tab. A field operator's
          role often cannot reach «الفروع» at all, so this cannot live behind that tab. Depends on
          no capability, only `session.operatorName` (never absent) and the branch read above. */}
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
        {/* THE TOP-LEVEL SWITCHER FOR THE WHOLE PAGE — TabBar, never Segmented: BranchesPane's own
            sub-tabs are ALSO a Segmented strip, and two pill-track rows stacked directly on each
            other is exactly the shape the owner ruled out entirely. */}
        <TabBar
          fullWidth
          ariaLabel={t('account.tabsAriaLabel')}
          value={active}
          onChange={(v) => setPane(v)}
          options={tabs.map((tab) => ({ value: tab.id, label: tab.label }))}
        />
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
        <BranchesPane session={session} catalog={catalog}
                      openOnWhatsapp={openOn === 'whatsapp'}
                      incomingNotice={incomingNotice} />
      ) : null}

      {active === 'data' ? <DataPane session={session} catalog={catalog} /> : null}
    </div>
  );
}
