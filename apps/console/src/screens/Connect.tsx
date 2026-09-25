/**
 * Connecting WhatsApp — the pane inside «حسابي», and the one screen whose timing is a hard limit.
 *
 * META'S CODE LIVES ABOUT THIRTY SECONDS. There is no queue for it and no retry: it is exchanged
 * inside the request that carries it or the owner starts the whole journey again. Everything here
 * is shaped by that.
 *
 *   · Meta's window opens OVER this screen and we never navigate to it. A navigation unmounts the
 *     listener, and the message carrying the code arrives at a page that no longer exists.
 *   · The moment the message lands we post it. No confirmation step, no "review and continue" —
 *     a screen asking him to press one more button spends a third of the code's life.
 *   · A stop shows the EXACT step he stopped at, not a failure. "Try again" costs him the entire
 *     popup journey to learn what one sentence could have told him.
 *
 * AND CLOSING THE POPUP IS NOT ALWAYS A CANCELLATION. The last step means Meta considers the
 * signup DONE — the account exists. The backend already classifies this; the screen only has to
 * not overrule it, which is why it renders the sentence the server sent rather than deciding for
 * itself what a CANCEL means.
 */
import { useEffect, useState } from 'react';
import { DENIED, hasFailed, isDenied, isLoading, type Loading } from '../loading';
import { Badge } from '../rj-ui/Badge';
import { Card } from '../rj-ui/Card';
import { Button } from '../rj-ui/Button';
import { action, call, type Catalog } from '../catalog';
import { loadMetaSdk, metaSdk, SIGNUP_EXTRAS, type MetaConfig, type SdkState } from '../meta';
import type { Session } from '../session';
import { digitsOnly } from '../digits';
import { useOperatorI18n, tf } from '../operator-i18n';
import './connect-i18n';

/**
 * THE WHATSAPP GLYPH, INLINED — this card used to say «غير مربوط» / «اربط واتساب» with no mark
 * on it at all, so a screenshot of it read as an unlabelled status card about nothing in
 * particular; the one thing giving it away was the word itself, in text, twice. A single fixed
 * brand-green circle (WhatsApp's own colour, never themed) is the fastest thing a reader
 * recognises on this whole pane.
 */
function WhatsAppMark() {
  return (
    <span
      className="grid size-9 shrink-0 place-items-center rounded-full"
      style={{ background: '#25D366' }}
      aria-hidden
    >
      <svg viewBox="0 0 24 24" width={18} height={18} fill="#fff">
        <path d="M17.6 6.32A7.85 7.85 0 0 0 12.05 4c-4.34 0-7.87 3.53-7.87 7.87 0 1.4.37 2.76 1.07 3.95L4.1 20l4.3-1.12a7.9 7.9 0 0 0 3.65.91h.01c4.34 0 7.87-3.53 7.87-7.87 0-2.1-.82-4.08-2.33-5.6zM12.05 18.4h-.01a6.5 6.5 0 0 1-3.32-.91l-.24-.14-2.47.64.66-2.41-.16-.25a6.53 6.53 0 0 1-1-3.48c0-3.61 2.94-6.55 6.56-6.55a6.5 6.5 0 0 1 4.63 1.92 6.5 6.5 0 0 1 1.92 4.63c0 3.61-2.94 6.55-6.56 6.55zm3.6-4.9c-.2-.1-1.17-.58-1.35-.64-.18-.07-.31-.1-.44.1-.13.2-.5.64-.62.77-.11.13-.23.15-.42.05-.2-.1-.83-.31-1.58-.98-.58-.52-.98-1.16-1.09-1.36-.11-.2-.01-.31.09-.4.09-.09.2-.23.3-.35.1-.11.13-.2.2-.33.07-.13.03-.25-.02-.35-.05-.1-.44-1.06-.6-1.45-.16-.38-.32-.33-.44-.34-.11 0-.25-.01-.38-.01-.13 0-.35.05-.53.25-.18.2-.7.68-.7 1.66 0 .98.72 1.93.82 2.06.1.13 1.4 2.14 3.4 3 .48.2.85.33 1.14.42.48.15.92.13 1.27.08.39-.06 1.17-.48 1.34-.94.17-.46.17-.86.12-.94-.05-.08-.18-.13-.38-.23z" />
      </svg>
    </span>
  );
}

