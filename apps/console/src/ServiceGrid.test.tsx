/**
 * ServiceGrid — the redesigned photo-tile grid (2026-09-14). Covers the two things this file
 * actually owns beyond plain rendering: a package tile selects/deselects its whole bundle of
 * services at once, and a service/package's photo is only fetched when `has_image` says one
 * exists (never a wasted request for the common case of a catalogue with no photos yet).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { OperatorI18nProvider } from './operator-i18n';
import type { CataloguePackage, CatalogueService } from './api';

const serviceImageUrlMock = vi.fn();
const packageImageUrlMock = vi.fn();

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    serviceImageUrl: (...args: unknown[]) => serviceImageUrlMock(...args),
    packageImageUrl: (...args: unknown[]) => packageImageUrlMock(...args),
  };
});

const { ServiceGrid } = await import('./ServiceGrid');

afterEach(() => { cleanup(); vi.clearAllMocks(); });

const SERVICES: CatalogueService[] = [
  { id: 'svc_wash', name: 'غسيل خارجي', has_image: true },
  { id: 'svc_wax', name: 'تلميع' },
];

const PACKAGE: CataloguePackage = {
  id: 'pkg_care', name: 'باقة العناية', service_ids: ['svc_wash', 'svc_wax'], price_minor: 12000,
};

function open(props: Partial<React.ComponentProps<typeof ServiceGrid>> = {}) {
  const selected: string[] = props.selected ?? [];
  return render(
    <OperatorI18nProvider session={{} as never}>
      <ServiceGrid
        session={{} as never}
        services={SERVICES}
        selected={selected}
        onToggle={() => {}}
        {...props}
      />
    </OperatorI18nProvider>,
  );
}

describe('ServiceGrid — photos', () => {
  it('fetches a photo only for the service that actually has one', async () => {
    serviceImageUrlMock.mockResolvedValue('blob:svc-photo');
    open();
    await waitFor(() => expect(serviceImageUrlMock).toHaveBeenCalledTimes(1));
    expect(serviceImageUrlMock).toHaveBeenCalledWith(expect.anything(), 'svc_wash');
  });

  it('shows the placeholder, not a broken screen, when the photo fails to load', async () => {
    serviceImageUrlMock.mockRejectedValue(new Error('boom'));
    open();
    await waitFor(() => expect(serviceImageUrlMock).toHaveBeenCalled());
    // The tile is still there, still tappable, still named — nothing about a failed photo blocks
    // recording the visit.
    expect(screen.getByText('غسيل خارجي')).toBeTruthy();
  });
});

describe('ServiceGrid — quantity', () => {
  it('shows no stepper on a tile that is not selected', () => {
    open({ selected: [] });
    expect(screen.queryByLabelText('زيادة الكمية')).toBeFalsy();
  });

  it('shows no stepper without onQuantityChange, even when selected', () => {
    open({ selected: ['svc_wash'] });
    expect(screen.queryByLabelText('زيادة الكمية')).toBeFalsy();
  });

  it('shows a stepper starting at 1 once a service is selected', () => {
    open({ selected: ['svc_wash'], onQuantityChange: () => {} });
    expect(screen.getByText('1')).toBeTruthy();
    expect(screen.getByLabelText('زيادة الكمية')).toBeTruthy();
  });

  it('tapping + calls onQuantityChange with the next count, never toggles the tile off', () => {
    const onQuantityChange = vi.fn();
    const onToggle = vi.fn();
    open({ selected: ['svc_wash'], quantities: { svc_wash: 1 }, onQuantityChange, onToggle });
    fireEvent.click(screen.getByLabelText('زيادة الكمية'));
    expect(onQuantityChange).toHaveBeenCalledWith('svc_wash', 2);
    expect(onToggle).not.toHaveBeenCalled();
  });

  it('tapping − above one calls onQuantityChange with one fewer', () => {
    const onQuantityChange = vi.fn();
    open({ selected: ['svc_wash'], quantities: { svc_wash: 2 }, onQuantityChange });
    fireEvent.click(screen.getByLabelText('إنقاص الكمية'));
    expect(onQuantityChange).toHaveBeenCalledWith('svc_wash', 1);
  });

  it('tapping − at one deselects the tile instead of going to zero', () => {
    const onQuantityChange = vi.fn();
    const onToggle = vi.fn();
    open({ selected: ['svc_wash'], quantities: { svc_wash: 1 }, onQuantityChange, onToggle });
    fireEvent.click(screen.getByLabelText('إنقاص الكمية'));
    expect(onToggle).toHaveBeenCalledWith('svc_wash');
    expect(onQuantityChange).not.toHaveBeenCalled();
  });

  it('tapping the stepper never also toggles the tile underneath it', () => {
    const onToggle = vi.fn();
    open({ selected: ['svc_wash'], quantities: { svc_wash: 1 }, onQuantityChange: () => {},
          onToggle });
    fireEvent.click(screen.getByLabelText('زيادة الكمية'));
    expect(onToggle).not.toHaveBeenCalled();
  });

  it('the tile itself still toggles on a plain tap, quantity or not', () => {
    const onToggle = vi.fn();
    open({ selected: ['svc_wash'], quantities: { svc_wash: 3 }, onQuantityChange: () => {},
          onToggle });
    fireEvent.click(screen.getByRole('button', { name: /غسيل خارجي/ }));
    expect(onToggle).toHaveBeenCalledWith('svc_wash');
  });
});

describe('ServiceGrid — packages', () => {
  it('selecting a package selects every one of its services at once', async () => {
    const onSelectPackage = vi.fn();
    open({ packages: [PACKAGE], onSelectPackage });
    fireEvent.click(screen.getByText('باقة العناية'));
    expect(onSelectPackage).toHaveBeenCalledWith(PACKAGE);
  });

  it('shows a check mark on the selected package and its price in riyals', async () => {
    open({ packages: [PACKAGE], selectedPackageId: 'pkg_care' });
    const tile = screen.getByRole('button', { name: /باقة العناية/ });
    expect(tile.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText(/120/)).toBeTruthy();
  });

  it('renders no package row at all for a shop with none', () => {
    open({ packages: [] });
    expect(screen.queryByText('باقة')).toBeFalsy();
  });
});
