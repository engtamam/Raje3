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
import { Badge } from '@base-ui/design-system/Badge';
import { Segmented } from '@base-ui/design-system/Segmented';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { Connect } from './Connect';
import { DataPane, InvoicesPane, KeysPane, LoginPane, ShopPane } from './AccountPanes';
import { PlansPane } from './Plans';
import { TeamScreen } from './Team';
import { type Loading } from '../loading';
import type { Owned } from '../apps';

interface Subscription { id: string; plan_name?: string; status?: string; period_end?: number }
/** Mirrors what operations answers — see Connect.tsx for why `can_send` is its own question. */
interface ConnectState { state: string; message: string; can_send?: boolean }

/**
 * FOUR TABS, AND FOUR OLD NAMES THAT STILL RESOLVE.
 *
 * `whatsapp`, `team`, `keys` and `invoices` were tabs of their own and are now SECTIONS inside two
 * of these. They stay in the type because they are live URLs: «أضِفه إلى اشتراكي» links, a
 * bookmark, a message somebody sent a colleague. Dropping them would turn every one of those into
 * a page that opens on the wrong thing — which is exactly the failure a deep link exists to
 * prevent.
 */
export type Pane = 'shop' | 'billing' | 'login' | 'data';
export type PaneLink = Pane | 'invoices' | 'whatsapp' | 'team' | 'keys';

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
  return (['shop', 'billing', 'login', 'data'] as const).includes(link as Pane)
    ? (link as Pane)
    : 'shop';
}

/** Where a name that is no longer a tab now lives. */
export const MOVED: Record<string, Pane> = {
  invoices: 'billing',
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
  // THE PLAN AND THE INVOICES ARE ONE ERRAND: money. They were split because choosing a plan and
  // fetching a receipt are different acts — which is true, and still leaves both under the one
  // word an owner thinks of when he is here for either.
  // «متجر التطبيقات», WHICH IS WHAT THE REST OF THE PRODUCT ALREADY CALLED IT. The tab said
  // «اشتراكي» and four screens said «متجر التطبيقات» — two names for one place, and the one
  // printed in the sentences that send people here was the one that did not exist.
  { id: 'billing', label: 'متجر التطبيقات', hint: 'تطبيقاتك وفواتيرك ووسيلة الدفع' },
  { id: 'login', label: 'دخولي', hint: 'جوالك وكلمة مرورك وتقريرك الأسبوعي' },
  { id: 'data', label: 'بياناتي', hint: 'الاحتفاظ، التصدير، الاتفاقيات' },
];


export function AccountScreen(
  { session, catalog, openOn, owned }:
  // `openOn` IS WHERE SOMEBODY ELSE SENT HIM. The locked cards across the product say «أضِفه إلى
  // اشتراكي», and a button that lands on a page and then makes him find the right tab is a button
  // that loses half the people who pressed it. Ignored when he may not read that tab.
  { session: Session; catalog: Catalog; openOn?: PaneLink; owned?: Loading<Owned> },
) {
  const [sub, setSub] = useState<Subscription | null | undefined>(undefined);
  const [connected, setConnected] = useState<ConnectState | null | undefined>(undefined);

  useEffect(() => {
    const a = action(catalog, 'billing.my_subscriptions');
    if (a) {
      call<{ subscriptions: Subscription[] }>(session, a)
        .then((x) => setSub(x.subscriptions?.[0] ?? null))
        .catch(() => setSub(null));
    } else {
      // The manager reaches this page without billing. Not an error and not a blank: the tab is
      // simply not offered to him, and the status line does not claim a plan it cannot read.
      setSub(null);
    }

    const w = action(catalog, 'whatsapp.connect_status');
    if (w) call<ConnectState>(session, w).then(setConnected).catch(() => setConnected(null));
  }, [session, catalog]);

  const tabs = TABS.filter((t) => {
    if (t.id === 'billing') {
      return Boolean(action(catalog, 'billing.plans') || action(catalog, 'billing.my_subscriptions')
        || action(catalog, 'billing.my_invoices'));
    }
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
  const isConnected = connected?.state === 'connected';
  // «يعمل» IS THE STRONGEST CLAIM ON THIS PAGE, and it was made on the strength of a successful
  // connection alone. A shop can be connected while nothing can leave — see Connect.tsx — and this
  // badge is what an owner glances at to decide everything is fine.
  const sendingOpen = isConnected && connected?.can_send !== false;

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* ── the two lines that answer the page's question without a tap ── */}
      <div className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
        {sub === undefined ? (
          <Skeleton height={20} />
        ) : (
          <div className="flex items-center justify-between">
            <span>{sub ? `باقتك «${sub.plan_name ?? '—'}»` : 'لا يوجد اشتراك فعّال'}</span>
            {sub?.status
              ? <Badge tone={sub.status === 'active' ? 'success' : 'warning'}>
                  {sub.status === 'active' ? 'فعّالة' : 'متوقفة'}
                </Badge>
              : null}
          </div>
        )}
        <div className="flex items-center justify-between">
          <span>
            {!isConnected ? 'واتساب غير مربوط'
              : sendingOpen ? 'واتساب مربوط' : 'واتساب مربوط — الإرسال لم يُفتح بعد'}
          </span>
          {!isConnected
            ? <Badge tone="warning">يحتاج ربط</Badge>
            : sendingOpen
              ? <Badge tone="success">يعمل</Badge>
              // NOT «يحتاج ربط»: he did the work and it succeeded. What is missing is ours, and a
              // badge that sends him back to a button he already pressed is the worse lie.
              : <Badge tone="warning">بانتظارنا</Badge>}
        </div>
      </div>

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
            // THE ONE SEAM BETWEEN TWO TABS, and it earns itself: a plan cannot run without a
            // connected number, so the pane that says so must be able to take him there — which is
            // now a section on another tab rather than a tab of its own.
            onGoConnect={() => setPane('shop')}
          />
          <InvoicesPane session={session} catalog={catalog} />
        </div>
      ) : null}

      {active === 'shop' ? (
        <div className="flex flex-col gap-6">
          {/* THE ORDER IS THE ORDER HE NEEDS THEM IN, not the order we built them: what the
              customer sees, then where the shop is, then who works there, then what sends in its
              name. Sections rather than nested tabs — a tab inside a tab hides half the page
              behind two taps, and nobody remembers which one they were on. */}
          <ShopPane session={session} catalog={catalog} />
          <TeamScreen session={session} catalog={catalog} />
          <Connect session={session} catalog={catalog} state={connected} onChange={setConnected} />
          <KeysPane session={session} catalog={catalog} />
        </div>
      ) : null}

      {active === 'login' ? <LoginPane session={session} catalog={catalog} /> : null}
      {active === 'data' ? <DataPane session={session} catalog={catalog} /> : null}
    </div>
  );
}
