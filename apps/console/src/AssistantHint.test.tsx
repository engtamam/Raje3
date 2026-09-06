/**
 * The env switch hides the icon ENTIRELY (not a disabled state) when off — the default, since no
 * VITE_ASSISTANT_HELP_ICON_ENABLED is set in the test environment. With it on: a 404 (no authored
 * anchor yet, the expected state until Phase 4) reads «ما فيه شرح لهذا بعد», never an error.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AssistantHint } from './AssistantHint';
import type { Session } from './session';

const SESSION = { token: 'tok-1' } as Session;

let fetchMock: ReturnType<typeof vi.fn> = vi.fn();
vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, fetchAssistantHelp: (...args: unknown[]) => fetchMock(...args) };
});

afterEach(() => vi.clearAllMocks());

describe('AssistantHint', () => {
  it('renders nothing when the switch is off (the default)', () => {
    const { container } = render(<AssistantHint session={SESSION} anchor="operations.catalogue" />);
    expect(container.innerHTML).toBe('');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('fetches only on tap, and shows the authored body when one exists', async () => {
    vi.stubEnv('VITE_ASSISTANT_HELP_ICON_ENABLED', 'true');
    fetchMock = vi.fn().mockResolvedValue({
      id: 'kb1', anchor: 'operations.catalogue', title: 'الخدمات',
      body: 'شبكة الخدمات هنا.', kind: 'action', related: [],
    });
    render(<AssistantHint session={SESSION} anchor="operations.catalogue" />);
    expect(fetchMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'شرح' }));
    await waitFor(() => expect(screen.getByText('شبكة الخدمات هنا.')).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledWith(SESSION, 'operations.catalogue');
  });

  it('reads a 404 (no anchor authored yet) as a quiet sentence, never an error', async () => {
    vi.stubEnv('VITE_ASSISTANT_HELP_ICON_ENABLED', 'true');
    fetchMock = vi.fn().mockResolvedValue(null);
    render(<AssistantHint session={SESSION} anchor="operations.something_unwritten" />);
    fireEvent.click(screen.getByRole('button', { name: 'شرح' }));
    await waitFor(() => expect(screen.getByText('ما فيه شرح لهذا بعد.')).toBeTruthy());
  });

  it('toggles closed on a second tap without re-fetching', async () => {
    vi.stubEnv('VITE_ASSISTANT_HELP_ICON_ENABLED', 'true');
    fetchMock = vi.fn().mockResolvedValue({
      id: 'kb1', anchor: 'a', title: 't', body: 'نص الشرح', kind: 'action', related: [],
    });
    render(<AssistantHint session={SESSION} anchor="a" />);
    const button = screen.getByRole('button', { name: 'شرح' });
    fireEvent.click(button);
    await waitFor(() => expect(screen.getByText('نص الشرح')).toBeTruthy());
    fireEvent.click(button);
    expect(screen.queryByText('نص الشرح')).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
