/**
 * What `/` is — which depends on who opened it.
 *
 * «تسجيل زيارة» IS THE HOME FOR EVERYONE WHO HAS IT (owner/manager included, 2026-09-14, the
 * owner's own call) — not «محلّي». «محلّي» is a real dashboard: several indicator/insight reads
 * fire the moment it mounts, on the ONE route every sign-in and every reload lands on first,
 * whether or not anyone is about to look at it. The counter screen is what most sign-ins are
 * actually FOR — recording the next visit — and it costs one cheap read, not a dashboard's worth.
 * «محلّي» is still one tap away in the rail, in its usual place; this only changes which screen a
 * fresh load opens on.
 *
 * NEVER OVERRIDES A REAL GATE. An operator who holds only `operations.record` already got «تسجيل
 * زيارة» as his one section before this — this just extends the SAME preference to everyone else
 * who has the section too, rather than only to the people who have nothing else.
 *
 * ASKED HERE RATHER THAN REDIRECTED IN THE SHELL, because a redirect out of `/` would fight the
 * back button: the operator presses back, lands on `/`, and is bounced forward again with no way
 * out of the loop.
 */
import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { ShopScreen } from './Shop';
import { Visit } from './Visit';
import { visibleSections } from '../nav';
import type { Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n } from '../operator-i18n';
import './home-i18n';

export function Home() {
  const { t } = useOperatorI18n();
  const { catalog } = useOutletContext<ShellContext>();
  const sections = visibleSections(catalog);
  // «تسجيل زيارة» WINS WHEN HE HAS IT AT ALL — see this file's own header for why. Falls through
  // to the same rule as before (first available section, then the first section outright) for
  // anyone who does not hold it, so an operator with a different single section is unaffected.
  const visitSection = sections.find((s) => s.id === 'visit' && !s.unavailable);
  // NEVER LAND HIM ON A SECTION THAT CANNOT ANSWER. The rail still shows it — he must know it
  // exists and why it is quiet — but the default screen has to be one that works.
  const first = visitSection?.id ?? (sections.find((s) => !s.unavailable) ?? sections[0])?.id;

  if (first === 'shop') return <ShopScreen />;
  if (first === 'visit') return <Visit />;
  // NEITHER, WHICH IS A REAL STATE RATHER THAN A FALLBACK: a person whose role reaches no section
  // at all. Saying so beats a blank page he would read as a broken product.
  return (
    <div className="p-6">
      <EmptyState
        title={t('home.noSections.title')}
        description={t('home.noSections.description')}
      />
    </div>
  );
}
