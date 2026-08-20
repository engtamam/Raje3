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
import {
  AlertTriangle, Cake, Gift, Info, Megaphone, RotateCcw, Tag, type LucideIcon,
} from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { Segmented } from '@base-ui/design-system/Segmented';
import { Badge } from '@base-ui/design-system/Badge';
import { isDenied, isReady, DENIED, hasFailed, isLoading, type Loading } from '../loading';
import { Waiting } from '../Waiting';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { western } from '../digits';

/**
 * `campaigns-service` (app/core/goals.py) sends a NAME, never an emoji — "return", "gift",
 * "megaphone"... the same identifier scheme `nav.ts` already uses for the rail. Rendering it as
 * literal text (which this screen did, Tamam 2026-08-20 — screenshot: an Arabic title with the
 * English word "return" printed right beside it) is what a caller does with a name it never
 * mapped. An unknown name falls back to `Tag` rather than rendering nothing — a wrong icon is a
 * smaller fault than a blank one, and both are more honest than the raw string.
 */
const GOAL_ICONS: Record<string, LucideIcon> = {
  return: RotateCcw,
  gift: Gift,
  megaphone: Megaphone,
  cake: Cake,
  info: Info,
  alert: AlertTriangle,
  tag: Tag,
};

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
  /**
   * The blanks this goal's message has for HIM to fill, by kind and in order — `amount`,
   * `catalogue`, `date`, `code`, `owner`. Read from the template this shop would actually send,
   * so a shop that rewrote its own message gets its own blanks.
   */
  blanks?: string[];
}

interface Preview {
  message?: string;
  reaches?: number;
  excluded?: number;
  too_recent?: number;
  spread_says?: string;
  /** The plan itself, and `refused` is the half the screen never read (ج-4): the sentence was
   *  rendered as advice before the launch and AS THE SUCCESS BANNER after it. A refusal shown in
   *  the place a confirmation goes is a refusal nobody reads as one. */
  spread?: { days?: number; per_day?: number; total?: number; refused?: string };
  why?: string[];
}

/**
 * DOES THIS GOAL'S MESSAGE HAVE A BLANK OF THIS KIND FOR HIM TO FILL? (ط-4)
 *
 * Meta approves the WORDS. The numbered blanks are the only thing a shop decides, and each one
 * belongs to somebody: `system` is ours — his name, the shop, a balance — and never a question;
 * `catalogue` is a tap on his own service list; `amount`/`code`/`date` are typed values with a
 * shape we can check; `owner` is the single free blank, and only where the sentence has nothing
 * but his own words to put there.
 *
 * WHAT THIS REPLACED. The screen drew a free text box for EVERY goal under «سطرك في الرسالة»,
 * and decided the three typed fields from `offers` — a fact about the goal rather than about the
 * message it sends. For four of the six goals that free line reached nothing: `mkt_offer` is «لك
 * خصم {{3}} على {{4}}. ساري حتى {{5}}» and has no room for a sentence at all. He typed one,
 * pressed launch, and never saw his words again. Nothing failed.
 *
 * Pure and exported so the rule is one thing a test can hold, rather than a condition spread
 * across four JSX branches that only a rendered page could check.
 */
export function hasBlank(picked: { blanks?: string[]; goal?: string }, kind: string): boolean {
  return (picked.blanks ?? []).includes(kind);
}

/** What to call the free blank, named by what it fills rather than by where it lands. */
export function freeBlankLabel(goal: string): string {
  return goal === 'announce' ? 'ما الجديد؟' : 'نصّ الرسالة';
}

interface Branch { id: string; name: string; active?: boolean }

interface Service { id: string; name: string }

