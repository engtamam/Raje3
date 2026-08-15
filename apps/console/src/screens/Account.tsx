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

interface Subscription { id: string; plan_name?: string; status?: string; period_end?: number }
interface ConnectState { state: string; message: string }

export type Pane = 'billing' | 'invoices' | 'whatsapp' | 'shop' | 'keys' | 'login' | 'data';

/**
 * The tabs, each with the sentence that says what is behind it.
 *
 * THE HINT SURVIVED THE REDESIGN, in the line under the tab strip rather than under a row. It is
 * what stops «دخولي» being a noun somebody has to open to understand — and the tab labels are
 * short precisely because that line carries the meaning.
 */
const TABS: { id: Pane; label: string; hint: string }[] = [
  { id: 'billing', label: 'الاشتراك', hint: 'باقتك ووسيلة الدفع' },
  // ITS OWN TAB, BECAUSE IT IS ITS OWN ERRAND. Choosing a plan is a decision made once or twice a
  // year; fetching an invoice is bookkeeping, done on a date somebody else set — an accountant
  // asks for last month's, and looking for it under «الاشتراك» means scrolling past four plans
  // he is not buying today. Two purposes sharing one tab makes both harder to reach.
  { id: 'invoices', label: 'فواتيري', hint: 'فواتيرك وإيصالاتك، جاهزة للتنزيل' },
  { id: 'whatsapp', label: 'واتساب', hint: 'الرقم المرتبط وسقفك الحالي' },
  { id: 'shop', label: 'منشأتي', hint: 'الاسم والشعار الذي يراه عميلك' },
  // AFTER «منشأتي», BEFORE «دخولي»: both are about who may act in this shop, and a machine's key
  // sits next to a person's password rather than under billing.
  { id: 'keys', label: 'مفاتيح الربط', hint: 'برامج تكتب زيارات باسم محلك' },
  { id: 'login', label: 'دخولي', hint: 'جوالك وكلمة مرورك' },
  // ONE WORD, BECAUSE THE HINT LINE CARRIES THE REST. «بياناتي وأوراقي» was the label that
  // pushed the strip past the screen and left the last tab sliced in half.
  { id: 'data', label: 'بياناتي', hint: 'الاحتفاظ، التصدير، الاتفاقيات' },
];

export function AccountScreen(
  { session, catalog, openOn }:
  // `openOn` IS WHERE SOMEBODY ELSE SENT HIM. The locked cards across the product say «أضِفه إلى
  // اشتراكي», and a button that lands on a page and then makes him find the right tab is a button
  // that loses half the people who pressed it. Ignored when he may not read that tab.
  { session: Session; catalog: Catalog; openOn?: Pane },
) {
  const [sub, setSub] = useState<Subscription | null | undefined>(undefined);
  const [connected, setConnected] = useState<ConnectState | null>(null);

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
    if (t.id === 'billing') return Boolean(action(catalog, 'billing.plans') || action(catalog, 'billing.my_subscriptions'));
    if (t.id === 'invoices') return Boolean(action(catalog, 'billing.my_invoices'));
    if (t.id === 'whatsapp') return Boolean(action(catalog, 'whatsapp.connect_status'));
    if (t.id === 'shop') return Boolean(action(catalog, 'tenant.view_self'));
    return true;
  });

  // OPENS ON THE FIRST TAB HE ACTUALLY HAS, not on a hardcoded 'billing' that a manager cannot
  // read. `tabs` is never empty — «دخولي» and «بياناتي» are everyone's.
  const [pane, setPane] = useState<Pane>(() => openOn ?? 'billing');
  const active = tabs.some((t) => t.id === pane) ? pane : tabs[0].id;
  const isConnected = connected?.state === 'connected';

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
          <span>{isConnected ? 'واتساب مربوط' : 'واتساب غير مربوط'}</span>
          {isConnected
            ? <Badge tone="success">يعمل</Badge>
            : <Badge tone="warning">يحتاج ربط</Badge>}
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
            connected={isConnected}
            // THE ONE SEAM BETWEEN TWO TABS, and it earns itself: a plan cannot run without a
            // connected number, so the pane that says so must be able to take him there.
            onGoConnect={() => setPane('whatsapp')}
          />
        </div>
      ) : null}
      {active === 'invoices' ? <InvoicesPane session={session} catalog={catalog} /> : null}
      {active === 'whatsapp'
        ? <Connect session={session} catalog={catalog} state={connected} onChange={setConnected} />
        : null}
      {active === 'shop' ? <ShopPane session={session} catalog={catalog} /> : null}
      {active === 'keys' ? <KeysPane session={session} catalog={catalog} /> : null}
      {active === 'login' ? <LoginPane /> : null}
      {active === 'data' ? <DataPane session={session} catalog={catalog} /> : null}
    </div>
  );
}
