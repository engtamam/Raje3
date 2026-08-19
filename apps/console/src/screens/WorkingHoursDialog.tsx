/**
 * أوقات الدوام — سياسة واحدة للمنشأة كلها، كل الفروع تشاركها (Tamam, 2026-08-19: "كل الفروع
 * تاخذ نفس النظام"). صلاحية `bookings.manage` وحدها — ليس كل من يقدر يحجز يقدر يعيد تعريف متى
 * يفتح المحل، نفس المسافة بين operations.manage وoperations.record.
 *
 * `0`=الاثنين..`6`=الأحد بالتخزين (نفس ترقيم weekday() اللي يستخدمه availability.Schedule في
 * السيرفر، بلا أي ترجمة) — وهذا الملف يعرضها بترتيب الأحد أولاً لأنه ترتيب الأسبوع عندنا في كل
 * مكان آخر بالتطبيق.
 */
import { useEffect, useState } from 'react';
import { Modal } from '@base-ui/design-system/Modal';
import { Button } from '@base-ui/design-system/Button';
import { setWorkingHours, sentenceFor, type WeeklyHours } from '../api';
import type { Session } from '../session';

// index 0..6 هنا = ترتيب العرض (الأحد أولاً)، والقيمة هي مفتاح weekday() المخزَّن فعلياً.
const DISPLAY_ORDER = [6, 0, 1, 2, 3, 4, 5];
const DAY_LABEL: Record<number, string> = {
  6: 'الأحد', 0: 'الاثنين', 1: 'الثلاثاء', 2: 'الأربعاء', 3: 'الخميس', 4: 'الجمعة', 5: 'السبت',
};

function minutesToTime(m: number): string {
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
}
function timeToMinutes(t: string): number {
  const [h, m] = t.split(':').map(Number);
  return (h || 0) * 60 + (m || 0);
}

export function WorkingHoursDialog({ session, weekly, onClose, onSaved }: {
  session: Session;
  weekly: WeeklyHours;
  onClose: () => void;
  onSaved: (w: WeeklyHours) => void;
}) {
  const [draft, setDraft] = useState<WeeklyHours>(weekly);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { setDraft(weekly); }, [weekly]);

  const set = (day: number, patch: Partial<WeeklyHours[string]>) => {
    setDraft((cur) => ({
      ...cur,
      [day]: { ...(cur[day] ?? { closed: false, start_minute: 480, end_minute: 1320 }), ...patch },
    }));
  };

  const save = async () => {
    setSaving(true);
    setError('');
    try {
      const saved = await setWorkingHours(session, draft);
      onSaved(saved.weekly);
      onClose();
    } catch (e) {
      // 403 هو الحالة المتوقعة لأغلب الموظفين — نفس هذه الجملة تحديداً، لا شاشة عطل.
      setError(sentenceFor(e, 'تعذّر حفظ أوقات الدوام.'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open onClose={onClose} size="lg" title="أوقات الدوام"
          subtitle="سياسة واحدة لكل الفروع — تُضبط هنا مرة، وتُعدَّل وقتما تحتاج">
      <div className="flex flex-col gap-2">
        {DISPLAY_ORDER.map((day) => {
          const d = draft[day] ?? { closed: false, start_minute: 480, end_minute: 1320 };
          return (
            <div key={day} className="flex items-center gap-3 rounded-xl bg-surface-1 px-3 py-2">
              <span className="w-16 shrink-0 text-sm font-semibold">{DAY_LABEL[day]}</span>
              <label className="flex shrink-0 items-center gap-1.5 text-xs text-text-secondary">
                <input type="checkbox" checked={!d.closed}
                       onChange={(e) => set(day, { closed: !e.target.checked })} />
                مفتوح
              </label>
              {!d.closed ? (
                <div className="flex flex-1 items-center gap-2">
                  <input type="time" value={minutesToTime(d.start_minute)}
                        onChange={(e) => set(day, { start_minute: timeToMinutes(e.target.value) })}
                        className="h-9 rounded-lg bg-surface-2 px-2 text-sm" dir="ltr" />
                  <span className="text-text-secondary">إلى</span>
                  <input type="time" value={minutesToTime(d.end_minute)}
                        onChange={(e) => set(day, { end_minute: timeToMinutes(e.target.value) })}
                        className="h-9 rounded-lg bg-surface-2 px-2 text-sm" dir="ltr" />
                </div>
              ) : (
                <span className="flex-1 text-sm text-text-muted">مغلق</span>
              )}
            </div>
          );
        })}

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="mt-2 flex items-center justify-end gap-2 border-t border-border-subtle pt-3">
          <Button variant="ghost" onClick={onClose}>إلغاء</Button>
          <Button disabled={saving} onClick={save}>{saving ? 'جارٍ الحفظ…' : 'حفظ'}</Button>
        </div>
      </div>
    </Modal>
  );
}
