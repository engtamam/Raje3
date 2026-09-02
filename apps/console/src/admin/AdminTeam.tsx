/**
 * فريق الإدارة وصلاحياتهم — إعادة بناء كاملة (المرحلة 9.5). الجولة الأولى كانت شاشة بحث فقط
 * لأن `authz-service` لا يملك مساراً لتصفّح كل من يحمل دوراً. لكن `identity-service` يملك دليل
 * أعضاء حقيقياً بنطاق التينانت المستدعي (`GET/POST/PUT/DELETE /api/v1/tenancy/members[/{id}]`،
 * `IDENTITY_MULTI_TENANT` مُفعَّل فعلاً بالنشر) — تينانت المشغّل نفسه `_platform`، فهذي القائمة
 * فريق الإدارة كاملاً، لا بحث بمعرّف معروف مسبقاً.
 *
 * لا حذف من هنا أبداً — إيقاف فقط (`identity.set_member_status`، نفس مبدأ "توقيف لا حذف"
 * المطبَّق بكل مكان بالمنصّة). "إزالة" (`identity.remove_member`) تُلغي عضويته بـ`_platform`
 * تحديداً لا حسابه، فهي مسلَّحة بكتابة معرّفه — الأقرب لإجراء هدّام حقيقي هنا.
 *
 * إضافة عضو تُرسل دعوة (`identity.add_member`) — لا كلمة مرور يضبطها المشغّل أبداً لحساب موجود؛
 * الحساب الجديد يضبط كلمة مروره بنفسه عبر رابط الدعوة (أو التسجيل المباشر لو الوضع
 * `password` بدل `invite`، حسب إعداد النشر — الشاشة تعرض `invite_token` لو رجع، وتصمت لو لا).
 */
import { useEffect, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Input } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { EmptyState } from '../rj-ui/EmptyState';
import { Table, type TableColumn } from '../rj-ui/Table';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';

const PLATFORM_ROLES: { id: string; label: string }[] = [
  { id: 'platform-owner', label: 'مالك المنصّة' },
  { id: 'platform-affiliates', label: 'المسوّقين' },
  { id: 'platform-operator', label: 'التشغيل' },
  { id: 'platform-support', label: 'الدعم (قراءة فقط)' },
  { id: 'platform-finance', label: 'المالية' },
  { id: 'platform-backup', label: 'النسخ الاحتياطي' },
];

interface Member {
  person_id: string; identifier: string | null; roles: string[]; caps: string[];
  status: 'active' | 'suspended'; since: number;
}

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

  const actions = catalog.services.flatMap((s) => s.actions);
  const listAction = actions.find((a) => a.id === 'identity.list_members');
  const addAction = actions.find((a) => a.id === 'identity.add_member');
  const updateAction = actions.find((a) => a.id === 'identity.update_member');
  const statusAction = actions.find((a) => a.id === 'identity.set_member_status');
  const removeAction = actions.find((a) => a.id === 'identity.remove_member');

  if (!listAction) {
    return <NoActionAvailable catalog={catalog} permissionTitle="لا صلاحية لديك لإدارة فريق الإدارة" />;
  }

  return (
    <TeamRoster session={session} listAction={listAction} addAction={addAction}
               updateAction={updateAction} statusAction={statusAction} removeAction={removeAction} />
  );
}

