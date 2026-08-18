/**
 * The rail's branch control: four states, and only one of them is a dropdown.
 *
 * WHAT THIS IS WRITTEN AFTER. Tamam opened the console and asked «الشريط الجانبي ما فيه التبديل
 * بين الفروع، ليه؟ ما أشوفه». The answer for his shop was the right one — one branch is no choice
 * — but the code could not have told him a different answer, and that is the defect:
 * `App.tsx` kept `null` for «could not read» and `[]` for «none», then collapsed both into `[]`
 * one line before rendering. So a chain of four branches whose scope read failed saw exactly what
 * a single-branch shop sees: nothing at all. Its screens silently showed the whole chain, and its
 * owner never learned that a choice existed and had not been offered.
 *
 * AND THE SECOND HALF IS HIS OWN IDEA: «هل ممكن نخلي انشاء الفروع من المبدل نفسه؟» — the moment a
 * person wants a second branch is the moment he is looking at this control, so the door is here,
 * drawn from the CAPABILITY and never from a role.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BranchSwitch } from './BranchSwitch';
import { DENIED } from './loading';
import type { Catalog } from './catalog';

const CAN_ADD = {
  services: [{ service: 'operations', actions: [{ id: 'operations.create_branch' }] }],
  unreachable: [],
} as unknown as Catalog;
const CANNOT_ADD = { services: [], unreachable: [] } as unknown as Catalog;

const TWO = [{ id: 'b1', name: 'الرياض' }, { id: 'b2', name: 'جدة' }];

describe('the branch control in the rail', () => {
  it('offers the choice when there is one to make', () => {
    render(<BranchSwitch branches={TWO} branch="" onChange={() => {}} catalog={CANNOT_ADD} />);
    expect(screen.getByLabelText('الفرع المعروض')).toBeTruthy();
  });

  it('says NOTHING for a shop with one branch', () => {
    const { container } = render(
      <BranchSwitch branches={[{ id: 'b1', name: 'الرياض' }]} branch=""
                    onChange={() => {}} catalog={CANNOT_ADD} />,
    );
    // A filter that cannot change anything is a question asked a hundred times a day for nothing.
    expect(container.textContent).toBe('');
  });

  it('SAYS SO when the scope could not be read — the whole point', () => {
    render(<BranchSwitch branches={null} branch="" onChange={() => {}} catalog={CANNOT_ADD} />);
    // Before the fix this rendered exactly like the single-branch case: silence, and screens
    // quietly showing the whole chain.
    expect(screen.getByText(/تعذّرت قراءة فروعك/)).toBeTruthy();
  });

  it('stays silent for a person whose role does not carry the read', () => {
    const { container } = render(
      <BranchSwitch branches={DENIED} branch="" onChange={() => {}} catalog={CANNOT_ADD} />,
    );
    // Denied is not a failure: nothing about branches concerns him, so nothing is said.
    expect(container.textContent).toBe('');
  });

  it('offers «أضف فرعاً» to whoever may create one, even with a single branch', () => {
    const onAdd = vi.fn();
    render(<BranchSwitch branches={[{ id: 'b1', name: 'الرياض' }]} branch=""
                         onChange={() => {}} catalog={CAN_ADD} onAdd={onAdd} />);
    screen.getByText('أضف فرعاً').click();
    expect(onAdd).toHaveBeenCalled();
  });

  it('never offers it to somebody the catalogue did not give the action to', () => {
    render(<BranchSwitch branches={TWO} branch="" onChange={() => {}}
                         catalog={CANNOT_ADD} onAdd={() => {}} />);
    // An offer he cannot take is a small lie repeated every day.
    expect(screen.queryByText('أضف فرعاً')).toBeNull();
  });
});
