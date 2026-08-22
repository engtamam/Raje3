/**
 * A supervisor over several branches reads an instruction, not an outage.
 *
 * A dashboard is built from ONE branch's snapshot, so insights answers a person whose scope is a
 * SET with 409 MANY_BRANCHES and the list — deliberately, rather than picking one of them and
 * showing him a quarter of his work as if it were all of it. «محلّي» caught every rejection into
 * one `failed` flag and drew «تعذّر قراءة المؤشرات · حاول بعد قليل», so the one answer that names
 * what to do next arrived as a temporary failure, and retrying produced it again for ever.
 *
 * The assertion is what he can DO — a control per branch he supervises — because a test on the
 * sentence alone would pass on a page that says the right thing and offers no way out of it.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createElement, useState } from 'react';
import { ApiError } from '../api';

const asked: { id: string; body: unknown }[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      asked.push({ id: a.id, body });
      if (a.id === 'insights.branches') {
        return { rows: [{ branch_id: 'b-1', name: 'فرع الرياض' },
                         { branch_id: 'b-2', name: 'فرع جدة' }], unknown: 0 };
      }
      if (a.id === 'insights.dashboard') {
        const asked_for = (body as { branch_id?: string } | undefined)?.branch_id;
        if (!asked_for) {
          throw new ApiError(409, { error: 'MANY_BRANCHES', branches: ['b-1', 'b-2'] },
                             'لوحتك تغطي أكثر من فرع.');
        }
        return { values: { return_rate: 0.4 }, entitlements: [] };
      }
      return {};
    },
  };
});

afterEach(() => { asked.length = 0; cleanup(); });

const { IndicatorsPanel: LocalScreen } = await import('./Shop');

/**
 * A HOST THAT HOLDS THE CHOICE, because the screen no longer does.
 *
 * The switcher moved to the sidebar and the branch became a shell-level fact, so «he picks a
 * branch and the screen re-reads» is now a round trip through the parent — which is exactly the
 * seam worth testing. Rendering the screen with a frozen prop would test a component that cannot
 * exist in the product.
 */
function Host() {
  const [branch, setBranch] = useState('');
  return createElement(LocalScreen, {
    session: {} as never, catalog: {} as never, branch, onBranch: setBranch,
  });
}

const open = () => render(createElement(Host));

describe('«محلّي» for a supervisor over several branches', () => {
  it('offers his branches by name instead of reporting a failure', async () => {
    open();
    await screen.findByText('فرع الرياض');
    expect(screen.getByText('فرع جدة')).toBeTruthy();
    // NOT AN OUTAGE. This is the line the old screen drew for him, and it must be gone.
    expect(screen.queryByText('تعذّر قراءة المؤشرات')).toBeNull();
  });

  it('does not answer for him — nothing is picked until he picks it', async () => {
    open();
    await screen.findByText('فرع الرياض');
    const scoped = asked.filter(
      (a) => a.id === 'insights.dashboard' && (a.body as { branch_id?: string })?.branch_id);
    expect(scoped).toHaveLength(0);
  });

  it('reads the branch he chooses', async () => {
    open();
    fireEvent.click(await screen.findByText('فرع جدة'));
    await waitFor(() => {
      expect(asked.some((a) => a.id === 'insights.dashboard'
        && (a.body as { branch_id?: string })?.branch_id === 'b-2')).toBe(true);
    });
  });
});
