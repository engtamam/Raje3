/**
 * فريق الإدارة — تعيين أدوار `_platform` لحساب موجود. مبنية يدوياً: `authz-service` لا يملك
 * مسار "اعرض كل من يحمل هذا الدور" أو "اعرض كل الحسابات بتينانت `_platform`" — فقط
 * `GET /subjects/{subject}/roles` لحساب مُعطى معرّفه، و`PUT` يستبدل مصفوفة أدواره كاملة (لا
 * منح/سحب ذرّي). فالشاشة بحث بمعرّف حساب معروف، لا قائمة تُتصفَّح — وهذا حدّ خلفي حقيقي، لا
 * قصور بالواجهة، يُذكر صراحة تحت مربع البحث.
 *
 * الحساب نفسه لا يُنشَأ من هنا أبداً — فقط أدواره تُعدَّل، بعد أن يوجد أصلاً عبر
 * `seed-roles.sh`/آلية مماثلة، بلا تسجيل ذاتي. نفس قرار `AdminDoor.tsx`.
 */
import { useEffect, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Input } from '../rj-ui/Field';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';

const PLATFORM_ROLES: { id: string; label: string }[] = [
  { id: 'platform-owner', label: 'مالك المنصّة' },
  { id: 'platform-affiliates', label: 'المسوّقين' },
  { id: 'platform-operator', label: 'التشغيل' },
  { id: 'platform-support', label: 'الدعم (قراءة فقط)' },
  { id: 'platform-finance', label: 'المالية' },
  { id: 'platform-backup', label: 'النسخ الاحتياطي' },
];

export function AdminTeam({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session).then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const getAction = catalog.services.flatMap((s) => s.actions).find((a) => a.id === 'authz.get_subject_roles');
  const assignAction = catalog.services.flatMap((s) => s.actions).find((a) => a.id === 'authz.assign_roles');

  if (!getAction || !assignAction) {
    return <div className="p-6"><EmptyState title="لا صلاحية لديك لإدارة فريق الإدارة" /></div>;
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">فريق الإدارة وصلاحياتهم</h1>
      <p className="text-sm text-text-secondary">
        ابحث بمعرّف حساب موجود لعرض وتعديل أدواره. لا قائمة تصفّح لكل الفريق — الخلفية لا تعرضها.
      </p>
      <SubjectLookup session={session} getAction={getAction} assignAction={assignAction} />
    </div>
  );
}

interface Assignment { subject: string; tenant: string; roles: string[]; capabilities: string[] }

function SubjectLookup({ session, getAction, assignAction }: {
  session: AdminSession; getAction: AdminAction; assignAction: AdminAction;
}) {
  const [query, setQuery] = useState('');
  const [assignment, setAssignment] = useState<Assignment | 'loading' | 'failed' | null>(null);
  const [draft, setDraft] = useState<Set<string>>(new Set());
  const [arm, setArm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function lookup() {
    if (!query.trim()) return;
    setAssignment('loading');
    setError('');
    try {
      const body = await req<Assignment>(
        getAction.path.replace('{subject}', encodeURIComponent(query.trim())),
        'GET', undefined, session.access_token,
      );
      setAssignment(body);
      setDraft(new Set(body.roles));
    } catch (err) {
      setAssignment('failed');
      setError(err instanceof Error ? err.message : 'تعذّر جلب أدوار هذا الحساب.');
    }
  }

  function toggle(roleId: string) {
    setDraft((prev) => {
      const next = new Set(prev);
      if (next.has(roleId)) next.delete(roleId); else next.add(roleId);
      return next;
    });
  }

  async function save() {
    if (typeof assignment !== 'object' || assignment === null) return;
    setBusy(true);
    setError('');
    try {
      const body = await req<Assignment>(
        assignAction.path.replace('{subject}', encodeURIComponent(assignment.subject)),
        'PUT', { roles: Array.from(draft), capabilities: assignment.capabilities }, session.access_token,
      );
      setAssignment(body);
      setDraft(new Set(body.roles));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر حفظ الأدوار.');
    } finally {
      setBusy(false);
      setArm(false);
    }
  }

  const changed = typeof assignment === 'object' && assignment !== null
    && (draft.size !== assignment.roles.length || Array.from(draft).some((r) => !assignment.roles.includes(r)));

  return (
    <div className="flex flex-col gap-4">
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); lookup(); }}>
        <Input dir="ltr" placeholder="subject id (بريد أو معرّف الحساب)"
              value={query} onChange={(e) => setQuery(e.target.value)} className="flex-1" />
        <Button type="submit" disabled={!query.trim()}>بحث</Button>
      </form>

      {assignment === 'loading' ? <p className="text-sm text-text-secondary">جارٍ البحث…</p> : null}
      {assignment === 'failed' ? <p role="alert" className="text-danger text-sm">{error}</p> : null}

      {typeof assignment === 'object' && assignment !== null ? (
        <div className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4">
          <p className="font-medium" dir="ltr">{assignment.subject}</p>
          <div className="flex flex-col gap-2">
            {PLATFORM_ROLES.map((r) => (
              <label key={r.id} className="flex items-center gap-2">
                <input type="checkbox" checked={draft.has(r.id)} onChange={() => toggle(r.id)}
                      className="h-5 w-5 accent-accent" />
                <span>{r.label}</span>
                <span dir="ltr" className="text-caption text-text-muted">({r.id})</span>
              </label>
            ))}
          </div>
          {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
          <Button type="button" disabled={!changed} onClick={() => setArm(true)} className="self-start">
            حفظ الأدوار
          </Button>
        </div>
      ) : null}

      <ConfirmDialog open={arm} onClose={() => setArm(false)} onConfirm={save} busy={busy}
                    title={typeof assignment === 'object' && assignment
                      ? `تعديل أدوار "${assignment.subject}"؟` : 'تعديل الأدوار؟'}
                    body="سيستبدل هذا كل أدواره الحالية بالمنصّة بالمجموعة المحدَّدة أعلاه فوراً." />
    </div>
  );
}
