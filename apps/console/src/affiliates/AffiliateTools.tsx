/**
 * «أدواتي» (2026-08-22) — the fourth screen, built on this session's own research into CRM
 * content-library and background-job UX (Pipedrive/Close/HubSpot template patterns, async-job
 * monitoring conventions) plus a full backend inventory of `core/outreach.py` + the lead-search
 * routes.
 *
 * A HUB, NOT ONE FLAT SCREEN — the research's own conclusion: template curation (frequent,
 * browsing-oriented) and the lead-search tool (rare, but a LIVE job when running) have
 * incompatible refresh cadences and mental models; cramming both under one scroll means a
 * progress bar polling above static template rows. So this is a landing menu into three focused
 * sub-screens, each owning its own back button — the same pattern Settings apps and CRMs use for
 * low-frequency admin tools.
 *
 * HIDE THE DESTINATION, NOT THE BUTTON. A promoter never sees the "أداة البحث" or citation-CRUD
 * cards at all — never a greyed-out card he cannot tap. Inside a screen he DOES use (the template
 * library), edit affordances are simply absent for him rather than disabled; the browsing/preview
 * experience itself is identical for both roles, which is the one place "same screen, controls
 * hidden" beats a forked read-only copy (research's own point 5).
 */
import { useEffect, useState } from 'react';
import {
  MessagesSquare, Quote, Search as SearchIcon, ChevronRight, Plus, Pencil, Ban, Copy, Check,
} from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { Badge } from '@base-ui/design-system/Badge';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import {
  AffiliateRefused, me, outreachStages, templates, templateStats, createTemplate, updateTemplate,
  deactivateTemplate, statCitations, createStatCitation, updateStatCitation,
  deactivateStatCitation, placesApiKey, setPlacesApiKey, clearPlacesApiKey, myLeadSearches,
  leadSearchStatus, startLeadSearch,
  type AffiliateSession, type OutreachStage, type MessageTemplate, type TemplateStat,
  type StatCitation, type PlacesApiKeyInfo, type LeadSearchJob,
} from './api';

type View = 'menu' | 'templates' | 'citations' | 'search';

export function AffiliateTools({ session }: { session: AffiliateSession }) {
  const [view, setView] = useState<View>('menu');
  const [isManager, setIsManager] = useState<boolean | 'loading'>('loading');

  useEffect(() => {
    let cancelled = false;
    me(session).then((m) => { if (!cancelled) setIsManager(m.role === 'affiliate_manager'); })
      .catch(() => { if (!cancelled) setIsManager(false); });
    return () => { cancelled = true; };
  }, [session]);

  if (view === 'templates') return <TemplateLibrary session={session} isManager={isManager === true} onBack={() => setView('menu')} />;
  if (view === 'citations') return <CitationLibrary session={session} isManager={isManager === true} onBack={() => setView('menu')} />;
  if (view === 'search') return <LeadSearchTool session={session} onBack={() => setView('menu')} />;

  if (isManager === 'loading') {
    return (
      <div className="flex flex-col gap-4 p-6">
        <h1 className="text-2xl leading-tight tracking-tight">أدواتي</h1>
        <Skeleton height={200} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">أدواتي</h1>

      <ToolCard icon={<MessagesSquare size={20} />} title="مكتبة الرسائل"
               subtitle={isManager ? 'قوالب واتساب لكل مرحلة — أضِف، عدّل، وتابع أداءها'
                                    : 'قوالب واتساب جاهزة لكل مرحلة من رحلة العميل'}
               onClick={() => setView('templates')} />

      <ToolCard icon={<Quote size={20} />} title="مكتبة الأدلة"
               subtitle={isManager ? 'حقائق مالية مُوثَّقة تدعم رسائلك — أضِف وعدّل'
                                    : 'حقائق مالية مُوثَّقة تقدر تستشهد بها'}
               onClick={() => setView('citations')} />

      {isManager ? (
        <ToolCard icon={<SearchIcon size={20} />} title="أداة البحث عن عملاء محتملين"
                 subtitle="ابحث عن محلات جديدة عبر خرائط جوجل، وتابع تقدّم البحث"
                 onClick={() => setView('search')} />
      ) : null}
    </div>
  );
}

function ToolCard({ icon, title, subtitle, onClick }: {
  icon: React.ReactNode; title: string; subtitle: string; onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick}
           className="flex items-center gap-3 rounded-card bg-surface-1 p-4 text-start shadow-sm active:scale-[0.99]">
      <div className="grid size-11 shrink-0 place-items-center rounded-full bg-accent-soft text-accent-on-soft">
        {icon}
      </div>
      <div className="flex min-w-0 flex-col">
        <span className="font-medium">{title}</span>
        <span className="truncate text-sm text-text-secondary">{subtitle}</span>
      </div>
      <ChevronRight size={18} className="ms-auto shrink-0 rotate-180 text-text-muted" aria-hidden />
    </button>
  );
}

