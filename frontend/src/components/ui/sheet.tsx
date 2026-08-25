import { useEffect, type HTMLAttributes, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';

interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  side?: 'right' | 'left';
  /** 설계서 §1.2 — XL 480px / L 420px / M 380px (MVP는 고정 폭 + 반응형 max) */
  width?: number;
  children: ReactNode;
}

/** shadcn/ui Sheet 수동 구현 — 우측 슬라이드 드로어(S5/S6 오버레이) */
export function Sheet({ open, onOpenChange, side = 'right', width = 480, children }: SheetProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onOpenChange(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onOpenChange]);

  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/40" onClick={() => onOpenChange(false)} aria-hidden="true" />
      <aside
        role="dialog"
        aria-modal="true"
        style={{ width: `min(${width}px, 100vw)` }}
        className={cn(
          'absolute top-0 flex h-full flex-col border-border bg-card text-card-foreground shadow-soft',
          side === 'right' ? 'right-0 border-l' : 'left-0 border-r',
        )}
      >
        {children}
      </aside>
    </div>,
    document.body,
  );
}

export function SheetHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex h-12 shrink-0 items-center justify-between border-b border-border px-4', className)}
      {...props}
    />
  );
}

export function SheetTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn('text-sm font-semibold', className)} {...props} />;
}

export function SheetBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('thin-scroll min-h-0 flex-1 overflow-y-auto p-4', className)} {...props} />;
}

export function SheetFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn('shrink-0 border-t border-border px-4 py-3', className)} {...props} />
  );
}
