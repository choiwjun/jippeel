/**
 * 회차 품질 진단 — 고도화 G-030~G-032.
 * 규칙 기반(로컬, LLM 호출 없음) 지표 + 개선 제안 + 제안 프리셋 바로가기.
 * 제안 프리셋 클릭 시 AI 패널 프리셋을 선택해 열어준다(자동 실행 아님).
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { useAiPanelStore } from '@/stores/aiPanelStore';
import { Button } from '@/components/ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Progress } from '@/components/ui/progress';
import { toast } from '@/components/ui/toast';
export interface QualityMetrics {
  chars_novelpia: number;
  dialogue_ratio: number;
  avg_para_chars: number;
  ending_repeat_per_1k: number;
  connector_per_1k: number;
  para_opener_variety: number;
  hook_present: boolean;
  para_count: number;
}

export interface ChapterQuality {
  chapter_id: number;
  score: number;
  metrics: QualityMetrics;
  suggestions: string[];
  suggested_preset_names: string[];
}

export function QualityDialog({ chapterId }: { chapterId: number | null }) {
  const [open, setOpen] = useState(false);
  const setPreset = useAiPanelStore((s) => s.setPreset);
  const presets = useAiPanelStore((s) => s.presetId);
  const openAiPanel = useAiPanelStore((s) => s.open);
  void presets;

  const qualityQuery = useQuery({
    queryKey: ['quality', chapterId],
    queryFn: () => api.get<ChapterQuality>(`/chapters/${chapterId}/quality`),
    enabled: chapterId !== null && open,
  });
  const q = qualityQuery.data;

  /** 제안 프리셋을 AI 패널 프리셋 셀렉트에 반영(실행은 작가가 직접) */
  const usePreset = async (name: string) => {
    try {
      const all = await api.get<Array<{ id: number; name: string }>>('/ai/presets');
      const found = all.find((p) => p.name === name);
      if (!found) {
        toast(`프리셋 "${name}"을 찾을 수 없습니다.`, 'warning');
        return;
      }
      setPreset(found.id);
      openAiPanel();
      toast(`프리셋 "${name}"을 선택했습니다 — AI 패널에서 실행하세요.`, 'info');
    } catch (e) {
      toast(`프리셋 조회 실패: ${(e as Error).message}`, 'error');
    }
  };

  const scoreColor = q == null ? '' : q.score >= 80 ? 'text-success' : q.score >= 60 ? 'text-warning' : 'text-destructive';

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button
        size="sm"
        variant="outline"
        disabled={chapterId === null}
        onClick={() => setOpen(true)}
        aria-label="회차 품질 진단"
      >
        품질 진단
      </Button>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>회차 품질 진단 (로컬 규칙 기반)</DialogTitle>
        </DialogHeader>
        {qualityQuery.isPending && (
          <p className="text-sm text-muted-foreground">계산 중…</p>
        )}
        {qualityQuery.isError && (
          <p className="text-sm text-destructive">{(qualityQuery.error as Error).message}</p>
        )}
        {q && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <span className="text-2xl font-bold">{q.score}</span>
              <span className="text-xs text-muted-foreground">/ 100</span>
              <Progress value={q.score} className="flex-1" aria-label="품질 점수" />
              <span className={`text-xs font-semibold ${scoreColor}`}>
                {q.score >= 80 ? '양호' : q.score >= 60 ? '보완 필요' : '개선 권장'}
              </span>
            </div>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              <div className="flex justify-between"><dt className="text-muted-foreground">대사 비율</dt><dd>{(q.metrics.dialogue_ratio * 100).toFixed(0)}%</dd></div>
              <div className="flex justify-between"><dt className="text-muted-foreground">평균 문단</dt><dd>{q.metrics.avg_para_chars}자</dd></div>
              <div className="flex justify-between"><dt className="text-muted-foreground">어미 반복/1k</dt><dd>{q.metrics.ending_repeat_per_1k}회</dd></div>
              <div className="flex justify-between"><dt className="text-muted-foreground">접속사/1k</dt><dd>{q.metrics.connector_per_1k}회</dd></div>
              <div className="flex justify-between"><dt className="text-muted-foreground">후크(끝 300자)</dt><dd>{q.metrics.hook_present ? '있음' : '없음'}</dd></div>
              <div className="flex justify-between"><dt className="text-muted-foreground">공백제외 글자</dt><dd>{q.metrics.chars_novelpia.toLocaleString()}자</dd></div>
            </dl>
            {q.suggestions.length > 0 && (
              <ul className="flex flex-col gap-1.5 rounded-md border border-border p-2">
                {q.suggestions.map((s, i) => (
                  <li key={i} className="text-xs leading-snug">· {s}</li>
                ))}
              </ul>
            )}
            {q.suggested_preset_names.length > 0 && (
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[11px] text-muted-foreground">추천 프리셋:</span>
                {q.suggested_preset_names.map((name) => (
                  <Button
                    key={name}
                    size="sm"
                    variant="outline"
                    className="h-6 px-2 text-[11px]"
                    onClick={() => void usePreset(name)}
                  >
                    {name}
                  </Button>
                ))}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground">
              지표는 웹소설 연재 관례 기준 참고값입니다 — 최종 판단은 작가의 몫입니다.
            </p>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