function BackRow({ onBack, title }: { onBack: () => void; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <button type="button" onClick={onBack} aria-label="رجوع"
             className="grid size-9 shrink-0 place-items-center rounded-full text-text-secondary hover:bg-surface-2">
        <ChevronRight size={18} />
      </button>
      <h1 className="text-xl leading-tight">{title}</h1>
    </div>
  );
}

/* ── مكتبة الرسائل ────────────────────────────────────────────────────────────────────────────── */
function TemplateLibrary({ session, isManager, onBack }: {
  session: AffiliateSession; isManager: boolean; onBack: () => void;
}) {
  const [stages, setStages] = useState<OutreachStage[] | 'loading'>('loading');
  const [stage, setStage] = useState('');
  const [rows, setRows] = useState<MessageTemplate[] | 'loading' | 'failed'>('loading');
  const [stats, setStats] = useState<Record<string, TemplateStat>>({});
  const [editing, setEditing] = useState<MessageTemplate | 'new' | null>(null);

  useEffect(() => {
    outreachStages(session).then((r) => {
      setStages(r.stages);
      if (r.stages.length) setStage((s) => s || r.stages[0].code);
    }).catch(() => setStages([]));
  }, [session]);

  const load = () => {
    if (!stage) return;
    setRows('loading');
    templates(session, stage).then((r) => setRows(r.templates)).catch(() => setRows('failed'));
    templateStats(session, { stageCode: stage }).then((r) => {
      const by: Record<string, TemplateStat> = {};
      for (const s of r.stats) by[s.template_id] = s;
      setStats(by);
    }).catch(() => {});
  };
  useEffect(load, [session, stage]);

  if (editing) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <BackRow onBack={() => setEditing(null)} title={editing === 'new' ? 'قالب جديد' : 'تعديل القالب'} />
        <TemplateForm session={session} stages={stages === 'loading' ? [] : stages}
                     defaultStage={stage} existing={editing === 'new' ? null : editing}
                     onDone={() => { setEditing(null); load(); }} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <BackRow onBack={onBack} title="مكتبة الرسائل" />

      {stages === 'loading' ? <Skeleton height={40} /> : (
        <div className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1">
          {stages.map((s) => (
            <button key={s.code} type="button" onClick={() => setStage(s.code)}
                   className={`shrink-0 rounded-full px-3 py-1.5 text-sm font-medium ${
                     stage === s.code ? 'bg-accent text-accent-contrast'
                                      : 'bg-surface-1 text-text-secondary'}`}>
              {s.name}
            </button>
          ))}
        </div>
      )}

      {isManager ? (
        <Button type="button" onClick={() => setEditing('new')}
               className="flex items-center justify-center gap-2">
          <Plus size={16} /> قالب جديد لهذه المرحلة
        </Button>
      ) : null}

      {rows === 'loading' ? (
        <Skeleton height={220} />
      ) : rows === 'failed' ? (
        <EmptyState title="تعذّرت القراءة" description="لم نستطع جلب القوالب الآن." />
      ) : rows.length === 0 ? (
        <EmptyState title="لا قوالب بهذه المرحلة بعد" />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows
            .slice()
            .sort((a, b) => (stats[b.id]?.advance_rate ?? -1) - (stats[a.id]?.advance_rate ?? -1))
            .map((t) => (
              <TemplateRow key={t.id} template={t} stat={stats[t.id]} isManager={isManager}
                          onEdit={() => setEditing(t)}
                          onDeactivate={async () => { await deactivateTemplate(session, t.id); load(); }} />
            ))}
        </ul>
      )}
    </div>
  );
}

