/**
 * A shop owner's visual walkthrough of a WhatsApp Flow (booking today) — the interactive-screen
 * twin of `MessagePreview.tsx`'s own green-bubble preview for a plain text template. Reads the
 * same Flow JSON notification-service already generates for Meta's own upload
 * (`build_booking_flow_json`), rendered through `FlowScreenView` (rj-ui/FlowScreenRenderer.tsx) —
 * an APPROXIMATION, never the real thing (WhatsApp itself is the only place a Flow truly runs),
 * same honesty `FlowScreenRenderer.tsx`'s own header states.
 *
 * `previewAction` IS NOT YET A REAL CATALOG ACTION — the owner-facing route (`require_user`,
 * tenant-scoped) was requested from base-services (session note, 2026-09-11) as the twin of
 * notification-service's existing `require_internal_token`-only `flow-json-for` route; this
 * component is built ahead of that route landing so wiring it later is a one-line change at the
 * call site (passing the real `AdminAction`/`Action` once the id is known) rather than a second
 * build. Until then `previewAction` is simply absent wherever this is used, and the trigger that
 * would open it renders nothing — same "an action missing from the catalog degrades silently"
 * contract every other conditional feature in this console already holds.
 */
import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { Modal } from '../rj-ui/Modal';
import { Button } from '../rj-ui/Button';
import { FlowScreenView, type FlowJson } from '../rj-ui/FlowScreenRenderer';
import { call, type Action } from '../catalog';
import type { Session } from '../session';

export function FlowPreviewModal({ session, previewAction, flowLabel, open, onClose }: {
  session: Session;
  /** The (not-yet-existing) owner-facing route — see this file's own header. */
  previewAction: Action | undefined;
  /** Shown as the modal title — "معاينة فلو الحجز", say — the caller names which flow this is. */
  flowLabel: string;
  open: boolean;
  onClose: () => void;
}) {
  const [flow, setFlow] = useState<FlowJson | 'loading' | 'failed'>('loading');
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!open || !previewAction) return;
    setFlow('loading');
    setStep(0);
    call<FlowJson>(session, previewAction).then(setFlow).catch(() => setFlow('failed'));
  }, [open, previewAction, session]);

  if (!previewAction) return null;

  const screen = flow !== 'loading' && flow !== 'failed' ? flow.screens[step] : undefined;

  return (
    <Modal open={open} onClose={onClose} title={flowLabel}
          subtitle="محاكاة تقريبية لشكل الشاشات — الشكل الحقيقي يظهر داخل واتساب نفسه فقط.">
      {flow === 'loading' ? (
        <p className="text-sm text-text-secondary">جارٍ التحميل…</p>
      ) : flow === 'failed' ? (
        <p role="alert" className="text-danger text-sm">تعذّرت قراءة معاينة الفلو.</p>
      ) : screen ? (
        <div className="flex flex-col gap-4">
          {/* THE PHONE FRAME — a plain WhatsApp-green header bar, same literal green
             MessagePreview.tsx's own bubble uses (#DCF8C6's darker sibling here, a header rather
             than a bubble), so a Flow screen and a text-message preview read as the same product
             surface rather than two unrelated mockups. */}
          <div className="overflow-hidden rounded-2xl border border-border-subtle">
            <div className="bg-[#075E54] px-4 py-2 text-sm font-semibold text-white">واتساب</div>
            <div className="bg-[#ECE5DD] p-4">
              <div className="rounded-xl bg-white p-4 shadow-sm">
                <FlowScreenView screen={screen} />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between gap-2">
            <Button size="sm" variant="ghost" disabled={step === 0}
                   onClick={() => setStep((s) => Math.max(0, s - 1))}>
              <ChevronRight size={14} /> السابقة
            </Button>
            <span className="text-xs text-text-muted">
              شاشة {step + 1} من {flow.screens.length}
            </span>
            <Button size="sm" variant="ghost" disabled={step >= flow.screens.length - 1}
                   onClick={() => setStep((s) => Math.min(flow.screens.length - 1, s + 1))}>
              التالية <ChevronLeft size={14} />
            </Button>
          </div>
        </div>
      ) : (
        <p className="text-sm text-text-secondary">لا شاشات لعرضها.</p>
      )}
    </Modal>
  );
}
