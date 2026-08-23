/**
 * «بوابة المسوّق» — the one property worth a render test: which pane opens, and off what.
 */
import { afterEach, describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { AffiliateDoor } from './AffiliateDoor';

function setSearch(qs: string) {
  window.history.replaceState({}, '', `/affiliates${qs}`);
}

describe('AffiliateDoor', () => {
  afterEach(() => setSearch(''));

  it('opens on sign-in by default, not on the shop\'s own copy', () => {
    setSearch('');
    render(<AffiliateDoor onSignedIn={() => {}} />);
    expect(screen.getByText('أهلاً بك')).toBeTruthy();
    // THE HERO IS THIS PRODUCT'S OWN — a marketer reading «افتح محلك» would think the wrong app
    // loaded. See DoorLayout.tsx's new title/subtitle props.
    expect(screen.getByText('عمولتك تكبر وأنت نائم.')).toBeTruthy();
  });

  it('opens on «تقديم طلب» when the link carries ?ref= — a referral link means apply, not log in', () => {
    setSearch('?ref=aff-1');
    render(<AffiliateDoor onSignedIn={() => {}} />);
    expect(screen.getByText('انضم كمسوّق')).toBeTruthy();
  });

  it('the apply pane keeps «إرسال الطلب» disabled until every field and the consent box are set', () => {
    setSearch('');
    const { container } = render(<AffiliateDoor onSignedIn={() => {}} />);
    const buttons = Array.from(container.querySelectorAll('button'));
    const applyTab = buttons.find((b) => b.textContent === 'تقديم طلب');
    if (!applyTab) throw new Error('apply tab not found');
    fireEvent.click(applyTab);
    const submit = screen.getByRole('button', { name: /إرسال الطلب/ });
    expect(submit.hasAttribute('disabled')).toBe(true);
  });
});
