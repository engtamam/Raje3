/**
 * «حسابي» — the page every product neglects, because it becomes where everything with no home
 * is dumped.
 *
 * THE RULE THAT KEEPS IT WHOLE: only what concerns the RELATIONSHIP between us and him — his
 * subscription, his channel, his identity, his data. A service price belongs to «خدماتي», a
 * template to «رسائلي». Anything proposed here because it "found no place" is refused by that
 * sentence, and this comment exists so the refusal has something to point at.
 *
 * INDEX AND DETAIL, ONE BREAKPOINT. On a phone the detail replaces the index and a back button
 * returns; on a wide screen the two sit side by side and there is no navigation at all. Same
 * components, same routes — the layout differs, not the product.
 *
 * AND THE STATUS IS READ WITHOUT A TAP. Three lines answer the only question this page exists for:
 * is the relationship healthy. Everything else is one tap away, which is what stops the page
 * scrolling — the fix for scroll is structure, not smaller text.
 */
import { useEffect, useState } from 'react';
import { CreditCard, Database, MessageCircle, Store, UserCog } from 'lucide-react';
import { Badge } from '@base-ui/design-system/Badge';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { Connect } from './Connect';

interface Subscription { id: string; plan_name?: string; status?: string; period_end?: number }
interface ConnectState { state: string; message: string }

type Pane = 'billing' | 'whatsapp' | 'shop' | 'login' | 'data';

const ROWS: { id: Pane; label: string; hint: string; icon: typeof Store }[] = [
  { id: 'billing', label: 'الاشتراك والفواتير', hint: 'باقتك، فواتيرك، وسيلة الدفع', icon: CreditCard },
  { id: 'whatsapp', label: 'واتساب', hint: 'الرقم المرتبط وسقفك الحالي', icon: MessageCircle },
  { id: 'shop', label: 'منشأتي', hint: 'الاسم والشعار الذي يراه عميلك', icon: Store },
  { id: 'login', label: 'دخولي', hint: 'جوالك وكلمة مرورك', icon: UserCog },
  { id: 'data', label: 'بياناتي وأوراقي', hint: 'الاحتفاظ، التصدير، الاتفاقيات', icon: Database },
];

export function AccountScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [pane, setPane] = useState<Pane | null>(null);
  const [sub, setSub] = useState<Subscription | null | undefined>(undefined);
  const [connected, setConnected] = useState<ConnectState | null>(null);

  useEffect(() => {
    const a = action(catalog, 'billing.my_subscriptions');
    if (a) {
      call<{ subscriptions: Subscription[] }>(session, a)
        .then((x) => setSub(x.subscriptions?.[0] ?? null))
        .catch(() => setSub(null));
    } else {
      // The manager reaches this page without billing. Not an error and not a blank: the row
      // below simply is not offered to him, and the status line does not claim a plan it cannot
      // read.
      setSub(null);
    }

    const w = action(catalog, 'whatsapp.connect_status');
    if (w) call<ConnectState>(session, w).then(setConnected).catch(() => setConnected(null));
  }, [session, catalog]);

  const rows = ROWS.filter((r) => {
    if (r.id === 'billing') return Boolean(action(catalog, 'billing.my_subscriptions'));
    if (r.id === 'whatsapp') return Boolean(action(catalog, 'whatsapp.connect_status'));
    return true;
  });

  const index = (
    <div className="flex flex-col gap-3">
      {/* ── the three lines that answer the page's question without a tap ── */}
      <div className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
        {sub === undefined ? (
          <Skeleton height={20} />
        ) : (
          <div className="flex items-center justify-between">
            <span>{sub ? `باقتك «${sub.plan_name ?? '—'}»` : 'لا يوجد اشتراك فعّال'}</span>
            {sub?.status ? <Badge tone={sub.status === 'active' ? 'success' : 'warning'}>{sub.status}</Badge> : null}
          </div>
        )}
        <div className="flex items-center justify-between">
          <span dir="ltr" className="tabular-nums">
            {connected?.state === 'connected' ? 'واتساب مربوط' : 'واتساب غير مربوط'}
          </span>
          {connected?.state === 'connected'
            ? <Badge tone="success">يعمل</Badge>
            : <Badge tone="warning">يحتاج ربط</Badge>}
        </div>
      </div>

      <ul className="flex flex-col gap-2">
        {rows.map((r) => (
          <li key={r.id}>
            <button
              type="button"
              onClick={() => setPane(r.id)}
              className={[
                'flex w-full items-center gap-3 rounded-card px-4 py-3 text-start shadow-sm',
                pane === r.id ? 'bg-accent-soft text-accent-on-soft' : 'bg-surface-1',
              ].join(' ')}
            >
              <r.icon size={18} />
              <span className="flex flex-col">
                <span>{r.label}</span>
                <span className="text-sm text-text-secondary">{r.hint}</span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );

  const detail = pane === 'whatsapp'
    ? <Connect session={session} catalog={catalog} state={connected} onChange={setConnected} />
    : pane
      ? <PaneStub label={ROWS.find((r) => r.id === pane)!.label} />
      : null;

  return (
    <div className="p-4">
      {/* ONE COLUMN ON A PHONE, TWO SIDE BY SIDE ON A WIDE SCREEN — and on the wide one there is
          no navigation and no scroll, which is the whole reason the page is structured this way
          rather than made smaller. */}
      <div className="grid gap-4 lg:grid-cols-[20rem_1fr]">
        <div className={pane ? 'hidden lg:block' : ''}>{index}</div>
        {detail ? (
          <div>
            <button
              type="button"
              onClick={() => setPane(null)}
              className="mb-3 text-sm text-text-secondary lg:hidden"
            >
              ← رجوع
            </button>
            {detail}
          </div>
        ) : null}
      </div>
    </div>
  );
}

/**
 * A pane whose screen is a later task.
 *
 * NAMED RATHER THAN LEFT OUT, and the difference matters: a row that opens nothing reads as a
 * broken product, while a row that says what is coming reads as one being built. It carries no
 * controls, so there is nothing here to become dead code — when the pane lands, this call site is
 * replaced rather than extended.
 */
function PaneStub({ label }: { label: string }) {
  return (
    <div className="rounded-card bg-surface-1 p-6 text-text-secondary shadow-sm">
      {label} — قيد الإعداد.
    </div>
  );
}
