/**
 * Discount-rule cards — same idea as CouponCards.tsx, for the OTHER kind of discount: one a shop
 * never types a code for. A coupon is redeemed once by someone who has it; a rule fires
 * automatically, every renewal, for as long as the shop still holds the app that earned it —
 * "تسجيل زيارة grants 25% off الحجوزات", forever, no code, no redemption count.
 *
 * BUILT AGAINST base-services' OWN CONFIRMED CONTRACT (v0.19.19, `billing.*_discount_rule` in
 * admin_actions.py) — `owning_key`/`target_key` are the SAME feature/plan keys `apps.ts`'s own
 * `APP_ROWS` already names (`feature.visit`, `feature.bookings`, …), so the two pickers below read
 * from that one registry rather than a free-text field an operator could mistype into silence.
 *
 * THE COMPOSITION RULE IS base-services' OWN CALL, RELAYED HERE FOR THE OPERATOR TO SEE: when a
 * subscription qualifies for more than one rule (or a rule and a coupon), the HIGHEST percent wins
 * — never summed. Two rules of 10% and 20% never make 30%. Said once, on every card, so a rule
 * that LOOKS unused ("عمره ما طبّق") is understood correctly: it may simply never have been the
 * highest offer a subscription qualified for.
 */
import { useState } from 'react';
import { Plus, Pencil, ArrowLeftRight } from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { Modal } from '../rj-ui/Modal';
import { EmptyState } from '../rj-ui/EmptyState';
import { Field, Input, Select } from '../rj-ui/Field';
import { Toggle } from '../rj-ui/Toggle';
import type { AdminAction } from './catalog';
import { req, type AdminSession } from './api';
import { sentenceFor } from '../api';
import { APP_ROWS } from '../apps';

interface DiscountRule {
  id: string; owning_key: string; target_key: string; percent: number; active: boolean;
  starts_at?: number | null; expires_at?: number | null; note?: string; created?: string;
}

// LABEL, NEVER A RAW KEY — same registry `apps.ts` already keeps, so a rule reads
// "تسجيل زيارة → الحجوزات" instead of "feature.visit → feature.bookings" on a screen an
// operator (not a developer) uses day to day. A key with no row here (future app, not yet added
// to APP_ROWS) still renders — the raw key itself — rather than hiding the rule.
function appName(key: string): string {
  return APP_ROWS.find((a) => a.key === key)?.name ?? key;
}

function toDateInput(epoch?: number | null): string {
  if (!epoch) return '';
  return new Date(epoch * 1000).toISOString().slice(0, 10);
}
function fromDateInput(value: string): number | null {
  if (!value) return null;
  return Math.floor(new Date(`${value}T00:00:00`).getTime() / 1000);
}
function dateLine(epoch?: number | null): string {
  if (!epoch) return '—';
  return new Date(epoch * 1000).toLocaleDateString('ar-SA-u-nu-latn');
}

export function DiscountRuleCards({ session, createAction, updateAction, deleteAction, rules, onReload }: {
  session: AdminSession; createAction?: AdminAction; updateAction?: AdminAction;
  deleteAction?: AdminAction; rules: DiscountRule[]; onReload: () => void;
}) {
  const [creating, setCreating] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-text-secondary">
        عند تعدّد القواعد المنطبقة على نفس المحل، أو تداخل قاعدة مع كوبون — <b>الأعلى نسبةً</b> هو
        اللي يُطبَّق، أبداً لا تُجمَع النسب مع بعضها.
      </p>

      {createAction ? (
        <Button type="button" size="sm" className="flex w-fit items-center gap-2" onClick={() => setCreating(true)}>
          <Plus size={14} /> قاعدة خصم جديدة
        </Button>
      ) : null}

      {rules.length === 0 ? (
        <EmptyState title="لا قواعد خصم مُنشأة بعد" />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {rules.map((r) => (
            <DiscountRuleCard key={r.id} session={session} rule={r}
                              updateAction={updateAction} deleteAction={deleteAction} onReload={onReload} />
          ))}
        </div>
      )}

      {createAction ? (
        <DiscountRuleEditDrawer session={session} action={createAction} mode="create"
                                open={creating} onClose={() => setCreating(false)}
                                onSaved={() => { setCreating(false); onReload(); }} />
      ) : null}
    </div>
  );
}