/** A WhatsApp-flavoured bubble — the research's own "preview before send/insert" pattern, applied
 *  here as "preview before you even leave the library", not just at send time (already covered on
 *  the Leads screen). The advance-rate badge is what turns a flat list into the leaderboard the
 *  research recommended folding INTO the list rather than a separate analytics screen. */
function TemplateRow({ template, stat, isManager, onEdit, onDeactivate }: {
  template: MessageTemplate; stat?: TemplateStat; isManager: boolean;
  onEdit: () => void; onDeactivate: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [confirmingDeactivate, setConfirmingDeactivate] = useState(false);

  return (
    <li className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <span className="font-medium">{template.title}</span>
        {stat && stat.uses > 0 ? (
          <Badge tone={stat.advance_rate >= 0.4 ? 'success' : stat.advance_rate >= 0.15 ? 'warning' : 'neutral'}>
            {Math.round(stat.advance_rate * 100)}٪ تقدّم — {stat.uses} استخدام
          </Badge>
        ) : null}
      </div>

      {/* THE BUBBLE — a WhatsApp-flavoured preview, plain text (no rich formatting, matching the
          research's own anti-pattern warning against rich editors on a phone). */}
      <div className="relative max-w-[85%] self-start rounded-2xl rounded-tr-sm bg-success-soft px-3 py-2 text-sm text-success-on-soft">
        {template.body || <span className="italic opacity-70">بلا نص بعد</span>}
      </div>

      <div className="flex items-center gap-1.5">
        <Button type="button" variant="ghost" size="icon" aria-label="نسخ نص القالب"
               onClick={() => {
                 navigator.clipboard?.writeText(template.body).then(() => {
                   setCopied(true); setTimeout(() => setCopied(false), 2000);
                 }).catch(() => {});
               }}>
          {copied ? <Check size={16} className="text-success" /> : <Copy size={16} />}
        </Button>
        {isManager ? (
          <>
            <Button type="button" variant="ghost" size="icon" aria-label="تعديل" onClick={onEdit}>
              <Pencil size={16} />
            </Button>
            {confirmingDeactivate ? (
              <>
                <Button type="button" variant="ghost" className="text-danger"
                       onClick={onDeactivate}>تأكيد التعطيل</Button>
                <Button type="button" variant="ghost" onClick={() => setConfirmingDeactivate(false)}>
                  إلغاء
                </Button>
              </>
            ) : (
              <Button type="button" variant="ghost" size="icon" aria-label="تعطيل"
                     onClick={() => setConfirmingDeactivate(true)}>
                <Ban size={16} className="text-danger" />
              </Button>
            )}
          </>
        ) : null}
      </div>
    </li>
  );
}

function TemplateForm({ session, stages, defaultStage, existing, onDone }: {
  session: AffiliateSession; stages: OutreachStage[]; defaultStage: string;
  existing: MessageTemplate | null; onDone: () => void;
}) {
  const [stageCode, setStageCode] = useState(existing?.stage_code || defaultStage);
  const [title, setTitle] = useState(existing?.title || '');
  const [body, setBody] = useState(existing?.body || '');
  const [kind, setKind] = useState(existing?.kind || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    setBusy(true); setError('');
    try {
      if (existing) await updateTemplate(session, existing.id, { stageCode, title, body, kind });
      else await createTemplate(session, { stageCode, title, body, kind });
      onDone();
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّر حفظ القالب.');
    } finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <label className="flex flex-col gap-1 text-sm text-text-secondary">
        المرحلة
        <select value={stageCode} onChange={(e) => setStageCode(e.target.value)}
               className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm text-text-primary">
          {stages.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
        </select>
      </label>
      <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="عنوان القالب"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <input value={kind} onChange={(e) => setKind(e.target.value)} placeholder="النوع (اختياري)"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={6}
               placeholder="نص الرسالة كما تُرسَل بالضبط"
               className="rounded-md border border-border-strong bg-surface-0 p-3 text-sm" />

      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}

      <Button type="button" disabled={busy || !title.trim() || !stageCode} onClick={save}>
        حفظ
      </Button>
    </div>
  );
}

/* ── مكتبة الأدلة ─────────────────────────────────────────────────────────────────────────────── */
function CitationLibrary({ session, isManager, onBack }: {
  session: AffiliateSession; isManager: boolean; onBack: () => void;
}) {
  const [rows, setRows] = useState<StatCitation[] | 'loading' | 'failed'>('loading');
  const [editing, setEditing] = useState<StatCitation | 'new' | null>(null);

  const load = () => {
    setRows('loading');
    statCitations(session).then((r) => setRows(r.citations)).catch(() => setRows('failed'));
  };
  useEffect(load, [session]);

  if (editing) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <BackRow onBack={() => setEditing(null)} title={editing === 'new' ? 'دليل جديد' : 'تعديل الدليل'} />
        <CitationForm session={session} existing={editing === 'new' ? null : editing}
                     onDone={() => { setEditing(null); load(); }} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <BackRow onBack={onBack} title="مكتبة الأدلة" />

      {isManager ? (
        <Button type="button" onClick={() => setEditing('new')}
               className="flex items-center justify-center gap-2">
          <Plus size={16} /> دليل جديد
        </Button>
      ) : null}

      {rows === 'loading' ? (
        <Skeleton height={220} />
      ) : rows === 'failed' ? (
        <EmptyState title="تعذّرت القراءة" />
      ) : rows.length === 0 ? (
        <EmptyState title="لا أدلة بعد" />
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.map((c) => (
            <li key={c.id} className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
              <span className="font-medium">{c.title}</span>
              <p className="text-sm text-text-secondary">{c.body}</p>
              {c.source_label ? (
                <a href={c.source_url || undefined} target="_blank" rel="noreferrer"
                   className="text-xs text-accent">المصدر: {c.source_label}</a>
              ) : null}
              {isManager ? (
                <div className="flex items-center gap-1.5">
                  <Button type="button" variant="ghost" size="icon" aria-label="تعديل"
                         onClick={() => setEditing(c)}>
                    <Pencil size={16} />
                  </Button>
                  <Button type="button" variant="ghost" size="icon" aria-label="تعطيل"
                         onClick={async () => { await deactivateStatCitation(session, c.id); load(); }}>
                    <Ban size={16} className="text-danger" />
                  </Button>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function CitationForm({ session, existing, onDone }: {
  session: AffiliateSession; existing: StatCitation | null; onDone: () => void;
}) {
  const [title, setTitle] = useState(existing?.title || '');
  const [body, setBody] = useState(existing?.body || '');
  const [sourceLabel, setSourceLabel] = useState(existing?.source_label || '');
  const [sourceUrl, setSourceUrl] = useState(existing?.source_url || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    setBusy(true); setError('');
    try {
      if (existing) await updateStatCitation(session, existing.id, { title, body, sourceLabel, sourceUrl });
      else await createStatCitation(session, { title, body, sourceLabel, sourceUrl });
      onDone();
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّر حفظ الدليل.');
    } finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="عنوان قصير"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={4}
               placeholder="النص الكامل بصيغة رقمية واقعية"
               className="rounded-md border border-border-strong bg-surface-0 p-3 text-sm" />
      <input value={sourceLabel} onChange={(e) => setSourceLabel(e.target.value)}
             placeholder="اسم المصدر المختصر (يظهر بالمنصة)"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <input value={sourceUrl} onChange={(e) => setSourceUrl(e.target.value)} dir="ltr"
             placeholder="رابط المصدر الكامل"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />

      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}

      <Button type="button" disabled={busy || !title.trim() || !body.trim()} onClick={save}>
        حفظ
      </Button>
    </div>
  );
}

/* ── أداة البحث عن عملاء محتملين ─────────────────────────────────────────────────────────────── */
function LeadSearchTool({ session, onBack }: { session: AffiliateSession; onBack: () => void }) {
  const [key, setKey] = useState<PlacesApiKeyInfo | 'loading'>('loading');
  const [jobs, setJobs] = useState<LeadSearchJob[] | 'loading' | 'failed'>('loading');
  const [showKeyForm, setShowKeyForm] = useState(false);
  const [starting, setStarting] = useState(false);

  const load = () => {
    placesApiKey(session).then((k) => { setKey(k); if (!k.set) setShowKeyForm(true); }).catch(() => {});
    setJobs('loading');
    myLeadSearches(session).then((r) => setJobs(r.jobs)).catch(() => setJobs('failed'));
  };
  useEffect(load, [session]);

  // A running job polls itself — the screen must stay honest about live progress without a
  // manual refresh, per the async-job convention the research called out.
  useEffect(() => {
    if (jobs === 'loading' || jobs === 'failed') return;
    const running = jobs.find((j) => j.status === 'running' || j.status === 'queued');
    if (!running) return;
    const id = window.setInterval(() => {
      leadSearchStatus(session, running.id)
        .then((j) => setJobs((cur) => (cur === 'loading' || cur === 'failed' ? cur
          : cur.map((x) => (x.id === j.id ? j : x)))))
        .catch(() => {});
    }, 4000);
    return () => window.clearInterval(id);
  }, [jobs, session]);

  const keyReady = key === 'loading' ? null : key;

  return (
    <div className="flex flex-col gap-4 p-6">
      <BackRow onBack={onBack} title="أداة البحث عن عملاء محتملين" />

      {keyReady && keyReady.set && !showKeyForm ? (
        <div className="flex items-center justify-between rounded-card bg-surface-1 p-4 shadow-sm">
          <span className="text-sm text-text-secondary">مفتاح خرائط جوجل: {keyReady.hint}</span>
          <Button type="button" variant="ghost" onClick={() => setShowKeyForm(true)}>تغيير</Button>
        </div>
      ) : null}

      {!keyReady ? <Skeleton height={56} /> : (!keyReady.set || showKeyForm) ? (
        <PlacesKeyForm session={session} hasKey={keyReady.set}
                       onDone={() => { setShowKeyForm(false); load(); }} />
      ) : null}

      {keyReady && keyReady.set ? (
        starting ? (
          <StartSearchForm session={session} onDone={() => { setStarting(false); load(); }}
                          onCancel={() => setStarting(false)} />
        ) : (
          <Button type="button" onClick={() => setStarting(true)}
                 className="flex items-center justify-center gap-2">
            <Plus size={16} /> ابدأ بحثًا جديدًا
          </Button>
        )
      ) : null}

      {jobs === 'loading' ? (
        <Skeleton height={140} />
      ) : jobs === 'failed' ? (
        <EmptyState title="تعذّرت قراءة عمليات البحث" />
      ) : jobs.length === 0 ? (
        <EmptyState title="ما فيه بحث سابق بعد"
                   description="ابدأ أول بحث لك عن محلات جديدة عبر خرائط جوجل." />
      ) : (
        <ul className="flex flex-col gap-3">
          {jobs.map((j) => <JobRow key={j.id} job={j} />)}
        </ul>
      )}
    </div>
  );
}

const JOB_STATUS_LABEL: Record<string, string> = {
  queued: 'بالانتظار', running: 'يعمل الآن', completed: 'اكتمل', failed: 'فشل',
};

function JobRow({ job }: { job: LeadSearchJob }) {
  const totalUnits = Math.max(1, job.cities.length * Math.max(1, job.keywords.length));
  const done = job.cursor.city * Math.max(1, job.keywords.length) + job.cursor.keyword;
  const pct = job.status === 'completed' ? 100 : Math.min(99, Math.round((done / totalUnits) * 100));

  return (
    <li className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <span className="text-sm">{job.sector_code} — {job.keywords.join('، ')}</span>
        <Badge tone={job.status === 'completed' ? 'success' : job.status === 'failed' ? 'danger'
                    : job.status === 'running' ? 'accent' : 'neutral'}>
          {JOB_STATUS_LABEL[job.status] ?? job.status}
        </Badge>
      </div>
      {job.status === 'running' || job.status === 'queued' ? (
        <div className="h-1.5 overflow-hidden rounded-full bg-surface-0">
          <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${pct}%` }} />
        </div>
      ) : null}
      <div className="flex gap-4 text-xs text-text-secondary">
        <span>وُجد: {job.found_count}</span>
        <span>مكرر: {job.duplicate_count}</span>
      </div>
      {job.error ? <p className="text-xs text-danger">{job.error}</p> : null}
    </li>
  );
}

function PlacesKeyForm({ session, hasKey, onDone }: {
  session: AffiliateSession; hasKey: boolean; onDone: () => void;
}) {
  const [apiKey, setApiKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    setBusy(true); setError('');
    try { await setPlacesApiKey(session, apiKey); onDone(); }
    catch (err) { setError(err instanceof AffiliateRefused ? err.message : 'تعذّر حفظ المفتاح.'); }
    finally { setBusy(false); }
  }
  async function clear() {
    setBusy(true);
    try { await clearPlacesApiKey(session); onDone(); } catch { /* stays as-is */ }
    finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <h2 className="text-sm font-medium text-text-secondary">مفتاح خرائط جوجل الخاص بك</h2>
      <input value={apiKey} onChange={(e) => setApiKey(e.target.value)} dir="ltr"
             placeholder="AIza..."
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      <div className="flex gap-2">
        <Button type="button" disabled={busy || !apiKey.trim()} onClick={save}>حفظ</Button>
        {hasKey ? (
          <Button type="button" variant="ghost" className="text-danger" disabled={busy} onClick={clear}>
            احذف المفتاح
          </Button>
        ) : null}
      </div>
    </div>
  );
}

function StartSearchForm({ session, onDone, onCancel }: {
  session: AffiliateSession; onDone: () => void; onCancel: () => void;
}) {
  const [sectorCode, setSectorCode] = useState('');
  const [keywords, setKeywords] = useState('');
  const [cityName, setCityName] = useState('');
  const [lat, setLat] = useState('');
  const [lng, setLng] = useState('');
  const [radiusKm, setRadiusKm] = useState('5');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit() {
    const latN = Number(lat), lngN = Number(lng);
    if (!sectorCode.trim() || !keywords.trim() || !cityName.trim()
        || !Number.isFinite(latN) || !Number.isFinite(lngN)) {
      setError('عبّي القطاع والكلمات ومدينة واحدة بإحداثياتها على الأقل.');
      return;
    }
    setBusy(true); setError('');
    try {
      await startLeadSearch(session, {
        sectorCode: sectorCode.trim(),
        keywords: keywords.split(/[،,]/).map((k) => k.trim()).filter(Boolean),
        cities: [{ name: cityName.trim(), lat: latN, lng: lngN, w_km: 20, h_km: 20 }],
        radiusKm: Number(radiusKm) || 5,
      });
      onDone();
    } catch (err) {
      setError(err instanceof AffiliateRefused ? err.message : 'تعذّر بدء البحث.');
    } finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
      <input value={sectorCode} onChange={(e) => setSectorCode(e.target.value)}
             placeholder="رمز القطاع (مثال: salons)"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <input value={keywords} onChange={(e) => setKeywords(e.target.value)}
             placeholder="كلمات البحث، مفصولة بفاصلة"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <input value={cityName} onChange={(e) => setCityName(e.target.value)} placeholder="اسم المدينة"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      <div className="flex gap-2">
        <input value={lat} onChange={(e) => setLat(e.target.value)} dir="ltr" placeholder="خط العرض"
               className="h-11 flex-1 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
        <input value={lng} onChange={(e) => setLng(e.target.value)} dir="ltr" placeholder="خط الطول"
               className="h-11 flex-1 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />
      </div>
      <input value={radiusKm} onChange={(e) => setRadiusKm(e.target.value)} dir="ltr"
             placeholder="نطاق البحث (كم)"
             className="h-11 rounded-md border border-border-strong bg-surface-0 px-3 text-sm" />

      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}

      <div className="flex gap-2">
        <Button type="button" disabled={busy} onClick={submit}>ابدأ البحث</Button>
        <Button type="button" variant="ghost" disabled={busy} onClick={onCancel}>إلغاء</Button>
      </div>
    </div>
  );
}
