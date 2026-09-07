/**
 * «عملائي المحتملين» — the second real screen (2026-08-22), built on the research this session
 * did on mobile CRM/pipeline UX (Pipedrive, Follow Up Boss, HubSpot mobile) plus a full backend
 * inventory of `core/lead_sourcing.py` + `core/outreach.py`. The converged pattern across every
 * app researched: a FLAT LIST (never kanban on a phone), sorted needs-attention-first, with a
 * sticky search bar and at most a couple of promoted filters — never a dashboard/KPI strip on the
 * list itself, since a metric earns its place only if an action follows it (NN/g's own finding).
 *
 * NEEDS-ATTENTION IS COMPUTED HERE THE SAME WAY `stale_leads()` DEFINES IT SERVER-SIDE (no
 * activity in 3 days, excluding a closed outcome) — not re-fetched as a second list, so the sort
 * order and the "تحتاج متابعة" chip never disagree with each other over two round trips.
 *
 * THE DETAIL VIEW IS THE WORKING SCREEN, NOT A READ-ONLY CARD: the quick-action row (send this
 * stage's template, one-tap outcome logging right under it) is what the research called out as the
 * single biggest lever — under 30 seconds from "who do I contact" to "logged", never a full form.
 *
 * WHATSAPP IS ONE TAP AWAY, NOT A NUMBER TO RETYPE — it is the fastest channel available to
 * support quick communication with them, so every template gets its own «نسخ» (clipboard) and a send action that
 * opens WhatsApp with the template's own text already in the composer (`waLink`, `?text=`), and
 * the lead's own phone number in the header is itself a WhatsApp link. Copy exists ALONGSIDE the
 * direct open, not instead of it — a `wa.me?text=` link fails silently on a phone with no
 * WhatsApp app registered for the scheme, and a promoter mid-conversation needs the words even
 * when the automatic hand-off does not fire.
 */
import { useEffect, useMemo, useState } from 'react';
import { Search, ChevronRight, Phone, Copy, Check, MessageCircle } from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { Segmented } from '../rj-ui/Segmented';
import { Badge } from '@base-ui/design-system/Badge';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import {
  AffiliateRefused, leads as fetchLeads, oneLead, setLeadStatus, outreachStages, templates,
  templateUsesForLead, logTemplateUse, setOutcome, setDecisionMaker,
  LEAD_MANUAL_STATUSES, TEMPLATE_OUTCOMES,
  type AffiliateSession, type Lead, type OutreachStage, type MessageTemplate, type TemplateUse,
} from './api';
import { waLink } from './whatsapp';

const CLOSED_STATUSES = new Set(['registered', 'not_interested']);
const STALE_AFTER_SECONDS = 3 * 86400;

function needsAttention(lead: Lead, now: number): boolean {
  if (CLOSED_STATUSES.has(lead.status)) return false;
  const lastActivity = lead.notes.length
    ? Math.max(...lead.notes.map((n) => n.at)) : lead.found_at;
  return now - lastActivity >= STALE_AFTER_SECONDS;
}

const STATUS_LABEL: Record<string, string> = {
  new: 'جديد', assigned: 'مُسنَد', contacted: 'تم التواصل', interested: 'مهتم',
  not_interested: 'غير مهتم', follow_up: 'متابعة لاحقة', registered: 'مسجَّل',
};
const STATUS_TONE: Record<string, 'neutral' | 'accent' | 'success' | 'warning' | 'danger'> = {
  new: 'neutral', assigned: 'accent', contacted: 'accent', interested: 'success',
  not_interested: 'danger', follow_up: 'warning', registered: 'success',
};

