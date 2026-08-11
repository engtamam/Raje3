/**
 * Launching a campaign — the journey that did not exist.
 *
 * THE ENGINE WAS COMPLETE AND HAD NO BUTTON. `campaigns.goals`, `preview`, `create`, `runs` and
 * `pause` were declared, served, tested and deployed; «حملاتي» listed campaigns and explained what
 * a campaign is FOR, which made it a brochure for a feature its owner could not use. Half of what
 * §7.2 and §10.9.1 describe was unreachable from the product.
 *
 * THREE STEPS, AND THE MIDDLE ONE IS THE PRODUCT. Goal, then preview, then send:
 *
 *   THE GOAL comes from the server WITH ITS LOCK — «هذا الهدف مقفل حتى…» is rendered from what the
 *   server returned rather than computed here. A console that decides availability for itself
 *   disagrees with the server the first time either changes, and the owner is the one who finds
 *   out, by pressing a card that then refuses him.
 *
 *   THE PREVIEW IS WHY THIS EXISTS. The real message, the number of PEOPLE it reaches, who was
 *   excluded and why, and how many days it will take. An owner who expected an afternoon and got a
 *   week will say the product is broken and he will be right — nothing told him. The number is
 *   shown while he is deciding, not reconstructed afterwards from a progress bar.
 *
 *   AND THE SEND IS ONE PRESS, on the screen that already shows exactly what will happen.
 *
 * NOTHING IS COMPOSED HERE. The text is the approved template plus one line of his — his own
 * sentence is the only free field, deliberately (§8.4.1): a template Meta approved cannot be
 * rewritten in a browser, and a form asking him to write a message would be a form he abandons.
 */
import { useEffect, useState } from 'react';
import { Button } from '@base-ui/design-system/Button';
import { Badge } from '@base-ui/design-system/Badge';
import { Waiting } from '../Waiting';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Goal {
  goal: string;
  title: string;
  line: string;
  icon?: string;
  available?: boolean;
  unavailable_reason?: string;
  behaviour?: string;
  needs_enabling?: boolean;
}

interface Preview {
  message?: string;
  reaches?: number;
  excluded?: number;
  too_recent?: number;
  spread_says?: string;
  why?: string[];
}

interface Service { id: string; name: string }

