/**
 * Wraps any control that fires a capability-gated backend action — renders nothing when the
 * session's own catalogue does not hold this action id.
 *
 * THE CATALOGUE, NOT A ROLE CHECK. See catalog.ts's own header: the gateway has ALREADY
 * filtered the catalogue by capability before this app ever sees it, so an action this operator
 * may not use is simply absent from it, never present-but-disabled. `action(catalog, id)` is the
 * one and only question this component asks; it never invents a decision the backend didn't
 * already make.
 *
 * THE SAME IDIOM ALREADY USED EVERYWHERE, JUST REUSABLE. `Services.tsx` and its peers already
 * gate every write button with `action(catalog, id) ? <Btn/> : null`, repeated inline at each
 * call site — this component is that exact same check, wrapped once for a new call site to
 * compose (`<Can catalog={catalog} action="operations.update_service">…</Can>`) instead of
 * writing the ternary again. NOT a replacement requirement for the many existing inline checks
 * already spread across this codebase — both forms answer the same question the same way.
 *
 * SCREEN-LEVEL GATING (a whole nav section's own `requires`, `nav.ts::visibleSections`) is a
 * SEPARATE, coarser question this component does not replace. This one is for the finer
 * question: one button, one action, inside a screen the operator can already open.
 */
import type { ReactNode } from 'react';
import { action, type Catalog } from './catalog';

export function Can({
  catalog, action: actionId, children,
}: {
  catalog: Catalog;
  action: string;
  children: ReactNode;
}) {
  return action(catalog, actionId) ? <>{children}</> : null;
}