function TeamRoster({ session, listAction, addAction, updateAction, statusAction, removeAction }: {
  session: AdminSession; listAction: AdminAction;
  addAction?: AdminAction; updateAction?: AdminAction; statusAction?: AdminAction; removeAction?: AdminAction;
}) {
  const [members, setMembers] = useState<Member[] | 'loading' | 'failed'>('loading');
  const [editing, setEditing] = useState<Member | null>(null);
  const [armStatus, setArmStatus] = useState<Member | null>(null);
  const [armRemove, setArmRemove] = useState<Member | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');

  function reload() {
    setMembers('loading');
    req<{ tenant: string; members: Member[]; next: string | null }>(
      `${listAction.path}?limit=200`, 'GET', undefined, session.access_token,
    ).then((b) => setMembers(b.members)).catch(() => setMembers('failed'));
  }

  useEffect(reload, [listAction, session]);

  const columns: TableColumn<Member>[] = [
    { key: 'identifier', header: 'الحساب', render: (m) => m.identifier ?? m.person_id },
    { key: 'roles', header: 'الأدوار', render: (m) => (
      <div className="flex flex-wrap gap-1">
        {m.roles.length === 0 ? <span className="text-text-muted">—</span> : m.roles.map((r) => (
          <Badge key={r} tone="accent">{PLATFORM_ROLES.find((p) => p.id === r)?.label ?? r}</Badge>
        ))}
      </div>
    ) },
    { key: 'status', header: 'الحالة', render: (m) => (
      <Badge tone={m.status === 'active' ? 'success' : 'neutral'}>{m.status === 'active' ? 'نشط' : 'موقوف'}</Badge>
    ) },
  ];
  if (updateAction || statusAction || removeAction) {
    columns.push({
      key: 'actions', header: '',
      render: (m) => (
        <div className="flex gap-1.5">
          {updateAction ? (
            <Button type="button" size="sm" variant="ghost" onClick={() => setEditing(m)}>تعديل الأدوار</Button>
          ) : null}
          {statusAction ? (
            <Button type="button" size="sm" variant="ghost" onClick={() => setArmStatus(m)}>
              {m.status === 'active' ? 'إيقاف' : 'تفعيل'}
            </Button>
          ) : null}
          {removeAction ? (
            <Button type="button" size="sm" variant="ghost" onClick={() => setArmRemove(m)}>إزالة</Button>
          ) : null}
        </div>
      ),
    });
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl leading-tight tracking-tight">فريق الإدارة وصلاحياتهم</h1>
        {addAction ? <Button type="button" onClick={() => setShowAdd(true)}>دعوة عضو</Button> : null}
      </div>
      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      <Table columns={columns} rows={members} getRowId={(m) => m.person_id}
            emptyTitle="لا أعضاء بفريق الإدارة بعد" failedTitle="تعذّرت قراءة فريق الإدارة" />

      {addAction ? (
        <AddMemberDialog session={session} action={addAction} open={showAdd}
                         onClose={() => setShowAdd(false)} onAdded={reload} />
      ) : null}
      {updateAction ? (
        <EditRolesDialog session={session} action={updateAction} member={editing}
                        onClose={() => setEditing(null)} onSaved={reload} />
      ) : null}
      {statusAction ? (
        <ConfirmDialog open={armStatus !== null} onClose={() => setArmStatus(null)}
                      onConfirm={async () => {
                        if (!armStatus) return;
                        try {
                          await req(statusAction.path.replace('{person_id}', armStatus.person_id), 'POST',
                                    { status: armStatus.status === 'active' ? 'suspended' : 'active' },
                                    session.access_token);
                          reload();
                        } catch (err) {
                          setError(err instanceof Error ? err.message : 'تعذّر تغيير حالة العضو.');
                        } finally {
                          setArmStatus(null);
                        }
                      }}
                      danger={armStatus?.status === 'active'}
                      title={armStatus ? `${armStatus.status === 'active' ? 'إيقاف' : 'تفعيل'} "${armStatus.identifier ?? armStatus.person_id}"؟` : ''}
                      body={armStatus?.status === 'active'
                        ? 'سيفقد وصوله للوحة الإدارة فوراً — يبقى سجلّه وأدواره كما هي.'
                        : 'سيستعيد وصوله للوحة الإدارة فوراً بنفس أدواره السابقة.'} />
      ) : null}
      {removeAction ? (
        <ConfirmDialog open={armRemove !== null} onClose={() => setArmRemove(null)}
                      onConfirm={async () => {
                        if (!armRemove) return;
                        try {
                          await req(removeAction.path.replace('{person_id}', armRemove.person_id),
                                    'DELETE', undefined, session.access_token);
                          reload();
                        } catch (err) {
                          setError(err instanceof Error ? err.message : 'تعذّرت الإزالة.');
                        } finally {
                          setArmRemove(null);
                        }
                      }}
                      danger confirmText={armRemove?.identifier ?? armRemove?.person_id ?? ''}
                      title={`إزالة "${armRemove?.identifier ?? armRemove?.person_id}" من فريق الإدارة؟`}
                      body="يفقد عضويته بالمنصّة تحديداً فقط — حسابه بحد ذاته يبقى موجوداً إن كان يعمل بمكان آخر." />
      ) : null}
    </div>
  );
}

