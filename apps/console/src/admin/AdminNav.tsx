/**
 * لوحة الإدارة's own nav — كان القيد الأصلي "5 إلى 6 أقسام فقط بالشريط الجانبي"؛ رُفع عمداً
 * لستة تشغيلية (+ حسابي = سبعة إجمالاً) بإضافة "تذاكر" كصفحة مستقلة — قرار المستخدم صراحة
 * (فصلها عن "العملاء والدعم" أوضح من دمجها بمودال عميل واحد)، لا انزلاق غير مقصود بالعدد.
 *
 * ثامن الآن، بنفس القرار الصريح — "المزوّدين الخارجيين": «المنصّة والفريق» صار طويلاً
 * ومزوّدين الخارجيين (Meta، الذكاء الاصطناعي، بوابات الدفع) موضوع قائم بذاته يستاهل قسمه — لا مطموراً
 * تبويباً فرعياً وسط تسعة تبويبات أخرى (سجل التدقيق، الامتثال...). كل مزوّد عالمه الكامل هناك:
 * إعداداته وأسراره معاً، لا شاشتين منفصلتين لمزوّد واحد.
 *
 * نفس dual-layout idiom الأصلي: one tab list, two renderings picked by CSS (`md:hidden`/
 * `hidden md:flex`), never `matchMedia`. Sidebar on desktop; bottom bar on the phone,
 * thumb-reachable — the SAME behaviour from day one, never "mobile support added later".
 */
import type { ReactNode } from 'react';
import {
  LayoutDashboard, Package, Users, Ticket, Wallet, Plug, Settings2, CircleUserRound,
} from 'lucide-react';

export type Tab =
  | 'home' | 'apps' | 'customers' | 'tickets' | 'billing' | 'providers' | 'platform' | 'account';

// سبعة أقسام تشغيلية + ثامن مخصّص لحساب المشغّل نفسه — كلمة مروره
// وبياناته الشخصية، لا وظيفة تشغيلية زيادة على السبعة.
const TABS: { id: Tab; label: string; icon: ReactNode }[] = [
  { id: 'home', label: 'الرئيسية', icon: <LayoutDashboard size={20} /> },
  { id: 'apps', label: 'التطبيقات والأسعار', icon: <Package size={20} /> },
  { id: 'customers', label: 'العملاء والدعم', icon: <Users size={20} /> },
  { id: 'tickets', label: 'تذاكر', icon: <Ticket size={20} /> },
  { id: 'billing', label: 'المالية', icon: <Wallet size={20} /> },
  { id: 'providers', label: 'المزوّدين الخارجيين', icon: <Plug size={20} /> },
  { id: 'platform', label: 'المنصّة والفريق', icon: <Settings2 size={20} /> },
];

const ACCOUNT_TAB: { id: Tab; label: string; icon: ReactNode } =
  { id: 'account', label: 'حسابي', icon: <CircleUserRound size={20} /> };

interface NavProps { active: Tab; onChange: (t: Tab) => void }

/** DESKTOP/TABLET (md and up) — a side rail, rendered FIRST so RTL row-reversal lands it on the
 *  start (right) edge — same convention as the shop console's `AppShell` and the affiliate
 *  portal's own `AffiliateSidebar`. */
export function AdminSidebar({ active, onChange }: NavProps) {
  return (
    <aside
      aria-label="أقسام لوحة الإدارة"
      className="sticky top-0 hidden h-dvh w-60 shrink-0 flex-col gap-0.5 border-e border-border-subtle bg-surface-1 p-3 md:flex"
    >
      {[...TABS, ACCOUNT_TAB].map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          aria-current={active === t.id ? 'page' : undefined}
          // NEUTRAL INK, NOT THE BRAND ACCENT — "this is the section I'm on" is a different
          // signal than "press this button", and the shop console's own AppShell rail already
          // made the same move (60-30-10 audit's category #2: every "selected/active" fill gets
          // its own neutral treatment; purple stays reserved for the one true primary action).
          className={`flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors ${
            active === t.id
              ? 'bg-surface-2 text-text-primary font-semibold'
              : 'text-text-secondary hover:bg-surface-2 hover:text-text-primary'
          }`}
        >
          {t.icon}
          {t.label}
        </button>
      ))}
    </aside>
  );
}

/** PHONE (below md) — بالضبط نفس فكرة تطبيق الجوال اللي بنيناها للمسوّقين: شريط سفلي ثابت،
 *  لمس أولاً، بدل شريط جانبي مضغوط بعرض غير كافٍ. */
export function AdminBottomNav({ active, onChange }: NavProps) {
  return (
    <nav
      aria-label="أقسام لوحة الإدارة"
      className="sticky bottom-0 z-20 flex border-t border-border-subtle bg-surface-1/95 backdrop-blur md:hidden"
    >
      {[...TABS, ACCOUNT_TAB].map((t) => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          aria-current={active === t.id ? 'page' : undefined}
          // Same neutral-ink move as the sidebar above — bold + dark, not brand purple.
          className={`flex min-h-11 flex-1 flex-col items-center gap-0.5 py-2 text-xs ${
            active === t.id ? 'font-semibold text-text-primary' : 'text-text-secondary'
          }`}
        >
          {t.icon}
          <span>{t.label}</span>
        </button>
      ))}
    </nav>
  );
}
