import { useQuery, useQueries } from '@tanstack/react-query';
import { api, type Project, type PlusStatus } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';

/**
 * S-104 노벨피아 PLUS 충족 현황 위젯 — F-033 / A-038.
 * 결정사항_G4 Q3: 프로젝트 내 회차 수 ≥ 15회.
 * 완료 회차 공백제외 3,000자 (백엔드 word_count_cache 기준).
 */
function PlusStatusRow({ project, status }: { project: Project; status?: PlusStatus }) {
  if (!status) return null;
  return (
    <li className="rounded-md border border-border bg-background px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <span className="truncate font-medium">{project.title}</span>
        <Badge variant={status.eligible ? 'default' : 'secondary'} className="ml-auto">
          {status.eligible ? 'PLUS 충족 ✓' : '미충족'}
        </Badge>
      </div>
      <div className="mt-1 flex flex-col gap-1 text-xs text-muted-foreground">
        <span>
          회차 수 {status.chapter_count}회 / 15회 이상{' '}
          {status.chapter_count_met ? '✓' : '✗'}
        </span>
        <span>
          완료 회차 공백제외 3,000자 — {status.done_chapters_3000}/{status.done_chapter_count}회{' '}
          {status.done_chars_met ? '✓' : '✗'}
        </span>
        <Progress
          value={(Math.min(status.chapter_count, 15) / 15) * 100}
          className="h-1.5"
          barClassName={status.eligible ? 'bg-status-done' : undefined}
        />
      </div>
    </li>
  );
}

export function PlusStatusWidget() {
  const projects = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.get<Project[]>('/projects'),
  });

  const statuses = useQueries({
    queries: (projects.data ?? []).map((p) => ({
      queryKey: ['plus-status', p.id],
      queryFn: () => api.get<PlusStatus>(`/projects/${p.id}/plus-status`),
    })),
  });

  return (
    <section className="rounded-md border border-border p-4" aria-label="노벨피아 PLUS 충족 현황">
      <h2 className="mb-2 text-sm font-semibold">노벨피아 PLUS 충족 현황</h2>
      {projects.isPending && (
        <p className="text-xs text-muted-foreground">불러오는 중…</p>
      )}
      {projects.data && projects.data.length === 0 && (
        <p className="text-xs text-muted-foreground">아직 작품이 없습니다.</p>
      )}
      <ul className="flex flex-col gap-2">
        {(projects.data ?? []).map((p, i) => (
          <PlusStatusRow key={p.id} project={p} status={statuses[i]?.data} />
        ))}
      </ul>
      <p className="mt-2 text-xs text-muted-foreground">
        노벨피아 PLUS 전환 기준: 하나의 작품에서 회차 15편 이상 · 완료 회차 3,000자 이상(공백·문장부호 제외).
        에디터 하단의 "노벨피아" 카운트가 이 기준과 같은 방식(공백·문장부호·특수문자 제외)으로 집계됩니다.
      </p>
    </section>
  );
}
