/**
 * The one application — owner, manager and operator, behind one login.
 *
 * WHY ONE AND NOT TWO. The MANAGER needs both surfaces: the field screen when he stands at the
 * till and the sections when he sits (spec 10.8). Two applications means two sign-ins for him, and
 * that alone settles it. The operator is not given a smaller app; he is given the same app, which
 * shows him one section because that is all his capabilities reach.
 *
 * THE CHROME IS platform/ui's AppShell, BY ALIAS. Sidebar rail, persisted collapse, brand slot,
 * user block, theme and language toggles, and a Toaster — all of it already built and all of it
 * arriving with their next release. We supply the nav items and the brand; nothing else here is
 * ours to design.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AppShell } from '@base-ui/shell';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { NAME_AR } from './brand/Mark';
import { fetchCatalog, type Catalog } from './catalog';
import { isOutage, visibleSections } from './nav';
import { isSignedIn, useSession } from './session';

export function App() {
  const session = useSession();
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!isSignedIn(session)) return;
    fetchCatalog(session).then(setCatalog).catch(() => setFailed(true));
  }, [session]);

  if (!isSignedIn(session)) {
    // Sign-in is its own route and its own task; until it lands this states the fact rather than
    // inventing a tenant — a placeholder establishment would let every screen appear to work while
    // writing into data nobody owns.
    return (
      <main className="grid min-h-dvh place-items-center bg-surface-0 p-6">
        <EmptyState title="لم تُفتح الجلسة بعد" />
      </main>
    );
  }

  if (failed) {
    // THE DISTINCTION THAT MATTERS TO A PAYING OWNER: "we cannot reach the platform" and "you have
    // access to nothing" look identical on an empty screen, and only one of them is about him.
    return (
      <main className="grid min-h-dvh place-items-center bg-surface-0 p-6">
        <EmptyState
          title="تعذّر الوصول إلى المنصة"
          description="حسابك سليم — أعد المحاولة بعد قليل."
        />
      </main>
    );
  }

  if (!catalog) {
    return (
      <main className="min-h-dvh bg-surface-0 p-6">
        <Skeleton width={192} height={40} />
      </main>
    );
  }

  if (isOutage(catalog)) {
    return (
      <main className="grid min-h-dvh place-items-center bg-surface-0 p-6">
        <EmptyState
          title="الخدمات غير متاحة الآن"
          description="لا علاقة لهذا بحسابك. نعمل على إعادتها."
        />
      </main>
    );
  }

  const sections = visibleSections(catalog);

  return (
    <AppShell
      // THE BRAND SLOT TAKES A NAME, NOT A MARK. The shell draws its own BrandMark, which is the
      // one component we fork rather than configure — see brand/Mark.tsx for why theirs (a notary
      // seal) cannot be ours. Substituting it is a shell change, and it is deliberately left for
      // the moment the mark is final rather than smuggled in through a prop that does not exist.
      brand={{ name: NAME_AR }}
      // DERIVED, NOT WRITTEN — see nav.ts. An operator's list has one entry and a manager's is
      // missing what the owner keeps, with no role check anywhere in this file.
      navItems={sections.map((s) => ({ to: s.path, label: s.label }))}
      user={{ name: session.operatorName || session.operator }}
      labels={{ collapse: 'طيّ القائمة', expand: 'فتح القائمة', signOut: 'تسجيل الخروج' }}
      onSignOut={() => navigate('/')}
    />
  );
}