export function Launch({ session, catalog, onDone }:
    { session: Session; catalog: Catalog; onDone: () => void }) {
  const [goals, setGoals] = useState<Loading<Goal[]>>(undefined);
  // `null` MEANS «STILL READING» HERE — the screen shows a Waiting on it — so the failure needs a
  // field of its own. Sharing one would make a dead peer indistinguishable from a slow one, and
  // «لا أهداف متاحة الآن» is a claim about the product rather than about the read.
  const [goalsFailed, setGoalsFailed] = useState(false);
  const [picked, setPicked] = useState<Goal | null | undefined>(undefined);
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
  const [preview, setPreview] = useState<Preview | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState('');

  /**
   * THE DAY «هنّئ في مناسبة» IS ABOUT, AND THE GOAL HAD NO WAY TO NAME IT.
   *
   * `occasion` is one of the six goals this screen offers; its card reads «رسالة في يوم يخصّه»
   * and the behaviour line the server sends back for it reads «تُرسَل في موعد تحدّده» — a moment
   * HE defines. The screen gave him nothing to define it with.
   *
   * AND THE CAMPAIGN THEN NEVER SENT AT ALL. `occasion` is the one goal whose trigger is
   * `scheduled` (`GOAL_TRIGGER`), and the dispatcher's guard is
   *
   *     if not fire_at or fire_at > now: skipped
   *
   * so `fire_at = 0` is not «send now» — it is «skip, every tick, for ever». The campaign was
   * created, listed as active, previewed correctly, and the banner said تم. Nothing failed, no
   * log said anything, and not one greeting was ever delivered by this product.
   */
  const [occasionOn, setOccasionOn] = useState('');

  /**
   * THE MORNING OF HIS DAY, not its last minute. `expiresAt` below takes 23:59 because an offer
   * «حتى الخميس» is good all Thursday; a greeting works the other way — it belongs at the start of
   * the day, not as it ends.
   */
  const fireAt = (() => {
    if (!occasionOn) return 0;
    const at = Date.parse(`${occasionOn}T08:00:00+03:00`);
    return Number.isNaN(at) ? 0 : Math.floor(at / 1000);
  })();

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
    if (!goalsAction) { setGoals(DENIED); return; }
    call<{ goals: Goal[] }>(session, goalsAction)
      .then((r) => setGoals(r.goals ?? []))
      .catch(() => { setGoalsFailed(true); setGoals([]); });

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
        // AND THE DAY, for the same reason: a greeting scheduled for next month spreads over a
        // different window than one going out now, and he should see that count before pressing.
        fire_at: fireAt,
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

  // «NOT YET» IS NOT «IT FAILED» (م · النمط 1). The guard read `=== null` and the failure
  // handler set `null`, so a failed read rendered this for ever and the sentence written
  // for the failure was unreachable. `undefined` waits; `null` says so.
  if (isLoading(goals)) return <Waiting what="نقرأ أهداف الحملات" />;

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

        {/* THE FREE BLANK — DRAWN ONLY WHERE THE MESSAGE HAS ONE (ط-4).
            
            This box used to appear for every goal, labelled «سطرك في الرسالة». Four of the six
            goals send a template with no free slot at all — `mkt_offer` is «لك خصم {{3}} على
            {{4}}. ساري حتى {{5}}», three typed values and no room for a sentence — so the owner
            wrote one, launched, and his words reached nobody. Nothing failed anywhere.

            Now the server says which blanks exist and this draws exactly those. The label names
            what the blank FILLS rather than promising a place in the message: «ما الجديد؟» for
            an announcement, whose whole content is that blank.

            THE LIMIT IS THE SERVER'S. The counter read «/ 200» while the server refused at 61 —
            a shop wrote three lines, pressed, and was told to shorten what the screen had just
            called fine. Sixty is the template's room. */}
        {hasBlank(picked, 'owner') ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">{freeBlankLabel(picked.goal)}</span>
            <textarea
              value={ownerText}
              maxLength={60}
              rows={2}
              onChange={(e) => { setOwnerText(e.target.value); setPreview(null); }}
              placeholder="مثال: افتتحنا فرعاً في حي الياسمين"
              className="rounded-lg bg-surface-2 p-3 text-sm"
            />
            <span className="text-xs text-text-secondary tabular-nums">
              {ownerText.length} / 60
            </span>
          </label>
        ) : null}

        {/* ── how much ────────────────────────────────────────────────────────────────────
            TWO BUTTONS AND A NUMBER, not a free field. He taps «نسبة» or «مبلغ» and types the
            number; we build «20%» or «50 ريال». A field that accepts anything accepts «خصم كبير»,
            and the send refuses it after he has already decided he is done. */}
        {hasBlank(picked, 'amount') ? (
          <div className="flex flex-col gap-1">
            <span className="text-sm">قيمة الخصم</span>
            <div className="flex items-center gap-2">
              <input
                type="number"
                min={1}
                // 99, WHICH IS WHAT THE SEND ACCEPTS. It said 90 while `_OFFER` in campaigns and
                // `_AMOUNT` in reminders both accept 1-99 — a third number for one rule, and the
                // only one a person ever reads.
                max={99}
                dir="ltr"
                value={western(offerValue).replace(/[^0-9.]/g, '')}
                onChange={(e) => {
                  // FOLD, THEN DROP THE PUNCTUATION. `[^0-9.]` is exactly 0-9 plus a dot, so an
                  // Arabic keyboard's digits were deleted here as he typed the discount — the
                  // box stayed empty on the screen that launches a campaign.
                  const n = western(e.target.value).replace(/[^0-9.]/g, '');
                  setOfferValue(n ? (offerValue.includes('ريال') ? `${n} ريال` : `${n}%`) : '');
                  setPreview(null);
                }}
                className="h-11 w-24 rounded-lg bg-surface-2 px-3 text-center text-sm tabular-nums"
              />
              <Segmented
                ariaLabel="نوع الخصم"
                value={offerValue.includes('ريال') ? 'sar' : 'pct'}
                onChange={(kind) => {
                  const n = western(offerValue).replace(/[^0-9.]/g, '');
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
        {hasBlank(picked, 'date') ? (
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

        {/* ── the day it is about ──────────────────────────────────────────────────────────
            ON THE GOAL, NOT ON A BLANK. Every other control here is drawn from `blanks` — what
            the approved message has room for him to fill. This one is not about the words at all:
            `fire_at` decides WHEN the campaign leaves, and `occasion` is the one goal whose whole
            premise is a day («رسالة في يوم يخصّه»). Reading it off a blank would tie the schedule
            to whichever template Meta happened to approve.

            AND IT MAY BE LEFT EMPTY, which means today. A shop congratulating a customer this
            afternoon is doing something ordinary; the defect was never having the choice. */}
        {picked.goal === 'occasion' ? (
          <label className="flex flex-col gap-1">
            <span className="text-sm">يوم المناسبة</span>
            <input
              type="date"
              value={occasionOn}
              min={new Date().toISOString().slice(0, 10)}
              onChange={(e) => { setOccasionOn(e.target.value); setPreview(null); }}
              dir="ltr"
              className="h-11 rounded-lg bg-surface-2 px-3 text-sm"
            />
            <span className="text-xs text-text-secondary">
              تخرج صباح ذلك اليوم. اتركه فارغاً لترسل الآن.
            </span>
          </label>
        ) : null}

        {/* WHICH SERVICE, when the goal is about one. The cycle lock (§10.9.1) holds back whoever
            took it too recently — and it can only do that if the campaign names the service. */}
        {hasBlank(picked, 'catalogue') ? (
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
            {/* THE REFUSAL LOOKS LIKE A REFUSAL. Same sentence, and the colour is the whole
                difference between «here is the plan» and «this cannot run as configured». */}
            {preview.spread?.refused ? (
              <p className="text-sm text-danger">{preview.spread.refused}</p>
            ) : preview.spread_says ? (
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
              // A PLAN THE SERVER WILL REFUSE IS NOT A PLAN TO PRESS. The refusal names two
              // remedies — shrink the audience, or extend the date — and both are edits on this
              // screen: the button that offers neither is the one that should not be live.
              disabled={busy || !createAction || Boolean(preview.spread?.refused)}
              onClick={async () => {
                if (!createAction || preview.spread?.refused) return;
                setBusy(true); setError('');
                try {
                  await call(session, createAction, {
                    goal: picked.goal, owner_text: ownerText, service_id: serviceId,
                    branch_id: branchId,
                    offer_value: offerValue,
                    service_name: (services ?? []).find((x) => x.id === serviceId)?.name ?? '',
                    expires_at: expiresAt,
                    fire_at: fireAt,
                  });
                  // WHAT HAPPENED, NOT WHAT WAS PLANNED. This used to print `spread_says` as the
                  // confirmation — so a campaign the server refused announced its own refusal in
                  // the voice of a success, and the owner walked away believing it had gone.
                  setSent(`تصل ${preview.reaches ?? 0} عميلاً.`);
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
      {goalsFailed ? (
        <p className="text-sm text-text-secondary">
          تعذّرت قراءة الأهداف الآن، والخلل عندنا. أعد المحاولة بعد قليل.
        </p>
      ) : isDenied(goals) ? (
        <p className="text-sm text-text-secondary">لا يشمل دورك إطلاق الحملات.</p>
      ) : hasFailed(goals) ? (
        // «لا أهداف متاحة» IS A CLAIM ABOUT HIS PLAN. Said after a failed read it sends him to
        // the pricing page for something he already owns.
        <p className="text-sm text-text-secondary">
          تعذّرت قراءة الأهداف الآن — والخلل عندنا. أعد المحاولة بعد قليل.
        </p>
      ) : goals.length === 0 ? (
        <p className="text-sm text-text-secondary">لا أهداف متاحة الآن.</p>
      ) : null}
      {(isReady(goals) ? goals : []).map((g) => (
        <button
          key={g.goal}
          type="button"
          disabled={g.available === false}
          onClick={() => setPicked(g)}
          className="flex items-start gap-3 rounded-card bg-surface-1 p-4 text-start shadow-sm disabled:opacity-60"
        >
          {g.icon ? (() => {
            const Icon = GOAL_ICONS[g.icon!] ?? Tag;
            return <Icon size={20} className="shrink-0" aria-hidden />;
          })() : null}
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
