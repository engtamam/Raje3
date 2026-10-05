/**
 * جهات الاتصال — the customer book itself: the fifty, findable, and the ones falling behind.
 *
 * This app's rows ARE the fifty customers foundation.mjs registers through its door
 * (`/api/v1/field/customers/ensure`), so there is nothing extra to write here. What «عملائي»
 * promises on top of the list is that every customer is findable the moment he exists, and the
 * «من تأخّر» tab — customers past the return date reminders learned from their own visits — so this
 * module holds both to account: every one of the fifty is found by the real type-ahead search
 * (search-service, indexed by operations), and the overdue view's entries — reminders' own pending
 * schedule, past due — all resolve to real customers of this shop through operations' own join.
 */
import { pool } from '../lib/demo-api.mjs';

export const app = 'feature.contacts';

export async function seed(ctx) {
  return { customers: ctx.customers.length };   // registered by the foundation, through this app's door
}

export async function verify(ctx) {
  const { api, customers } = ctx;
  const problems = [];
  let found = 0;
  // BY THE WHOLE NUMBER AND THE WHOLE NAME — type-ahead answers its best few matches, and a short
  // prefix shared by a dozen customers is a ranking question, not a findability one.
  await pool(customers, 6, async (c) => {
    const byPhone = (await api.call(api.act('operations.customer_suggest'), { prefix: c.phone })).customers ?? [];
    const byName = (await api.call(api.act('operations.customer_suggest'), { prefix: c.name })).customers ?? [];
    if (byPhone.some((h) => h.id === c.id) && byName.some((h) => h.id === c.id)) found += 1;
    else problems.push(`${c.phone} (${c.name}) not found by number${byPhone.some((h) => h.id === c.id) ? '' : ' ✗'} / name${byName.some((h) => h.id === c.id) ? '' : ' ✗'}`);
  });
  const schedule = (await api.call(api.act('reminders.list_schedule'))).schedule ?? [];
  const now = Math.floor(Date.now() / 1000);
  const overdue = schedule.filter((s) => s.state === 'pending' && s.due_at < now);
  const refs = [...new Set(schedule.map((s) => s.subject_ref))];
  const resolved = refs.length
    ? ((await api.call(api.act('operations.customers_by_refs'), { refs })).customers ?? []) : [];
  const ours = new Set(customers.map((c) => c.subject_ref));
  const strangers = resolved.filter((r) => !ours.has(r.subject_ref));
  if (resolved.length !== refs.length) problems.push(`${refs.length - resolved.length} scheduled refs resolve to no customer`);
  if (strangers.length) problems.push(`${strangers.length} scheduled customers are not among the fifty`);
  if (!schedule.length) problems.push('reminders learned no return dates from any visit');
  if (problems.length) throw new Error(`contacts check failed (${problems.length}): ${problems.slice(0, 4).join(' | ')}`);
  return { findable: found, of: customers.length, scheduled_reminders: schedule.length,
    customers_with_a_return_date: refs.length, overdue_now: overdue.length };
}
