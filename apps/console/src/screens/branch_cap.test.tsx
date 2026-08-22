/**
 * A full plan is an offer, not a refusal.
 *
 * WHAT IT USED TO DO. At the branch cap the button vanished and a grey sentence took its place:
 * «بلغت عدد الفروع المتاحة في باقتك. للمزيد، رقِّ باقتك من «متجر التطبيقات».» Two things wrong at
 * once — a control that disappears teaches an owner the product cannot do the thing, and the place
 * it named existed nowhere in the console.
 *
 * THE FIX: give the owner the choice — let them press it, and only then show the message with a
 * link to the upgrade card.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { STORE_PATH } from '../nav';

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return { ...real, action: () => null, call: async () => ({}) };
});

const { Branches } = await import('./Team');

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;
const may = { id: 'operations.create_branch', label: 'x', method: 'POST', path: '/x' } as never;

function open(mayAdd: boolean | undefined) {
  return render(
    <MemoryRouter>
      <Branches
        session={session}
        catalog={catalog}
        branches={[{ id: 'b1', name: 'الفرع الأول' }] as never}
        operators={[] as never}
        add={may}
        edit={null as never}
        mayRead
        limit={3}
        mayAdd={mayAdd}
        onChanged={() => {}}
      />
    </MemoryRouter>,
  );
}

describe('the branch cap', () => {
  it('keeps the button at the cap instead of deleting it', () => {
    open(false);
    expect(screen.getByRole('button', { name: 'إضافة فرع' })).toBeTruthy();
  });

  it('answers the press with an offer and a door', () => {
    open(false);
    fireEvent.click(screen.getByRole('button', { name: 'إضافة فرع' }));
    expect(screen.getByText(/وصلت إلى عدد الفروع/)).toBeTruthy();
    const link = screen.getByRole('link', { name: 'افتح متجر التطبيقات' });
    expect(link.getAttribute('href')).toContain(STORE_PATH);
  });

  it('opens the form, not the offer, when the plan has room', () => {
    open(true);
    fireEvent.click(screen.getByRole('button', { name: 'إضافة فرع' }));
    expect(screen.getByLabelText(/اسم الفرع/)).toBeTruthy();
  });

  it('opens the form when the cap never answered, rather than selling him something', () => {
    // `undefined` is «we could not ask billing». Reading that as «you are full» would put an
    // upgrade card in front of a shop on its first branch because a service was slow.
    open(undefined);
    fireEvent.click(screen.getByRole('button', { name: 'إضافة فرع' }));
    expect(screen.getByLabelText(/اسم الفرع/)).toBeTruthy();
  });
});
