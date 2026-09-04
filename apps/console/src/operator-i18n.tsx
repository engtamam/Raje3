/**
 * Language for the operator's day-to-day screens (Visit, Bookings, Services, …) — a SEPARATE
 * surface from `./i18n.ts` (the owner's Arabic-only sign-in/legal kit) and from
 * `@base-ui/i18n` (the shared auth-kit base catalog). CURRENT PHASE covers field-operator
 * screens only — the owner's own admin screens stay Arabic-only for now too, but that is this
 * phase's scope, not a permanent split (do not assume it stays that way).
 *
 * A HIRED OPERATOR HAS HIS OWN LOGIN (`PIN_OPERATORS_ENABLED=false` is this deployment's live
 * default — see services/operations/app/api/v1/staff.py's own header: "the shared-tablet
 * employee is switched off... every employee gets an account on his own phone"). So this is a
 * PER-ACCOUNT preference, stored on his own `Operator` row (`Operator.locale`,
 * `GET/PATCH /api/v1/staff/operators/me...`) — never `localStorage`. A device-local setting
 * would reset the moment he signs in on a different phone or the shop hands him a new tablet;
 * his account is the one thing that follows him.
 *
 * DIRECTION IS A TABLE, NOT A TERNARY. `@base-ui/i18n`'s `applyDir` hardcodes ar→rtl/else→ltr,
 * which breaks the moment a second RTL language exists. Urdu is RTL (Perso-Arabic script);
 * Hausa and Filipino are LTR (Latin script) despite Hausa historically also having an Arabic-
 * script (Ajami) tradition — the modern standard "Boko" orthography used here is Latin.
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { getMyOperator, setMyOperatorLocale } from './api';
import type { Session } from './session';

export type OperatorLocale = 'ar' | 'en' | 'ur' | 'ha' | 'fil';

export const OPERATOR_LOCALES: { value: OperatorLocale; label: string }[] = [
  { value: 'ar', label: 'العربية' },
  { value: 'en', label: 'English' },
  { value: 'ur', label: 'اردو' },
  { value: 'ha', label: 'Hausa' },
  { value: 'fil', label: 'Filipino' },
];

const RTL_LOCALES: ReadonlySet<OperatorLocale> = new Set(['ar', 'ur']);

export function isRtl(locale: OperatorLocale): boolean {
  return RTL_LOCALES.has(locale);
}

/** Same effect as `@base-ui/i18n`'s `applyDir`, generalized to a locale set instead of one
 *  hardcoded language. Flips the WHOLE document — the operator screens are not a sub-region
 *  of the page, so `dir`/`lang` belong on `<html>`, same as the base helper's own contract. */
export function applyOperatorDir(locale: OperatorLocale, el: HTMLElement = document.documentElement): void {
  el.setAttribute('dir', isRtl(locale) ? 'rtl' : 'ltr');
  el.setAttribute('lang', locale);
}

function isKnownLocale(v: unknown): v is OperatorLocale {
  return OPERATOR_LOCALES.some((l) => l.value === v);
}

/**
 * The dictionary itself. Every key answered in EVERY locale is the goal, but a screen ships one
 * at a time — a key present in `ar`/`en` and missing elsewhere is not a bug in THIS file, it
 * means that screen's translation hasn't landed yet. FALLBACK CHAIN: requested locale → Arabic
 * (the product's own original — every key is written here first) → the key itself. Never
 * English as the fallback: a Filipino operator on a screen not yet translated to Filipino
 * should see the same Arabic the shop has always shown, not English he never asked for.
 */
export type OperatorDict = Record<string, string>;
const CATALOGS: Partial<Record<OperatorLocale, OperatorDict>> = {};

/** A screen module calls this once, at import time, to register its own strings — same idea as
 *  `mergeDicts` in `@base-ui/i18n`, but additive across many small per-screen files instead of
 *  one large one, so translating "الزيارة" doesn't require touching "الحجوزات"'s own keys. */
export function registerOperatorStrings(byLocale: Partial<Record<OperatorLocale, OperatorDict>>): void {
  for (const [locale, dict] of Object.entries(byLocale) as [OperatorLocale, OperatorDict][]) {
    CATALOGS[locale] = { ...CATALOGS[locale], ...dict };
  }
}

function translate(locale: OperatorLocale, key: string): string {
  return CATALOGS[locale]?.[key] ?? CATALOGS.ar?.[key] ?? key;
}

interface Ctx {
  locale: OperatorLocale;
  /** `undefined` while the account's own preference is still loading — screens that read `t()`
   *  before this settles get the Arabic default, same as an operator whose account has never
   *  set one (`Operator.locale === ""`). */
  ready: boolean;
  setLocale: (l: OperatorLocale) => void;
  t: (key: string) => string;
}

const OperatorI18nContext = createContext<Ctx | null>(null);

export function OperatorI18nProvider({ session, children }: { session: Session; children: ReactNode }) {
  const [locale, setLocaleState] = useState<OperatorLocale>('ar');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let live = true;
    getMyOperator(session)
      .then((row) => {
        if (!live) return;
        if (row && isKnownLocale(row.locale)) setLocaleState(row.locale);
        setReady(true);
      })
      // ANY failure — including the owner's real, expected 404 (he has no Operator row) — is
      // still Arabic default, still `ready`: a signed-in owner must never sit on a loading
      // screen waiting for a preference his account structurally cannot have.
      .catch(() => { if (live) setReady(true); });
    return () => { live = false; };
  }, [session]);

  useEffect(() => { applyOperatorDir(locale); }, [locale]);

  function setLocale(l: OperatorLocale) {
    const prev = locale;
    setLocaleState(l); // optimistic — the switch must feel instant, not wait on a round trip
    setMyOperatorLocale(session, l).catch(() => setLocaleState(prev)); // account is the truth
  }

  const value: Ctx = { locale, ready, setLocale, t: (key: string) => translate(locale, key) };
  return <OperatorI18nContext.Provider value={value}>{children}</OperatorI18nContext.Provider>;
}

/** `const { t, locale, setLocale } = useOperatorI18n();` inside any operator screen. Throws
 *  outside the provider — the SAME loud-failure choice `./i18n.ts`'s own header argues for
 *  (a silent identity fallback here would ship `visit.save` as literal screen text again). */
export function useOperatorI18n(): Ctx {
  const ctx = useContext(OperatorI18nContext);
  if (!ctx) throw new Error('useOperatorI18n() outside <OperatorI18nProvider>');
  return ctx;
}

/** `tf(t, 'visit.pending', { n: 3 })` — `t()` alone answers a FIXED string; a count or a name
 *  inside a sentence needs a `{placeholder}` substituted after translation, not a template
 *  literal built before it (that would hardcode the vars' ORDER, which differs by language —
 *  "3 left of 10" in English is "10 كن 3 باقي" in Urdu). Missing values are left as-is rather
 *  than silently dropped, so a wiring mistake is visible on screen instead of erasing a word. */
export function tf(t: (key: string) => string, key: string, vars: Record<string, string | number>): string {
  return t(key).replace(/\{(\w+)\}/g, (m, name) => (name in vars ? String(vars[name]) : m));
}
