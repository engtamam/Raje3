/**
 * The one place every admin screen decides what to say when its own action is missing from the
 * catalog — "no permission" and "a service never answered" are different causes with an identical
 * symptom (an action absent from `catalog.services`), and a screen that only ever wrote one of the
 * two messages guessed wrong every time the real cause was the other one. See
 * ci/check_admin_catalog_targets_are_actually_deployed.py's own header for the live incident this
 * exists to stop repeating: an operator holding `platform.secrets_manage` was told "ليست ضمن
 * صلاحياتك" because secrets-admin — not the operator's token — was the thing actually missing.
 *
 * Every screen renders THIS instead of writing its own EmptyState with a permission-shaped title,
 * so the distinction is made once, not reinvented (and re-forgotten) per screen.
 */
import { EmptyState } from '../rj-ui/EmptyState';
import type { AdminCatalog } from './catalog';

export function NoActionAvailable({ catalog, permissionTitle }: {
  catalog: AdminCatalog;
  /** What to say when every declared service DID answer, and the action is simply absent — a
   *  real permission gap, not a service outage. Phrase this one as "you don't have access", the
   *  screen's own honest answer for that case. */
  permissionTitle: string;
}) {
  if (catalog.unreachable.length > 0) {
    // AT LEAST ONE declared service failed to answer when the catalog was built — this MAY be
    // why this screen's own action is missing (we cannot prove which unreachable service would
    // have declared it, only that not every service got a chance to). Naming the unreachable
    // ones lets an operator recognise "oh, that's the one I know is still being deployed" rather
    // than concluding their own account is broken.
    return (
      <div className="p-6">
        <EmptyState title="تعذّر الوصول لخدمة أو أكثر عند بناء هذي الشاشة"
                    description={`قد يكون هذا سبب عدم ظهور شي هنا، لا صلاحياتك — الخدمات: ${
                      catalog.unreachable.join('، ')}.`} />
      </div>
    );
  }
  return <div className="p-6"><EmptyState title={permissionTitle} /></div>;
}
