/**
 * 기획 페이지 — 고도화 G-050 권 개요 + G-040 문체 프로파일.
 * 권 개요: 부트스트랩 목차와 회차 본문 사이의 중간 서사 레이어
 * (개요·감정 곡선·고봉). AI 패널 "목차 자동 포함" 시 권 개요도 함께 주입된다.
 * 문체 프로파일: AI 패널 "문체 프로파일 적용" 체크 시 system 프롬프트에 결합.
 */
import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, type EndingImpact, type Project } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { toast } from '@/components/ui/toast';

interface VolumeNote {
  id: number;
  project_id: number;
  volume: number;
  title: string;
  overview: string | null;
  emotion_curve: string | null;
  climax_note: string | null;
}

const FIELDS: Array<{ key: 'overview' | 'emotion_curve' | 'climax_note'; label: string; hint: string }> = [
  { key: 'overview', label: '개요', hint: '권 전체 흐름 — 주인공이 어디서 시작해 어디로 가는가' },
  { key: 'emotion_curve', label: '감정 곡선', hint: '고조↔완충 배치 — 예: 3화 고조, 4화 완충, 7화 반전 고조' },
  { key: 'climax_note', label: '고봉 노트', hint: '권의 클라이맥스 — 언제, 누구와, 무엇이 걸리는가' },
];

