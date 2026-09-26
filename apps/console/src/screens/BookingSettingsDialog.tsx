/**
 * إعدادات الحجوزات — نافذة واحدة بتبويبين، لا زران منفصلان بواجهة مزدحمة أصلاً. كانا يعيشان في
 * ملفين مستقلين (WorkingHoursDialog.tsx وAssignmentSettingsDialog.tsx، كل واحد بزره الدائري
 * الخاص بجانب الآخر) — دُمجا هنا بطلب مباشر: نفس المساحة، تكرار أقل، ومنظر أهدأ.
 *
 * كل تبويب يحمل مسودّته وخطأه وزر حفظه الخاص — حفظ أوقات الدوام لا يستلزم أن يكون إعداد التوزيع
 * صالحاً، والعكس، فلكل واحد فعل حفظ مستقل — لكن غلاف واحد (Modal)، وتبديل Segmented واحد، وزر
 * «إلغاء» واحد يغلق الاثنين معاً.
 */
import { useEffect, useState } from 'react';
import { Modal } from '../rj-ui/Modal';
import { Button } from '../rj-ui/Button';
import { GripVertical } from 'lucide-react';
import { Segmented } from '../rj-ui/Segmented';
import {
  setAssignmentSettings, setWorkingHours, sentenceFor,
  type AssignmentSettings, type FieldOperator, type WeeklyHours,
} from '../api';
import type { Session } from '../session';
import { action, type Catalog } from '../catalog';
import { useOperatorI18n, tf } from '../operator-i18n';
import './booking-settings-dialog-i18n';

// Same display order and day naming used in WorkingHoursDialog.tsx's predecessor — Sunday first,
// same weekday() numbering actually stored, with no translation applied to it.
const DISPLAY_ORDER = [6, 0, 1, 2, 3, 4, 5];
function dayLabel(t: (key: string) => string, day: number): string {
  return t(`bookingSettings.day.${day}`);
}
function minutesToTime(m: number): string {
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}
function timeToMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return (h || 0) * 60 + (m || 0);
}

function algorithms(t: (key: string) => string): { value: AssignmentSettings['algorithm']; label: string; hint: string }[] {
  return [
    { value: 'nearest', label: t('bookingSettings.algo.nearest.label'),
     hint: t('bookingSettings.algo.nearest.hint') },
    { value: 'least_loaded', label: t('bookingSettings.algo.leastLoaded.label'),
     hint: t('bookingSettings.algo.leastLoaded.hint') },
    { value: 'manual_order', label: t('bookingSettings.algo.manualOrder.label'),
     hint: t('bookingSettings.algo.manualOrder.hint') },
  ];
}

