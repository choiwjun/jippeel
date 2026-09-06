import { cn } from '@/lib/utils';

interface ProgressProps {
  value: number;          // 0~100
  barClassName?: string;  // 게이트 색상 등 커스텀
  className?: string;
  /** 접근성 — 스크린리더가 진행 표시줄을 읽을 수 있게 한다 (TC-501) */
  'aria-label'?: string;
}

/** shadcn/ui Progress 수동 구현 — S6 변경률 게이트(FR-505) 시각화에 색 토큰 적용 */
export function Progress({ value, barClassName, className, 'aria-label': ariaLabel }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div
      role="progressbar"
      aria-label={ariaLabel}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(clamped)}
      className={cn('h-2.5 w-full overflow-hidden rounded-full bg-muted', className)}
    >
      <div
        className={cn('h-full rounded-full bg-primary transition-all duration-200', barClassName)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
