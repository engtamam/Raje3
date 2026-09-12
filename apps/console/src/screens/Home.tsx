/**
 * What `/` is — which depends on who opened it.
 *
 * «محلّي» IS THE HOME FOR ALMOST EVERYONE, and for the operator it is a page of 403s: he holds
 * `operations.record` and nothing else. So the index route asks the nav — the same derived list
 * the sidebar renders — and shows the first section this person actually has.
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
  // NEVER LAND HIM ON A SECTION THAT CANNOT ANSWER. The rail still shows it — he must know it
  // exists and why it is quiet — but the default screen has to be one that works.
  const first = (sections.find((s) => !s.unavailable) ?? sections[0])?.id;

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
