import type { InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: string;
}

/** FR-404 컨텍스트 포함 체크박스 — 색+텍스트 병기 */
export function Checkbox({ label, className, id, ...props }: CheckboxProps) {
  const inputId = id ?? `cb-${label.replace(/\s+/g, '-')}`;
  return (
    <label htmlFor={inputId} className="flex cursor-pointer items-center gap-2 text-sm">
      <input
        id={inputId}
        type="checkbox"
        className={cn('h-4 w-4 accent-[hsl(var(--primary))]', className)}
        {...props}
      />
      <span>{label}</span>
    </label>
  );
}