export function BookingSettingsDialog({ session, catalog, weekly, assignment, staff, onClose, onHoursSaved, onAssignmentSaved }: {
  session: Session;
  catalog: Catalog;
  weekly: WeeklyHours;
  assignment: AssignmentSettings;
  /** كل الموظفين النشطين بدور ميداني — نفس المجموعة اللي «تلقائي» يختار من بينها فعلياً. */
  staff: FieldOperator[];
  onClose: () => void;
  onHoursSaved: (w: WeeklyHours) => void;
  onAssignmentSaved: (s: AssignmentSettings) => void;
}) {
  const { t } = useOperatorI18n();
  const ALGORITHMS = algorithms(t);
  const [tab, setTab] = useState<'hours' | 'assignment'>('hours');

  // ── أوقات الدوام ──────────────────────────────────────────────────────────────────────────
  const [hoursDraft, setHoursDraft] = useState<WeeklyHours>(weekly);
  const [hoursSaving, setHoursSaving] = useState(false);
  const [hoursError, setHoursError] = useState('');
  useEffect(() => { setHoursDraft(weekly); }, [weekly]);

  const setDay = (day: number, patch: Partial<WeeklyHours[string]>) => {
    setHoursDraft((cur) => ({
      ...cur,
      [day]: { ...(cur[day] ?? { closed: false, start_minute: 480, end_minute: 1320 }), ...patch },
    }));
  };
  const saveHours = async () => {
    setHoursSaving(true);
    setHoursError('');
    try {
      const saved = await setWorkingHours(session, hoursDraft);
      onHoursSaved(saved.weekly);
      onClose();
    } catch (e) {
      setHoursError(sentenceFor(e, t('bookingSettings.hours.saveFailed')));
    } finally {
      setHoursSaving(false);
    }
  };

  // ── طريقة التوزيع ─────────────────────────────────────────────────────────────────────────
  const [assignDraft, setAssignDraft] = useState<AssignmentSettings>(assignment);
  const [assignSaving, setAssignSaving] = useState(false);
  const [assignError, setAssignError] = useState('');
  useEffect(() => { setAssignDraft(assignment); }, [assignment]);

  const ordered = [
    ...assignDraft.manual_order.map((id) => staff.find((s) => s.id === id)).filter((s): s is FieldOperator => Boolean(s)),
    ...staff.filter((s) => !assignDraft.manual_order.includes(s.id)),
  ];
  const move = (id: string, dir: -1 | 1) => {
    const current = ordered.map((s) => s.id);
    const i = current.indexOf(id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= current.length) return;
    [current[i], current[j]] = [current[j], current[i]];
    setAssignDraft((cur) => ({ ...cur, manual_order: current }));
  };
  const saveAssignment = async () => {
    setAssignSaving(true);
    setAssignError('');
    try {
      const saved = await setAssignmentSettings(session, assignDraft);
      onAssignmentSaved(saved);
      onClose();
    } catch (e) {
      setAssignError(sentenceFor(e, t('bookingSettings.assignment.saveFailed')));
    } finally {
      setAssignSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} size="lg" title={t('bookingSettings.title')}>
      <div className="flex flex-col gap-4">
        <Segmented
          ariaLabel={t('bookingSettings.tabsAriaLabel')}
          value={tab}
          onChange={(v) => setTab(v as 'hours' | 'assignment')}
          options={[
            { value: 'hours', label: t('bookingSettings.tab.hours') },
            { value: 'assignment', label: t('bookingSettings.tab.assignment') },
          ]}
        />

        {tab === 'hours' ? (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-text-secondary">{t('bookingSettings.hours.policyHint')}</p>
            <div className="flex flex-col gap-2">
              {DISPLAY_ORDER.map((day) => {
                const d = hoursDraft[day] ?? { closed: false, start_minute: 480, end_minute: 1320 };
                return (
                  // A ROW THAT WRAPS INSTEAD OF SPILLING — see this dialog's own predecessor's
                  // history: a phone at 430px needs the day label, "Open", and two time inputs
                  // on their own line when they cannot all fit on one.
                  <div key={day} className="flex flex-wrap items-center gap-3 rounded-xl bg-surface-1 px-3 py-2">
                    <span className="w-16 shrink-0 text-sm font-semibold">{dayLabel(t, day)}</span>
                    <label className="flex shrink-0 items-center gap-1.5 text-xs text-text-secondary">
                      <input type="checkbox" checked={!d.closed}
                            onChange={(e) => setDay(day, { closed: !e.target.checked })} />
                      {t('bookingSettings.hours.open')}
                    </label>
                    {!d.closed ? (
                      <div className="flex min-w-[220px] flex-1 items-center gap-2">
                        <input type="time" value={minutesToTime(d.start_minute)}
                              onChange={(e) => setDay(day, { start_minute: timeToMinutes(e.target.value) })}
                              className="h-9 rounded-lg bg-surface-2 px-2 text-sm" dir="ltr" />
                        <span className="text-text-secondary">{t('bookingSettings.hours.to')}</span>
                        <input type="time" value={minutesToTime(d.end_minute)}
                              onChange={(e) => setDay(day, { end_minute: timeToMinutes(e.target.value) })}
                              className="h-9 rounded-lg bg-surface-2 px-2 text-sm" dir="ltr" />
                      </div>
                    ) : (
                      <span className="flex-1 text-sm text-text-muted">{t('bookingSettings.hours.closed')}</span>
                    )}
                  </div>
                );
              })}
            </div>
            {hoursError ? <p className="text-sm text-danger">{hoursError}</p> : null}
            <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
              <Button variant="ghost" onClick={onClose}>{t('bookingSettings.cancel')}</Button>
              {action(catalog, 'bookings.set_working_hours') ? (
                <Button disabled={hoursSaving} onClick={saveHours}>{hoursSaving ? t('bookingSettings.saving') : t('bookingSettings.save')}</Button>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <p className="text-sm text-text-secondary">{t('bookingSettings.assignment.hint')}</p>
            <Segmented
              size="sm"
              ariaLabel={t('bookingSettings.assignment.algoAriaLabel')}
              value={assignDraft.algorithm}
              onChange={(v) => setAssignDraft((cur) => ({ ...cur, algorithm: v as AssignmentSettings['algorithm'] }))}
              options={ALGORITHMS}
            />
            <p className="text-sm text-text-secondary">
              {ALGORITHMS.find((a) => a.value === assignDraft.algorithm)?.hint}
            </p>

            {assignDraft.algorithm === 'manual_order' ? (
              staff.length === 0 ? (
                <p className="text-sm text-text-muted">{t('bookingSettings.assignment.noStaff')}</p>
              ) : (
                <ul className="flex flex-col gap-1.5">
                  {ordered.map((s, i) => (
                    <li key={s.id}
                       className="flex items-center gap-2 rounded-xl bg-surface-1 px-3 py-2 text-sm">
                      <GripVertical size={14} aria-hidden className="shrink-0 text-text-muted" />
                      <span className="min-w-0 flex-1 truncate">{s.name}</span>
                      <button type="button" disabled={i === 0} onClick={() => move(s.id, -1)}
                             aria-label={tf(t, 'bookingSettings.assignment.moveUp', { name: s.name })}
                             className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-text-secondary disabled:opacity-30">
                        ↑
                      </button>
                      <button type="button" disabled={i === ordered.length - 1} onClick={() => move(s.id, 1)}
                             aria-label={tf(t, 'bookingSettings.assignment.moveDown', { name: s.name })}
                             className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-2 text-text-secondary disabled:opacity-30">
                        ↓
                      </button>
                    </li>
                  ))}
                </ul>
              )
            ) : null}

            {assignError ? <p className="text-sm text-danger">{assignError}</p> : null}
            <div className="flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
              <Button variant="ghost" onClick={onClose}>{t('bookingSettings.cancel')}</Button>
              {action(catalog, 'bookings.set_assignment_settings') ? (
                <Button disabled={assignSaving} onClick={saveAssignment}>{assignSaving ? t('bookingSettings.saving') : t('bookingSettings.save')}</Button>
              ) : null}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}
