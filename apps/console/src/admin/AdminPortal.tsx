/**
 * لوحة الإدارة's own shell — Door, or five sections once signed in. Same shape as
 * `../affiliates/AffiliatePortal.tsx` (ONE `useAdminSession()` instance held here and passed
 * down, two layouts/one markup picked by CSS) — see that file's own header note for the full
 * reasoning.
 *
 * THE TAB LIVES IN THE URL NOW (2026-09-07) — this used to be a bare `useState`, with a comment
 * saying "بلا موجّه (router) بهذا التطبيق أصلاً" as if that were still true; it stopped being true
 * the day `main.tsx` put `AdminPortal` under `RouterProvider` at `/*` for the legal route. A tab
 * only living in memory meant a refresh always landed back on "الرئيسية" no matter where the
 * operator actually was — the exact thing `screens/Customers.tsx`'s own real route does NOT do,
 * which is what an operator comparing the two panels actually notices. No new `<Route>` entries
 * needed: `/*` already catches everything on this host, so `tab` is read straight from
 * `location.pathname` here instead of a second router table main.tsx would have to keep in sync.
 */
import { useLocation, useNavigate } from 'react-router-dom';
import { AdminBottomNav, AdminSidebar, type Tab } from './AdminNav';
import { AdminAccount } from './AdminAccount';
import { AdminApps } from './AdminApps';
import { AdminCustomers } from './AdminCustomers';
import { AdminDoor } from './AdminDoor';
import { AdminFinance } from './AdminFinance';
import { AdminHome } from './AdminHome';
import { AdminPlatform } from './AdminPlatform';
import { AdminProviderSecrets } from './AdminProviderSecrets';
import { AdminTickets } from './AdminTickets';
import { useAdminSession } from './session';

// المسار مقابل التبويب — "الرئيسية" هي الجذر، البقية بمسارها الخاص. `legal/:slug` (main.tsx) يبقى
// المسار الوحيد المحجوز خارج هذي القائمة، فلا تعارض معه.
const TAB_PATH: Record<Tab, string> = {
  home: '/', apps: '/apps', customers: '/customers', tickets: '/tickets', billing: '/billing',
  providers: '/providers', platform: '/platform', account: '/account',
};
const PATH_TAB: Record<string, Tab> = Object.fromEntries(
  Object.entries(TAB_PATH).map(([tab, path]) => [path, tab as Tab]),
);

export function AdminPortal() {
  const { session, signedIn, signIn, signOut } = useAdminSession();
  const location = useLocation();
  const navigate = useNavigate();
  // مسار غير معروف (رابط قديم، أو خطأ كتابة) يقع على "الرئيسية" بدل شاشة بيضاء — نفس منطق أي مزوّد
  // غير معروف يقع على بطاقة "أخرى" بشاشة الأسرار، لا يُفقد المستخدم صامتاً.
  const tab: Tab = PATH_TAB[location.pathname] ?? 'home';
  // رابط تحويل مباشر: تبويب "بوابة الدفع" بالمالية يفتح على "المزوّدين الخارجيين" مباشرة، بفئة
  // بوابة الدفع مفتوحة — عابر بذاكرة التنقّل (`location.state`) لا بالمسار نفسه، فهو تفصيل جلسة
  // حالية لا شي يستحق رابطاً خاصاً به أو أن يبقى بعد تحديث الصفحة.
  const openProvider = (location.state as { openProvider?: string } | null)?.openProvider ?? null;

  if (!signedIn) {
    return <AdminDoor onSignedIn={signIn} />;
  }

  function openProviderSecrets(provider: string) {
    navigate(TAB_PATH.providers, { state: { openProvider: provider } });
  }

  // A manual tab click (sidebar/bottom-nav) is a fresh visit, not a continuation of the deep link —
  // otherwise "بوابة الدفع" would keep reopening every time the owner returns to "المزوّدين" on
  // their own, since AdminProviderSecrets remounts (and re-reads its `initial*` prop) on every tab
  // switch. `state: null` clears it explicitly rather than leaving the previous entry's state to
  // bleed into this one.
  function changeTab(next: Tab) {
    navigate(TAB_PATH[next], { state: null });
  }

  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <AdminSidebar active={tab} onChange={changeTab} />
      <div className="mx-auto flex w-full max-w-lg flex-1 flex-col md:max-w-4xl">
        <div className="flex-1">
          {tab === 'home' ? <AdminHome session={session} /> : null}
          {tab === 'apps' ? <AdminApps session={session} /> : null}
          {tab === 'customers' ? <AdminCustomers session={session} /> : null}
          {tab === 'tickets' ? <AdminTickets session={session} /> : null}
          {tab === 'billing' ? (
            <AdminFinance session={session} onOpenProviderSecrets={() => openProviderSecrets('payment')} />
          ) : null}
          {tab === 'providers' ? (
            <AdminProviderSecrets session={session} initialOpenProvider={openProvider ?? undefined} />
          ) : null}
          {tab === 'platform' ? <AdminPlatform session={session} /> : null}
          {tab === 'account' ? <AdminAccount onSignOut={signOut} /> : null}
        </div>
        <AdminBottomNav active={tab} onChange={changeTab} />
      </div>
    </div>
  );
}
