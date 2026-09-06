import { Link, useLocation, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type Chapter } from '@/lib/api';
import { useEditorStore } from '@/stores/editorStore';
import { StatusBadge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { cn } from '@/lib/utils';

/**
 * LeftSidebar 240px — 에디터에서는 회차 트리(권/화), 그 외 프로젝트 화면에서는
 * 화면 전환 네비만 노출. 홈·설정에서는 홈/설정 링크만 (§1.1 3분할 셸).
 * FR-102 회차 계층(권 단위 묶음) + FR-105 상태 칩.
 */
export function LeftSidebar() {
  const { pathname } = useLocation();
  const isProjectRoute = /^\/projects\/\d+/.test(pathname);
  const isEditorRoute = /^\/projects\/\d+\/write/.test(pathname);
  const pid = Number(pathname.match(/^\/projects\/(\d+)/)?.[1]);

  return (
    <aside className="hidden w-60 shrink-0 border-r border-border bg-background md:flex md:flex-col">
      <ScrollArea className="min-h-0 flex-1 p-2">
        {isProjectRoute && (
          <ProjectNavLinks pid={pathname.match(/^\/projects\/(\d+)/)?.[1] ?? ''} pathname={pathname} />
        )}
        {isEditorRoute && <ChapterTree pid={pid} />}
      </ScrollArea>
      <div className="flex flex-col border-t border-border p-2">
        <Link
          to="/"
          className="block rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors duration-fast hover:bg-muted hover:text-foreground"
        >
          ← 홈으로
        </Link>
        <Link
          to="/settings"
          className={cn(
            'block rounded-md px-3 py-2 text-sm text-muted-foreground transition-colors duration-fast hover:bg-muted hover:text-foreground',
            pathname === '/settings' && 'text-foreground',
          )}
        >
          ⚙ 설정
        </Link>
      </div>
    </aside>
  );
}

/** 프로젝트 컨텍스트 네비 — 회차집필 / 캐릭터 / 로어북 전환 */
function ProjectNavLinks({ pid, pathname }: { pid: string; pathname: string }) {
  const base = `/projects/${pid}`;
  const links = [
    { to: `${base}/write`, label: '✍ 회차 집필', active: pathname.endsWith('/write') },
    { to: `${base}/characters`, label: '👤 캐릭터', active: pathname.endsWith('/characters') },
    { to: `${base}/lore`, label: '🗺 로어북', active: pathname.endsWith('/lore') },
  ];
  return (
    <nav className="mb-1 flex flex-col gap-0.5" aria-label="프로젝트 화면 전환">
      <p className="px-3 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide">프로젝트</p>
      {links.map((l) => (
        <Link
          key={l.to}
          to={l.to}
          aria-current={l.active || undefined}
          className={cn(
            'rounded-md px-3 py-1.5 text-sm transition-colors duration-fast hover:bg-muted',
            l.active ? 'bg-primary/10 font-medium text-foreground' : 'text-muted-foreground',
          )}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  );
}

function ChapterTree({ pid: pidProp }: { pid?: number }) {
  // LeftSidebar는 <Routes> 바깥에서 렌더되므로 useParams()가 비어 있다(m-2).
  // 라우트 파라미터가 없으면 pathname에서 pid를 복원한다(ProjectNavLinks와 동일 방식).
  const { pathname } = useLocation();
  const pid = pidProp ?? Number(pathname.match(/^\/projects\/(\d+)/)?.[1]);
  const queryClient = useQueryClient();

  const chapters = useQuery({
    queryKey: ['chapters', pid],
    queryFn: () => api.get<Chapter[]>(`/projects/${pid}/chapters`),
    enabled: Number.isFinite(pid),
  });

  const chapterId = useEditorStore((s) => s.chapterId);
  const setContext = useEditorStore((s) => s.setContext);
  const expandedVolumes = useEditorStore((s) => s.expandedVolumes);
  const toggleVolume = useEditorStore((s) => s.toggleVolume);

  const createChapter = useMutation({
    mutationFn: (volume: number) =>
      api.post<Chapter>(`/projects/${pid}/chapters`, {
        volume,
        title: '',
        sort_order: Date.now() % 1e7,
      }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['chapters', pid] });
      setContext(pid, created.id);
    },
  });

  if (chapters.isPending) {
    return <p className="px-3 py-2 text-sm text-muted-foreground">회차 불러오는 중…</p>;
  }
  if (chapters.isError) {
    return <p className="px-3 py-2 text-sm text-destructive">회차를 불러올 수 없습니다.</p>;
  }

  // 권(volume) 단위 그룹핑 — FR-102
  const byVolume = new Map<number, Chapter[]>();
  for (const ch of [...chapters.data].sort(
    (a, b) => a.volume - b.volume || a.sort_order - b.sort_order,
  )) {
    const list = byVolume.get(ch.volume) ?? [];
    list.push(ch);
    byVolume.set(ch.volume, list);
  }

  const volumes = [...byVolume.keys()].sort((a, b) => a - b);

  return (
    <div className="flex flex-col gap-0.5 px-1">
      {volumes.map((volume) => {
        const expanded = expandedVolumes.has(volume);
        return (
          <div key={volume}>
            <button
              type="button"
              onClick={() => toggleVolume(volume)}
              aria-expanded={expanded}
              className="flex w-full items-center gap-1 rounded-md px-2 py-1.5 text-sm font-medium hover:bg-muted"
            >
              <span className="inline-block w-3 text-muted-foreground">{expanded ? '▾' : '▸'}</span>
              {volume}권
            </button>
            {expanded &&
              byVolume.get(volume)!.map((ch) => (
                <button
                  key={ch.id}
                  type="button"
                  onClick={() => setContext(pid, ch.id)}
                  aria-current={chapterId === ch.id || undefined}
                  className={cn(
                    'ml-4 flex w-[calc(100%-1rem)] items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm',
                    chapterId === ch.id ? 'bg-primary/10 font-medium text-foreground' : 'hover:bg-muted',
                  )}
                >
                  <span className="truncate">{ch.title.trim() || `${volume}권 ${ch.id}화`}</span>
                  <StatusBadge status={ch.status} />
                </button>
              ))}
          </div>
        );
      })}

      <Button
        variant="ghost"
        size="sm"
        className="mt-2 justify-start"
        disabled={createChapter.isPending}
        onClick={() => createChapter.mutate(volumes[volumes.length - 1] ?? 1)}
      >
        + 회차 추가
      </Button>
    </div>
  );
}