export function PlanPage() {
  const params = useParams();
  const pid = Number(params.pid);
  const queryClient = useQueryClient();

  const notesQuery = useQuery({
    queryKey: ['volume-notes', pid],
    queryFn: () => api.get<VolumeNote[]>(`/projects/${pid}/volume-notes`),
  });
  const projectQuery = useQuery({
    queryKey: ['project', pid],
    queryFn: () => api.get<Project>(`/projects/${pid}`),
  });

  const create = useMutation({
    mutationFn: (volume: number) =>
      api.post<VolumeNote>(`/projects/${pid}/volume-notes`, { volume, title: '' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['volume-notes', pid] }),
    onError: (e) => toast(`권 개요 추가 실패: ${(e as Error).message}`, 'error'),
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Partial<VolumeNote> }) =>
      api.patch<VolumeNote>(`/volume-notes/${id}`, body),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['volume-notes', pid] }),
    onError: (e) => toast(`저장 실패: ${(e as Error).message}`, 'error'),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.del(`/volume-notes/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['volume-notes', pid] }),
    onError: (e) => toast(`삭제 실패: ${(e as Error).message}`, 'error'),
  });

  const notes = [...(notesQuery.data ?? [])].sort((a, b) => a.volume - b.volume);
  const nextVolume = (notes.length > 0 ? notes[notes.length - 1].volume : 0) + 1;

  return (
    <div className="mx-auto flex h-full max-w-[820px] flex-col gap-4 overflow-y-auto px-6 py-4">
      <header className="flex items-center gap-2">
        <h1 className="text-lg font-semibold">기획</h1>
        <p className="text-xs text-muted-foreground">
          권 개요·문체 프로파일 — AI 집필 시 참고 컨텍스트로만 사용됩니다
        </p>
        <Button
          size="sm"
          className="ml-auto"
          disabled={create.isPending}
          onClick={() => create.mutate(nextVolume)}
        >
          + 권 개요 추가
        </Button>
      </header>

      {/* 문체 프로파일 */}
      <StyleProfileEditor
        pid={pid}
        initial={projectQuery.data?.style_profile ?? ''}
        loading={projectQuery.isPending}
      />

      {/* 결말 후보 + 변경 영향 (D03-7) */}
      <EndingSection pid={pid} project={projectQuery.data} />

      {/* 권 개요 목록 */}
      {notesQuery.isPending && <p className="text-sm text-muted-foreground">불러오는 중…</p>}
      {notes.length === 0 && !notesQuery.isPending && (
        <p className="text-sm text-muted-foreground">
          권 개요가 없습니다. "목차 자동 포함" 시 권 개요가 있으면 AI가 권 전체 방향을 알고 집필합니다.
        </p>
      )}
      {notes.map((note) => (
        <VolumeNoteCard
          key={note.id}
          note={note}
          onSave={(body) => update.mutate({ id: note.id, body })}
          onDelete={() => remove.mutate(note.id)}
          saving={update.isPending}
        />
      ))}
    </div>
  );
}

function VolumeNoteCard({
  note, onSave, onDelete, saving,
}: {
  note: VolumeNote;
  onSave: (body: Partial<VolumeNote>) => void;
  onDelete: () => void;
  saving: boolean;
}) {
  const [title, setTitle] = useState(note.title);
  const [fields, setFields] = useState<Record<string, string>>({
    overview: note.overview ?? '',
    emotion_curve: note.emotion_curve ?? '',
    climax_note: note.climax_note ?? '',
  });

  const save = () =>
    onSave({
      title,
      overview: fields.overview || null,
      emotion_curve: fields.emotion_curve || null,
      climax_note: fields.climax_note || null,
    });

  return (
    <section className="rounded-md border border-border p-3">
      <div className="mb-2 flex items-center gap-2">
        <Input
          aria-label={`${note.volume}권 제목`}
          className="h-8 w-56 font-semibold"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => title !== note.title && save()}
          placeholder={`${note.volume}권 제목`}
        />
        <span className="text-xs font-semibold text-muted-foreground">{note.volume}권</span>
        <Button
          size="sm" className="ml-auto"
          disabled={saving}
          onClick={save}
        >
          저장
        </Button>
        <Button size="sm" variant="ghost" className="text-destructive" onClick={onDelete}>
          삭제
        </Button>
      </div>
      <div className="grid grid-cols-1 gap-2">
        {FIELDS.map((f) => (
          <div key={f.key}>
            <Label className="text-xs">{f.label}</Label>
            <p className="mb-1 text-[10px] text-muted-foreground">{f.hint}</p>
            <Textarea
              aria-label={`${note.volume}권 ${f.label}`}
              rows={2}
              value={fields[f.key]}
              onChange={(e) => setFields((s) => ({ ...s, [f.key]: e.target.value }))}
              onBlur={() => fields[f.key] !== (note[f.key] ?? '') && save()}
            />
          </div>
        ))}
      </div>
    </section>
  );
}

/** G-040 — 작품 문체 프로파일 (1.5초 디바운스 자동 저장) */
function StyleProfileEditor({ pid, initial, loading }: { pid: number; initial: string; loading: boolean }) {
  const [text, setText] = useState(initial);
  const timer = useRef<number | undefined>(undefined);
  const latest = useRef(text);

  useEffect(() => {
    setText(initial);
    latest.current = initial;
  }, [initial, pid]);

  const save = useMutation({
    mutationFn: (value: string) => api.patch<Project>(`/projects/${pid}`, { style_profile: value }),
    onSuccess: () => toast('문체 프로파일을 저장했습니다.', 'success'),
    onError: (e) => toast(`저장 실패: ${(e as Error).message}`, 'error'),
  });

  const onChange = (value: string) => {
    setText(value);
    latest.current = value;
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => save.mutate(latest.current), 1500);
  };

  return (
    <section className="rounded-md border border-border p-3">
      <Label>문체 프로파일 (작품별)</Label>
      <p className="mb-2 mt-1 text-[11px] text-muted-foreground">
        AI 패널의 "문체 프로파일 적용" 체크 시 system 프롬프트에 결합됩니다.
        예: 문장 길이, 호칭 규칙, 금지 표현, 회상 장면 표기법…
      </p>
      <Textarea
        aria-label="문체 프로파일"
        rows={4}
        disabled={loading}
        placeholder="이 작품의 문체 규칙을 적어두세요…"
        value={text}
        onChange={(e) => onChange(e.target.value)}
      />
    </section>
  );
}


/** D03-7 — 작품 수준 결말 후보 + 변경 영향(파생). 잠금은 실수 방지이며 변경 금지가 아니다. */
function EndingSection({ pid, project }: { pid: number; project: Project | undefined }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<string | null>(null);
  const locked = project?.ending_locked ?? false;
  const text = draft ?? project?.ending_intent ?? '';

  // 프로젝트 전환·외부 변경 시 작업본을 리셋한다(StyleProfileEditor와 같은 패턴).
  useEffect(() => {
    setDraft(null);
  }, [pid, project?.ending_intent]);

  const impactQuery = useQuery({
    queryKey: ['ending-impact', pid],
    queryFn: () => api.get<EndingImpact>(`/projects/${pid}/ending-impact`),
  });

  const patch = useMutation({
    mutationFn: (body: { ending_intent?: string | null; ending_locked?: boolean }) =>
      api.patch<Project>(`/projects/${pid}`, body),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ['project', pid] });
      queryClient.invalidateQueries({ queryKey: ['ending-impact', pid] });
      if ('ending_intent' in vars) {
        setDraft(null);
        toast('결말 후보를 저장했습니다.', 'success');
      } else {
        toast(vars.ending_locked ? '결말을 잠갔습니다.' : '결말 잠금을 해제했습니다.', 'success');
      }
    },
    onError: (e) => toast(`저장 실패: ${(e as Error).message}`, 'error'),
  });

  const save = () => {
    const value = text.trim() || null;
    // 잠긴 상태에서는 해제를 같은 요청에 포함한다(백엔드 불변조건).
    patch.mutate(
      locked
        ? { ending_locked: false, ending_intent: value }
        : { ending_intent: value },
    );
  };

  const impact = impactQuery.data;

  return (
    <section className="rounded-md border border-border p-3" aria-label="결말 후보">
      <div className="mb-2 flex items-center gap-2">
        <Label>결말 후보</Label>
        {locked && <Badge variant="secondary">잠김</Badge>}
        {project?.ending_updated_at && (
          <span className="text-[11px] text-muted-foreground">
            변경 {new Date(project.ending_updated_at).toLocaleString('ko-KR')}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={patch.isPending}
            onClick={() => patch.mutate({ ending_locked: !locked })}
          >
            {locked ? '잠금 해제' : '잠금'}
          </Button>
          <Button
            size="sm"
            disabled={patch.isPending || project === undefined}
            onClick={save}
          >
            저장
          </Button>
        </div>
      </div>
      <Textarea
        aria-label="결말 후보"
        rows={3}
        disabled={locked || patch.isPending || project === undefined}
        placeholder="작품 전체의 결말 후보 — 회차 목표의 결말 의도와 별개로 관리됩니다…"
        value={text}
        onChange={(e) => setDraft(e.target.value)}
      />

      {impact && (
        <div className="mt-3 space-y-1 text-xs" aria-label="결말 변경 영향">
          {impact.open_foreshadows.length > 0 && (
            <p>
              <span className="text-muted-foreground">미해결 복선:</span>{' '}
              {impact.open_foreshadows.map((f) => f.title).join(', ')}
            </p>
          )}
          {impact.stale_goal_chapters.length > 0 && (
            <p>
              <span className="text-muted-foreground">결말 변경 전 목표:</span>{' '}
              {impact.stale_goal_chapters
                .map((c) => `${c.title}(목표 v${c.goal_version})`)
                .join(', ')}
            </p>
          )}
          {impact.finale_chapters.length > 0 && (
            <p>
              <span className="text-muted-foreground">최종화 회차:</span>{' '}
              {impact.finale_chapters
                .map((c) => `${c.title}${c.has_ending_intent ? '' : '(결말 의도 없음)'}`)
                .join(', ')}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
