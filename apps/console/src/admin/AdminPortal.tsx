/**
 * لوحة الإدارة's own shell — Door, or five sections once signed in. Same shape as
 * `../affiliates/AffiliatePortal.tsx` (ONE `useAdminSession()` instance held here and passed
 * down, two layouts/one markup picked by CSS) — see that file's own header note for the full
 * reasoning.
 */
import { useState } from 'react';
import { AdminBottomNav, AdminSidebar, type Tab } from './AdminNav';
import { AdminAccount } from './AdminAccount';
import { AdminApps } from './AdminApps';
import { AdminCustomers } from './AdminCustomers';
import { AdminDoor } from './AdminDoor';
import { AdminFinance } from './AdminFinance';
import { AdminHome } from './AdminHome';
import { AdminPlatform } from './AdminPlatform';
import { AdminTickets } from './AdminTickets';
import { useAdminSession } from './session';

export function AdminPortal() {
  const { session, signedIn, signIn, signOut } = useAdminSession();
  const [tab, setTab] = useState<Tab>('home');
  // رابط تحويل مباشر: تبويب "بوابة الدفع" بالمالية يفتح على "مفاتيح المزوّدين" مباشرة، ببطاقة
  // بوابة الدفع مفتوحة — بلا موجّه (router) بهذا التطبيق أصلاً، فالحالة تُرفع لهذا المستوى وتُمرَّر
  // كخاصية أولية مرة واحدة، لا كحالة مشتركة مستمرة.
  const [platformDeepLink, setPlatformDeepLink] = useState<{ sub: 'provider_secrets'; openProvider: string } | null>(null);

  if (!signedIn) {
    return <AdminDoor onSignedIn={signIn} />;
  }

  function openProviderSecrets(provider: string) {
    setPlatformDeepLink({ sub: 'provider_secrets', openProvider: provider });
    setTab('platform');
  }

  // A manual tab click (sidebar/bottom-nav) is a fresh visit, not a continuation of the deep link —
  // otherwise "بوابة الدفع" would keep reopening every time the owner returns to "المنصّة" on their
  // own, since AdminPlatform remounts (and re-reads its `initial*` props) on every tab switch.
  function changeTab(next: Tab) {
    setPlatformDeepLink(null);
    setTab(next);
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
          {tab === 'platform' ? (
            <AdminPlatform session={session} initialSub={platformDeepLink?.sub}
                           initialOpenProvider={platformDeepLink?.openProvider} />
          ) : null}
          {tab === 'account' ? <AdminAccount onSignOut={signOut} /> : null}
        </div>
        <AdminBottomNav active={tab} onChange={changeTab} />
      </div>
    </div>
  );
}
