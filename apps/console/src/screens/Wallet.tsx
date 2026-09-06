/**
 * «محفظتي» — one wallet, several purposes, never sharing a riyal between them.
 *
 * WHY IT LOOKS NOTHING LIKE «متجر التطبيقات». Built independently and on purpose — that screen is
 * slated for a full rebuild and is not a reference here, in either code or design (owner's own
 * direction, 2026-09-06).
 *
 * FOUR FUNDS, NEVER THE WORD "صندوق". `wallet.my_balance` answers `funds`/`held` keyed by the
 * engineering name (`ai_credit`, `topup`, `renewal`, `commission`) — this screen is the one place
 * that translates each into what it actually means to the person looking at it, and shows only
 * the ones that apply to him:
 *   ai_credit  — every shop with the AI bot. The included monthly allowance.
 *   topup      — every shop with the AI bot. Manual top-up, spent only once ai_credit is empty.
 *   renewal    — ONLY a shop whose subscription is pinned to pay-by-wallet (billing.
 *                my_subscriptions' own `payment_gateway === "wallet"` — gateways with no
 *                recurring charge, e.g. TuwaiqPay).
 *   commission — ONLY an affiliate/partner account (`partner.my_shops` present in the catalogue).
 *
 * ABSENT MEANS ABSENT, same discipline as AiNotesCard: a card for a purpose that does not apply
 * to him is not rendered greyed-out, it does not exist on the page at all.
 */
import { useEffect, useState } from 'react';
import { Banknote, Bot, RefreshCw, Wallet as WalletIcon } from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { EmptyState } from '../rj-ui/EmptyState';
import { KpiCard } from '../rj-ui/KpiCard';
import { Skeleton } from '../rj-ui/Skeleton';
import { action, call, type Catalog } from '../catalog';
import { riyalsLabel } from '../money';
import type { Session } from '../session';

interface WalletBalance {
  currency: string;
  funds: Record<string, number>;
  held: Record<string, number>;
  available: Record<string, number>;
  balance: number;
  available_total: number;
}

interface SubscriptionLite { payment_gateway?: string; status?: string }

export function WalletPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [wallet, setWallet] = useState<WalletBalance | null | undefined>(undefined);
  const [walletFundEnabled, setWalletFundEnabled] = useState(false);

  const balanceAction = action(catalog, 'wallet.my_balance');
  const subsAction = action(catalog, 'billing.my_subscriptions');
  const isPartner = !!action(catalog, 'partner.my_shops');

  const load = () => {
    if (!balanceAction) { setWallet(null); return; }
    call<WalletBalance>(session, balanceAction)
      .then(setWallet)
      .catch(() => setWallet(null));
  };

  useEffect(load, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!subsAction) return;
    call<{ subscriptions: SubscriptionLite[] }>(session, subsAction)
      .then((x) => setWalletFundEnabled(
        (x.subscriptions ?? []).some((s) => (s.payment_gateway ?? '').toLowerCase() === 'wallet'
          && s.status !== 'canceled')))
      .catch(() => setWalletFundEnabled(false));
  }, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!balanceAction) return null;

  if (wallet === undefined) {
    return (
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Skeleton height={140} radius="card" />
        <Skeleton height={140} radius="card" />
        <Skeleton height={140} radius="card" />
      </div>
    );
  }

  if (wallet === null) {
    return (
      <EmptyState
        icon={<WalletIcon size={22} />}
        title="تعذّرت قراءة محفظتك"
        description="لم نستطع جلب رصيدك الآن — والخلل عندنا لا فيك. أعد المحاولة بعد قليل."
      />
    );
  }

  const funds = wallet.funds ?? {};
  const held = wallet.held ?? {};
  const at = (name: string) => Math.max(0, (funds[name] ?? 0) - (held[name] ?? 0));

  const aiCredit = at('ai_credit');
  const topup = at('topup');
  const renewal = at('renewal');
  const commission = at('commission');
  const aiTotal = aiCredit + topup;

  return (
    <div className="flex flex-col gap-5">
      {/* ── the hero: one number, the whole point of opening this tab ─────────────────────── */}
      <section className="relative overflow-hidden rounded-card bg-gradient-to-br from-accent to-accent/70 p-6 text-accent-contrast shadow-sm">
        <span aria-hidden
             className="pointer-events-none absolute -end-8 -top-8 size-40 rounded-full bg-white/10" />
        <span aria-hidden
             className="pointer-events-none absolute -bottom-10 -start-4 size-32 rounded-full bg-white/10" />
        <div className="relative flex flex-col gap-1">
          <span className="flex items-center gap-2 text-sm font-medium text-accent-contrast/85">
            <WalletIcon size={16} aria-hidden /> إجمالي رصيدك
          </span>
          <span className="text-4xl font-bold tabular-nums tracking-tight">
            {riyalsLabel(wallet.available_total ?? wallet.balance)}
          </span>
          <span className="text-sm text-accent-contrast/85">
            رصيدك مقسّم حسب الغرض — بالتفصيل تحت، كل غرض له بطاقته الخاصة.
          </span>
        </div>
      </section>

      {/* ── every purpose that applies to him, and only those ─────────────────────────────── */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {/* THE AI BOT'S OWN ALLOWANCE — every shop with the bot sees this, bundled with its
            manual top-up right beside it: one errand, one story («استخدمت المضمّن؟ هذا احتياطك»),
            not two unrelated numbers. */}
        <KpiCard
          icon={<Bot size={20} aria-hidden />}
          tone="accent"
          label="رصيد الذكاء الاصطناعي"
          value={riyalsLabel(aiTotal)}
          hint={
            <span className="flex flex-col gap-0.5">
              <span>{riyalsLabel(aiCredit)} مضمّن من باقتك — يتجدد تلقائياً كل شهر</span>
              {topup > 0 ? (
                <span>+ {riyalsLabel(topup)} شحنته يدوياً — يُستخدم فقط بعد ما ينتهي المضمّن</span>
              ) : (
                <span className="flex items-center gap-1">
                  الشحن اليدوي يبقيه شغّالاً لو انتهى المضمّن قبل نهاية الشهر
                  <Badge tone="neutral">قريباً</Badge>
                </span>
              )}
            </span>
          }
        />

        {walletFundEnabled ? (
          <KpiCard
            icon={<RefreshCw size={20} aria-hidden />}
            tone={renewal > 0 ? 'neutral' : 'warning'}
            label="رصيد تجديد الاشتراك"
            value={riyalsLabel(renewal)}
            hint={renewal > 0
              ? 'يُخصم منه تلقائياً عند كل تجديد — لا يلمس رصيد الذكاء الاصطناعي أبداً'
              : 'رصيدك لا يكفي التجديد القادم — اشحنه قبل موعده حتى لا يتوقف اشتراكك'}
          />
        ) : null}

        {isPartner ? (
          <KpiCard
            icon={<Banknote size={20} aria-hidden />}
            tone="success"
            label="عمولتك كشريك"
            value={riyalsLabel(commission)}
            hint="قابلة للسحب — من شاشة الشراكة"
          />
        ) : null}
      </div>
    </div>
  );
}
