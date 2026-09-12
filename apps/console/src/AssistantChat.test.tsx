/**
 * The env switch hides the chat ENTIRELY when off (the default). With it on: sends a question via
 * askAssistant, shows the answer, and a failure reads as a quiet sentence in the thread, not an
 * app-level error.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { AssistantChat } from './AssistantChat';
import type { Session } from './session';
import { OperatorI18nProvider } from './operator-i18n';

// AssistantChat now reads `useOperatorI18n()` — wrap once here so every existing `render(<...>)`
// call site below stays unchanged.
const SESSION_FOR_I18N = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION_FOR_I18N}>{ui}</OperatorI18nProvider>);
}

const SESSION = { token: 'tok-1' } as Session;

let askMock: ReturnType<typeof vi.fn> = vi.fn();
vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, askAssistant: (...args: unknown[]) => askMock(...args) };
});

afterEach(() => vi.clearAllMocks());

describe('AssistantChat', () => {
  it('renders nothing when the switch is off (the default)', () => {
    const { container } = render(<AssistantChat session={SESSION} surface="shop" />);
    expect(container.innerHTML).toBe('');
    expect(askMock).not.toHaveBeenCalled();
  });

  it('sends a question and shows the grounded answer', async () => {
    vi.stubEnv('VITE_ASSISTANT_CHAT_ENABLED', 'true');
    askMock = vi.fn().mockResolvedValue({
      answer: 'هذا هو الجواب.', message_id: 'm1', grounded: true, citations: [],
      actions: [], abstained_because: '', searched: 3, redacted: [],
    });
    render(<AssistantChat session={SESSION} surface="shop" />);
    fireEvent.change(screen.getByLabelText('سؤالك'), { target: { value: 'كيف أضيف موظف؟' } });
    fireEvent.click(screen.getByRole('button', { name: /إرسال/ }));
    await waitFor(() => expect(screen.getByText('هذا هو الجواب.')).toBeTruthy());
    expect(askMock).toHaveBeenCalledWith(SESSION, 'كيف أضيف موظف؟', 'shop');
  });

  it('reads a failure as a quiet sentence in the thread', async () => {
    vi.stubEnv('VITE_ASSISTANT_CHAT_ENABLED', 'true');
    askMock = vi.fn().mockRejectedValue(new TypeError('network'));
    render(<AssistantChat session={SESSION} surface="shop" />);
    fireEvent.change(screen.getByLabelText('سؤالك'), { target: { value: 'سؤال' } });
    fireEvent.click(screen.getByRole('button', { name: /إرسال/ }));
    await waitFor(() => expect(screen.getByText('لا يوجد اتصال — تحقّق من الشبكة وحاول مرة أخرى.')).toBeTruthy());
  });
});
