/**
 * 장면(Scene) 관리 — 고도화 G-010/G-012.
 * 현재 회차의 장면 목록을 만들고, AI 패널에서 "현재 장면"으로 선택해
 * 장면 단위 AI 생성의 대상을 지정한다. 결과 반영은 여전히 P1 수동 삽입만.
 */
import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from '@/components/ui/toast';

export interface Scene {
  id: number;
  chapter_id: number;
  sort_order: number;
  title: string;
  content_md: string;
}

export function SceneManager({
  chapterId,
  sceneId,
  onPick,
}: {
  chapterId: number | null;
  sceneId: number | null;
  onPick: (sceneId: number | null) => void;
}) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Scene | null>(null);
  const [draftTitle, setDraftTitle] = useState('');
  const [draftContent, setDraftContent] = useState('');

  const scenesQuery = useQuery({
    queryKey: ['scenes', chapterId],
    queryFn: () => api.get<Scene[]>(`/chapters/${chapterId}/scenes`),
    enabled: chapterId !== null,
  });
  const scenes = scenesQuery.data ?? [];

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['scenes', chapterId] });

  const createScene = useMutation({
    mutationFn: () => api.post<Scene>(`/chapters/${chapterId}/scenes`, {
      title: draftTitle,
      content_md: draftContent,
      sort_order: Date.now() % 1e7,
    }),
    onSuccess: () => {
      setDraftTitle('');
      setDraftContent('');
      void invalidate();
      toast('장면을 추가했습니다.', 'success');
    },
    onError: (e) => toast(`장면 추가 실패: ${(e as Error).message}`, 'error'),
  });

  const updateScene = useMutation({
    mutationFn: (s: Scene) =>
      api.patch<Scene>(`/scenes/${s.id}`, {
        title: draftTitle || s.title,
        content_md: draftContent,
      }),
    onSuccess: () => {
      setEditing(null);
      void invalidate();
      toast('장면을 저장했습니다.', 'success');
    },
    onError: (e) => toast(`장면 저장 실패: ${(e as Error).message}`, 'error'),
  });

  const deleteScene = useMutation({
    mutationFn: (id: number) => api.del(`/scenes/${id}`),
    onSuccess: () => {
      if (sceneId !== null) onPick(null);
      void invalidate();
      toast('장면을 삭제했습니다.', 'success');
    },
    onError: (e) => toast(`장면 삭제 실패: ${(e as Error).message}`, 'error'),
  });

  const startEdit = (s: Scene) => {
    setEditing(s);
    setDraftTitle(s.title);
    setDraftContent(s.content_md);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <Button
        variant="ghost" size="sm" className="h-6 px-2 text-[11px]"
        onClick={() => setOpen(true)}
        aria-label="장면 관리 열기"
      >
        장면 관리 ({scenes.length})
      </Button>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>현재 회차 장면 관리</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-2">
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <Input
              aria-label="장면 제목"
              placeholder="장면 제목 (예: 골목 대치)"
              value={draftTitle}
              onChange={(e) => setDraftTitle(e.target.value)}
            />
            <Button
              size="sm"
              disabled={createScene.isPending || (!draftTitle.trim() && !draftContent.trim())}
              onClick={() => createScene.mutate()}
            >
              + 추가
            </Button>
          </div>
          <Textarea
            aria-label="장면 본문"
            placeholder="장면 본문을 붙여넣거나 직접 쓰세요…"
            rows={4}
            value={draftContent}
            onChange={(e) => setDraftContent(e.target.value)}
          />
          {editing && (
            <p className="text-[11px] text-muted-foreground">
              편집 중: {editing.title || '무제'} — [장면 저장]으로 반영
            </p>
          )}
          <div className="thin-scroll max-h-64 overflow-y-auto rounded-md border border-border">
            {scenes.length === 0 && (
              <p className="p-3 text-sm text-muted-foreground">
                아직 장면이 없습니다. 본문 일부를 잘라 장면으로 만들어 보세요.
              </p>
            )}
            {scenes.map((s) => (
              <div key={s.id} className="flex items-center gap-2 border-b border-border px-2 py-1.5 last:border-b-0">
                <button
                  type="button"
                  className="flex-1 truncate text-left text-sm hover:underline"
                  onClick={() => {
                    startEdit(s);
                    setDraftTitle(s.title);
                    setDraftContent(s.content_md);
                  }}
                  title="클릭하면 편집 내용에 불러옵니다"
                >
                  {s.title || '무제'}
                  {s.content_md ? (
                    <span className="ml-1 text-[10px] text-muted-foreground">
                      ({s.content_md.length}자)
                    </span>
                  ) : null}
                </button>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-6 px-2 text-[11px]"
                  disabled={updateScene.isPending}
                  onClick={() => {
                    setEditing(s);
                    setDraftTitle(s.title);
                    setDraftContent(s.content_md);
                    updateScene.mutate(s);
                  }}
                >
                  저장
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-6 px-2 text-[11px] text-destructive"
                  disabled={deleteScene.isPending}
                  onClick={() => deleteScene.mutate(s.id)}
                >
                  삭제
                </Button>
              </div>
            ))}
          </div>
          <Label className="text-[11px] text-muted-foreground">
            장면 선택은 AI 패널의 "현재 장면" 드롭다운에서 합니다.
          </Label>
        </div>
      </DialogContent>
    </Dialog>
  );
}