export function AffiliateLeads({ session }: { session: AffiliateSession }) {
  const [data, setData] = useState<Lead[] | 'loading' | 'failed'>('loading');
  const [query, setQuery] = useState('');
  const [onlyAttention, setOnlyAttention] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const load = () => {
    setData('loading');
    fetchLeads(session).then((r) => setData(r.leads)).catch(() => setData('failed'));
  };
  useEffect(load, [session]);

  const now = Math.floor(Date.now() / 1000);
  const rows = useMemo(() => {
    if (data === 'loading' || data === 'failed') return [];
    const q = query.trim();
    return data
      .filter((l) => !q || l.name.includes(q) || l.city.includes(q))
      .filter((l) => !onlyAttention || needsAttention(l, now))
      .slice()
      .sort((a, b) => {
        const aa = needsAttention(a, now), ba = needsAttention(b, now);
        if (aa !== ba) return aa ? -1 : 1;
        return b.found_at - a.found_at;
      });
  }, [data, query, onlyAttention, now]);

  if (openId) {
    return <LeadDetail session={session} leadId={openId} onBack={() => { setOpenId(null); load(); }} />;
  }

  const attentionCount = data === 'loading' || data === 'failed'
    ? 0 : data.filter((l) => needsAttention(l, now)).length;

  return (
    <div className="flex flex-col gap-4 p-4">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl leading-tight tracking-tight">عملائي المحتملين</h1>
        {attentionCount > 0 ? (
          <p className="text-sm text-warning">
            {attentionCount === 1 ? 'عميل واحد يحتاج متابعة الآن' : `${attentionCount} عملاء يحتاجون متابعة الآن`}
          </p>
        ) : null}
      </div>

      <label className="relative block">
        <Search size={18} className="absolute top-1/2 -translate-y-1/2 start-3 text-text-muted" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="ابحث بالاسم أو المدينة"
          className="h-12 w-full rounded-xl bg-surface-1 ps-10 pe-4 shadow-sm placeholder:text-text-muted"
        />
      </label>

      <Segmented
        className="flex w-full [&>button]:flex-1 [&>button]:whitespace-nowrap"
        ariaLabel="فلترة العملاء المحتملين"
        value={onlyAttention ? 'attention' : 'all'}
        onChange={(v) => setOnlyAttention(v === 'attention')}
        options={[
          { value: 'all', label: 'الكل' },
          { value: 'attention', label: 'تحتاج متابعة' },
        ]}
      />

      {data === 'loading' ? (
        <Skeleton height={280} />
      ) : data === 'failed' ? (
        <EmptyState title="تعذّرت القراءة"
                   description="لم نستطع جلب قائمة عملائك الآن. أعد المحاولة بعد قليل." />
      ) : rows.length === 0 ? (
        query || onlyAttention ? (
          <EmptyState title="لا نتائج" description="جرّب كلمة بحث أخرى أو ألغِ الفلتر." />
        ) : (
          <EmptyState title="لا عملاء محتملون بعد"
                     description="يظهرون هنا أول ما يُسنَد لك عميل محتمل." />
        )
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((l) => (
            <li key={l.id}>
              <button
                type="button"
                onClick={() => setOpenId(l.id)}
                className="flex w-full items-center justify-between rounded-card bg-surface-1 px-4 py-3 text-start shadow-sm active:scale-[0.99]"
              >
                <div className="flex flex-col gap-1">
                  <span className="font-medium">{l.name || 'محل بلا اسم مسجَّل'}</span>
                  <span className="text-sm text-text-secondary">{l.city}</span>
                </div>
                <div className="flex items-center gap-2">
                  {needsAttention(l, now) ? <Badge tone="warning">تحتاج متابعة</Badge> : null}
                  <Badge tone={STATUS_TONE[l.status] ?? 'neutral'}>
                    {STATUS_LABEL[l.status] ?? l.status}
                  </Badge>
                  <ChevronRight size={18} className="shrink-0 text-text-muted rotate-180" aria-hidden />
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** THE HEADER + QUICK-ACTION ROW + ONE-TAP OUTCOME + TIMELINE — see the module docstring for why
 *  this shape, not a read-only card. */
function LeadDetail({ session, leadId, onBack }: {
  session: AffiliateSession; leadId: string; onBack: () => void;
}) {
  const [lead, setLead] = useState<Lead | 'loading' | 'failed'>('loading');
  const [stages, setStages] = useState<OutreachStage[]>([]);
  const [stageTemplates, setStageTemplates] = useState<MessageTemplate[]>([]);
  const [uses, setUses] = useState<TemplateUse[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [pendingUseId, setPendingUseId] = useState<string | null>(null);

  const reload = () => {
    oneLead(session, leadId).then(setLead).catch(() => setLead('failed'));
    templateUsesForLead(session, leadId).then((r) => setUses(r.uses)).catch(() => {});
  };
  useEffect(reload, [session, leadId]);
  useEffect(() => { outreachStages(session).then((r) => setStages(r.stages)).catch(() => {}); },
    [session]);

  useEffect(() => {
    if (lead === 'loading' || lead === 'failed') return;
    const stage = lead.outreach_stage_code || (stages[0]?.code ?? '');
    if (!stage) { setStageTemplates([]); return; }
    templates(session, stage).then((r) => setStageTemplates(r.templates)).catch(() => {});
  }, [session, lead, stages]);

  if (lead === 'loading') {
    return (
      <div className="flex flex-col gap-4 p-4">
        <BackRow onBack={onBack} />
        <Skeleton height={300} />
      </div>
    );
  }
  if (lead === 'failed') {
    return (
      <div className="flex flex-col gap-4 p-4">
        <BackRow onBack={onBack} />
        <EmptyState title="تعذّر فتح هذا العميل"
                   description="قد لا يكون ضمن قائمتك، أو تعذّرت القراءة الآن." />
      </div>
    );
  }

  const lastPending = uses.find((u) => u.outcome === 'pending');

  async function send(templateId: string) {
    setBusy(true); setError('');
    try {
      await logTemplateUse(session, leadId, templateId);
      reload();
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّر تسجيل الإرسال.');
    } finally { setBusy(false); }
  }

  async function logOutcome(useId: string, outcome: string) {
    setBusy(true); setError(''); setPendingUseId(useId);
    try {
      await setOutcome(session, useId, outcome);
      reload();
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّر تسجيل النتيجة.');
    } finally { setBusy(false); setPendingUseId(null); }
  }

  async function changeStatus(newStatus: string) {
    setBusy(true); setError('');
    try {
      await setLeadStatus(session, leadId, newStatus);
      reload();
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّر تحديث الحالة.');
    } finally { setBusy(false); }
  }

  // TIMELINE — template uses and status notes merged and sorted newest-first, a single history
  // rather than two the promoter has to cross-reference himself.
  const timeline = [
    ...uses.map((u) => ({ at: u.used_at, kind: 'use' as const, use: u })),
    ...lead.notes.map((n) => ({ at: n.at, kind: 'note' as const, note: n })),
  ].sort((a, b) => b.at - a.at);

  return (
    <div className="flex flex-col gap-4 p-4">
      <BackRow onBack={onBack} />

      <div className="flex flex-col gap-1 rounded-card bg-surface-1 p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h1 className="text-xl leading-tight">{lead.name || 'محل بلا اسم مسجَّل'}</h1>
          <Badge tone={STATUS_TONE[lead.status] ?? 'neutral'}>
            {STATUS_LABEL[lead.status] ?? lead.status}
          </Badge>
        </div>
        <span className="text-sm text-text-secondary">{lead.city}</span>
        {lead.phone ? (
          <div className="mt-1 flex items-center gap-3">
            {/* THE FAST PATH — one tap straight into WhatsApp, no number to retype or switch app
                for. Absent when the number is not recognisably a Saudi mobile (`waLink` returns
                null), rather than opening WhatsApp to nowhere. */}
            {waLink(lead.phone) ? (
              <a href={waLink(lead.phone) ?? undefined} target="_blank" rel="noreferrer" dir="ltr"
                 className="flex items-center gap-1.5 text-sm text-success">
                <MessageCircle size={14} /> واتساب
              </a>
            ) : null}
            <a href={`tel:${lead.phone}`} dir="ltr"
               className="flex items-center gap-1.5 text-sm text-accent">
              <Phone size={14} /> {lead.phone}
            </a>
          </div>
        ) : null}
      </div>

      {error ? <p role="alert" className="text-danger">{error}</p> : null}

      {/* THE QUICK ACTION — send the stage's own template, then log what happened right under it.
          Absent entirely once a lead is closed (registered/not interested) — there is nothing left
          to send. */}
      {!CLOSED_STATUSES.has(lead.status) ? (
        <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
          <h2 className="text-sm font-medium text-text-secondary">
            قوالب {stages.find((s) => s.code === lead.outreach_stage_code)?.name || 'المرحلة الحالية'}
          </h2>
          {stageTemplates.length === 0 ? (
            <p className="text-sm text-text-secondary">لا قوالب متاحة لهذه المرحلة بعد.</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {stageTemplates.slice(0, 5).map((t) => (
                <TemplateRow key={t.id} template={t} lead={lead} busy={busy} onSend={() => send(t.id)} />
              ))}
            </ul>
          )}

          {lastPending ? (
            <div className="flex flex-col gap-2 border-t border-border-subtle pt-3">
              <span className="text-sm text-text-secondary">ما نتيجة آخر تواصل؟</span>
              <div className="flex gap-2">
                {TEMPLATE_OUTCOMES.filter((o) => o !== 'pending').map((o) => (
                  <Button
                    key={o} type="button" variant="ghost"
                    disabled={busy && pendingUseId === lastPending.id}
                    onClick={() => logOutcome(lastPending.id, o)}
                  >
                    {o === 'advanced' ? 'تقدّم' : o === 'no_response' ? 'لا رد' : 'رفض'}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      ) : null}

      {/* الحالة يدويًا — فقط الحالات اللي يملك المسوّق تغييرها فعليًا */}
      <div className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
        <h2 className="text-sm font-medium text-text-secondary">تحديث الحالة</h2>
        <div className="flex flex-wrap gap-2">
          {LEAD_MANUAL_STATUSES.map((s) => (
            <Button key={s} type="button" variant={lead.status === s ? 'solid' : 'ghost'}
                   disabled={busy} onClick={() => changeStatus(s)}>
              {STATUS_LABEL[s]}
            </Button>
          ))}
        </div>
      </div>

      <DecisionMakerCard session={session} lead={lead} onSaved={reload} />

      {timeline.length > 0 ? (
        <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
          <h2 className="text-sm font-medium text-text-secondary">السجل</h2>
          <ul className="flex flex-col gap-2">
            {timeline.map((e, i) => (
              <li key={i} className="border-t border-border-subtle pt-2 text-sm first:border-0 first:pt-0">
                {e.kind === 'use' ? (
                  <span>أُرسل قالب — {e.use.outcome === 'pending' ? 'بانتظار الرد'
                    : e.use.outcome === 'advanced' ? 'تقدّم' : e.use.outcome === 'no_response'
                    ? 'لا رد' : 'رفض'}</span>
                ) : (
                  <span>{e.note.text || `تغيّرت الحالة إلى ${STATUS_LABEL[e.note.status_to] ?? e.note.status_to}`}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/** One template — «نسخ» (clipboard, no side effect) and the send action, which copies the SAME
 *  text as a fallback, opens WhatsApp with it pre-filled, and only then logs the use. Copy first,
 *  open second: if the WhatsApp hand-off silently fails (no app registered for the `wa.me` scheme),
 *  the text is still in his clipboard to paste by hand rather than lost. */
function TemplateRow({ template, lead, busy, onSend }: {
  template: MessageTemplate; lead: Lead; busy: boolean; onSend: () => void;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard?.writeText(template.body);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* clipboard permission denied — the send button still works */ }
  }

  function sendViaWhatsApp() {
    navigator.clipboard?.writeText(template.body).catch(() => {});
    const link = waLink(lead.phone, template.body);
    if (link) window.open(link, '_blank', 'noreferrer');
    onSend();
  }

  return (
    <li className="flex items-center justify-between gap-2">
      <span className="truncate text-sm">{template.title}</span>
      <div className="flex shrink-0 items-center gap-1.5">
        <Button type="button" variant="ghost" size="icon" aria-label="نسخ نص القالب" onClick={copy}>
          {copied ? <Check size={16} className="text-success" /> : <Copy size={16} />}
        </Button>
        <Button type="button" disabled={busy} onClick={sendViaWhatsApp}>أرسِل عبر واتساب</Button>
      </div>
    </li>
  );
}

function BackRow({ onBack }: { onBack: () => void }) {
  return (
    <button type="button" onClick={onBack}
           className="flex w-fit items-center gap-1 text-sm text-text-secondary">
      <ChevronRight size={16} aria-hidden /> رجوع لقائمة العملاء
    </button>
  );
}

function DecisionMakerCard({ session, lead, onSaved }: {
  session: AffiliateSession; lead: Lead; onSaved: () => void;
}) {
  const [name, setName] = useState(lead.decision_maker_name);
  const [phone, setPhone] = useState(lead.decision_maker_phone);
  const [role, setRole] = useState(lead.decision_maker_role);
  const [busy, setBusy] = useState(false);

  const dirty = name !== lead.decision_maker_name || phone !== lead.decision_maker_phone
    || role !== lead.decision_maker_role;

  async function save() {
    setBusy(true);
    try { await setDecisionMaker(session, lead.id, { name, phone, role }); onSaved(); }
    catch { /* the field values stay as typed; he can retry */ }
    finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
      <h2 className="text-sm font-medium text-text-secondary">صاحب القرار</h2>
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="الاسم"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="جواله" dir="ltr"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="صفته (مالك، مدير...)"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      {dirty ? (
        <Button type="button" disabled={busy} onClick={save}>حفظ</Button>
      ) : null}
    </div>
  );
}
