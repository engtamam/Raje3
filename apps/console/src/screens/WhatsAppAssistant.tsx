/**
 * «المساعد الذكي عبر واتساب» — its own dedicated workspace (2026-09-16), not a tab buried three
 * clicks deep inside «حسابي». The owner's own instruction: ربط واتساب itself stays in «حسابي»
 * (it is a GENERAL establishment fact, not specific to this one bot) — everything that configures
 * the ASSISTANT's own behaviour, plus real proof it is earning its price, lives here instead.
 *
 * REAL NUMBERS, NOT A SETTINGS PAGE PRETENDING TO BE A DASHBOARD. `whatsapp_assistant.my_impact`
 * (the same read `Shop.tsx`'s own `AIImpactCard` already uses — imported, never re-derived) is
 * REAL bookings the bot closed, a REAL average invoice, a REAL upsell-acceptance rate. A shop
 * paying for a "VIP" app deserves the receipt, not a gauge with no needle.
 *
 * EVERY CONTROL BELOW IS THE SAME REAL LOGIC `AccountPanes.tsx` ALREADY HAD — `AiToggleCard`,
 * `AiNotesCard`, `MsgWordLimitCard`, `WhatsAppVisitRegistrationCard`, `WhatsAppAutoRegisterCard`
 * are reused as-is (real actions, real state, real confirm dialogs); only the SHELL around them —
 * the hero, the section framing, the analytics — is new.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight, Bot, Brain, Crown, MessageCircle, ShieldCheck, Sparkles, TrendingUp, Zap,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { AppGate } from './Locked';
import {
  AiNotesCard, AiToggleCard, MsgWordLimitCard, WhatsAppAutoRegisterCard,
  WhatsAppVisitRegistrationCard,
} from './AccountPanes';
import type { ShopImpact } from './Shop';
import { unitsLabel, type WalletBalance } from './Wallet';
import { riyalsLabel } from '../money';
import type { Owned } from '../apps';
import type { Loading } from '../loading';
import { useOperatorI18n, tf } from '../operator-i18n';
import './whatsapp-assistant-i18n';

/** ONE STAT TILE, ONE VISUAL LANGUAGE — the whole analytics row is built from this so five
 *  different numbers never read as five different widgets thrown together. */
function StatTile({ icon: Icon, label, value, sub }: {
  icon: LucideIcon; label: string; value: string; sub?: string;
}) {
  return (
    <div className="flex flex-col gap-2 rounded-2xl border border-[#d4af37]/25 bg-gradient-to-b from-surface-1 to-surface-2/40 p-4">
      <span aria-hidden className="grid h-9 w-9 place-items-center rounded-full bg-[#d4af37]/15 text-[#a9822a] dark:text-[#f4e2a4]">
        <Icon size={17} />
      </span>
      <span className="text-2xl font-extrabold tabular-nums leading-none">{value}</span>
      <span className="text-xs font-semibold text-text-secondary">{label}</span>
      {sub ? <span className="text-[.7rem] text-text-muted">{sub}</span> : null}
    </div>
  );
}

/** A SECTION SHELL, NEW AND SHARED — an icon medallion + title/desc header over a soft-bordered
 *  panel, so «الحالة العامة»/«ذكاء المساعد»/«الأتمتة» read as three rooms of the SAME workspace
 *  rather than three unrelated cards stacked in a list (the plain `rj-ui/Card` stack this screen
 *  replaces). The cards INSIDE stay whatever they already were — this only frames them. */
function SectionShell({ icon: Icon, title, desc, children }: {
  icon: LucideIcon; title: string; desc: string; children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-3.5 rounded-[26px] border border-border-subtle bg-surface-1 p-5 shadow-sm">
      <div className="flex items-start gap-3">
        <span aria-hidden className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-accent-soft text-accent-on-soft">
          <Icon size={19} />
        </span>
        <div className="flex flex-col gap-0.5 pt-0.5">
          <h2 className="text-[.95rem] font-extrabold">{title}</h2>
          <p className="text-xs leading-relaxed text-text-secondary">{desc}</p>
        </div>
      </div>
      <div className="flex flex-col gap-4">{children}</div>
    </section>
  );
}

