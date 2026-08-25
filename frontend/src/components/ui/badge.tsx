import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export type BadgeVariant = 'default' | 'secondary' | 'outline' | 'draft' | 'revising' | 'done';

const variantClasses: Record<BadgeVariant, string> = {
  default: 'border-transparent bg-primary text-primary-foreground',
  secondary: 'border-transparent bg-muted text-muted-foreground',
  outline: 'text-foreground',
  draft: 'border-transparent bg-status-draft/20 text-status-draft',
  revising: 'border-transparent bg-status-revising/20 text-status-revising',
  done: 'border-transparent bg-status-done/20 text-status-done',
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

/** shadcn/ui Badge 수동 구현 — 회차 상태 칩(FR-105: 초고/수정중/완료) 지원 */
export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
        variantClasses[variant],
        className,
      )}
      {...props}
    />
  );
}

/** FR-105 상태 칩 헬퍼 — 색만으로 정보 전달 금지(§6.2), 텍스트 병기 */
export function StatusBadge({ status }: { status: string }) {
  const variant =
    status === '완료' ? 'done' : status === '수정중' ? 'revising' : 'draft';
  return <Badge variant={variant}>{status}</Badge>;
}
