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
import { Banknote, Bot, Minus, Plus, RefreshCw, Wallet as WalletIcon } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import { KpiCard } from '../rj-ui/KpiCard';
import { Skeleton } from '../rj-ui/Skeleton';
import { ApiError, sentenceFor } from '../api';
import { action, call, type Catalog } from '../catalog';
import { riyalsLabel } from '../money';
import type { Session } from '../session';

/** «وحدات الذكاء» — halalas × units_per_halala, the SAME fixed display scale
 *  services/whatsapp-assistant/app/core/ai_unit_pricing.py's own docstring defines: 1 halala is
 *  always worth this many units, whatever model is actually running. `null` unitsPerHalala (the
 *  read failed, or the shop has no AI-pricing capability) falls back to riyals rather than
 *  guessing a rate — the same ABSENT-MEANS-ABSENT posture the rest of this file already keeps. */
function unitsLabel(minorHalalas: number, unitsPerHalala: number | null): string {
  if (unitsPerHalala === null) return riyalsLabel(minorHalalas);
  const units = Math.round(minorHalalas * unitsPerHalala);
  return `${units.toLocaleString('en-US')} وحدة`;
}

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
  const topupCheckoutAction = action(catalog, 'billing.wallet_topup_checkout');
  const pricingCurrentAction = action(catalog, 'whatsapp_assistant.pricing_current');
  const isPartner = !!action(catalog, 'partner.my_shops');
  const [topupOpen, setTopupOpen] = useState(false);
  // null = not read yet (or the shop cannot read it) — unitsLabel falls back to riyals then, never
  // guesses a rate. See ai_unit_pricing.py's own docstring on why this is a FIXED, shared scale.
  const [unitsPerHalala, setUnitsPerHalala] = useState<number | null>(null);

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

  useEffect(() => {
    if (!pricingCurrentAction) return;
    call<{ ai_unit_units_per_halala: number }>(session, pricingCurrentAction)
      .then((x) => setUnitsPerHalala(x.ai_unit_units_per_halala))
      .catch(() => setUnitsPerHalala(null));
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
          tone="info"
          label="وحدات الذكاء"
          value={unitsLabel(aiTotal, unitsPerHalala)}
          hint={
            <span className="flex flex-col gap-0.5">
              <span>{unitsLabel(aiCredit, unitsPerHalala)} مضمّن من باقتك — يتجدد تلقائياً كل شهر</span>
              {topup > 0 ? (
                <span>+ {unitsLabel(topup, unitsPerHalala)} شحنته يدوياً — يُستخدم فقط بعد ما ينتهي المضمّن</span>
              ) : (
                <span>الشحن اليدوي يبقيه شغّالاً لو انتهى المضمّن قبل نهاية الشهر</span>
              )}
              {topupCheckoutAction ? (
                <Button type="button" size="sm" variant="outline" className="mt-1 self-start"
                       onClick={() => setTopupOpen(true)}>
                  شحن رصيدي يدوياً
                </Button>
              ) : null}
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
              ? 'يُخصم منه تلقائياً عند كل تجديد — لا يلمس وحدات الذكاء أبداً'
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

      {topupCheckoutAction ? (
        <TopUpDialog session={session} action={topupCheckoutAction} open={topupOpen}
                    unitsPerHalala={unitsPerHalala}
                    onClose={() => setTopupOpen(false)} onCharged={load} />
      ) : null}
    </div>
  );
}

// المبلغ دايماً مضاعف لهذا الرقم — بلا كسور غريبة (7 ريال)، وحتى تطلع أرقام الوحدات مستديرة هي
// كمان. أزرار +/- بدل مبلغ حر أو باقات ثابتة.
const TOPUP_STEP_SAR = 10;
const TOPUP_MIN_SAR = 10;
const TOPUP_MAX_SAR = 5000;

/**
 * ONE FUND: the manual top-up always credits `topup` (the fund's own default on the backend, per
 * `WALLET_TOPUP_FUND` — this dialog does not pass `fund` at all, so a future second top-uppable
 * fund needs its own explicit decision here rather than silently reusing this button).
 *
 * TUWAIQPAY HAS NO CARD-ON-FILE, so this always uses the HOSTED-CHECKOUT route
 * (`billing.wallet_topup_checkout`) and redirects the browser to the gateway's own page — never
 * the token route (`billing.wallet_topup`), which TuwaiqPay cannot serve at all.
 */
function TopUpDialog({ session, action: checkoutAction, open, unitsPerHalala, onClose, onCharged }: {
  session: Session; action: import('../catalog').Action; open: boolean;
  unitsPerHalala: number | null; onClose: () => void; onCharged: () => void;
}) {
  const [amountSar, setAmountSar] = useState(TOPUP_STEP_SAR * 5);   // 50 ريال — بداية معقولة
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { if (open) { setAmountSar(TOPUP_STEP_SAR * 5); setError(''); } }, [open]);

  const amountMinor = amountSar * 100;
  const ready = amountSar >= TOPUP_MIN_SAR && amountSar <= TOPUP_MAX_SAR;

  // مضاعفات 10 دائماً — أي رقم يُكتب أو يُصل إليه يُقرَّب لأقرب مضاعف بدل ما يُرفض ويُترك المحل
  // يصحح بنفسه.
  function setClamped(next: number) {
    const rounded = Math.round(next / TOPUP_STEP_SAR) * TOPUP_STEP_SAR;
    setAmountSar(Math.max(TOPUP_MIN_SAR, Math.min(TOPUP_MAX_SAR, rounded)));
  }

  async function submit() {
    if (!ready) { setError('أدخل مبلغاً صحيحاً أولاً.'); return; }
    setBusy(true);
    setError('');
    try {
      const result = await call<{ checkout: { ok: boolean; redirect_url: string; error?: string } }>(
        session, checkoutAction, { amount_minor: amountMinor, return_url: window.location.href },
      );
      if (result.checkout?.ok && result.checkout.redirect_url) {
        // A real redirect to the gateway's own hosted page — not a fetch we can retry from here.
        // `onCharged()` is not called: nothing was credited yet, only a pending payment opened.
        window.location.href = result.checkout.redirect_url;
        return;
      }
      setError('تعذّر فتح صفحة الدفع — حاول مرة أخرى بعد قليل.');
    } catch (err) {
      setError(topupErrorSentence(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ConfirmDialog open={open} onClose={onClose} onConfirm={submit} busy={busy} danger={false}
                  confirmLabel="الدفع الآن" title="شحن رصيدك"
                  body="سيحوّلك هذا لصفحة الدفع الآمنة. المبلغ يُضاف لرصيدك فور إتمام الدفع، ولا يُسترجع بعد الشحن.">
      <div className="flex flex-col gap-1.5">
        <span className="text-label font-medium text-text-secondary">المبلغ (مضاعفات {TOPUP_STEP_SAR} ريال)</span>
        <div className="flex items-center gap-2" role="group" aria-label="المبلغ">
          <Button type="button" variant="outline" size="sm" aria-label={`إنقاص ${TOPUP_STEP_SAR} ريال`}
                 disabled={busy || amountSar <= TOPUP_MIN_SAR}
                 onClick={() => setClamped(amountSar - TOPUP_STEP_SAR)}>
            <Minus size={14} />
          </Button>
          <span className="min-w-[5rem] text-center text-lg font-semibold tabular-nums" dir="ltr">
            {amountSar} ريال
          </span>
          <Button type="button" variant="outline" size="sm" aria-label={`زيادة ${TOPUP_STEP_SAR} ريال`}
                 disabled={busy || amountSar >= TOPUP_MAX_SAR}
                 onClick={() => setClamped(amountSar + TOPUP_STEP_SAR)}>
            <Plus size={14} />
          </Button>
        </div>
        <p className="text-label text-text-secondary">
          = {unitsLabel(amountMinor, unitsPerHalala)}
        </p>
      </div>
      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
    </ConfirmDialog>
  );
}

/** The backend's own words are English codes written for a client, not a person — «AMOUNT_EXCEEDS_
 *  MAX» is meaningless to a shop owner staring at a failed payment. Map the ones this screen can
 *  actually trigger; anything else falls to sentenceFor's own generic handling. */
function topupErrorSentence(err: unknown): string {
  if (err instanceof ApiError) {
    const detail = String((err.body as { detail?: string } | null)?.detail ?? '');
    if (detail === 'AMOUNT_EXCEEDS_MAX') return 'هذا المبلغ أكبر من الحد المسموح للشحن اليدوي.';
    if (detail === 'AMOUNT_MUST_BE_POSITIVE' || detail === 'FUND_REQUIRED') return 'مبلغ غير صالح — جرّب رقماً آخر.';
    if (detail === 'CHECKOUT_UNSUPPORTED' || detail === 'CHECKOUT_FAILED') {
      return 'تعذّر فتح صفحة الدفع الآن. حاول بعد قليل.';
    }
    if (err.status === 503) return 'بوابة الدفع لا تستجيب الآن. حاول بعد قليل.';
  }
  return sentenceFor(err, 'تعذّر بدء عملية الشحن.');
}
