import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { useAiPanelStore, type EpisodePurpose } from '@/stores/aiPanelStore';

export function AiContextControls({
  projectId,
  chapterId,
  selectedCharacterCount = 0,
  showForeshadows = true,
}: {
  projectId: number | null;
  chapterId: number | null;
  selectedCharacterCount?: number;
  showForeshadows?: boolean;
}) {
  const [foreshadowOpen, setForeshadowOpen] = useState(false);
  const directives = useAiPanelStore((s) => s.getDirectives(projectId, chapterId));
  const setDirectives = useAiPanelStore((s) => s.setDirectives);
  const foreshadows = useQuery({
    queryKey: ['ai-foreshadows', projectId],
    queryFn: () => api.get<Array<{ id: number; title: string; status: string }>>(
      `/projects/${projectId}/foreshadows?status_filter=${encodeURIComponent('설치')}`,
    ),
    enabled: showForeshadows && foreshadowOpen && projectId !== null,
  });

  return (
    <div className="flex flex-col gap-1.5 rounded-sm border border-border/60 p-2">
      <div className="grid grid-cols-[auto_1fr] items-center gap-2">
        <Label htmlFor={`ai-episode-purpose-${chapterId ?? 'none'}`} className="text-xs">회차 목적</Label>
        <Select
          id={`ai-episode-purpose-${chapterId ?? 'none'}`}
          value={directives.episodePurpose}
          onChange={(e) => setDirectives(projectId, chapterId, { episodePurpose: e.target.value as EpisodePurpose })}
        >
          <option value="serial">연재화</option>
          <option value="volume_end">권말</option>
          <option value="series_finale">최종화</option>
        </Select>
      </div>
      <Checkbox
        label="선택 인물 관계 포함"
        checked={directives.includeRelationships}
        disabled={selectedCharacterCount < 2}
        onChange={(e) => setDirectives(projectId, chapterId, { includeRelationships: e.target.checked })}
      />
      {showForeshadows && (
        <ButtonLikeToggle
          open={foreshadowOpen}
          disabled={projectId === null}
          onClick={() => setForeshadowOpen((v) => !v)}
        />
      )}
      {showForeshadows && foreshadowOpen && (foreshadows.data ?? []).length > 0 && (
        <div className="flex flex-col gap-1" aria-label="승인된 복선 회수">
          {(foreshadows.data ?? []).map((f) => (
            <Checkbox
              key={f.id}
              label={`이번 요청에서 회수/공개 허용: ${f.title}`}
              checked={directives.approvedForeshadowIds.includes(f.id)}
              onChange={(e) => {
                const next = e.target.checked
                  ? [...directives.approvedForeshadowIds, f.id]
                  : directives.approvedForeshadowIds.filter((id) => id !== f.id);
                setDirectives(projectId, chapterId, { approvedForeshadowIds: next });
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}


function ButtonLikeToggle({ open, disabled, onClick }: { open: boolean; disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-sm px-1.5 py-1 text-left text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
    >
      {open ? '▾' : '▸'} 복선 회수 승인 선택
    </button>
  );
}
