/**
 * «طلبات التوصيل عبر الواتساب» — the console's own live order board for
 * services/operations/app/core/orders.py::OrderService. A STANDALONE delivery product, never to
 * be confused with «خدمات متنقلة» (the owner's own correction, 2026-10-05: "كل تطبيق منعزل عن
 * الاخر" — this one competes with HungerStation/Jahez, a customer orders off the shop's own
 * catalogue and pays into the shop's own gateway).
 *
 * CAPABILITY = `operations.record`, SAME AS TODAY'S VISIT — api/v1/whatsapp_orders.py's own module
 * docstring: the whole screen (view/update status/share) is every role that can record a visit,
 * never manager-only. Connection settings (payment gateway, delivery radius) are deliberately NOT
 * here — the owner's own instruction: "بوابة الدفع هذه نحطها بعدين في شاشة حسابي" — they live in
 * «حسابي» only, never duplicated on this screen.
 *
 * A KANBAN BOARD, NOT A LIST — the owner's own request for "تصميم فاخر"/"مكونات ابداعية": each
 * column is one real status from `core/orders.py`'s own forward-only state machine, so the shape
 * on screen IS the shape of the engine, not a second taxonomy invented for display. `received`/
 * `payment_mismatch` share one column (orders not yet in the kitchen's hands); `delivered`/
 * `cancelled` share the closed column — four live working columns in between.
 *
 * NEW-ORDER GLOW + CHIME — a card whose id was not in the previous poll gets `.wo-card-new` (a
 * CSS keyframe glow, theme.css) for a few seconds and fires one short beep via the Web Audio API
 * (no asset file: a single oscillator is simpler than shipping and licensing a sound file for
 * one four-note cue). Polled every 8s — this product has no websocket/live-push infra yet, so a
 * short poll is the honest "live" this screen can actually offer today.
 *
 * THE PAUSE SWITCH IS A BIG RED CIRCLE IN THE HEADER, NOT A ROW IN SETTINGS — the owner's own
 * instruction: a cashier swamped right now must stop new orders in one tap, not hunt for it.
 * Backed by `core/order_pause.py::OrderPauseStore`, per-branch, already enforced live inside
 * `OrderService.create()` — this switch is the door Step 8's own backend audit found missing.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Receipt, Clock, AlertTriangle, CheckCircle2, MessageCircle, Copy, Check, Pause, Play,
  MapPin, Package, Share2,
} from 'lucide-react';
import { PageHeader } from '../rj-ui/PageHeader';
import { Card } from '../rj-ui/Card';
import { KpiCard } from '../rj-ui/KpiCard';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { Drawer } from '../rj-ui/Drawer';
import { Select } from '../rj-ui/Field';
import { Toggle } from '../rj-ui/Toggle';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import { riyals, riyalsLabel } from '../money';
import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import './whatsapp-orders-i18n';

type OrderStatus =
  | 'received' | 'payment_mismatch' | 'confirmed' | 'preparing'
  | 'out_for_delivery' | 'ready' | 'delivered' | 'cancelled';

interface OrderLine { service_id: string; name: string; quantity: number; unit_price_minor: number; line_total_minor: number }

interface Order {
  id: string;
  tenant: string;
  branch_id: string;
  phone: string;
  customer_name: string;
  lines: OrderLine[];
  total_minor: number;
  amount_due_minor: number;
  discount_minor: number;
  discount_source: string;
  points_reward_name: string;
  points_reward_minor: number;
  lat: number;
  lng: number;
  maps_url: string;
  status: OrderStatus;
  created: number;
  paid_amount_minor: number;
  payment_ref: string;
  cancel_reason: string;
  note: string;
}

// `r.phone` is signup.py's canonical "+<digits>" shape — wa.me wants the digits alone.
function whatsappLink(phone: string): string {
  return `https://wa.me/${phone.replace(/[^\d]/g, '')}`;
}

/**
 * STEP 9 — «مشاركة الطلب مع المندوب». NO STORED REP NUMBER ANYWHERE in this product (nothing in
 * `Branch`/`Order` carries one) — `wa.me/?text=…` with NO phone segment opens WhatsApp's own
 * contact picker with the message already composed, so the merchant picks whichever rep he is
 * using for THIS delivery, exactly the plan's own acceptance test: "رسالة فيها كل تفاصيل الطلب"،
 * never a "send to this fixed number" assumption this product has no data to back.
 */