// MODULE-LEVEL, ON PURPOSE — Meta's popup message arrives on `window`, and in per_branch mode
// several `<Connect>` cards (one per branch) are mounted at once, each with its own listener.
// Without this, pressing «اربط واتساب» on ONE branch's card would have every OTHER mounted
// card's listener react to the same message too — several branches racing to claim one popup's
// result. Only one popup can realistically be open at a time, so a single shared flag naming
// which card's button opened it is enough; each listener ignores a message that is not its own.
let pendingConnectBranch: string | undefined;

interface ConnectState {
  state: string;
  message: string;
  /**
   * WHETHER A MESSAGE CAN ACTUALLY LEAVE — which is not the same question as «did the connection
   * succeed», and the screen used to answer only the second. The server decides it (operations
   * core/connect.py) from the one flag that also governs signup's verification code, so the two
   * cannot drift apart.
   */
  can_send?: boolean;
}

/** What Embedded Signup posts back. Meta's shape, not ours. */
interface SignupMessage {
  type?: string;
  event?: string;
  // `error_message` and `error_code` arrive on the CANCEL that Meta sends when the OWNER reports a
  // problem from inside the popup (v4). They are the only account we get of what he saw — the
  // popup is Meta's window and we cannot look into it — so dropping them leaves «تعذّر إكمال
  // الربط» as the whole story for a failure that had a stated cause.
  data?: { code?: string; waba_id?: string; phone_number_id?: string; business_id?: string;
           current_step?: string; error_message?: string; error_code?: string };
}

