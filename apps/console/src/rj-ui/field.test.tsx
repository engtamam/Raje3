import { describe, expect, it } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Field, Input, Select, Textarea } from './Field';

describe('rj-ui Field/Input/Select/Textarea', () => {
  it('binds the label to the control via htmlFor/id', () => {
    render(
      <Field label="اسم المكافأة" htmlFor="rw-name">
        <Input id="rw-name" defaultValue="غسيل خارجي" />
      </Field>,
    );
    expect(screen.getByLabelText('اسم المكافأة')).toHaveProperty('value', 'غسيل خارجي');
  });

  it('shows the hint, and swaps it for the error when one is given', () => {
    const { rerender } = render(<Field label="ت" hint="تلميح">{<Input />}</Field>);
    expect(screen.getByText('تلميح')).toBeTruthy();
    rerender(<Field label="ت" hint="تلميح" error="خطأ حصل">{<Input />}</Field>);
    expect(screen.queryByText('تلميح')).toBeNull();
    expect(screen.getByRole('alert').textContent).toBe('خطأ حصل');
  });

  it('Select renders its options and reports the chosen value', () => {
    render(
      <Select aria-label="اختر خدمة" defaultValue="b" onChange={() => {}}>
        <option value="a">أ</option>
        <option value="b">ب</option>
      </Select>,
    );
    const el = screen.getByLabelText('اختر خدمة') as HTMLSelectElement;
    expect(el.value).toBe('b');
    fireEvent.change(el, { target: { value: 'a' } });
    expect(el.value).toBe('a');
  });

  it('Textarea defaults to 4 rows and stays overridable', () => {
    render(<Textarea aria-label="نص" />);
    expect(screen.getByLabelText('نص').getAttribute('rows')).toBe('4');
  });
});