function buildShareText(o: Order, t: (k: string) => string): string {
  const lines = o.lines.map((l) => `${l.quantity}× ${l.name}`).join('\n');
  return [
    t('whatsappOrders.share.heading'),
    tf(t, 'whatsappOrders.share.customer', { name: o.customer_name || t('whatsappOrders.card.unnamed') }),
    tf(t, 'whatsappOrders.share.phone', { phone: o.phone }),
    tf(t, 'whatsappOrders.share.address', { url: o.maps_url }),
    '',
    lines,
    '',
    tf(t, 'whatsappOrders.share.total', { total: riyalsLabel(o.amount_due_minor, t) }),
  ].join('\n');
}

function shareWithRepLink(o: Order, t: (k: string) => string): string {
  return `https://wa.me/?text=${encodeURIComponent(buildShareText(o, t))}`;
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button type="button" aria-label={label} title={label}
           className="rounded-md p-1 text-text-tertiary transition-colors hover:bg-surface-2 hover:text-text-primary"
           onClick={() => {
             navigator.clipboard?.writeText(text).then(() => {
               setCopied(true);
               setTimeout(() => setCopied(false), 2000);
             }).catch(() => {});
           }}>
      {copied ? <Check size={13} className="text-success" /> : <Copy size={13} />}
    </button>
  );
}

/** One short rising two-note chime, synthesised rather than shipped as an audio asset — fires
 *  only on a genuinely NEW order id, never on an ordinary poll refresh. A browser that has not
 *  yet had a user gesture may refuse `AudioContext`; failing silently is correct here; a missed
 *  chime is never worth a console error on a screen about orders, not sound. */
function chime() {
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const notes = [880, 1174.66];
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.value = freq;
      const start = ctx.currentTime + i * 0.12;
      gain.gain.setValueAtTime(0.0001, start);
      gain.gain.exponentialRampToValueAtTime(0.18, start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.22);
      osc.connect(gain).connect(ctx.destination);
      osc.start(start);
      osc.stop(start + 0.25);
    });
    setTimeout(() => ctx.close().catch(() => {}), 600);
  } catch {
    // no audio support — the glow animation alone still carries the "new order" signal
  }
}

function actionErrorMessage(e: unknown, t: (k: string) => string): string {
  return e instanceof Error && e.message ? e.message : t('whatsappOrders.action.genericError');
}

function formatDate(ts: number, locale: string): string {
  if (!ts) return '';
  return new Date(ts * 1000).toLocaleDateString(locale === 'ar' ? 'ar-SA' : locale, {
    day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
  });
}

const POLL_MS = 8000;
const GLOW_MS = 6000;

// STUCK = sitting in the same working status for a long time with no progress — a real customer
// waiting signal, not an arbitrary number. 25 minutes is long enough that a busy kitchen is not
// flagged for a normal order, short enough that a genuinely forgotten one gets a red halo before
// the customer calls asking where their food is.
const STUCK_MINUTES = 25;
const STUCK_SECONDS = STUCK_MINUTES * 60;

const WORKING_STATUSES: OrderStatus[] = ['confirmed', 'preparing', 'ready', 'out_for_delivery'];

function statusTone(s: OrderStatus): 'info' | 'warning' | 'accent' | 'success' | 'danger' | 'neutral' {
  if (s === 'received') return 'info';
  if (s === 'payment_mismatch') return 'danger';
  if (s === 'confirmed') return 'accent';
  if (s === 'preparing') return 'warning';
  if (s === 'ready') return 'accent';
  if (s === 'out_for_delivery') return 'info';
  if (s === 'delivered') return 'success';
  return 'neutral';
}

