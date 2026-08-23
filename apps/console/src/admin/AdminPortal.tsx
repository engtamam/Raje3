/**
 * لوحة الإدارة's own shell — Door, or five sections once signed in. Same shape as
 * `../affiliates/AffiliatePortal.tsx` (ONE `useAdminSession()` instance held here and passed
 * down, two layouts/one markup picked by CSS) — see that file's own header note for the full
 * reasoning.
 */
import { useState } from 'react';
import { AdminBottomNav, AdminSidebar, type Tab } from './AdminNav';
import { AdminApps } from './AdminApps';
import { AdminCustomers } from './AdminCustomers';
import { AdminDoor } from './AdminDoor';
import { AdminHome } from './AdminHome';
import { ComingSoon } from './ComingSoon';
import { useAdminSession } from './session';

export function AdminPortal() {
  const { session, signedIn, signIn } = useAdminSession();
  const [tab, setTab] = useState<Tab>('home');

  if (!signedIn) {
    return <AdminDoor onSignedIn={signIn} />;
  }

  return (
    <div className="flex min-h-dvh flex-col md:flex-row">
      <AdminSidebar active={tab} onChange={setTab} />
      <div className="mx-auto flex w-full max-w-lg flex-1 flex-col md:max-w-4xl">
        <div className="flex-1">
          {tab === 'home' ? <AdminHome session={session} /> : null}
          {tab === 'apps' ? <AdminApps session={session} /> : null}
          {tab === 'customers' ? <AdminCustomers session={session} /> : null}
          {tab === 'billing' ? <ComingSoon label="المالية" /> : null}
          {tab === 'platform' ? <ComingSoon label="المنصّة والفريق" /> : null}
          {tab === 'account' ? <ComingSoon label="حسابي" /> : null}
        </div>
        <AdminBottomNav active={tab} onChange={setTab} />
      </div>
    </div>
  );
}
