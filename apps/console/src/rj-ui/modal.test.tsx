import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { Modal } from './Modal';

afterEach(cleanup);

describe('rj-ui Modal', () => {
  it('renders nothing when closed', () => {
    render(<Modal open={false} onClose={vi.fn()} title="عنوان">محتوى</Modal>);
    expect(screen.queryByText('محتوى')).toBeNull();
  });

  it('shows the title, subtitle and children when open', () => {
    render(
      <Modal open onClose={vi.fn()} title="من يحفظ؟" subtitle="فرعك">
        محتوى الحوار
      </Modal>,
    );
    expect(screen.getByText('من يحفظ؟')).toBeTruthy();
    expect(screen.getByText('فرعك')).toBeTruthy();
    expect(screen.getByText('محتوى الحوار')).toBeTruthy();
  });

  it('closes on the × button, the backdrop, and Escape', () => {
    const onClose = vi.fn();
    render(<Modal open onClose={onClose} title="عنوان">محتوى</Modal>);
    fireEvent.click(screen.getByLabelText('إغلاق'));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
