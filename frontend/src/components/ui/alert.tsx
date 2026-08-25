import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export type AlertVariant = 'default' | 'info' | 'warning' | 'error';

const variantClasses: Record<AlertVariant, string> = {
  default: 'border-border text-card-foreground',
  info: 'border-info/40 bg-info/10 text-foreground [&>svg]:text-info',
  warning: 'border-warning/40 bg-warning/10 text-foreground [&>svg]:text-warning',
  error: 'border-destructive/40 bg-destructive/10 text-foreground [&>svg]:text-destructive',
};

export interface AlertProps extends HTMLAttributes<HTMLDivElement> {
  variant?: AlertVariant;
}

/** shadcn/ui Alert 수동 구현 — P1/NFR-201/NFR-404 안내 문구용 */
export function Alert({ className, variant = 'default', ...props }: AlertProps) {
  return (
    <div
      role="alert"
      className={cn('relative w-full rounded-md border px-4 py-3 text-sm [&:has(+*)&]:mt-2', variantClasses[variant], className)}
      {...props}
    />
  );
}

export function AlertTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h5 className={cn('mb-1 font-semibold leading-none tracking-wide', className)} {...props} />;
}

export function AlertDescription({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('[&_p]:leading-relaxed', className)} {...props} />;
}
