import { useEffect, useState } from 'react';
import { create } from 'zustand';
import { cn } from '@/lib/utils';

/**
 * 경량 토스트 — sonner 미도입 MVP 대체.
 * aria-live="polite"(성공/정보), assertive(에러) 역할로 a11y 유지.
 */
export type ToastVariant = 'info' | 'success' | 'warning' | 'error';

export interface ToastItem {
  id: number;
  title: string;
  variant: ToastVariant;
}

interface ToastState {
  toasts: ToastItem[];
  push: (title: string, variant?: ToastVariant) => void;
  dismiss: (id: number) => void;
}

let nextId = 1;

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (title, variant = 'info') => {
    const id = nextId++;
    set((s) => ({ toasts: [...s.toasts.slice(-3), { id, title, variant }] }));
    window.setTimeout(() => get().dismiss(id), 3500);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export function toast(title: string, variant?: ToastVariant) {
  useToastStore.getState().push(title, variant);
}

const variantClasses: Record<ToastVariant, string> = {
  info: 'border-info/40 bg-card text-foreground',
  success: 'border-status-done/40 bg-card text-foreground',
  warning: 'border-warning/50 bg-card text-foreground',
  error: 'border-destructive/50 bg-card text-foreground',
};

export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted || toasts.length === 0) return null;

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="fixed bottom-11 right-4 z-[60] flex flex-col gap-2"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role={t.variant === 'error' ? 'alert' : 'status'}
          onClick={() => dismiss(t.id)}
          className={cn(
            'cursor-pointer rounded-md border px-4 py-2.5 text-sm shadow-soft transition-opacity',
            variantClasses[t.variant],
          )}
        >
          {t.title}
        </div>
      ))}
    </div>
  );
}
