import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type Project, type ProjectCreate } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from '@/components/ui/dialog';
import { BootstrapDialog } from '@/components/home/BootstrapDialog';
import { PlusStatusWidget } from '@/components/home/PlusStatusWidget';

/**
 * S1 홈 / 프로젝트 목록 (`/`) — FR-101 프로젝트 CRUD 카드 그리드.
 * 상태 칩은 회차 상태 집계 기준(설계서 m-3) — MVP 4a에서는 장르 배지만 표시.
 */
export function HomePage() {
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<Project | null>(null);
  const [bootstrapOpen, setBootstrapOpen] = useState(false);
  const [form, setForm] = useState<ProjectCreate>({ title: '', genre: '', synopsis: '' });

  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<Project[]>('/projects'),
  });

  const createProject = useMutation({
    mutationFn: (body: ProjectCreate) => api.post<Project>('/projects', body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setCreateOpen(false);
      setForm({ title: '', genre: '', synopsis: '' });
    },
  });

  const deleteProject = useMutation({
    mutationFn: (pid: number) => api.del<void>(`/projects/${pid}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['projects'] }),
  });

  return (
    <div className="mx-auto max-w-5xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold">내 프로젝트</h1>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => setBootstrapOpen(true)}>
            ✨ AI로 작품 자동 생성
          </Button>
          <Button onClick={() => setCreateOpen(true)}>+ 새 작품</Button>
        </div>
      </div>

      {projects.isPending && (
        <p className="text-sm text-muted-foreground">프로젝트 불러오는 중…</p>
      )}

      {projects.isError && (
        <Alert variant="error">
          <AlertDescription>
            {(projects.error as Error).message || '프로젝트를 불러올 수 없습니다.'}
          </AlertDescription>
        </Alert>
      )}

      {projects.data && projects.data.length === 0 && (
        <div className="rounded-lg border border-dashed border-border p-12 text-center">
          <p className="mb-3 text-sm text-muted-foreground">아직 작품이 없어요.</p>
          <Button onClick={() => setCreateOpen(true)}>+ 새 작품으로 시작</Button>
        </div>
      )}

      {projects.data && projects.data.length > 0 && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.data.map((project) => (
            <div
              key={project.id}
              className="flex flex-col rounded-lg border border-border bg-card p-5 shadow-soft transition-shadow duration-fast hover:shadow-md"
            >
              <h2 className="mb-1 truncate text-base font-semibold">{project.title}</h2>
              {project.genre ? (
                <Badge variant="secondary" className="w-fit">{project.genre}</Badge>
              ) : null}
              <p className="mt-2 line-clamp-2 min-h-[2.5rem] text-sm text-muted-foreground">
                {project.synopsis || '시놉시스 없음'}
              </p>
              <p className="mt-2 text-xs font-medium text-foreground/80">
                회차 {project.chapter_count ?? 0}편
                {project.total_chars != null && project.total_chars > 0
                  ? ` · 글자 ${project.total_chars.toLocaleString()}`
                  : ''}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                최근 수정: {new Date(project.updated_at).toLocaleString('ko-KR')}
              </p>
              <div className="mt-4 flex items-center gap-2">
                <Link to={`/projects/${project.id}/write`}>
                  <Button size="sm">열기 →</Button>
                </Link>
                <Button
                  size="sm"
                  variant="ghost"
                  className="ml-auto text-destructive"
                  onClick={() => setDeleteTarget(project)}
                >
                  삭제
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* 새 작품 Dialog — FR-101 */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>새 작품</DialogTitle>
            <DialogDescription>제목은 필수입니다.</DialogDescription>
          </DialogHeader>
          <div className="flex flex-col gap-3">
            <Input
              placeholder="제목"
              value={form.title}
              onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            />
            <Input
              placeholder="장르 (예: 판타지, 무협)"
              value={form.genre ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, genre: e.target.value }))}
            />
            <textarea
              className="min-h-20 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="시놉시스"
              value={form.synopsis ?? ''}
              onChange={(e) => setForm((f) => ({ ...f, synopsis: e.target.value }))}
            />
          </div>
          {createProject.isError && (
            <Alert variant="error" className="mt-3">
              <AlertDescription>{(createProject.error as Error).message}</AlertDescription>
            </Alert>
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>취소</Button>
            <Button
              disabled={!form.title.trim() || createProject.isPending}
              onClick={() => createProject.mutate({ ...form, title: form.title.trim() })}
            >
              생성
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ✨ AI 부트스트랩 마법사 — POST /projects/bootstrap */}
      <BootstrapDialog open={bootstrapOpen} onOpenChange={setBootstrapOpen} />

      {/* 삭제 confirm — FR-101 */}
      <Dialog open={deleteTarget !== null} onOpenChange={(o) => (!o ? setDeleteTarget(null) : undefined)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>프로젝트 삭제</DialogTitle>
            <DialogDescription>
              ‘{deleteTarget?.title}’을(를) 삭제할까요? 회차·본문이 함께 삭제되며 되돌릴 수 없습니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteTarget(null)}>취소</Button>
            <Button
              variant="destructive"
              disabled={deleteProject.isPending}
              onClick={() => {
                if (deleteTarget) {
                  deleteProject.mutate(deleteTarget.id);
                  setDeleteTarget(null);
                }
              }}
            >
              삭제
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* S-104 노벨피아 PLUS 충족 현황 위젯 (F-033 / A-038) */}
      <div className="mt-8">
        <PlusStatusWidget />
      </div>
    </div>
  );
}
