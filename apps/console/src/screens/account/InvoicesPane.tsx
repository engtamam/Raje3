/**
 * «الفواتير» — his invoices, and the document he actually needs.
 *
 * TWO DOWNLOADS, NOT ONE, because they are two different papers: the tax invoice is what his
 * accountant files, the receipt is proof he paid. Offering only "download" and picking one for him
 * sends half the shops to support. THIS WAS WRITTEN AND NEVER BUILT (audit #4, 2026-08-22) — the
 * three routes existed, tested, for months; this pane listed invoices and stopped there.
 *
 * WHY «تنزيل المستند» IS THE ONE ALWAYS OFFERED. `/document` self-selects the right paper (the
 * tax invoice if one was issued and still backed, the receipt otherwise) and never refuses — the
 * other two routes 409 on a mismatch, and this pane has no reliable way to predict that from the
 * list alone. «الإيصال» is offered SEPARATELY only when `doc_type` says a tax invoice was actually
 * issued — the one case where a second, different paper genuinely exists to ask for.
 */
import { useEffect, useState } from 'react';
import { Badge } from '../../rj-ui/Badge';
import { Card } from '../../rj-ui/Card';
import { Button } from '../../rj-ui/Button';
import { Skeleton } from '../../rj-ui/Skeleton';
import { riyalsLabel } from '../../money';
import { DENIED, hasFailed, isLoading, isDenied, type Loading } from '../../loading';
import { action, call, downloadUrl, type Catalog } from '../../catalog';
import type { Session } from '../../session';
import { useOperatorI18n } from '../../operator-i18n';
import '../account-panes-i18n';

interface Invoice {
  id: string; number?: string; status?: string; total_minor?: number; issued_at?: string;
  /** "receipt" | "tax_invoice" — frozen the moment the invoice was paid. Empty on a legacy row
   *  with nothing stamped; treated as "no tax invoice exists" rather than guessed at. */
  doc_type?: string;
}

export function InvoicesPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const [rows, setRows] = useState<Loading<Invoice[]>>(undefined);
  const [downloading, setDownloading] = useState('');
  const [downloadError, setDownloadError] = useState('');
  const canList = action(catalog, 'billing.my_invoices');
  const canDocument = action(catalog, 'billing.invoice_document');
  const canReceipt = action(catalog, 'billing.invoice_receipt');

  const download = async (a: ReturnType<typeof action>, key: string, invoiceId: string) => {
    if (!a) return;
    setDownloading(key); setDownloadError('');
    try {
      const url = await downloadUrl(session, a, { id: invoiceId });
      window.open(url, '_blank', 'noreferrer');
    } catch {
      // NO SENTENCE FROM THE SERVER TO SHOW — a PDF route answers with a status, not a body. One
      // fixed sentence here beats printing a raw HTTP code at an owner looking for his invoice.
      setDownloadError(t('accountPanes.invoices.downloadFailed'));
    } finally {
      setDownloading('');
    }
  };

  useEffect(() => {
    if (!canList) { setRows(DENIED); return; }
    call<{ invoices: Invoice[] }>(session, canList)
      .then((x) => setRows(x.invoices ?? []))
      .catch(() => setRows(null));
  }, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!canList) return null;
  // «NOT YET» IS NOT «IT FAILED». `undefined` waits; `null` says so.
  if (isLoading(rows)) return <Skeleton height={80} />;

  return (
    <Card className="flex flex-col gap-2 p-4">
      <h3 className="text-sm text-text-secondary">{t('accountPanes.invoices.title')}</h3>
      {isDenied(rows) ? (
        // A ROLE ANSWER, AND IT SAYS WHICH. "No invoices yet" to somebody whose role simply
        // excludes billing is a fact about the shop that is not his to be given.
        <p className="text-sm text-text-secondary">{t('accountPanes.invoices.noPermission')}</p>
      ) : hasFailed(rows) ? (
        // HE CAME HERE FOR HIS ACCOUNTANT. "No invoices yet" to a shop that has been paying for
        // months is a sentence that sends him looking for a receipt he will not find.
        <p className="text-sm text-text-secondary">
          {t('accountPanes.invoices.readFailed')}
        </p>
      ) : rows.length === 0 ? (
        // NOT AN APOLOGY. No invoices before the first subscription is the correct state.
        <p className="text-sm text-text-secondary">{t('accountPanes.invoices.empty')}</p>
      ) : (
        <>
          {downloadError ? <p className="text-sm text-danger">{downloadError}</p> : null}
          <ul className="flex flex-col gap-2">
            {rows.map((v) => (
              <li key={v.id} className="flex flex-col gap-2 border-b border-surface-2 pb-2 last:border-0">
                <div className="flex items-center justify-between gap-3">
                  <span className="flex flex-col">
                    <span className="tabular-nums" dir="ltr">{v.number || v.id}</span>
                    <span className="text-sm text-text-secondary">{(v.issued_at || '').slice(0, 10)}</span>
                  </span>
                  <span className="flex items-center gap-3">
                    <span className="tabular-nums">
                      {v.total_minor ? riyalsLabel(v.total_minor, t) : '—'}
                    </span>
                    <Badge tone={v.status === 'paid' ? 'success' : 'warning'}>
                      {v.status === 'paid' ? t('accountPanes.invoices.paid') : t('accountPanes.invoices.unpaid')}
                    </Badge>
                  </span>
                </div>
                {/* «تنزيل المستند» — self-selects the right paper and never refuses; the ONLY
                    download offered when no tax invoice was issued for this row. */}
                <div className="flex flex-wrap gap-2">
                  {canDocument ? (
                    <Button variant="ghost" size="sm" disabled={downloading === `doc:${v.id}`}
                            onClick={() => void download(canDocument, `doc:${v.id}`, v.id)}>
                      {downloading === `doc:${v.id}` ? t('accountPanes.invoices.downloading') : t('accountPanes.invoices.downloadDocument')}
                    </Button>
                  ) : null}
                  {/* THE SECOND PAPER, ONLY WHEN IT GENUINELY EXISTS: a tax invoice was issued for
                      this row AND it is paid — a receipt for money not yet collected is not real. */}
                  {canReceipt && v.doc_type === 'tax_invoice' && v.status === 'paid' ? (
                    <Button variant="ghost" size="sm" disabled={downloading === `receipt:${v.id}`}
                            onClick={() => void download(canReceipt, `receipt:${v.id}`, v.id)}>
                      {downloading === `receipt:${v.id}` ? t('accountPanes.invoices.downloading') : t('accountPanes.invoices.downloadReceipt')}
                    </Button>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}
