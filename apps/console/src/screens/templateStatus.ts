/**
 * The badge every customer-facing message now carries — the SAME picture the admin panel's own
 * template screen shows (`admin/AdminWhatsAppTemplates.tsx`'s own `STATUS_META`), surfaced on
 * «متى نرسل»'s own rows and «حملاتي»'s own goal cards instead of hidden behind a modal a person
 * has to open one row at a time to learn a fact that decides whether it sends at all.
 *
 * THE WORDS ARE OURS, NEVER META'S RAW STATUS NAME — same rule the admin screen already follows.
 * `not_registered`/`not_seeded`/`unknown` are OUR OWN three, not Meta states: they distinguish
 * "seeded but nobody submitted it for this establishment yet" from "not even in our library"
 * from "we could not ask" — three different problems with three different owners (the platform,
 * the platform, and a transient outage, respectively).
 */
import type { LucideIcon } from 'lucide-react';
import { CheckCircle2, Clock, HelpCircle, PauseCircle, XCircle } from 'lucide-react';

export type TemplateStatus =
  | 'approved' | 'pending' | 'rejected' | 'paused' | 'disabled'
  | 'not_registered' | 'not_seeded' | 'unknown';

export const TEMPLATE_STATUS_META: Record<TemplateStatus,
    { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral'; icon: LucideIcon }> = {
  approved: { label: 'معتمدة', tone: 'success', icon: CheckCircle2 },
  pending: { label: 'قيد المراجعة عند واتساب', tone: 'warning', icon: Clock },
  rejected: { label: 'رفضها واتساب', tone: 'danger', icon: XCircle },
  paused: { label: 'متوقفة مؤقتاً', tone: 'warning', icon: PauseCircle },
  disabled: { label: 'معطّلة', tone: 'danger', icon: XCircle },
  not_registered: { label: 'لم تُرفع بعد', tone: 'neutral', icon: Clock },
  not_seeded: { label: 'قيد التجهيز عندنا', tone: 'neutral', icon: Clock },
  // NO BADGE AT ALL FOR "unknown" AT THE CALL SITE — a status this file cannot vouch for must
  // not be drawn as if it were one; see each screen's own `t.template_status !== 'unknown'` guard
  // rather than rendering this entry. Kept here only so the type stays total and every real value
  // this map is indexed by resolves to something, never a runtime `undefined`.
  unknown: { label: '', tone: 'neutral', icon: HelpCircle },
};
