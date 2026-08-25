import { useEffect, type ReactNode } from 'react';
import { TopBar } from './TopBar';
import { LeftSidebar } from './LeftSidebar';
import { StatusBar } from './StatusBar';
import { RightPanel } from './RightPanel';
import { useAiPanelStore } from '@/stores/aiPanelStore';
import { Toaster } from '@/components/ui/toast';

/** §1.1 3분할 레이아웃 — TopBar / (LeftSidebar | CenterStage | RightPanel) / StatusBar */
export function AppShell({ children }: { children: ReactNode }) {
  // 전역 단축키 Alt+A(패널 토글) / Alt+R(윤문 실행) — NFR-303
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey && e.code === 'KeyA') {
        e.preventDefault();
        useAiPanelStore.getState().toggle();
      } else if (e.altKey && e.code === 'KeyR') {
        e.preventDefault();
        const store = useAiPanelStore.getState();
        store.setMode('refine');
        store.open();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <LeftSidebar />
        <main className="min-w-0 flex-1 overflow-y-auto thin-scroll">{children}</main>
        <RightPanel />
      </div>
      <StatusBar />
      <Toaster />
    </div>
  );
}
