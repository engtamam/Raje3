/**
 * «بياناتي» — PDPL, as a control he can press, not as a paragraph.
 *
 * The right to access, export, correct and erase is his by law; a product that describes the right
 * and offers no way to use it has not granted it. `compliance.open_my_dsar` is that way, and this
 * pane exists to put it one tap from where he already is.
 */
import { useState } from 'react';
import { Card } from '../../rj-ui/Card';
import { Button } from '../../rj-ui/Button';
import { ConfirmDialog } from '../../rj-ui/ConfirmDialog';
import { action, call, type Catalog } from '../../catalog';
import { legalUrl } from '../../legal/url';
import type { Session } from '../../session';
import { useOperatorI18n, tf } from '../../operator-i18n';
import '../account-panes-i18n';

export function DataPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const [busy, setBusy] = useState(false);
  const [said, setSaid] = useState('');
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState(false);
  const canAsk = action(catalog, 'compliance.open_my_dsar');

  // ONLY ERASURE HAS A BUTTON HERE — owner's own explicit simplification (2026-09-22): access,
  // export, and correction are rare enough that a real button for each cost more screen than it
  // saved, on both console and mobile. Every other right still routes through the SAME real
  // channel PDPL requires — the Data Protection Officer's own address, already the one the privacy
  // policy itself names, never a second, invented contact point.
  const DPO_EMAIL = 'mang.raje3@gmail.com';

  const askErasure = async () => {
    if (!canAsk) return;
    setBusy(true); setError(''); setSaid(''); setConfirming(false);
    try {
      // `type`, NOT `kind` — read off compliance-service rather than guessed. `erasure` is one of
      // the service's own DSAR_TYPES.
      await call<{ id?: string; dsar_id?: string }>(session, canAsk, { type: 'erasure' });

      // NO CODE DELIVERY TODAY — `reminders.send_dsar_code` was deleted along with the
      // customer-facing WhatsApp code flow it shared a template with. The request is recorded —
      // that part is real and the 30-day clock in the regulation starts from it.
      setSaid(tf(t, 'accountPanes.dsar.recordedNoCode', { label: t('accountPanes.dsar.erasure') }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('accountPanes.dsar.requestFailed'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <h3 className="mb-1">{t('accountPanes.retention.title')}</h3>
        <p className="text-sm text-text-secondary">
          {t('accountPanes.retention.desc')}
        </p>
      </Card>

      {canAsk ? (
        <Card className="flex flex-col gap-3 p-4">
          <h3>{t('accountPanes.dsar.title')}</h3>
          <p className="text-sm text-text-secondary">
            {t('accountPanes.dsar.desc')}
          </p>
          {/* ERASURE ALONE, NOT STYLED AS DANGER — it is a right, not an accident. The confirm
              dialog below is what actually protects against a stray tap, not a red button. */}
          <div>
            <Button type="button" variant="ghost" disabled={busy}
                    onClick={() => setConfirming(true)}>
              {t('accountPanes.dsar.erasure')}
            </Button>
          </div>
          <p className="text-sm text-text-secondary">
            {tf(t, 'accountPanes.dsar.otherRequests', { email: DPO_EMAIL })}
          </p>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          {said ? <p className="text-sm">{said}</p> : null}
          <ConfirmDialog
            open={confirming}
            onClose={() => setConfirming(false)}
            onConfirm={askErasure}
            title={t('accountPanes.dsar.erasure')}
            body={t('accountPanes.dsar.erasureConfirmBody')}
            confirmLabel={t('accountPanes.dsar.erasure')}
            danger={false}
            busy={busy}
          />
        </Card>
      ) : null}

      <Card>
        <h3 className="mb-1">{t('accountPanes.agreements.title')}</h3>
        <p className="text-sm text-text-secondary">
          {t('accountPanes.agreements.desc')}
        </p>
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          <a className="underline" href={legalUrl('terms')} target="_blank" rel="noreferrer">{t('accountPanes.agreements.terms')}</a>
          <a className="underline" href={legalUrl('privacy-policy')} target="_blank" rel="noreferrer">{t('accountPanes.agreements.privacy')}</a>
          {/* THE DPA HAS NO PAGE OF ITS OWN — it is an annex to the Terms and accepting the Terms
              accepts it, so its text lives at the same URL rather than at a route that would
              otherwise 404. */}
          <a className="underline" href={legalUrl('terms')} target="_blank" rel="noreferrer">{t('accountPanes.agreements.dpa')}</a>
        </div>
      </Card>
    </div>
  );
}
