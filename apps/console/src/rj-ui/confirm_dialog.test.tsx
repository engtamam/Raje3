import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { ConfirmDialog } from './ConfirmDialog';

afterEach(cleanup);

describe('rj-ui ConfirmDialog', () => {
  it('a plain confirm needs no typed answer', () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog open onClose={vi.fn()} onConfirm={onConfirm} title="متأكد؟"
                    body="سيُعلَّق حساب هذا المحل.">
        محتوى إضافي
      </ConfirmDialog>,
    );
    expect(screen.getByText('محتوى إضافي')).toBeTruthy();
    fireEvent.click(screen.getByText('تأكيد'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('armed mode disables confirm until the exact target name is typed', () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog open onClose={vi.fn()} onConfirm={onConfirm}
                    title="سيُغلق حساب بنشري الملك ويتوقف إرسال رسائله"
                    confirmText="بنشري الملك" />,
    );
    const confirmBtn = screen.getByText('تأكيد').closest('button') as HTMLButtonElement;
    expect(confirmBtn.disabled).toBe(true);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'اسم خطأ' } });
    expect(confirmBtn.disabled).toBe(true);

    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'بنشري الملك' } });
    expect(confirmBtn.disabled).toBe(false);

    fireEvent.click(confirmBtn);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('cancel closes without confirming', () => {
    const onClose = vi.fn();
    const onConfirm = vi.fn();
    render(<ConfirmDialog open onClose={onClose} onConfirm={onConfirm} title="متأكد؟" />);
    fireEvent.click(screen.getByText('إلغاء'));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('busy disables both actions', () => {
    render(<ConfirmDialog open onClose={vi.fn()} onConfirm={vi.fn()} title="متأكد؟" busy />);
    expect((screen.getByText('إلغاء').closest('button') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByText('تأكيد').closest('button') as HTMLButtonElement).disabled).toBe(true);
  });
});
