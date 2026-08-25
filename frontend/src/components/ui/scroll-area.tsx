import { forwardRef, type HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

/** shadcn/ui ScrollArea 수동 구현 — 네이티브 스크롤 + 저채도 얇은 스크롤바 */
export const ScrollArea = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('thin-scroll relative overflow-y-auto', className)} {...props} />
  ),
);
ScrollArea.displayName = 'ScrollArea';
