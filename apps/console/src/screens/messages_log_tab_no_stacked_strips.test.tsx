/**
 * «الحملات»'s log tab used to put its top-level strip (the "أقسام الرسائل" Segmented) and its own
 * delivery-status filter (another Segmented) directly next to each other with nothing rendered
 * between them — two radiogroups in a row, which is exactly the "شريطين تحت بعض" shape the owner
 * ruled out entirely (see ci/check_no_two_tab_strips_stack_in_one_view.py's own docstring). Every
 * other tab on this screen opens on real content first; only «السجل» opened straight onto a
 * second strip. Fixed by moving the tab's own explanatory sentence above the filter, so there is
 * always real content between the page's own navigation strip and this tab's content filter.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DENIED } from '../loading';
import { OperatorI18nProvider } from '../operator-i18n';

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'reminders.log') return { log: [] };
      if (a.id === 'operations.list_branches') return { branches: [] };
      return {};
    },
  };
});

const { MessagesScreen } = await import('./Messages');

afterEach(() => cleanup());

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

describe('«الحملات»\'s log tab never stacks its filter directly under the top strip', () => {
  it('renders real content (the explanatory sentence) between the two radiogroups', async () => {
    render(
      <OperatorI18nProvider session={session}>
        <MemoryRouter initialEntries={['/']}>
          <MessagesScreen session={session} catalog={catalog} owned={DENIED} />
        </MemoryRouter>
      </OperatorI18nProvider>,
    );
    fireEvent.click(screen.getByRole('radio', { name: 'ماذا حدث؟' }));

    // THE SENTENCE THAT NOW SITS BETWEEN THE TWO STRIPS — it must appear in the DOM, and it must
    // appear BEFORE the log filter's own radiogroup, not after it (a reorder that put it back
    // below would silently restore the two-strips-with-nothing-between-them bug).
    const hint = await screen.findByText(/كل رسالة لم تخرج، ومعها سببها/);
    const filter = screen.getByRole('radiogroup', { name: 'تصفية السجل' });
    expect(
      hint.compareDocumentPosition(filter) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    // AND ONLY ONE STRIP MAY EVER RENDER WITHOUT ANY OTHER CONTENT IMMEDIATELY FOLLOWING THE
    // TOP-LEVEL ONE — the top nav strip's very next sibling in the DOM must never itself be a
    // second radiogroup.
    const topStrip = screen.getByRole('radiogroup', { name: 'أقسام الرسائل' });
    let sibling = topStrip.nextElementSibling;
    // Skip a possible inline error paragraph (rendered only when `switchError` is set — never in
    // this test) to reach the actual next real element, matching what a shop owner would see.
    expect(sibling?.getAttribute('role')).not.toBe('radiogroup');
  });
});
