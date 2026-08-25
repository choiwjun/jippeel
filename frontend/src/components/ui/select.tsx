import type { SelectHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

/** 네이티브 Select 래퍼 — 저채도 톤 통일 (Radix Select 미도입 MVP) */
export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        'h-8 w-full rounded-md border border-input bg-background px-2 text-sm',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50',
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}
