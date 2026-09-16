/**
 * «الشريط الجانبي» IS GONE — the last, most careful step of the 7-phase app-store redesign
 * (2026-09-16, [[task-app-store-redesign-7-phases]]), done only once every rail row had a real
 * equivalent path (confirmed live: every `nav.ts` SECTIONS row already surfaces as a launcher
 * tile via `myApps()`, which reads the SAME `visibleSections(catalog)` the rail used; «حسابي» and
 * «تسجيل الخروج» live in `TopBar`'s own `AccountMenu`; «الدعم الفني» is its own top-bar icon —
 * nothing the old rail reached is now unreachable).
 *
 * A FRESH, MINIMAL SHELL — not a reskin of `@base-ui/shell`'s `AppShell` (that file is the OLD nav
 * chrome [[app-store-redesign-new-components-not-reused]] forbids restyling; it is simply no
 * longer USED here at all, which is the one thing that rule always allowed). Keeps only what
 * `AppShell` did that nothing else replaces: the page's own background/text tokens. NO `Toaster`
 * here — this console no longer imports through the `@base-ui` alias at all (removed from
 * `vite.config.ts`/`tsconfig.json`, 2026-09-16, the owner's own instruction: راجِع has its own
 * `rj-ui/` design system, built fresh for this product); the handful of real, not-yet-duplicated
 * shared components it still reads (OtpVerify, AcceptTerms, the block renderers, theme/i18n
 * providers, `AppShell` itself) are now plain relative imports into `ui/packages/ui/src` instead.
 * Grep confirms nothing in this console ever actually calls a toast trigger, so `AppShell`'s own
 * mounted `Toaster` was dead chrome, not a feature this layout needs to carry forward.
 */
import type { ReactNode } from 'react';

export function ConsoleLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-dvh bg-surface-0 text-text-primary">
      {children}
    </div>
  );
}
