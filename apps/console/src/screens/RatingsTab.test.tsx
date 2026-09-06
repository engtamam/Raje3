/**
 * «التقييمات» tab (rating-app-feature.md phase 5) — filters, the unhandled-first default, and
 * marking a rating handled. Server calls mocked; the real request/response shapes are covered on
 * the backend side (test_ratings_api.py, test_rating_fields.py).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

let callImpl: (session: unknown, a: { id: string }, body?: unknown) => Promise<unknown>;
let actionIds: Set<string>;
const listCalls: unknown[] = [];
const handleCalls: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => (actionIds.has(id) ? { id, label: id, method: 'GET', path: `/${id}` } : undefined),
    call: async (session: unknown, a: { id: string }, body?: unknown) => callImpl(session, a, body),
  };
});

const { RatingsTab } = await import('./RatingsTab');

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function open() {
  return render(
    <MemoryRouter>
      <RatingsTab session={session} catalog={catalog} branch="" />
    </MemoryRouter>,
  );
}

afterEach(() => { cleanup(); listCalls.length = 0; handleCalls.length = 0; });

function withActions(extra: string[] = []) {
  actionIds = new Set(['operations.ratings', 'operations.mark_rating_handled', ...extra]);
}

describe('RatingsTab', () => {
  it('is absent entirely when operations.ratings is not in the catalogue', () => {
    actionIds = new Set([]);
    const { container } = open();
    expect(container.firstChild).toBeNull();
  });

  it('defaults to the unhandled filter and lists what it gets back', async () => {
    withActions();
    callImpl = async (_s, a, body) => {
      if (a.id === 'operations.ratings') { listCalls.push(body); return { ratings: [
        { id: 'vis1', customer_id: 'cus1', rating: 5, feedback_text: 'ممتاز', rated_at: 1000,
          rating_handled_at: 0, rating_handled_note: '' },
      ] }; }
      return {};
    };
    open();
    await waitFor(() => expect(screen.getByText('ممتاز')).toBeTruthy());
    expect(listCalls[0]).toMatchObject({ handled: 'false' });
  });

  it('shows the compliment-shaped empty state when nothing is unhandled', async () => {
    withActions();
    callImpl = async () => ({ ratings: [] });
    open();
    await waitFor(() => expect(screen.getByText('لا تقييمات بانتظار المعالجة')).toBeTruthy());
  });

  it('a failed read shows the real failure sentence, not an empty list', async () => {
    withActions();
    callImpl = async () => { throw new Error('boom'); };
    open();
    await waitFor(() => expect(screen.getByText('تعذّرت القراءة')).toBeTruthy());
  });

  it('switching the star filter re-queries with the chosen rank', async () => {
    withActions();
    callImpl = async (_s, a, body) => {
      if (a.id === 'operations.ratings') { listCalls.push(body); return { ratings: [] }; }
      return {};
    };
    open();
    await waitFor(() => expect(listCalls.length).toBeGreaterThan(0));
    fireEvent.click(screen.getByText('5 نجوم'));
    await waitFor(() => expect(listCalls[listCalls.length - 1]).toMatchObject({ stars: '5' }));
  });

  it('switching to «الكل» drops the handled filter entirely', async () => {
    withActions();
    callImpl = async (_s, a, body) => {
      if (a.id === 'operations.ratings') { listCalls.push(body); return { ratings: [] }; }
      return {};
    };
    open();
    await waitFor(() => expect(listCalls.length).toBeGreaterThan(0));
    fireEvent.click(screen.getByText('الكل'));
    await waitFor(() => {
      const last = listCalls[listCalls.length - 1] as Record<string, unknown>;
      expect(last.handled).toBeUndefined();
    });
  });

  it('marking a rating handled posts the note and removes it from the unhandled list', async () => {
    withActions();
    let ratingsResponse = [
      { id: 'vis1', customer_id: 'cus1', rating: 4, feedback_text: 'جيد', rated_at: 1000,
        rating_handled_at: 0, rating_handled_note: '' },
    ];
    callImpl = async (_s, a, body) => {
      if (a.id === 'operations.ratings') return { ratings: ratingsResponse };
      if (a.id === 'operations.mark_rating_handled') {
        handleCalls.push(body);
        ratingsResponse = [];
        return { handled: true };
      }
      return {};
    };
    open();
    await waitFor(() => expect(screen.getByText('جيد')).toBeTruthy());
    const note = screen.getByPlaceholderText(/ملاحظة \(اختياري\)/);
    fireEvent.change(note, { target: { value: 'تواصلنا معه' } });
    fireEvent.click(screen.getByText('تمت المعالجة'));
    await waitFor(() => expect(screen.queryByText('جيد')).toBeFalsy());
    expect(handleCalls[0]).toMatchObject({ visit_id: 'vis1', note: 'تواصلنا معه' });
  });

  it('a handled rating shows its badge and note, with no mark-handled control', async () => {
    withActions();
    callImpl = async (_s, a) => {
      if (a.id === 'operations.ratings') return { ratings: [
        { id: 'vis1', customer_id: 'cus1', rating: 3, feedback_text: '', rated_at: 1000,
          rating_handled_at: 2000, rating_handled_note: 'تم التواصل' },
      ] };
      return {};
    };
    open();
    fireEvent.click(screen.getByText('الكل'));
    await waitFor(() => expect(screen.getByText('معالَجة')).toBeTruthy());
    expect(screen.getByText(/تم التواصل/)).toBeTruthy();
    expect(screen.queryByText('تمت المعالجة')).toBeNull();
  });

  it('no mark-handled control renders when the capability is absent', async () => {
    withActions([]);
    actionIds = new Set(['operations.ratings']);   // read-only role: no mark_rating_handled
    callImpl = async (_s, a) => {
      if (a.id === 'operations.ratings') return { ratings: [
        { id: 'vis1', customer_id: 'cus1', rating: 4, feedback_text: 'رائع', rated_at: 1000,
          rating_handled_at: 0, rating_handled_note: '' },
      ] };
      return {};
    };
    open();
    await waitFor(() => expect(screen.getByText('رائع')).toBeTruthy());
    expect(screen.queryByText('تمت المعالجة')).toBeNull();
  });
});