export function Launch({ session, catalog, onDone }:
    { session: Session; catalog: Catalog; onDone: () => void }) {
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [picked, setPicked] = useState<Goal | null>(null);
  const [ownerText, setOwnerText] = useState('');
  const [serviceId, setServiceId] = useState('');
  const [services, setServices] = useState<Service[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState('');

  const goalsAction = action(catalog, 'campaigns.goals');
  const previewAction = action(catalog, 'campaigns.preview');
  const createAction = action(catalog, 'campaigns.create');

  useEffect(() => {
    if (!goalsAction) { setGoals([]); return; }
    call<{ goals: Goal[] }>(session, goalsAction)
      .then((r) => setGoals(r.goals ?? []))
      .catch(() => setGoals([]));

    // HIS OWN CATALOGUE, because «عرض على خدمة» must name one of HIS services. Without it that
    // goal would be an untargeted announcement wearing a targeted goal's name — which is exactly
    // the bug the service_id field was added to fix.
    const list = action(catalog, 'operations.list_services');
    if (list) {
      call<{ services: Service[] }>(session, list)
        .then((x) => setServices(x.services ?? []))
        .catch(() => setServices([]));
    }
  }, [session, catalog, goalsAction]);

  const ask = async (goal: Goal) => {
    if (!previewAction) return;
    setBusy(true); setError(''); setPreview(null);
    try {
      setPreview(await call<Preview>(session, previewAction, {
        goal: goal.goal, owner_text: ownerText, service_id: serviceId,
      }));
    } catch (e) {
      // THE SERVER'S SENTENCE, RENDERED AS IT CAME. «لا يوجد قالب مفعّل لهذا الهدف» is actionable;
      // «تعذّر» is not, and inventing our own explanation for somebody else's refusal is how
      // support ends up answering for a rule that does not exist.
      setError(e instanceof Error ? e.message : 'تعذّرت المعاينة.');
    } finally {
      setBusy(false);
    }
  };

  if (goals === null) return <Waiting what="نقرأ أهداف الحملات" />;

  if (sent) {
    return (
      <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 text-center shadow-sm">
        <p className="font-medium">أُطلقت الحملة ✓</p>
        <p className="text-sm text-text-secondary">{sent}</p>
        <div><Button onClick={onDone}>تمام</Button></div>
      </section>
    );
  }

  // ── step 2 and 3: what will happen, and the one press ────────────────────────────────────────
  if (picked) {
    return (
      <section className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
        <div className="flex items-center justify-between gap-2">
          <span className="font-medium">{picked.title}</span>
          <Button variant="ghost" onClick={() => { setPicked(null); setPreview(null); setError(''); }}>
            تغيير الهدف
          </Button>
        </div>
        {picked.behaviour ? (
          <p className="text-sm text-text-secondary">{picked.behaviour}</p>
        ) : null}

        {/* THE ONE FREE FIELD, AND ITS LIMIT IS ON SCREEN. Two hundred characters is the template's
            room, not a preference — a longer line is refused by the send, and finding that out
            after writing three lines is finding it out too late. */}
        <label className="flex flex-col gap-1">
          <span className="text-sm">سطرك في الرسالة</span>
          <textarea
            value={ownerText}
            maxLength={200}
            rows={2}
            onChange={(e) => { setOwnerText(e.target.value); setPreview(null); }}
            placeholder="مثال: خصم 20% على غسيل السيارة حتى الخميس"
            className="rounded-lg bg-surface-2 p-3 text-sm"
          />
          <span className="text-xs text-text-secondary tabular-nums">
            {ownerText.length} / 200
          </span>
        </label>

        {/* WHICH SERVICE, when the goal is about one. The cycle lock (§10.9.1) holds back whoever
            took it too recently — and it can only do that if the campaign names the service. */}
        {picked.goal === 'service_offer' ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">على أي خدمة؟</span>
            <select
              value={serviceId}
              onChange={(e) => { setServiceId(e.target.value); setPreview(null); }}
              className="h-11 rounded-lg bg-surface-2 px-3 text-sm"
            >
              <option value="">اختر خدمة</option>
              {services.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        ) : null}

        {preview ? (
          <div className="flex flex-col gap-2 rounded-lg bg-surface-2 p-3">
            {/* THE MESSAGE AS IT WILL ARRIVE — rendered, not described. */}
            <p className="whitespace-pre-wrap text-sm">{preview.message}</p>
            <p className="text-sm">
              تصل <b className="tabular-nums">{preview.reaches ?? 0}</b> عميلاً
            </p>
            {/* SHOWN ONLY WHEN NON-ZERO. A permanent «0 مستثنى» is noise, and noise is what teaches
                a person to stop reading the area where the real number appears. */}
            {preview.excluded ? (
              <p className="text-xs text-text-secondary">
                {preview.excluded} لم يوافقوا على التسويق أو تجاوزوا حدّهم اليوم.
              </p>
            ) : null}
            {preview.too_recent ? (
              <p className="text-xs text-text-secondary">
                {preview.too_recent} أخذوا هذه الخدمة قريباً — لا نعرض عليهم ما اشتروه للتوّ.
              </p>
            ) : null}
            {preview.spread_says ? (
              <p className="text-sm text-accent-on-soft">{preview.spread_says}</p>
            ) : null}
          </div>
        ) : null}

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex flex-wrap gap-2">
          {!preview ? (
            <Button disabled={busy} onClick={() => void ask(picked)}>اعرض ما سيصل</Button>
          ) : (
            <Button
              disabled={busy || !createAction}
              onClick={async () => {
                if (!createAction) return;
                setBusy(true); setError('');
                try {
                  await call(session, createAction, {
                    goal: picked.goal, owner_text: ownerText, service_id: serviceId,
                  });
                  setSent(preview.spread_says
                    || `تصل ${preview.reaches ?? 0} عميلاً.`);
                } catch (e) {
                  setError(e instanceof Error ? e.message : 'تعذّر الإطلاق.');
                } finally {
                  setBusy(false);
                }
              }}
            >
              أطلق الحملة
            </Button>
          )}
          <Button variant="ghost" onClick={onDone}>إلغاء</Button>
        </div>
      </section>
    );
  }

  // ── step 1: what does he want to achieve ─────────────────────────────────────────────────────
  return (
    <section className="flex flex-col gap-2">
      <p className="text-sm text-text-secondary">ماذا تريد أن تحقّق؟</p>
      {goals.length === 0 ? (
        <p className="text-sm text-text-secondary">لا أهداف متاحة الآن.</p>
      ) : null}
      {goals.map((g) => (
        <button
          key={g.goal}
          type="button"
          disabled={g.available === false}
          onClick={() => setPicked(g)}
          className="flex items-start gap-3 rounded-card bg-surface-1 p-4 text-start shadow-sm disabled:opacity-60"
        >
          {g.icon ? <span className="text-xl leading-none">{g.icon}</span> : null}
          <span className="flex min-w-0 flex-col gap-0.5">
            <span className="font-medium">{g.title}</span>
            <span className="text-sm text-text-secondary">{g.line}</span>
            {/* LOCKED, AND THE REASON IS ON THE CARD — never in a tooltip and never in a dialog
                after he presses. A card that looks pressable and then refuses is worse than one
                that says so before he reaches for it. */}
            {g.available === false && g.unavailable_reason ? (
              <span className="mt-1 text-xs text-text-secondary">{g.unavailable_reason}</span>
            ) : null}
            {g.needs_enabling ? <Badge tone="warning">يحتاج تفعيل قالبه</Badge> : null}
          </span>
        </button>
      ))}
    </section>
  );
}
