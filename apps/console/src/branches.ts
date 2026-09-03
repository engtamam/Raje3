/**
 * Why the branches surface is closed, when it is — and the two reasons are not interchangeable.
 *
 * IT LIVES HERE RATHER THAN INSIDE «فريقي» for the reason `Customer.tsx` already states about its
 * own rules: a rule that lives inside a component is a rule only a rendered page can check, and
 * the rendered page is the thing most likely to be rewritten. This is one function with one job.
 *
 * WHAT WENT WRONG (هـ-3). The lock was `Boolean(action(catalog, 'operations.list_branches'))` — a
 * fact about the PERSON's role — under the sentence «الفروع متاحة كتطبيق إضافي», a fact about the
 * SHOP's app entitlement. Wrong in both directions at once:
 *
 *   · an owner whose entitlement allows exactly one branch holds that capability regardless of
 *     which app is enabled, so he saw no lock at all, typed a branch name, and met a 402 from the server;
 *   · an employee who simply lacks the permission was told his shop had to pay more — a claim
 *     about money that may be false, and one he cannot act on either way.
 *
 * `Locked.tsx` had already written the general form of this down: «Each screen decided for itself
 * whether to lock, and it decided from the CAPABILITY — which is about the person's role.» This
 * tab was the one that had not been converted.
 */

export type BranchGate = 'open' | 'role' | 'plan';

/**
 * @param mayRead whether this person holds `operations.list_branches` — a role fact.
 * @param limit   how many branches the shop may have, as billing stated it on the read.
 *                `-1` is «no known ceiling»: an unlimited entitlement AND a billing we could not reach
 *                both land there, because the gauge fails open by design (core/seats.py).
 *                `undefined` is an answer that has not arrived, or one that carried no limit.
 */
export function branchGate(mayRead: boolean, limit: number | undefined): BranchGate {
  // THE ROLE ANSWERS FIRST, whatever the app entitlement says. There is nothing to sell somebody who cannot
  // use the thing, and «تطبيق إضافي» sends an employee to ask his owner for money instead of for a
  // permission.
  if (!mayRead) return 'role';
  // AND ONLY A STATED ONE LOCKS. Every unknown resolves to `open`: telling a paying shop it has
  // not paid is the worst sentence in the product, and an outage must never be what says it.
  return limit === 1 ? 'plan' : 'open';
}
