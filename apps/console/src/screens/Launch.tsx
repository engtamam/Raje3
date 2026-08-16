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
import { Segmented } from '@base-ui/design-system/Segmented';
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
  /** Whether this goal promises something — and therefore must name the day it stops. */
  offers?: boolean;
}

interface Preview {
  message?: string;
  reaches?: number;
  excluded?: number;
  too_recent?: number;
  spread_says?: string;
  why?: string[];
}

interface Branch { id: string; name: string; active?: boolean }

interface Service { id: string; name: string }

export function Launch({ session, catalog, onDone }:
    { session: Session; catalog: Catalog; onDone: () => void }) {
  const [goals, setGoals] = useState<Goal[] | null>(null);
  const [picked, setPicked] = useState<Goal | null>(null);
  const [ownerText, setOwnerText] = useState('');
  const [serviceId, setServiceId] = useState('');
  /**
   * WHEN THE OFFER STOPS. «لا افتراض له» (§10.9.1) — we do not pick a date for him, because a
   * discount whose end we chose is a discount he honours at the till on a day he did not agree to.
   *
   * IT WAS NOT ON THIS SCREEN AT ALL, and three of the six goals refuse without it: «عرض على
   * خدمة»، «رجّع اللي غابوا»، «كافئ المخلصين» each answered «حدّد تاريخ انتهاء العرض» to a screen
   * that had no field to answer with. Half the campaign engine was unreachable.
   */
  const [endsOn, setEndsOn] = useState('');
  /**
   * THE DISCOUNT, AS A VALUE RATHER THAN A SENTENCE. It used to live inside his one free line, so
   * «خصم كبير» reached customers as a promise nobody could be held to, and «٢٠٪» reached them in
   * digits half the phones in this market render badly. Typed, we phrase it the same way every
   * time and refuse a number that cannot be honoured.
   */
  // arabic-indic-digits: intentional — «٢٠٪» appears in the note above as the shape we refuse.
  const [offerValue, setOfferValue] = useState('');
  const [services, setServices] = useState<Service[] | null>([]);
  // HIS BRANCHES, and the empty list is the common case — one branch, or a role that may not read
  // them. The picker below simply does not render then, which is right: a shop with one place has
  // no targeting decision to make, and a control offering one option is a control that lies about
  // having a choice.
  const [branches, setBranches] = useState<Branch[] | null>([]);
  const [branchId, setBranchId] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState('');

  /** The chosen day, at its last minute in Riyadh — an offer «حتى الخميس» is good all Thursday. */
  const expiresAt = (() => {
    if (!endsOn) return 0;
    const at = Date.parse(`${endsOn}T23:59:59+03:00`);
    return Number.isNaN(at) ? 0 : Math.floor(at / 1000);
  })();

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
        .catch(() => setServices(null));
    }

    // AND HIS BRANCHES, for the same reason: a campaign aimed at one of them must name it, and a
    // name this screen invented would reach nobody.
    const brs = action(catalog, 'operations.list_branches');
    if (brs) {
      call<{ branches: Branch[] }>(session, brs)
        .then((x) => setBranches((x.branches ?? []).filter((b) => b.active !== false)))
        .catch(() => setBranches(null));
    }
  }, [session, catalog, goalsAction]);

  const ask = async (goal: Goal) => {
    if (!previewAction) return;
    setBusy(true); setError(''); setPreview(null);
    try {
      setPreview(await call<Preview>(session, previewAction, {
        goal: goal.goal, owner_text: ownerText, service_id: serviceId,
        // THE BRANCH IS IN THE PREVIEW TOO, and that is the whole point of previewing: the count
        // he decides on must be the count that goes out.
        branch_id: branchId,
        offer_value: offerValue,
        service_name: (services ?? []).find((x) => x.id === serviceId)?.name ?? '',
        // CARRIED INTO THE PREVIEW TOO, not only into the launch: the spread refuses a plan that
        // would still be sending after the offer has ended, and that refusal is only useful
        // BEFORE he presses.
        expires_at: expiresAt,
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

        {/* THE ONE FREE FIELD, AND ITS LIMIT IS THE SERVER'S. The counter read «/ 200» while the
            server refused at 61 — so a shop wrote three lines, pressed, and was told to shorten
            something the screen had just told it was fine. Sixty is the template's room. */}
        <label className="flex flex-col gap-1">
          <span className="text-sm">سطرك في الرسالة</span>
          <textarea
            value={ownerText}
            maxLength={60}
            rows={2}
            onChange={(e) => { setOwnerText(e.target.value); setPreview(null); }}
            placeholder="مثال: غسيل خارجي وداخلي"
            className="rounded-lg bg-surface-2 p-3 text-sm"
          />
          <span className="text-xs text-text-secondary tabular-nums">
            {ownerText.length} / 60
          </span>
        </label>

        {/* ── how much ────────────────────────────────────────────────────────────────────
            TWO BUTTONS AND A NUMBER, not a free field. He taps «نسبة» or «مبلغ» and types the
            number; we build «20%» or «50 ريال». A field that accepts anything accepts «خصم كبير»,
            and the send refuses it after he has already decided he is done. */}
        {picked.offers ? (
          <div className="flex flex-col gap-1">
            <span className="text-sm">قيمة الخصم</span>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                max={90}
                dir="ltr"
                value={offerValue.replace(/[^0-9.]/g, '')}
                onChange={(e) => {
                  const n = e.target.value.replace(/[^0-9.]/g, '');
                  setOfferValue(n ? (offerValue.includes('ريال') ? `${n} ريال` : `${n}%`) : '');
                  setPreview(null);
                }}
                className="h-11 w-24 rounded-lg bg-surface-2 px-3 text-center text-sm tabular-nums"
              />
              <Segmented
                ariaLabel="نوع الخصم"
                value={offerValue.includes('ريال') ? 'sar' : 'pct'}
                onChange={(kind) => {
                  const n = offerValue.replace(/[^0-9.]/g, '');
                  setOfferValue(n ? (kind === 'sar' ? `${n} ريال` : `${n}%`) : '');
                  setPreview(null);
                }}
                options={[{ value: 'pct', label: '%' }, { value: 'sar', label: 'ريال' }]}
              />
            </div>
            <span className="text-xs text-text-secondary">
              يظهر في الرسالة كما هو — {offerValue || '20%'}.
            </span>
          </div>
        ) : null}

        {/* ── when it stops ────────────────────────────────────────────────────────────────
            NO DEFAULT, DELIBERATELY (§10.9.1). A date we picked is a date he honours at the till
            without having agreed to it — and «إلى متى؟» is the one question a customer asks about
            an offer. */}
        {picked.offers ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">العرض ساري حتى</span>
            <input
              type="date"
              value={endsOn}
              min={new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)}
              onChange={(e) => { setEndsOn(e.target.value); setPreview(null); }}
              dir="ltr"
              className="h-11 rounded-lg bg-surface-2 px-3 text-sm"
            />
            <span className="text-xs text-text-secondary">
              يظهر لعميلك في الرسالة وفي صفحته، ويسقط بعده تلقائياً.
            </span>
          </label>
        ) : null}

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
              {(services ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        ) : null}

        {/* WHICH BRANCH — only for a shop that has more than one, and «كل الفروع» stays the
            default. Changing it drops the preview: a count computed for the whole chain sitting
            under a branch's name is the exact kind of wrong that nobody notices. */}
        {(branches ?? []).length > 1 ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">لأي فرع؟</span>
            <select
              value={branchId}
              onChange={(e) => { setBranchId(e.target.value); setPreview(null); }}
              className="h-11 rounded-lg bg-surface-2 px-3 text-sm"
            >
              <option value="">كل الفروع</option>
              {(branches ?? []).map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
            <span className="text-xs text-text-secondary">
              يصل من زار هذا الفرع آخر مرة — والعميل ينتقل مع فرعه بأول زيارة.
            </span>
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
            {/* WHY THIS AUDIENCE AND NOT ANOTHER — the server's own reasons, and the screen
                declared this field for months without ever rendering it. An owner who cannot see
                why 47 became 47 has no way to trust the number. */}
            {(preview.why ?? []).map((line) => (
              <p key={line} className="text-xs text-text-secondary">{line}</p>
            ))}
          </div>
        ) : null}

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex flex-wrap gap-2">
          {!preview ? (
            // REFUSED HERE RATHER THAN BY THE SERVER. He is looking at the field; a round trip to
            // be told to fill it in is a round trip that teaches him nothing.
            <Button disabled={busy || (picked.offers && (!endsOn || !offerValue))}
                    onClick={() => void ask(picked)}>اعرض ما سيصل</Button>
          ) : (
            <Button
              disabled={busy || !createAction}
              onClick={async () => {
                if (!createAction) return;
                setBusy(true); setError('');
                try {
                  await call(session, createAction, {
                    goal: picked.goal, owner_text: ownerText, service_id: serviceId,
                    branch_id: branchId,
                    offer_value: offerValue,
                    service_name: (services ?? []).find((x) => x.id === serviceId)?.name ?? '',
                    expires_at: expiresAt,
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