export function Connect({
  session, catalog, state, onChange, branchId, branchLabel,
}: {
  session: Session;
  catalog: Catalog;
  /** `undefined` while the read is in flight, `null` if it failed — see ../loading.ts. The two
   *  used to be one value, so a WhatsApp status we could not read rendered as «غير مربوط» with a
   *  «يحتاج ربط» badge, and the owner started the whole Embedded Signup journey again for a
   *  connection that was working. */
  state: ConnectState | null | undefined;
  onChange: (s: ConnectState) => void;
  /** ABSENT FOR EVERY SHOP IN THE DEFAULT MODE — one card, the establishment's own number, byte
   *  for byte what this screen has always been. Set only by `AccountPanes`'s per-branch list once
   *  a chain has deliberately moved to `shop_mode: per_branch` (core/shop_mode.py on the server);
   *  threaded into every call below exactly as the backend routes already expect it
   *  (`SignupResultIn.branch_id`, `RegisterIn.branch_id`, `GET /connect?branch_id=`). */
  branchId?: string;
  branchLabel?: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // THE SDK IS FETCHED WHEN THE PANE OPENS, so the popup can be opened by the press itself.
  // Meta's authorization code lives about thirty seconds; loading a script inside that window
  // would spend a third of it before the popup even appears.
  const [sdk, setSdk] = useState<SdkState>('loading');
  // THE FETCHED CONFIG ITSELF, KEPT — `fb.login({config_id: ...})` below needs it, and it would
  // otherwise only exist inside the effect that fetched it. `null` means "not answered yet or the
  // fetch failed"; `loadMetaSdk` already treats that the same as `configured: false`.
  const [metaConfig, setMetaConfig] = useState<MetaConfig | null>(null);
  // HIS OWN 6-DIGIT PIN, held only long enough to travel. It is his business account's two-step
  // verification code — we do not have it, cannot look it up, and never store it.
  const [pin, setPin] = useState('');
  const [registering, setRegistering] = useState(false);
  const [registerNote, setRegisterNote] = useState('');
  const { t } = useOperatorI18n();

  useEffect(() => {
    // FETCHED WHEN THE PANE OPENS, so the popup can be opened by the press itself — same timing
    // reasoning as loading the SDK script (loadMetaSdk's own note): Meta's authorization code
    // lives about thirty seconds, so nothing that can happen before the button is pressed should
    // wait for it. Not secret (meta.ts's own docstring), so a normal `call` through the catalog —
    // same mechanism as every other console read.
    const a = action(catalog, 'whatsapp.meta_config');
    if (!a) { setSdk('unconfigured'); return; }
    let cancelled = false;
    call<MetaConfig>(session, a)
      .then((cfg) => {
        if (cancelled) return;
        setMetaConfig(cfg);
        loadMetaSdk(cfg).then((s) => { if (!cancelled) setSdk(s); });
      })
      // A FAILED FETCH IS OURS, NEVER HIS — collapses into the same `'unconfigured'` state
      // `loadMetaSdk(null)` would produce, not a distinct error the button has to learn to show.
      .catch(() => { if (!cancelled) setSdk('unconfigured'); });
    return () => { cancelled = true; };
  }, [session, catalog]);

  /**
   * THE LISTENER IS MOUNTED BEFORE THE POPUP OPENS AND STAYS FOR THE PANE'S LIFE.
   *
   * Attaching it when the button is pressed would be a race against a window that can answer
   * immediately — and against a user who opens the popup twice.
   */
  useEffect(() => {
    const submit = action(catalog, 'whatsapp.connect');
    if (!submit) return;

    const onMessage = async (ev: MessageEvent) => {
      // ORIGIN IS CHECKED FIRST, because this listener accepts a credential. Any page that can
      // reach this window can post to it, and a message shaped like Meta's is trivial to forge —
      // what it would buy an attacker is our exchange endpoint called with a code of their
      // choosing, in this shop's name.
      if (!/^https:\/\/(www\.)?facebook\.com$/.test(ev.origin)) return;

      let msg: SignupMessage;
      try {
        msg = typeof ev.data === 'string' ? JSON.parse(ev.data) : (ev.data as SignupMessage);
      } catch {
        return;
      }
      if (msg?.type !== 'WA_EMBEDDED_SIGNUP') return;
      // NOT MY POPUP — a different branch's card (or none, in the ordinary single-card case)
      // opened it; this listener stays out of the way and lets the right one claim it.
      if (pendingConnectBranch !== (branchId ?? '')) return;

      setBusy(true);
      setError('');
      try {
        const answer = await call<ConnectState>(session, submit, {
          event: msg.event ?? 'FINISH',
          code: msg.data?.code ?? '',
          waba_id: msg.data?.waba_id ?? '',
          phone_number_id: msg.data?.phone_number_id ?? '',
          business_id: msg.data?.business_id ?? '',
          step: msg.data?.current_step ?? '',
          // WHAT META SAID, IF IT SAID ANYTHING. Kept by operations beside the attempt (never
          // shown to the owner — it is English and it is theirs), so support can answer «why did
          // the connect fail on Thursday» instead of guessing from a step name.
          detail: msg.data?.error_message
            ? `${msg.data.error_code ?? ''} ${msg.data.error_message}`.trim().slice(0, 400)
            : '',
          // EMPTY IS THE ESTABLISHMENT'S OWN NUMBER — `sending_identity.resolve` drops it anyway
          // while the shop is central, so sending it unconditionally changes nothing for the
          // shop this screen has always served.
          branch_id: branchId ?? '',
        });
        onChange(answer);
      } catch (e) {
        setError(e instanceof Error ? e.message : t('connect.linkFailed'));
      } finally {
        setBusy(false);
      }
    };

    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [session, catalog, onChange, branchId]);

  const connected = state?.state === 'connected';
  // CONNECTED IS NOT THE SAME AS SENDING. A shop can hold a perfectly good connection while our
  // side cannot put a message on WhatsApp yet — and the green tick over that sentence is the
  // reason an owner records visits all week waiting for messages that were never attempted.
  // `can_send` is absent on an older answer, and absence is treated as «yes» so nothing regresses.
  const waiting = connected && state?.can_send === false;
  const registerAction = action(catalog, 'whatsapp.register_number');
  const statusAction = action(catalog, 'whatsapp.connect_status');

  return (
    <Card className="flex flex-col gap-4 p-4">
      {/* THE MARK AND THE NAME, FIRST — a card that only ever said «مربوط» / «اربط» in plain text
          read as belonging to nothing recognisable on a screenshot; the brand mark and the actual
          product name it connects to are what make this card legible at a glance. */}
      <div className="flex items-center gap-3">
        <WhatsAppMark />
        <span className="flex flex-col">
          <span className="font-medium">{branchLabel ? tf(t, 'connect.title.branch', { branch: branchLabel }) : t('connect.title.shop')}</span>
          <span className="text-xs text-text-secondary">
            {branchLabel ? t('connect.subtitle.branch') : t('connect.subtitle.shop')}
          </span>
        </span>
        {/* ONE STATUS VOCABULARY, NOT TWO — this used to say the same fact the top summary card
            already states, in raw `text-warning`/`text-success` Tailwind classes instead of the
            Badge tones every other status in the console uses. Same colour, same shape, so an
            owner reading this card and the one above it recognises them as the same kind of fact
            rather than two different systems that happen to agree. */}
        {!isLoading(state) && !hasFailed(state) ? (
          <Badge tone={waiting ? 'warning' : connected ? 'success' : 'neutral'} className="ms-auto">
            {waiting ? t('connect.status.waiting') : connected ? t('connect.status.connected') : t('connect.status.disconnected')}
          </Badge>
        ) : null}
      </div>
      {/* AMBER, NOT GREEN, WHILE IT WAITS. The colour is read before the words are, and green over
          «الإرسال لم يُفتح بعد» tells him the opposite of the sentence under it. */}
      <p className={waiting ? 'text-warning' : connected ? 'text-success' : 'text-text-primary'}>
        {/* THREE ANSWERS, NOT TWO. `undefined` is the read still running and `null` is the read
            having failed — and «لم تبدأ الربط بعد» is true of neither. An owner whose WhatsApp is
            connected and whose status we could not fetch was told he had never started, next to a
            badge asking him to connect: so he ran the whole Embedded Signup journey again for a
            connection that was already working. */}
        {isLoading(state)
          ? t('connect.message.loading')
          : hasFailed(state)
            ? t('connect.message.failed')
            : state?.message || t('connect.message.notStarted')}
      </p>

      {error ? <p className="text-danger">{error}</p> : null}

      {/* ── THE STEP THAT TURNS «مربوط» INTO A NUMBER THAT SENDS ────────────────────────────────
          Meta refuses to send from a number until it is REGISTERED with the business's own 6-digit
          two-step-verification PIN (error 133010). Embedded Signup does not do it: it returns a
          token in about thirty seconds and cannot pause for a person to fetch a code.

          SO WITHOUT THIS FORM THE JOURNEY ENDS ONE STEP SHORT. The connection is stored, the
          sentence above turns amber, and nothing anywhere lets him finish — he records visits all
          week and not one message is ever attempted. The route, its three refusals and its audit
          row were all built; this is the field that reaches them.

          TEN ATTEMPTS PER 72 HOURS, so the field refuses a malformed PIN here rather than spending
          one of them to learn what we already know. */}
      {waiting && registerAction ? (
        <form
          className="flex flex-col gap-2"
          onSubmit={async (e) => {
            e.preventDefault();
            if (registering) return;
            setRegistering(true);
            setError('');
            setRegisterNote('');
            try {
              const out = await call<{ registered: boolean; message: string }>(
                session, registerAction, { pin, branch_id: branchId ?? '' });
              setRegisterNote(out.message || '');
              if (out.registered) {
                setPin('');
                // The sentence above is the server's, so it is re-read rather than rewritten here.
                const fresh = statusAction
                  ? await call<ConnectState>(session, statusAction, branchId ? { branch_id: branchId } : {})
                  : null;
                if (fresh) onChange(fresh);
              }
            } catch (err) {
              // THE SERVER'S SENTENCE, NOT OURS. «الرمز غير صحيح» and «لا تعِد المحاولة قبل 72
              // ساعة» are different instructions, and collapsing them into one «تعذّر» is what
              // makes an owner burn his remaining attempts on a problem no attempt can fix.
              setError(err instanceof Error ? err.message : t('connect.register.activateFailed'));
            } finally {
              setRegistering(false);
            }
          }}
        >
          <label className="flex flex-col gap-1 text-sm" htmlFor="wa-pin">
            <span>{t('connect.register.pinLabel')}</span>
            <input
              id="wa-pin"
              className="rounded-input border border-border bg-surface-2 p-2 text-center tracking-widest"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={pin}
              // WESTERN DIGITS AND NOTHING ELSE: Meta's field is numeric, and a keyboard that
              // produces Arabic-Indic digits would send six characters it rejects.
              onChange={(e) => setPin(digitsOnly(e.target.value).slice(0, 6))}
            />
          </label>
          <p className="text-xs text-text-secondary">
            {t('connect.register.pinHint')}
          </p>
          <Button type="submit" disabled={registering || pin.length !== 6}>
            {registering ? t('connect.register.activating') : t('connect.register.activate')}
          </Button>
          {registerNote ? <p className="text-sm text-text-secondary">{registerNote}</p> : null}
        </form>
      ) : null}

      {connected || !action(catalog, 'whatsapp.connect') ? null : (
        <div className="flex flex-col gap-2">
          <Button
            disabled={busy || sdk === 'loading' || sdk === 'unconfigured'}
            onClick={() => {
              // THE POPUP, AND NOTHING BEFORE IT: we do not navigate, and we do not close the
              // pane. A navigation unmounts the listener the code arrives on.
              const fb = metaSdk();
              if (!fb) {
                setError(sdk === 'unconfigured'
                  ? t('connect.popup.unconfigured')
                  : t('connect.popup.openFailed'));
                return;
              }
              // CLAIMED, BEFORE THE POPUP EVEN OPENS — see `pendingConnectBranch`'s own note. This
              // card's button is the one that opened it, so this card's listener is the one that
              // may act on whatever message comes back.
              pendingConnectBranch = branchId ?? '';
              fb.login(() => { /* the answer arrives on the message listener, never here */ }, {
                config_id: metaConfig?.config_id ?? '',
                response_type: 'code',
                override_default_response_type: true,
                extras: SIGNUP_EXTRAS,
              });
            }}
          >
            {busy ? t('connect.button.linking')
              : sdk === 'loading' ? t('connect.button.preparing')
              : sdk === 'unconfigured' ? t('connect.button.unconfigured')
              : t('connect.button.link')}
          </Button>
          {/* THE REASON, NOT JUST THE REFUSAL — a disabled button can never be clicked to reach
              the sentence that used to live only inside `onClick`. «الربط غير مُفعَّل بعد» told
              him nothing he could act on: not ours or his to fix, not temporary or permanent. This
              is the exact sentence that was stranded there, said where he can actually read it. */}
          {sdk === 'unconfigured' ? (
            <p className="text-sm text-danger">
              {t('connect.unconfiguredNote')}
            </p>
          ) : (
            <p className="text-sm text-text-secondary">
              {t('connect.startHint')}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

/** ONE CARD PER BRANCH, ONLY WHEN THIS CHAIN HAS DELIBERATELY MOVED TO `per_branch`
 *  (core/shop_mode.py) — every shop in the default `central` mode sees exactly the single card
 *  this screen has always shown, unchanged.
 *
 *  BEFORE THIS, THERE WAS NO WAY TO CONNECT A SECOND NUMBER AT ALL — `Connect` was mounted once,
 *  establishment-wide, no matter how the shop was configured. A chain that switched to per_branch
 *  (`Team.tsx`'s own `ModeCard`) had a mode with nowhere to act on it.
 */
export function ConnectByBranch({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const [mode, setMode] = useState<{ mode: string; available?: boolean } | null | undefined>(undefined);
  const [branches, setBranches] = useState<Loading<{ id: string; name?: string }[]>>(undefined);
  // ONE INDEPENDENT STATUS PER BRANCH — a Map, not one shared `ConnectState`, because a chain's
  // three branches are three unrelated connections and reading one must never repaint another.
  const [states, setStates] = useState<Record<string, ConnectState | null | undefined>>({});
  // THE ESTABLISHMENT-WIDE CARD'S OWN STATE — held here too, ALWAYS (never behind an `if`), so
  // every hook below runs in the same order on every render regardless of which mode this shop is
  // in. `central` is the only branch that ever reads or writes it.
  const [connected, setConnected] = useState<ConnectState | null | undefined>(undefined);

  useEffect(() => {
    const m = action(catalog, 'operations.shop_mode');
    if (m) call<{ mode: string; available?: boolean }>(session, m).then(setMode).catch(() => setMode(null));
    else setMode(null);
  }, [session, catalog]);

  useEffect(() => {
    if (mode?.mode !== 'per_branch') return;
    const b = action(catalog, 'operations.list_branches');
    if (!b) { setBranches(DENIED); return; }
    call<{ branches?: { id: string; name?: string }[] }>(session, b)
      .then((x) => setBranches(x.branches ?? []))
      .catch(() => setBranches(null));
  }, [session, catalog, mode?.mode]);

  useEffect(() => {
    if (!Array.isArray(branches) || !branches.length) return;
    const statusAction = action(catalog, 'whatsapp.connect_status');
    if (!statusAction) return;
    branches.forEach((br) => {
      call<ConnectState>(session, statusAction, { branch_id: br.id })
        .then((s) => setStates((was) => ({ ...was, [br.id]: s })))
        .catch(() => setStates((was) => ({ ...was, [br.id]: null })));
    });
  }, [session, catalog, branches]);

  useEffect(() => {
    if (mode?.mode === 'per_branch') return;
    const w = action(catalog, 'whatsapp.connect_status');
    if (w) call<ConnectState>(session, w).then(setConnected).catch(() => setConnected(null));
  }, [session, catalog, mode?.mode]);

  // STILL DECIDING, OR THE READ FAILED — the single establishment-wide card is the safe default
  // in both cases: it is what this screen has always shown, and a shop in `central` mode (every
  // shop that never touched `Team.tsx`'s own mode card) must see exactly that, unconditionally.
  if (mode?.mode !== 'per_branch') {
    return <Connect session={session} catalog={catalog} state={connected} onChange={setConnected} />;
  }

  if (isLoading(branches)) return null;
  if (isDenied(branches)) {
    return (
      <p className="rounded-card bg-surface-1 p-4 text-sm text-text-secondary shadow-sm">
        {t('connect.byBranch.noAccess')}
      </p>
    );
  }
  if (hasFailed(branches)) {
    return (
      <p role="alert" className="rounded-card bg-surface-1 p-4 text-sm text-danger shadow-sm">
        {t('connect.byBranch.readFailed')}
      </p>
    );
  }
  if (!branches.length) {
    return (
      <p className="rounded-card bg-surface-1 p-4 text-sm text-text-secondary shadow-sm">
        {t('connect.byBranch.noBranches')}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {branches.map((br) => (
        <Connect
          key={br.id}
          session={session}
          catalog={catalog}
          branchId={br.id}
          branchLabel={br.name || br.id}
          state={states[br.id]}
          onChange={(s) => setStates((was) => ({ ...was, [br.id]: s }))}
        />
      ))}
    </div>
  );
}