export function WhatsAppOrdersScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t, locale } = useOperatorI18n();
  const { branches } = useOutletContext<ShellContext>();

  const listAction = action(catalog, 'whatsapp_order.list');
  const pauseGetAction = action(catalog, 'whatsapp_order.pause_get');
  const pauseSetAction = action(catalog, 'whatsapp_order.pause_set');
  const preparingAction = action(catalog, 'whatsapp_order.preparing');
  const readyAction = action(catalog, 'whatsapp_order.ready');
  const outForDeliveryAction = action(catalog, 'whatsapp_order.out_for_delivery');
  const deliveredAction = action(catalog, 'whatsapp_order.delivered');
  const cancelAction = action(catalog, 'whatsapp_order.cancel');
  const resolveMismatchAction = action(catalog, 'whatsapp_order.resolve_mismatch');
  const shareToggleGetAction = action(catalog, 'whatsapp_order.share_toggle_get');
  const shareToggleSetAction = action(catalog, 'whatsapp_order.share_toggle_set');

  const [rows, setRows] = useState<Order[] | 'loading' | 'failed'>('loading');
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState('');
  const [openOrder, setOpenOrder] = useState<Order | null>(null);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const [branchId, setBranchId] = useState('');
  const [paused, setPaused] = useState(false);
  const [pauseReason, setPauseReason] = useState('');
  // STEP 9'S OWN ON/OFF SWITCH — defaults to shown (same "absent means on" the backend store
  // itself takes) until the real read lands, so the button never flashes in only to disappear.
  const [shareEnabled, setShareEnabled] = useState(true);
  const seenIds = useRef<Set<string> | null>(null);

  function reportActionError(e: unknown) {
    setActionError(actionErrorMessage(e, t));
    window.setTimeout(() => setActionError(''), 5000);
  }

  useEffect(() => {
    const id = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 30_000);
    return () => clearInterval(id);
  }, []);

  // BRANCHES, FOR THE PAUSE SWITCH ONLY — orders themselves need no branch picker (the list is
  // already branch-scoped on read by the server, same discipline every other screen's read uses).
  useEffect(() => {
    if (!branchId && branches.length > 0) setBranchId(branches[0].id);
  }, [branches, branchId]);

  const load = () => {
    if (!listAction) { setRows('failed'); return; }
    call<{ orders: Order[] }>(session, listAction)
      .then((x) => {
        const incoming = x.orders;
        if (seenIds.current) {
          const fresh = incoming.filter((o) => !seenIds.current!.has(o.id) && o.status !== 'delivered' && o.status !== 'cancelled');
          if (fresh.length > 0) {
            chime();
            setNewIds((prev) => {
              const next = new Set(prev);
              fresh.forEach((o) => next.add(o.id));
              return next;
            });
            fresh.forEach((o) => {
              window.setTimeout(() => {
                setNewIds((prev) => { const n = new Set(prev); n.delete(o.id); return n; });
              }, GLOW_MS);
            });
          }
        }
        seenIds.current = new Set(incoming.map((o) => o.id));
        setRows(incoming);
      })
      .catch(() => setRows('failed'));
  };

  useEffect(() => {
    setRows('loading');
    seenIds.current = null;
    load();
    const id = setInterval(load, POLL_MS);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, catalog]);

  useEffect(() => {
    if (!pauseGetAction || !branchId) return;
    call<{ paused: boolean; reason: string }>(session, pauseGetAction, { branch_id: branchId })
      .then((x) => { setPaused(x.paused); setPauseReason(x.reason); })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, catalog, branchId]);

  useEffect(() => {
    if (!shareToggleGetAction) return;
    call<{ enabled: boolean }>(session, shareToggleGetAction)
      .then((x) => setShareEnabled(x.enabled))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, catalog]);

  async function toggleShare() {
    if (!shareToggleSetAction) return;
    const next = !shareEnabled;
    try {
      const row = await call<{ enabled: boolean }>(session, shareToggleSetAction, { enabled: next });
      setShareEnabled(row.enabled);
    } catch (e) {
      reportActionError(e);
    }
  }

  async function togglePause() {
    if (!pauseSetAction || !branchId) return;
    const next = !paused;
    try {
      const row = await call<{ paused: boolean; reason: string }>(session, pauseSetAction, {
        branch_id: branchId, paused: next,
        reason: next ? t('whatsappOrders.pause.defaultReason') : '',
      });
      setPaused(row.paused);
      setPauseReason(row.reason);
    } catch (e) {
      reportActionError(e);
    }
  }

  const list = Array.isArray(rows) ? rows : [];

  async function transition(order: Order, act: ReturnType<typeof action>, extra?: Record<string, unknown>) {
    if (!act || busyId) return;
    setBusyId(order.id);
    setActionError('');
    try {
      await call(session, act, { order_id: order.id, ...(extra ?? {}) });
      load();
      if (openOrder?.id === order.id) setOpenOrder(null);
    } catch (e) {
      reportActionError(e);
    } finally { setBusyId(null); }
  }

  const incoming = useMemo(
    () => list.filter((o) => o.status === 'received' || o.status === 'payment_mismatch')
      .sort((a, b) => b.created - a.created),
    [list],
  );
  const confirmedCol = useMemo(() => list.filter((o) => o.status === 'confirmed').sort((a, b) => a.created - b.created), [list]);
  const preparingCol = useMemo(() => list.filter((o) => o.status === 'preparing').sort((a, b) => a.created - b.created), [list]);
  const readyCol = useMemo(() => list.filter((o) => o.status === 'ready').sort((a, b) => a.created - b.created), [list]);
  const deliveryCol = useMemo(() => list.filter((o) => o.status === 'out_for_delivery').sort((a, b) => a.created - b.created), [list]);
  const closedCol = useMemo(
    () => list.filter((o) => o.status === 'delivered' || o.status === 'cancelled').sort((a, b) => b.created - a.created).slice(0, 20),
    [list],
  );

  const waitingCount = incoming.length;
  const stuckIds = useMemo(() => new Set(
    list.filter((o) => WORKING_STATUSES.includes(o.status) && now - o.created > STUCK_SECONDS).map((o) => o.id),
  ), [list, now]);
  const deliveredToday = useMemo(() => {
    const dayStart = new Date(); dayStart.setHours(0, 0, 0, 0);
    const cutoff = dayStart.getTime() / 1000;
    return list.filter((o) => o.status === 'delivered' && o.created >= cutoff).length;
  }, [list]);

  function nextAction(o: Order): { label: string; act: ReturnType<typeof action>; extra?: Record<string, unknown> } | null {
    if (o.status === 'confirmed') return { label: t('whatsappOrders.action.startPreparing'), act: preparingAction };
    if (o.status === 'preparing') return { label: t('whatsappOrders.action.markReady'), act: readyAction };
    if (o.status === 'ready') return { label: t('whatsappOrders.action.startDelivery'), act: outForDeliveryAction };
    if (o.status === 'out_for_delivery') return { label: t('whatsappOrders.action.markDelivered'), act: deliveredAction };
    return null;
  }

  function OrderCard({ o }: { o: Order }) {
    const isNew = newIds.has(o.id);
    const isStuck = stuckIds.has(o.id);
    const next = nextAction(o);
    return (
      <Card
        data-testid="whatsapp-order-card"
        interactive
        onClick={() => setOpenOrder(o)}
        className={[
          'flex flex-col gap-2 p-3',
          isNew ? 'wo-card-new' : '',
          isStuck ? 'wo-card-stuck' : '',
        ].join(' ')}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-bold">{o.customer_name || t('whatsappOrders.card.unnamed')}</span>
          {o.status === 'payment_mismatch' ? (
            <Badge tone="danger"><AlertTriangle size={11} /> {t('whatsappOrders.status.payment_mismatch')}</Badge>
          ) : isStuck ? (
            <Badge tone="danger" className="border border-danger/40">
              <AlertTriangle size={11} /> {t('whatsappOrders.card.stuck')}
            </Badge>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-1">
          {o.lines.slice(0, 3).map((line, i) => (
            <span key={i} className="rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] font-semibold text-text-secondary">
              {line.quantity}× {line.name}
            </span>
          ))}
          {o.lines.length > 3 ? (
            <span className="rounded-md bg-surface-2 px-1.5 py-0.5 text-[11px] text-text-tertiary">+{o.lines.length - 3}</span>
          ) : null}
        </div>
        <div className="flex items-center justify-between text-xs text-text-secondary">
          <span className="flex items-center gap-1">
            <Clock size={12} /> {formatDate(o.created, locale)}
          </span>
          <span className="font-bold tabular-nums">
            {o.discount_minor > 0 || o.points_reward_minor > 0 ? (
              <>
                <s className="me-1 font-normal text-text-tertiary">{riyals(o.total_minor)}</s>
                {riyalsLabel(o.amount_due_minor, t)}
              </>
            ) : riyalsLabel(o.amount_due_minor, t)}
          </span>
        </div>
        {next ? (
          <Button size="sm" disabled={busyId === o.id}
                 onClick={(e) => { e.stopPropagation(); transition(o, next.act); }}
                 data-testid={`whatsapp-order-next-${o.id}`}>
            {next.label}
          </Button>
        ) : null}
      </Card>
    );
  }

  function Column({ title, tone, orders, testId }: {
    title: string; tone: 'info' | 'warning' | 'accent' | 'success'; orders: Order[]; testId: string;
  }) {
    return (
      <div className="flex min-w-64 flex-1 flex-col gap-2" data-testid={testId}>
        <div className="flex items-center gap-2 px-1">
          <h3 className="text-sm font-bold text-text-primary">{title}</h3>
          <Badge tone={tone}>{orders.length}</Badge>
        </div>
        <div className="flex flex-col gap-2 rounded-card bg-surface-2/40 p-2">
          {orders.length === 0 ? (
            <p className="px-2 py-6 text-center text-xs text-text-tertiary">{t('whatsappOrders.column.empty')}</p>
          ) : orders.map((o) => <OrderCard key={o.id} o={o} />)}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-4">
      <PageHeader icon={Receipt} title={t('whatsappOrders.title')}
                 action={pauseSetAction && branchId ? (
                   <button
                     type="button"
                     onClick={togglePause}
                     data-testid="whatsapp-orders-pause-toggle"
                     aria-pressed={paused}
                     title={paused ? t('whatsappOrders.pause.resumeHint') : t('whatsappOrders.pause.pauseHint')}
                     className={[
                       'flex h-14 w-14 shrink-0 items-center justify-center rounded-full border-4 font-bold',
                       'shadow-pop transition-transform active:scale-95',
                       paused
                         ? 'border-danger bg-danger text-danger-contrast animate-pulse'
                         : 'border-danger/60 bg-surface-1 text-danger hover:bg-danger-soft',
                     ].join(' ')}
                   >
                     {paused ? <Play size={22} /> : <Pause size={22} />}
                   </button>
                 ) : undefined} />
      <p className="-mt-2 text-sm text-text-secondary">{t('whatsappOrders.subtitle')}</p>

      {branches.length > 1 ? (
        <Select value={branchId} onChange={(e) => setBranchId(e.target.value)} className="!w-auto"
               aria-label={t('whatsappOrders.branchLabel')} data-testid="whatsapp-orders-branch">
          {branches.map((b) => <option key={b.id} value={b.id}>{b.name || b.id}</option>)}
        </Select>
      ) : null}

      {shareToggleSetAction ? (
        <div className="flex items-center justify-between gap-3 rounded-card border border-border-subtle bg-surface-1 px-4 py-2.5">
          <div className="flex items-center gap-2 text-sm">
            <Share2 size={15} className="text-text-secondary" />
            <span className="font-semibold text-text-secondary">{t('whatsappOrders.share.toggleLabel')}</span>
          </div>
          <Toggle checked={shareEnabled} onChange={toggleShare}
                 ariaLabel={t('whatsappOrders.share.toggleLabel')}
                 testId="whatsapp-orders-share-toggle" />
        </div>
      ) : null}

      {paused ? (
        <div className="flex flex-wrap items-center gap-3 rounded-card border border-danger/40 bg-danger-soft px-4 py-3 text-sm font-semibold text-danger">
          <AlertTriangle size={18} className="shrink-0" />
          <span>{tf(t, 'whatsappOrders.pause.bannerText', { reason: pauseReason || t('whatsappOrders.pause.defaultReason') })}</span>
        </div>
      ) : null}

      {actionError ? (
        <p role="alert" className="rounded-card border border-danger/30 bg-danger-soft px-4 py-2 text-sm font-semibold text-danger">
          {actionError}
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <KpiCard icon={<Package size={18} className={waitingCount > 0 ? 'wo-pulse' : ''} />}
                label={t('whatsappOrders.kpi.waiting')} value={waitingCount} tone="info"
                testId="whatsapp-orders-kpi-waiting" />
        <KpiCard icon={<AlertTriangle size={18} />} label={t('whatsappOrders.kpi.stuck')}
                value={stuckIds.size} tone={stuckIds.size > 0 ? 'danger' : 'neutral'}
                testId="whatsapp-orders-kpi-stuck" />
        <KpiCard icon={<CheckCircle2 size={18} />} label={t('whatsappOrders.kpi.deliveredToday')}
                value={deliveredToday} tone="success" testId="whatsapp-orders-kpi-delivered" />
      </div>

      {rows === 'loading' ? (
        <EmptyState title={t('whatsappOrders.loading')} />
      ) : rows === 'failed' ? (
        <EmptyState title={t('whatsappOrders.readFailed.title')} description={t('whatsappOrders.readFailed.desc')} />
      ) : list.length === 0 ? (
        <EmptyState icon={<Receipt size={22} />} title={t('whatsappOrders.empty.title')}
                   description={t('whatsappOrders.empty.desc')} />
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2">
          <Column title={t('whatsappOrders.col.incoming')} tone="info" orders={incoming} testId="whatsapp-orders-col-incoming" />
          <Column title={t('whatsappOrders.col.confirmed')} tone="accent" orders={confirmedCol} testId="whatsapp-orders-col-confirmed" />
          <Column title={t('whatsappOrders.col.preparing')} tone="warning" orders={preparingCol} testId="whatsapp-orders-col-preparing" />
          <Column title={t('whatsappOrders.col.ready')} tone="accent" orders={readyCol} testId="whatsapp-orders-col-ready" />
          <Column title={t('whatsappOrders.col.delivery')} tone="info" orders={deliveryCol} testId="whatsapp-orders-col-delivery" />
          <Column title={t('whatsappOrders.col.closed')} tone="success" orders={closedCol} testId="whatsapp-orders-col-closed" />
        </div>
      )}

      {openOrder ? (
        <Drawer open onClose={() => setOpenOrder(null)} title={openOrder.customer_name || t('whatsappOrders.card.unnamed')}
               subtitle={<Badge tone={statusTone(openOrder.status)}>{t(`whatsappOrders.status.${openOrder.status}`)}</Badge>}
               testId="whatsapp-order-drawer"
               footer={(
                 <div className="flex w-full flex-wrap gap-2">
                   {nextAction(openOrder) ? (
                     <Button className="flex-1" disabled={busyId === openOrder.id}
                            onClick={() => transition(openOrder, nextAction(openOrder)!.act)}
                            data-testid="whatsapp-order-drawer-next">
                       {nextAction(openOrder)!.label}
                     </Button>
                   ) : null}
                   {shareEnabled && WORKING_STATUSES.includes(openOrder.status) ? (
                     <a href={shareWithRepLink(openOrder, t)} target="_blank" rel="noreferrer"
                       className="flex-1" data-testid="whatsapp-order-drawer-share">
                       <Button variant="outline" className="w-full">
                         <Share2 size={15} /> {t('whatsappOrders.action.shareWithRep')}
                       </Button>
                     </a>
                   ) : null}
                   {openOrder.status === 'payment_mismatch' && resolveMismatchAction ? (
                     <Button className="flex-1" disabled={busyId === openOrder.id}
                            onClick={() => transition(openOrder, resolveMismatchAction)}
                            data-testid="whatsapp-order-drawer-resolve">
                       {t('whatsappOrders.action.resolveMismatch')}
                     </Button>
                   ) : null}
                   {cancelAction && (openOrder.status === 'received' || openOrder.status === 'payment_mismatch' || openOrder.status === 'confirmed') ? (
                     <Button variant="danger" disabled={busyId === openOrder.id}
                            onClick={() => {
                              // eslint-disable-next-line no-alert -- same lightweight prompt MobileRequests.tsx's own reject uses
                              const reason = window.prompt(t('whatsappOrders.cancel.reasonPrompt')) ?? '';
                              transition(openOrder, cancelAction, { reason: reason.trim() });
                            }}
                            data-testid="whatsapp-order-drawer-cancel">
                       {t('whatsappOrders.action.cancel')}
                     </Button>
                   ) : null}
                 </div>
               )}>
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 text-sm">
            <a href={whatsappLink(openOrder.phone)} target="_blank" rel="noreferrer" dir="ltr"
              className="flex items-center gap-1 font-semibold text-info-on-soft hover:underline">
              <MessageCircle size={14} /> {openOrder.phone}
            </a>
            <CopyButton text={openOrder.phone} label={t('whatsappOrders.card.copyPhone')} />
          </div>
          <a href={openOrder.maps_url} target="_blank" rel="noreferrer"
            className="flex items-center gap-1.5 text-sm font-semibold text-info-on-soft hover:underline">
            <MapPin size={14} /> {t('whatsappOrders.card.openMap')}
          </a>

          <div className="flex flex-col gap-1.5 rounded-card border border-border-subtle p-3">
            {openOrder.lines.map((line, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span>{line.quantity}× {line.name}</span>
                <span className="tabular-nums text-text-secondary">{riyalsLabel(line.line_total_minor, t)}</span>
              </div>
            ))}
            <div className="mt-1 flex items-center justify-between border-t border-border-subtle pt-1.5 text-sm">
              <span className="text-text-secondary">{t('whatsappOrders.drawer.subtotal')}</span>
              <span className="tabular-nums">{riyalsLabel(openOrder.total_minor, t)}</span>
            </div>
            {openOrder.discount_minor > 0 ? (
              <div className="flex items-center justify-between text-sm text-success">
                <span>{t('whatsappOrders.drawer.discount')}</span>
                <span className="tabular-nums">-{riyalsLabel(openOrder.discount_minor, t)}</span>
              </div>
            ) : null}
            {openOrder.points_reward_minor > 0 ? (
              <div className="flex items-center justify-between text-sm text-success">
                <span>{openOrder.points_reward_name || t('whatsappOrders.drawer.pointsReward')}</span>
                <span className="tabular-nums">-{riyalsLabel(openOrder.points_reward_minor, t)}</span>
              </div>
            ) : null}
            <div className="flex items-center justify-between text-base font-bold">
              <span>{t('whatsappOrders.drawer.total')}</span>
              <span className="tabular-nums">{riyalsLabel(openOrder.amount_due_minor, t)}</span>
            </div>
          </div>

          {openOrder.status === 'payment_mismatch' ? (
            <p className="rounded-card border border-danger/30 bg-danger-soft px-3 py-2 text-xs font-semibold text-danger">
              {tf(t, 'whatsappOrders.drawer.mismatchHint', { paid: riyalsLabel(openOrder.paid_amount_minor, t) })}
            </p>
          ) : null}
          {openOrder.cancel_reason ? (
            <p className="text-xs text-text-tertiary">{tf(t, 'whatsappOrders.drawer.cancelReason', { reason: openOrder.cancel_reason })}</p>
          ) : null}
          {openOrder.note ? (
            <p className="text-xs text-text-tertiary">{tf(t, 'whatsappOrders.drawer.note', { note: openOrder.note })}</p>
          ) : null}
        </div>
        </Drawer>
      ) : null}
    </div>
  );
}
