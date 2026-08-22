/** "بدون عربون بعربون او مدفوع" — one shared label+colour pair per state, so
 *  the booking dialog, the grid's filter chips and each card's own badge never drift into three
 *  different vocabularies for the same three values.
 *
 *  NOT `payment.ts` — that module is the subscription card-form stub (a different "payment"
 *  entirely: what the shop owes راجِع, not what a customer owes the shop for one booking).
 *  Sharing the name would have made two unrelated concepts import from the same file. */
export type PaymentStatus = 'none' | 'deposit' | 'paid';

export const PAYMENT_LABEL: Record<PaymentStatus, string> = {
  none: 'بدون عربون',
  deposit: 'عربون',
  paid: 'مدفوع',
};

// Distinct hues, not just distinct opacity — a glance at the card must tell the three apart
// without reading the label. Neutral for "nothing in hand yet", accent violet for "something",
// teal for "settled" — the same traffic-light logic the rest of the product's status colours use.
export const PAYMENT_COLOR: Record<PaymentStatus, { fg: string; bg: string }> = {
  none: { fg: 'var(--rj-ink-soft)', bg: 'var(--rj-line)' },
  deposit: { fg: 'var(--rj-accent-deep)', bg: 'var(--rj-accent-soft)' },
  paid: { fg: 'var(--rj-attended)', bg: 'var(--rj-attended-soft)' },
};

export const PAYMENT_ORDER: PaymentStatus[] = ['none', 'deposit', 'paid'];