function DiscountRuleCard({ session, rule, updateAction, deleteAction, onReload }: {
  session: AdminSession; rule: DiscountRule;
  updateAction?: AdminAction; deleteAction?: AdminAction; onReload: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [armDelete, setArmDelete] = useState(false);
  const [editing, setEditing] = useState(false);

  async function doDelete() {
    if (!deleteAction) return;
    setBusy(true);
    try {
      await req(deleteAction.path.replace('{rule_id}', encodeURIComponent(rule.id)),
                'DELETE', undefined, session.access_token);
      onReload();
    } finally {
      setBusy(false);
      setArmDelete(false);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-card border border-border-subtle bg-surface-1 p-4 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium">
          <span>{appName(rule.owning_key)}</span>
          <ArrowLeftRight size={14} className="shrink-0 text-text-secondary" />
          <span>{appName(rule.target_key)}</span>
        </div>
        <Badge tone={rule.active ? 'success' : 'neutral'}>{rule.active ? 'فعّالة' : 'مُعطَّلة'}</Badge>
      </div>

      <p className="text-xl font-bold tabular-nums">خصم {rule.percent}%{rule.percent === 100 ? ' — مجاني بالكامل' : ''}</p>

      <ul className="flex flex-col gap-1 text-sm">
        <li className="flex items-center justify-between gap-2">
          <span className="text-text-secondary">مالك من يملك</span>
          <span className="font-medium">{appName(rule.owning_key)}</span>
        </li>
        <li className="flex items-center justify-between gap-2">
          <span className="text-text-secondary">الخصم على</span>
          <span className="font-medium">{appName(rule.target_key)}</span>
        </li>
        <li className="flex items-center justify-between gap-2">
          <span className="text-text-secondary">البداية</span>
          <span className="font-medium">{dateLine(rule.starts_at)}</span>
        </li>
        <li className="flex items-center justify-between gap-2">
          <span className="text-text-secondary">الانتهاء</span>
          <span className="font-medium">{dateLine(rule.expires_at)}</span>
        </li>
      </ul>

      {rule.note ? <p className="text-label text-text-secondary">{rule.note}</p> : null}

      <div className="flex gap-2">
        {updateAction ? (
          <Button type="button" size="sm" variant="outline" className="flex flex-1 items-center justify-center gap-2"
                  disabled={busy} onClick={() => setEditing(true)}>
            <Pencil size={14} /> تعديل
          </Button>
        ) : null}
        {deleteAction ? (
          <Button type="button" size="sm" variant="outline" className="flex-1 text-danger" disabled={busy}
                  onClick={() => setArmDelete(true)}>
            حذف
          </Button>
        ) : null}
      </div>

      <ConfirmDialog open={armDelete} onClose={() => setArmDelete(false)} onConfirm={doDelete}
                    busy={busy} danger title="حذف قاعدة الخصم؟"
                    body="لا رجعة — كل اشتراك يعتمد على هذه القاعدة يرجع لسعره الكامل من الدورة القادمة." />

      {updateAction ? (
        <DiscountRuleEditDrawer session={session} action={updateAction} mode="edit" rule={rule}
                                open={editing} onClose={() => setEditing(false)}
                                onSaved={() => { setEditing(false); onReload(); }} />
      ) : null}
    </section>
  );
}

// EVERY REAL APP KEY apps.ts NAMES — never the base (key: null, not something a rule can target
// or require: الأساس is retired from sale entirely, per this session's own earlier work).
const APP_KEYS = APP_ROWS.filter((a): a is typeof a & { key: string } => a.key !== null);

function DiscountRuleEditDrawer({ session, action, mode, rule, open, onClose, onSaved }: {
  session: AdminSession; action: AdminAction; mode: 'create' | 'edit'; rule?: DiscountRule;
  open: boolean; onClose: () => void; onSaved: () => void;
}) {
  const [owningKey, setOwningKey] = useState(rule?.owning_key ?? APP_KEYS[0]?.key ?? '');
  const [targetKey, setTargetKey] = useState(rule?.target_key ?? APP_KEYS[0]?.key ?? '');
  const [percentText, setPercentText] = useState(String(rule?.percent ?? 25));
  const [active, setActive] = useState(rule?.active ?? true);
  const [startsAt, setStartsAt] = useState(toDateInput(rule?.starts_at));
  const [expiresAt, setExpiresAt] = useState(toDateInput(rule?.expires_at));
  const [note, setNote] = useState(rule?.note ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function save() {
    if (!owningKey || !targetKey) { setError('اختر التطبيقين.'); return; }
    if (owningKey === targetKey) { setError('لا يصح أن يكون التطبيقان نفس التطبيق.'); return; }
    const percent = Number(percentText);
    if (!Number.isInteger(percent) || percent < 0 || percent > 100) {
      setError('النسبة بين 0 و100.'); return;
    }

    setBusy(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        owning_key: owningKey, target_key: targetKey, percent, active,
        starts_at: fromDateInput(startsAt), expires_at: fromDateInput(expiresAt), note,
      };
      const path = mode === 'edit' && rule
        ? action.path.replace('{rule_id}', encodeURIComponent(rule.id)) : action.path;
      await req(path, mode === 'edit' ? 'PATCH' : 'POST', body, session.access_token);
      onSaved();
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر حفظ قاعدة الخصم.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={mode === 'create' ? 'قاعدة خصم جديدة' : 'تعديل قاعدة الخصم'}
           footer={
             <>
               <Button type="button" variant="ghost" onClick={onClose}>إلغاء</Button>
               <Button type="button" disabled={busy} onClick={save}>{busy ? 'جارٍ الحفظ…' : 'حفظ'}</Button>
             </>
           }>
      <div className="flex flex-col gap-4">
        <Field label="لو المحل يملك" htmlFor="rule-owning" hint="التطبيق اللي وجوده يمنح الخصم">
          <Select id="rule-owning" value={owningKey} onChange={(e) => setOwningKey(e.target.value)}>
            {APP_KEYS.map((a) => <option key={a.key} value={a.key}>{a.name}</option>)}
          </Select>
        </Field>

        <Field label="يحصل على خصم في" htmlFor="rule-target" hint="التطبيق اللي ينزل سعره">
          <Select id="rule-target" value={targetKey} onChange={(e) => setTargetKey(e.target.value)}>
            {APP_KEYS.map((a) => <option key={a.key} value={a.key}>{a.name}</option>)}
          </Select>
        </Field>

        <Field label="نسبة الخصم (%)" htmlFor="rule-percent" hint="100 = مجاني بالكامل">
          <Input id="rule-percent" dir="ltr" inputMode="numeric" value={percentText}
                onChange={(e) => setPercentText(e.target.value)} />
        </Field>

        <div className="flex items-center justify-between">
          <span className="text-sm">فعّالة</span>
          <Toggle checked={active} onChange={setActive} ariaLabel="فعّالة" />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="تاريخ البداية" htmlFor="rule-starts" hint="اختياري">
            <Input id="rule-starts" type="date" dir="ltr" value={startsAt}
                  onChange={(e) => setStartsAt(e.target.value)} />
          </Field>
          <Field label="تاريخ الانتهاء" htmlFor="rule-expires" hint="اختياري">
            <Input id="rule-expires" type="date" dir="ltr" value={expiresAt}
                  onChange={(e) => setExpiresAt(e.target.value)} />
          </Field>
        </div>

        <Field label="ملاحظة" htmlFor="rule-note" hint="للمشغّلين فقط، لا يراها العميل">
          <Input id="rule-note" value={note} onChange={(e) => setNote(e.target.value)} />
        </Field>

        {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      </div>
    </Modal>
  );
}