function AddMemberDialog({ session, action, open, onClose, onAdded }: {
  session: AdminSession; action: AdminAction; open: boolean; onClose: () => void; onAdded: () => void;
}) {
  const [identifier, setIdentifier] = useState('');
  const [roles, setRoles] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [inviteToken, setInviteToken] = useState('');

  useEffect(() => { if (open) { setIdentifier(''); setRoles(new Set()); setError(''); setInviteToken(''); } }, [open]);

  async function submit() {
    if (!identifier.trim()) return;
    setBusy(true);
    setError('');
    try {
      const body = await req<{ member: { person_id: string }; invite_token?: string }>(
        action.path, 'POST', { identifier: identifier.trim(), roles: Array.from(roles) }, session.access_token,
      );
      if (body.invite_token) {
        setInviteToken(body.invite_token);
      } else {
        onAdded();
        onClose();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّرت الدعوة.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <ConfirmDialog open={open} onClose={() => { onAdded(); onClose(); }}
                  onConfirm={inviteToken ? () => { onAdded(); onClose(); } : submit} busy={busy}
                  danger={false} confirmLabel={inviteToken ? 'تم' : 'دعوة'}
                  title="دعوة عضو جديد لفريق الإدارة">
      {inviteToken ? (
        <div className="flex flex-col gap-2">
          <p className="text-sm text-text-secondary">أُرسلت الدعوة. رمزها (يظهر مرة واحدة فقط):</p>
          <p dir="ltr" className="break-all rounded-input bg-surface-2 p-2 font-mono text-sm">{inviteToken}</p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1">
            {/* PHONE, NOT EMAIL — every account on this platform (including this one's own
             *  seed-admin.sh) is identified by phone number; this used to say "email" while
             *  sending the exact same phone-shaped identifier every login door already expects. */}
            <span className="text-label font-medium text-text-secondary">رقم جوال العضو</span>
            <Input dir="ltr" type="tel" inputMode="tel" placeholder="05XXXXXXXX"
                  value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
          </label>
          <div className="flex flex-col gap-2">
            {PLATFORM_ROLES.map((r) => (
              <label key={r.id} className="flex items-center gap-2">
                <input type="checkbox" checked={roles.has(r.id)} className="h-5 w-5 accent-accent"
                      onChange={() => setRoles((prev) => {
                        const next = new Set(prev);
                        if (next.has(r.id)) next.delete(r.id); else next.add(r.id);
                        return next;
                      })} />
                <span>{r.label}</span>
              </label>
            ))}
          </div>
          {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
        </div>
      )}
    </ConfirmDialog>
  );
}

function EditRolesDialog({ session, action, member, onClose, onSaved }: {
  session: AdminSession; action: AdminAction; member: Member | null; onClose: () => void; onSaved: () => void;
}) {
  const [roles, setRoles] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { if (member) { setRoles(new Set(member.roles)); setError(''); } }, [member]);

  if (!member) return null;

  async function submit() {
    setBusy(true);
    setError('');
    try {
      await req(action.path.replace('{person_id}', member!.person_id), 'PUT',
                { roles: Array.from(roles) }, session.access_token);
      onSaved();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر حفظ الأدوار.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <ConfirmDialog open onClose={onClose} onConfirm={submit} busy={busy} danger={false}
                  confirmLabel="حفظ الأدوار" title={`أدوار "${member.identifier ?? member.person_id}"`}>
      <div className="flex flex-col gap-2">
        {PLATFORM_ROLES.map((r) => (
          <label key={r.id} className="flex items-center gap-2">
            <input type="checkbox" checked={roles.has(r.id)} className="h-5 w-5 accent-accent"
                  onChange={() => setRoles((prev) => {
                    const next = new Set(prev);
                    if (next.has(r.id)) next.delete(r.id); else next.add(r.id);
                    return next;
                  })} />
            <span>{r.label}</span>
          </label>
        ))}
      </div>
      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
    </ConfirmDialog>
  );
}
