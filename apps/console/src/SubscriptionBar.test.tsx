/**
 * The one-line banner above every screen — proven it no longer assumes الأساس is the only
 * subscription worth naming. A shop with no base at all can still hold تسجيل زيارة standalone,
 * and جهات الاتصال (free, `interval='once'`) must never trigger a banner at all.
 */
import { describe, expect, it } from 'vitest';
import { render as rtlRender, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ReactElement } from 'react';
import { SubscriptionBar } from './SubscriptionBar';
import type { Owned } from './apps';
import { OperatorI18nProvider } from './operator-i18n';

// SubscriptionBar now reads `useOperatorI18n()` — wrap once here so every existing
// `render(<...>)` call site below stays unchanged.
const SESSION_FOR_I18N = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION_FOR_I18N}>{ui}</OperatorI18nProvider>);
}

const NOW = 1_700_000_000_000; // ms

function renderBar(owned: Owned) {
  render(
    <MemoryRouter>
      <SubscriptionBar owned={owned} now={NOW} />
    </MemoryRouter>,
  );
}

describe('SubscriptionBar', () => {
  it('names الأساس when its own trial is ending — reading the name from the data, not a literal', () => {
    renderBar({
      checked: true, message: '', keys: [], apps: [],
      base: { plan_id: 'p1', status: 'trialing', renews_at: NOW / 1000 + 3 * 86400 },
    });
    expect(screen.getByText(/فعِّل الأساس/)).toBeTruthy();
  });

  it('says nothing for a shop with no base and no standalone app either', () => {
    renderBar({ checked: true, message: '', keys: [], apps: [], base: null });
    expect(screen.queryByRole('status')).toBeNull();
  });

  it('names the standalone app actually ending, never الأساس, when there is no base at all', () => {
    renderBar({
      checked: true, message: '', keys: ['feature.visit'],
      apps: [
        { key: 'feature.visit', name: 'تسجيل زيارة', what: '', screen: '', owned: true,
          renews_at: NOW / 1000 + 3 * 86400 },
      ],
      base: null,
    });
    const status = screen.getByRole('status');
    expect(status.textContent).toContain('تسجيل زيارة');
    expect(status.textContent).not.toContain('الأساس');
  });

  it('never mentions جهات الاتصال — it is free and carries no renewal date', () => {
    renderBar({
      checked: true, message: '', keys: ['feature.contacts'],
      apps: [
        { key: 'feature.contacts', name: 'جهات الاتصال', what: '', screen: '', owned: true,
          renews_at: null },
      ],
      base: null,
    });
    expect(screen.queryByRole('status')).toBeNull();
  });
});