export function WhatsAppAssistant({ session, catalog, owned }: {
  session: Session; catalog: Catalog; owned: Loading<Owned>;
}) {
  const { t } = useOperatorI18n();
  const navigate = useNavigate();
  const [impact, setImpact] = useState<ShopImpact | null | undefined>(undefined);
  const [wallet, setWallet] = useState<WalletBalance | null | undefined>(undefined);
  const [unitsPerHalala, setUnitsPerHalala] = useState<number | null>(null);
  // THE PLATFORM-WIDE SWITCH (2026-09-19) — see AiUnitsGauge.tsx's own note; same fetch below,
  // same "only ever hides, never invents visibility" rule.
  const [aiEnabled, setAiEnabled] = useState(true);

  useEffect(() => {
    const a = action(catalog, 'whatsapp_assistant.my_impact');
    if (!a) { setImpact(null); return; }
    call<ShopImpact>(session, a).then(setImpact).catch(() => setImpact(null));
  }, [session, catalog]);

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

  const aiCreditRemaining = wallet && aiEnabled
    ? Math.max(0, (wallet.funds?.ai_credit ?? 0) - (wallet.held?.ai_credit ?? 0))
    : null;

  return (
    <div className="flex flex-col gap-6 pb-8">
      {/* ── THE HERO — the same "royal" gold identity the old store gave this one app (owner's
          own precedent: "بوت خدمة العملاء الذكي" was already the one gold/VIP card on the shelf),
          reinterpreted as a full workspace header instead of a shelf card. */}
      <div className="relative overflow-hidden rounded-[28px] border border-[#d4af37]/40 bg-gradient-to-br from-[#120d05] via-[#241a09] to-[#3d2c0e] p-7 text-white shadow-[0_10px_40px_-12px_rgba(212,175,55,0.45)]">
        <span aria-hidden className="pointer-events-none absolute -end-10 -top-10 size-52 rounded-full bg-[#d4af37]/10 blur-2xl" />
        <span aria-hidden className="pointer-events-none absolute -bottom-14 -start-6 size-40 rounded-full bg-[#d4af37]/10 blur-2xl" />
        <button
          type="button"
          onClick={() => navigate('/')}
          className="relative z-[1] mb-5 flex w-fit items-center gap-1.5 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-semibold text-white/80 transition hover:bg-white/10"
        >
          <ArrowRight size={13} className="rtl:rotate-180" /> {t('whatsappAssistant.backToStore')}
        </button>
        <div className="relative z-[1] flex items-start gap-4">
          <span aria-hidden className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-[#d4af37]/20 ring-1 ring-[#f0d98c]/50">
            <MessageCircle size={26} className="text-[#f4e2a4]" />
          </span>
          <div className="flex flex-col gap-1.5">
            <span className="flex w-fit items-center gap-1 rounded-full bg-[#d4af37]/20 px-2.5 py-0.5 text-[11px] font-bold text-[#f4e2a4]">
              <Crown size={11} /> {t('whatsappAssistant.eyebrow')}
            </span>
            <h1 className="text-2xl font-extrabold">{t('whatsappAssistant.title')}</h1>
            <p className="max-w-md text-sm leading-relaxed text-white/75">{t('whatsappAssistant.subtitle')}</p>
          </div>
        </div>
      </div>

      <AppGate appId="whatsapp" owned={owned} session={session} catalog={catalog}>
        {/* ── THE RECEIPT — real numbers, never invented. Absent tiles simply do not render
            (`impact`/`wallet` null means the session cannot read that capability), same
            absence-means-absence posture every other read in this product already keeps. */}
        {impact ? (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatTile icon={MessageCircle} value={String(impact.conversations)}
                     label={t('shop.tile.conversations')} />
            <StatTile icon={TrendingUp} value={String(impact.ai_bookings)}
                     label={t('whatsappAssistant.stat.aiBookings')} />
            <StatTile icon={Sparkles} value={impact.avg_invoice_value_minor != null ? riyalsLabel(impact.avg_invoice_value_minor, t) : '—'}
                     label={t('shop.tile.avgInvoice')} />
            <StatTile icon={ShieldCheck}
                     value={impact.upsell_acceptance_rate != null ? `${Math.round(impact.upsell_acceptance_rate * 100)}%` : '—'}
                     label={t('shop.tile.upsellAcceptance')} />
          </div>
        ) : null}

        {aiCreditRemaining != null ? (
          <div className="flex items-center gap-3 rounded-2xl bg-gradient-to-l from-[#4c1d95] via-[#6d28d9] to-[#7c3aed] p-4 shadow-[0_4px_20px_-4px_rgba(109,40,217,0.45)]">
            <span aria-hidden className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-white/15 text-white">
              <Zap size={19} />
            </span>
            <div className="flex min-w-0 flex-col">
              <span className="text-base font-extrabold text-white">{unitsLabel(aiCreditRemaining, unitsPerHalala, t)}</span>
              <span className="text-xs font-medium text-white/80">{t('whatsappAssistant.stat.aiRemaining')}</span>
            </div>
          </div>
        ) : null}

        <SectionShell icon={Bot} title={t('whatsappAssistant.section.status.title')} desc={t('whatsappAssistant.section.status.desc')}>
          <AiToggleCard session={session} catalog={catalog} />
        </SectionShell>

        <SectionShell icon={Brain} title={t('whatsappAssistant.section.brain.title')} desc={t('whatsappAssistant.section.brain.desc')}>
          <div className="grid gap-4 lg:grid-cols-2">
            <AiNotesCard session={session} catalog={catalog} />
            <MsgWordLimitCard session={session} catalog={catalog} />
          </div>
        </SectionShell>

        <SectionShell icon={Sparkles} title={t('whatsappAssistant.section.automations.title')} desc={t('whatsappAssistant.section.automations.desc')}>
          <div className="grid gap-4 lg:grid-cols-2">
            {/* ITS OWN, SECOND ownership check inside (feature.visit/feature.contacts) — this shop
                already proved it owns واتساب (the AppGate above), but each of these needs its own
                app too. Silently absent rather than a locked card stacked inside this section —
                see each card's own header note. */}
            <WhatsAppVisitRegistrationCard session={session} catalog={catalog} owned={owned} />
            <WhatsAppAutoRegisterCard session={session} catalog={catalog} />
          </div>
        </SectionShell>
      </AppGate>
    </div>
  );
}
