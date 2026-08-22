import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Drawer } from './Drawer';

afterEach(cleanup);

describe('rj-ui Drawer', () => {
  it('renders nothing when closed', () => {
    render(<Drawer open={false} onClose={vi.fn()} title="عنوان">محتوى</Drawer>);
    expect(screen.queryByText('محتوى')).toBeNull();
  });

  it('shows the title, subtitle, children and footer when open', () => {
    render(
      <Drawer open onClose={vi.fn()} title="سبب التعديل" subtitle="اختر واحداً" footer={<span>تذييل</span>}>
        محتوى الدرج
      </Drawer>,
    );
    expect(screen.getByText('سبب التعديل')).toBeTruthy();
    expect(screen.getByText('اختر واحداً')).toBeTruthy();
    expect(screen.getByText('محتوى الدرج')).toBeTruthy();
    expect(screen.getByText('تذييل')).toBeTruthy();
  });

  it('closes on the × button and on Escape', () => {
    const onClose = vi.fn();
    render(<Drawer open onClose={onClose} title="عنوان">محتوى</Drawer>);
    fireEvent.click(screen.getAllByLabelText('إغلاق')[0]);
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
