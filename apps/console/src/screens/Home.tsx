/**
 * What `/` is — which depends on who opened it.
 *
 * «اليوم» IS THE HOME FOR ALMOST EVERYONE, and for the operator it is a page of 403s: he holds
 * `operations.record` and nothing else. So the index route asks the nav — the same derived list
 * the sidebar renders — and shows the first section this person actually has.
 *
 * ASKED HERE RATHER THAN REDIRECTED IN THE SHELL, because a redirect out of `/` would fight the
 * back button: the operator presses back, lands on `/`, and is bounced forward again with no way
 * out of the loop.
 */
import { useOutletContext } from 'react-router-dom';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { TodayScreen } from './Today';
import { Visit } from './Visit';
import { visibleSections } from '../nav';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Home() {
  const { session, catalog } = useOutletContext<{ session: Session; catalog: Catalog }>();
  const sections = visibleSections(catalog);
  const first = sections[0]?.id;

  if (first === 'today') return <TodayScreen session={session} catalog={catalog} />;
  if (first === 'visit') return <Visit />;
  // NEITHER, WHICH IS A REAL STATE RATHER THAN A FALLBACK: a person whose role reaches no section
  // at all. Saying so beats a blank page he would read as a broken product.
  return (
    <div className="p-6">
      <EmptyState
        title="لا توجد أقسام متاحة لحسابك"
        description="تواصل مع مالك الحساب لضبط صلاحياتك."
      />
    </div>
  );
}
