/**
 * AdminPortal's own tab<->URL wiring — see AdminPortal.tsx's header note: the tab used to be a bare
 * `useState`, resetting to "الرئيسية" on every refresh no matter where the operator actually was.
 * Every tab screen is mocked to a bare marker here on purpose: this file tests ONLY the routing
 * decision (which marker renders for a given URL, and where a click/refresh lands), not any real
 * screen's own behaviour — those are each screen's own test file's job.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AdminPortal } from './AdminPortal';
import { KEY } from './session';

vi.mock('./AdminHome', () => ({ AdminHome: () => <div>مقياس الرئيسية</div> }));
vi.mock('./AdminApps', () => ({ AdminApps: () => <div>مقياس التطبيقات</div> }));
vi.mock('./AdminCustomers', () => ({ AdminCustomers: () => <div>مقياس العملاء</div> }));
vi.mock('./AdminTickets', () => ({ AdminTickets: () => <div>مقياس التذاكر</div> }));
vi.mock('./AdminFinance', () => ({
  AdminFinance: ({ onOpenProviderSecrets }: { onOpenProviderSecrets: () => void }) => (
    <div>
      مقياس المالية
      <button onClick={onOpenProviderSecrets}>افتح بوابة الدفع</button>
    </div>
  ),
}));
vi.mock('./AdminProviderSecrets', () => ({
  AdminProviderSecrets: ({ initialOpenProvider }: { initialOpenProvider?: string }) => (
    <div>مقياس المزوّدين{initialOpenProvider ? ` — ${initialOpenProvider}` : ''}</div>
  ),
}));
vi.mock('./AdminPlatform', () => ({ AdminPlatform: () => <div>مقياس المنصّة</div> }));
vi.mock('./AdminAccount', () => ({ AdminAccount: () => <div>مقياس الحساب</div> }));

function signIn() {
  localStorage.setItem(KEY, JSON.stringify({ access_token: 'tok-1' }));
}

afterEach(() => { localStorage.clear(); vi.clearAllMocks(); });

describe('AdminPortal — tab lives in the URL', () => {
  it('the root path shows "الرئيسية", the default tab', () => {
    signIn();
    render(<MemoryRouter initialEntries={['/']}><AdminPortal /></MemoryRouter>);
    expect(screen.getByText('مقياس الرئيسية')).toBeTruthy();
  });

  it('a direct visit to a tab\'s own path shows that tab immediately — this IS what a page refresh replays', () => {
    signIn();
    render(<MemoryRouter initialEntries={['/customers']}><AdminPortal /></MemoryRouter>);
    expect(screen.getByText('مقياس العملاء')).toBeTruthy();
    expect(screen.queryByText('مقياس الرئيسية')).toBeNull();
  });

  it('clicking a sidebar tab updates the URL, not just an in-memory flag', () => {
    signIn();
    render(<MemoryRouter initialEntries={['/']}><AdminPortal /></MemoryRouter>);
    // العنوان يظهر مرتين (الشريط الجانبي وشريط الأسفل) — أي واحد يفتح نفس التبويب.
    fireEvent.click(screen.getAllByText('تذاكر')[0]);
    expect(screen.getByText('مقياس التذاكر')).toBeTruthy();
  });

  it('an unknown/stale path falls back to "الرئيسية" instead of a blank screen', () => {
    signIn();
    render(<MemoryRouter initialEntries={['/no-such-tab']}><AdminPortal /></MemoryRouter>);
    expect(screen.getByText('مقياس الرئيسية')).toBeTruthy();
  });

  it('the finance screen\'s "بوابة الدفع" deep link opens providers with that category pre-selected', () => {
    signIn();
    render(<MemoryRouter initialEntries={['/billing']}><AdminPortal /></MemoryRouter>);
    fireEvent.click(screen.getByText('افتح بوابة الدفع'));
    expect(screen.getByText('مقياس المزوّدين — payment')).toBeTruthy();
  });

  it('a manual tab click after the deep link is a fresh visit — the pre-selected category does not follow it', () => {
    signIn();
    render(<MemoryRouter initialEntries={['/billing']}><AdminPortal /></MemoryRouter>);
    fireEvent.click(screen.getByText('افتح بوابة الدفع'));
    expect(screen.getByText('مقياس المزوّدين — payment')).toBeTruthy();

    fireEvent.click(screen.getAllByText('المنصّة والفريق')[0]);
    fireEvent.click(screen.getAllByText('المزوّدين الخارجيين')[0]);
    expect(screen.getByText('مقياس المزوّدين')).toBeTruthy();
    expect(screen.queryByText('مقياس المزوّدين — payment')).toBeNull();
  });
});
