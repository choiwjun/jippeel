import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

/**
 * shadcn/ui Tooltip 수동 구현 — CSS 호버 기반 경량판.
 * Radix 지연 표시(delayDuration 300)는 Sprint 4b 접근성 강화 시 교체.
 */
export function Tooltip({
  content,
  children,
  className,
}: {
  content: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={cn('group/tt relative inline-flex', className)}>
      {children}
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute bottom-full left-1/2 z-50 mb-1.5 -translate-x-1/2 whitespace-nowrap',
          'rounded-md border border-border bg-popover px-2.5 py-1 text-xs text-popover-foreground shadow-soft',
          'invisible opacity-0 transition-opacity duration-fast group-hover/tt:visible group-hover/tt:opacity-100',
        )}
      >
        {content}
      </span>
    </span>
  );
}
