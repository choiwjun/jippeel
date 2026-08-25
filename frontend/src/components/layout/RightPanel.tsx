import { Sheet, SheetBody, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { CloseIcon } from '@/components/ui/icons';
import { AiPanel } from '@/components/panels/AiPanel';
import { RefineReport } from '@/components/panels/RefineReport';
import { useAiPanelStore } from '@/stores/aiPanelStore';

/** §1.1 RightPanel — S5 AI 패널/S6 윤문 리포트가 겹쳐 열리는 단일 Sheet (mode 스위치) */
export function RightPanel() {
  const isOpen = useAiPanelStore((s) => s.isOpen);
  const close = useAiPanelStore((s) => s.close);
  const mode = useAiPanelStore((s) => s.mode);

  return (
    <Sheet open={isOpen} onOpenChange={(o) => (!o ? close() : undefined)} width={480}>
      <SheetHeader>
        <SheetTitle>{mode === 'refine' ? '윤문 리포트' : 'AI 어시스턴트'}</SheetTitle>
        <Button variant="ghost" size="sm" onClick={close} aria-label="패널 닫기">
          <CloseIcon />
        </Button>
      </SheetHeader>
      <SheetBody className="flex flex-col gap-3">
        {mode === 'refine' ? <RefineReport /> : <AiPanel />}
      </SheetBody>
    </Sheet>
  );
}
