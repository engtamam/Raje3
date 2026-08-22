/**
 * Our own Skeleton — component #3. Same API as @base-ui/design-system/Skeleton (width/height/radius,
 * plus every native div prop), so a call site needs only the import changed.
 *
 * `animate-pulse` is Tailwind's own utility and already respects `prefers-reduced-motion` through the
 * global rule in index.css — nothing to reimplement there, only the surface colour and shape.
 */
import type { CSSProperties, HTMLAttributes } from 'react';

export interface RjSkeletonProps extends HTMLAttributes<HTMLDivElement> {
  width?: number | string;
  height?: number | string;
  radius?: 'sm' | 'md' | 'card' | 'full' | 'text';
}

const RADIUS = {
  sm: 'rounded-sm',
  md: 'rounded-md',
  card: 'rounded-card',
  full: 'rounded-full',
  text: 'rounded',
} as const;

export function Skeleton({ width, height, radius = 'md', className, style, ...props }: RjSkeletonProps) {
  const s: CSSProperties = { ...style };
  if (width != null) s.width = width;
  if (height != null) s.height = height;
  return (
    <div
      aria-hidden
      className={[
        'animate-pulse bg-surface-2',
        radius === 'text' ? 'h-[0.85em]' : '',
        RADIUS[radius],
        className ?? '',
      ].filter(Boolean).join(' ')}
      style={s}
      {...props}
    />
  );
}
