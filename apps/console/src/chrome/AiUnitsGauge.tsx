/**
 * «مقياس وحدات الذكاء الاصطناعي» — a real-time donut in the top bar, the owner's own instruction
 * (2026-09-16): "الشريط العلوي نقدر نستغله ونسوي رسم بياني... يعرض عدد الوحدات اللي عنده حالياً
 * سواء المضمّنة أو اللي اشتراها من خلال شحن المحفظة".
 *
 * TWO DIFFERENT NUMBERS, ON PURPOSE — never confused with each other again after the owner caught
 * exactly this on the app tile (`AppPriceStrip`/`AiUnitsChip` in `AppDetailsModal.tsx`): the CARD
 * shows the plan's own INCLUDED allowance (a fixed fact about the price, from `Plan.prices[].
 * included_credit_minor`) — this gauge shows the LIVE remaining BALANCE (`wallet.my_balance`),
 * split by source (included vs a manual top-up), and it depletes as the month is used.
 *
 * SHOWN WHENEVER HE HOLDS THE APP, EVEN AT A REAL ZERO — found live (owner's own report): gating
 * on `remaining > 0` alone hid the gauge the moment a subscribed shop's balance actually hit zero,
 * which is exactly the moment a zero balance is most worth seeing. Gated on owning
 * `feature.whatsapp` (`owns(owned, 'feature.whatsapp')`) OR still holding a leftover manual
 * top-up balance — a shop that cancelled the bot but still has unspent top-up money keeps seeing
 * it until that runs out too.
 *
 * BLACK-AND-GOLD, FREE-STANDING NEXT TO SUPPORT (2026-09-19, owner's own instruction) — two fixes
 * in one: (1) it used to sit inside the same muted neutral pill as language/notifications/account,
 * reading as one more dull utility icon rather than the "how much AI is left" moment it actually
 * is — moved out to its own chip in `TopBar.tsx`, beside the support button, the same free-standing
 * treatment that button already earned. (2) the empty ring used to be `text-border-subtle` at 0.4
 * opacity — on a light surface that is nearly the same colour as the page itself, so a real zero
 * balance (the moment this gauge matters most) looked like nothing was there at all. Now a solid
 * black chip with the ring always drawn in gold (`#d4af37`, visible at every fill level, empty
 * included) and the bolt in the same gold — never blends into the background, whatever the balance.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap } from 'lucide-react';
import { action, call, type Catalog } from '../catalog';
import { unitsLabel, type WalletBalance } from '../screens/Wallet';
import { owns, type Owned } from '../apps';
import type { Loading } from '../loading';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import './top-bar-i18n';

const R = 15;
const STROKE = 4;
const CIRCUMFERENCE = 2 * Math.PI * R;

export function AiUnitsGauge({ session, catalog, owned }: { session: Session; catalog: Catalog; owned: Loading<Owned> }) {
  const { t } = useOperatorI18n();
  const navigate = useNavigate();
  const [wallet, setWallet] = useState<WalletBalance | null | undefined>(undefined);
  const [unitsPerHalala, setUnitsPerHalala] = useState<number | null>(null);
  // THE PLATFORM-WIDE SWITCH (2026-09-19) — `true` until the same read that already fetches
  // `unitsPerHalala` answers, so this never flickers the gauge on then off; a shop that cannot
  // read this action at all (no `whatsapp_assistant.pricing_read`) never gets asked, same as the
  // rate fetch below, and the gauge falls back to showing per the real balance/ownership rules
  // beneath — the switch only ever HIDES, never invents visibility.
  const [aiEnabled, setAiEnabled] = useState(true);

  useEffect(() => {
    const a = action(catalog, 'wallet.my_balance');
    if (!a) { setWallet(null); return; }
    call<WalletBalance>(session, a).then(setWallet).catch(() => setWallet(null));
  }, [session, catalog]);

  useEffect(() => {
    const a = action(catalog, 'whatsapp_assistant.pricing_current');
    if (!a) return;
    call<{ ai_unit_units_per_halala: number; ai_enabled?: boolean }>(session, a)
      .then((x) => { setUnitsPerHalala(x.ai_unit_units_per_halala); setAiEnabled(x.ai_enabled !== false); })
      .catch(() => {});
  }, [session, catalog]);

  if (!wallet || !aiEnabled) return null;

  const at = (name: string) => Math.max(0, (wallet.funds?.[name] ?? 0) - (wallet.held?.[name] ?? 0));
  const included = at('ai_credit');
  const topup = at('topup');
  const total = included + topup;
  // SUBSCRIBED, OR STILL HOLDING LEFTOVER TOP-UP MONEY — either keeps the gauge on screen even at
  // a real zero balance. Neither: a shop that never had the bot and never topped up sees nothing.
  const subscribed = owns(owned, 'feature.whatsapp') === true;
  if (!subscribed && total <= 0) return null;

  const includedFrac = total > 0 ? included / total : 0;
  const includedLen = includedFrac * CIRCUMFERENCE;
  const topupLen = CIRCUMFERENCE - includedLen;

  return (
    <button
      type="button"
      onClick={() => navigate('/whatsapp-assistant')}
      title={tf(t, 'topBar.aiUnits.breakdown', {
        included: unitsLabel(included, unitsPerHalala, t),
        topup: unitsLabel(topup, unitsPerHalala, t),
      })}
      aria-label={t('topBar.aiUnits.label')}
      className="grid size-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-zinc-800 to-black shadow-[0_2px_10px_-2px_rgba(212,175,55,0.55)] transition hover:brightness-110 focus-ring"
    >
      <span className="relative grid size-7 place-items-center">
        <svg viewBox="0 0 36 36" className="absolute inset-0 size-7 -rotate-90">
          {/* THE EMPTY-RING BASE, ALWAYS GOLD — never the page's own muted border colour, so a
              real zero balance still reads as "a gauge, showing nothing left" rather than "no
              gauge here at all". */}
          <circle cx="18" cy="18" r={R} fill="none" stroke="#d4af37" strokeWidth={STROKE} opacity={0.35} />
          {included > 0 ? (
            <circle
              cx="18" cy="18" r={R} fill="none" stroke="#a78bfa" strokeWidth={STROKE} strokeLinecap="round"
              strokeDasharray={`${includedLen} ${CIRCUMFERENCE - includedLen}`}
            />
          ) : null}
          {topup > 0 ? (
            <circle
              cx="18" cy="18" r={R} fill="none" stroke="#d4af37" strokeWidth={STROKE} strokeLinecap="round"
              strokeDasharray={`${topupLen} ${CIRCUMFERENCE - topupLen}`}
              strokeDashoffset={-includedLen}
            />
          ) : null}
        </svg>
        <Zap size={12} className="relative text-amber-400" />
      </span>
    </button>
  );
}
