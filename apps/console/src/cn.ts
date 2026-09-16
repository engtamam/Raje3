/**
 * Our own className merge — never `@base-ui/lib/cn`. Plain string concatenation (as EmptyState.tsx
 * already did) is fine for classes that never collide, but a component whose caller may want to
 * override one of its OWN default utilities (Card's own `p-5`, say, with a caller's `p-4`) needs
 * `tailwind-merge` to actually drop the earlier one — string concatenation leaves both in the
 * output and the winner becomes whichever Tailwind happened to generate later, not whichever the
 * caller wrote. `clsx` handles the falsy/conditional class filtering the same way our other
 * components already do by hand.
 */
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
