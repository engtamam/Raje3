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
import { Button } from '@base-ui/design-system/Button';
import { action, call, type Catalog } from '../catalog';
import { loadMetaSdk, metaSdk, type SdkState } from '../meta';
import type { Session } from '../session';

interface ConnectState { state: string; message: string }

/** What Embedded Signup posts back. Meta's shape, not ours. */
interface SignupMessage {
  type?: string;
  event?: string;
  data?: { code?: string; waba_id?: string; phone_number_id?: string; business_id?: string; current_step?: string };
}

export function Connect({
  session, catalog, state, onChange,
}: {
  session: Session;
  catalog: Catalog;
  state: ConnectState | null;
  onChange: (s: ConnectState) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  // THE SDK IS FETCHED WHEN THE PANE OPENS, so the popup can be opened by the press itself.
  // Meta's authorization code lives about thirty seconds; loading a script inside that window
  // would spend a third of it before the popup even appears.
  const [sdk, setSdk] = useState<SdkState>('loading');

  useEffect(() => { loadMetaSdk().then(setSdk); }, []);

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
        });
        onChange(answer);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'تعذّر إكمال الربط.');
      } finally {
        setBusy(false);
      }
    };

    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [session, catalog, onChange]);

  const connected = state?.state === 'connected';

  return (
    <div className="flex flex-col gap-4 rounded-card bg-surface-1 p-6 shadow-sm">
      <p className={connected ? 'text-success' : 'text-text-primary'}>
        {state?.message || 'لم تبدأ الربط بعد.'}
      </p>

      {error ? <p className="text-danger">{error}</p> : null}

      {connected ? null : (
        <div className="flex flex-col gap-2">
          <Button
            disabled={busy || sdk === 'loading' || sdk === 'unconfigured'}
            onClick={() => {
              // THE POPUP, AND NOTHING BEFORE IT: we do not navigate, and we do not close the
              // pane. A navigation unmounts the listener the code arrives on.
              const fb = metaSdk();
              if (!fb) {
                setError(sdk === 'unconfigured'
                  ? 'ربط واتساب غير مُفعَّل بعد — عُطلٌ لدينا لا في حسابك. تواصل معنا ونكمل معك.'
                  : 'تعذّر فتح نافذة واتساب. تأكد من اتصالك وحاول مرة أخرى.');
                return;
              }
              fb.login(() => { /* the answer arrives on the message listener, never here */ }, {
                config_id: import.meta.env.VITE_META_CONFIG_ID,
                response_type: 'code',
                override_default_response_type: true,
                extras: { setup: {}, featureType: '', sessionInfoVersion: '3' },
              });
            }}
          >
            {busy ? 'جارٍ الربط…'
              : sdk === 'loading' ? 'نُحضّر نافذة واتساب…'
              : sdk === 'unconfigured' ? 'الربط غير مُفعَّل بعد'
              : 'اربط واتساب'}
          </Button>
          <p className="text-sm text-text-secondary">
            دقائق، ولا يشترط توثيق نشاطك التجاري للبدء.
          </p>
        </div>
      )}
    </div>
  );
}
