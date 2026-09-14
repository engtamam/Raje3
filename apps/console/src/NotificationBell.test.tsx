/**
 * The bell: badge count on mount, the panel opens/closes, an unread item marks itself read on
 * click (optimistic), "mark all as read" clears every unread item, and a failed read shows the
 * real failure sentence rather than an empty, silent panel.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { NotificationBell } from './NotificationBell';
import type { Session } from './session';
import { OperatorI18nProvider } from './operator-i18n';

const SESSION_FOR_I18N = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION_FOR_I18N}>{ui}</OperatorI18nProvider>);
}

const SESSION = { token: 'tok-1' } as Session;

let listImpl: () => Promise<unknown[]>;
const readCalls: string[] = [];

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    listNotifications: async () => listImpl(),
    markNotificationRead: async (_s: unknown, id: string) => { readCalls.push(id); },
  };
});

afterEach(() => { cleanup(); readCalls.length = 0; });

function row(over: Partial<{ id: string; title: string; body: string; read: boolean; ts: string }> = {}) {
  return { id: 'n1', title: 'عنوان', body: 'تفصيل', read: false, ts: new Date().toISOString(), ...over };
}

describe('NotificationBell', () => {
  it('shows the unread count as a badge after the initial load', async () => {
    listImpl = async () => [row({ id: 'a' }), row({ id: 'b', read: true })];
    render(<NotificationBell session={SESSION} />);
    await waitFor(() => expect(screen.getByText('1')).toBeTruthy());
  });

  it('no badge at all when everything is read', async () => {
    listImpl = async () => [row({ read: true })];
    render(<NotificationBell session={SESSION} />);
    await waitFor(() => expect(listImpl).toBeTruthy());
    expect(screen.queryByText('1')).toBeNull();
  });

  it('opens the panel and lists the items, newest/unread-first order preserved as given', async () => {
    listImpl = async () => [row({ id: 'a', title: 'الأول' }), row({ id: 'b', title: 'الثاني' })];
    render(<NotificationBell session={SESSION} />);
    fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' }));
    await waitFor(() => expect(screen.getByText('الأول')).toBeTruthy());
    expect(screen.getByText('الثاني')).toBeTruthy();
  });

  it('an empty feed shows the honest empty state', async () => {
    listImpl = async () => [];
    render(<NotificationBell session={SESSION} />);
    fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' }));
    await waitFor(() => expect(screen.getByText('لا توجد إشعارات بعد.')).toBeTruthy());
  });

  it('a failed read shows the real failure sentence, not an empty panel', async () => {
    listImpl = async () => { throw new Error('boom'); };
    render(<NotificationBell session={SESSION} />);
    fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' }));
    await waitFor(() => expect(screen.getByText('تعذّرت قراءة الإشعارات — حاول بعد قليل.')).toBeTruthy());
  });

  it('clicking an unread item marks it read', async () => {
    listImpl = async () => [row({ id: 'n1', title: 'انخفاض تقييم' })];
    render(<NotificationBell session={SESSION} />);
    fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' }));
    await waitFor(() => screen.getByText('انخفاض تقييم'));
    fireEvent.click(screen.getByText('انخفاض تقييم'));
    await waitFor(() => expect(readCalls).toEqual(['n1']));
  });

  it('«تعليم الكل كمقروء» marks every unread item, and only the unread ones', async () => {
    listImpl = async () => [row({ id: 'a' }), row({ id: 'b' }), row({ id: 'c', read: true })];
    render(<NotificationBell session={SESSION} />);
    fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' }));
    await waitFor(() => screen.getByText('تعليم الكل كمقروء'));
    fireEvent.click(screen.getByText('تعليم الكل كمقروء'));
    await waitFor(() => expect(readCalls.sort()).toEqual(['a', 'b']));
  });

  it('«تعليم الكل كمقروء» is absent when nothing is unread', async () => {
    listImpl = async () => [row({ read: true })];
    render(<NotificationBell session={SESSION} />);
    fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' }));
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
    expect(screen.queryByText('تعليم الكل كمقروء')).toBeNull();
  });

  it('opens upward when the bell sits near the bottom of the screen', async () => {
    listImpl = async () => [row()];
    render(<NotificationBell session={SESSION} />);
    const bell = screen.getByRole('button', { name: 'الإشعارات' });
    // Measured off the wrapping <div> (wrapRef), not the button — the bell sits low in AppShell's
    // own rail (right above the theme/language row), so this pins 100px of room left beneath a
    // panel whose own worst case is ~470px.
    vi.spyOn(bell.parentElement as HTMLElement, 'getBoundingClientRect').mockReturnValue(
      { bottom: window.innerHeight - 100, top: 0, left: 0, right: 0, width: 0, height: 0, x: 0, y: 0, toJSON() { return {}; } });
    fireEvent.click(bell);
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
    expect(screen.getByRole('dialog').className).toContain('bottom-full');
  });

  it('opens downward when there is plenty of room below the bell', async () => {
    listImpl = async () => [row()];
    render(<NotificationBell session={SESSION} />);
    const bell = screen.getByRole('button', { name: 'الإشعارات' });
    vi.spyOn(bell.parentElement as HTMLElement, 'getBoundingClientRect').mockReturnValue(
      { bottom: 50, top: 0, left: 0, right: 0, width: 0, height: 0, x: 0, y: 0, toJSON() { return {}; } });
    fireEvent.click(bell);
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
    expect(screen.getByRole('dialog').className).toContain('top-full');
  });

  it('a second click on the bell closes the panel', async () => {
    listImpl = async () => [row()];
    render(<NotificationBell session={SESSION} />);
    const bell = screen.getByRole('button', { name: 'الإشعارات' });
    fireEvent.click(bell);
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
    fireEvent.click(bell);
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
