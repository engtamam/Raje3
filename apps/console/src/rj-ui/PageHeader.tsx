/**
 * PageHeader — component #17. Every screen the rail links to needs the same first thing a person
 * sees: the icon that also marks it in the rail, and the page's own name, so a person who just
 * pressed «رسائلي» in the sidebar lands on a page that visibly says «رسائلي» back — not a screen
 * that starts straight into its own content with no title at all.
 *
 * WHY THIS EXISTS RATHER THAN A PLAIN `<h1>` PER SCREEN. `Support.tsx` already had this exact
 * shape (icon + title, one row) and nothing else did — most of the shop-facing screens
 * (Bookings/Points/Services/Messages/Customers/Shop/Visit/Plans) opened directly into their own
 * content with no header at all, found from a live screenshot and the owner's own instruction to
 * make every screen match. One shared component means the NEXT screen inherits the same shape by
 * construction, rather than by a comment telling whoever writes it to copy Support.tsx's JSX.
 *
 * THE ICON IS THE SAME ONE nav.ts ALREADY ASSIGNS THAT SCREEN'S ROW IN THE RAIL — passed in by the
 * caller rather than looked up here, so this component stays screen-agnostic. Reusing it (rather
 * than picking a second icon for the same page) is what lets the header read as "this is where
 * that rail row leads," not as a second, disconnected decoration.
 *
 * THE TITLE WEARS THE DISPLAY FACE (theme.config.ts's `font.display`, Cairo) — rebranded
 * 2026-09-12, matching the approved campaigns mockup's own heading treatment. This is the one
 * shared component nearly every screen's own title already renders through, so the new heading
 * voice reaches the whole product from here rather than a per-screen change.
 */
import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

export function PageHeader({ icon: Icon, title, action }: {
  icon: LucideIcon;
  title: string;
  /** An optional control on the header's OWN row (e.g. Support.tsx's own tab strip sits below
   *  this, never inside it) — for the rare screen whose title row also carries one action, like
   *  a primary button. Most screens omit this; the title stands alone. */
  action?: ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <Icon size={22} className="text-text-secondary" aria-hidden />
        <h1 className="text-2xl font-bold leading-tight tracking-tight"
            style={{ fontFamily: 'var(--font-display)' }}>{title}</h1>
      </div>
      {action}
    </div>
  );
}
