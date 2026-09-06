/**
 * S3 캐릭터 갤러리 (`/projects/{pid}/characters`) — 설계서 §2.3.
 * FR-205 카드 그리드 + 상세 드로어(Sheet), FR-201 검색, FR-202 역할 필터,
 * FR-203 관계 편집(텍스트 라벨), P1: AI 결과 자동 삽입 없음.
 */
import { useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  api,
  type Character,
  type CharacterCreate,
  type CharacterRole,
  type CharacterUpdate,
  type Relationship,
} from '@/lib/api';
import { useAiPanelStore } from '@/stores/aiPanelStore';
import { toast } from '@/components/ui/toast';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Sheet, SheetBody, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Textarea } from '@/components/ui/textarea';

const ROLES: (CharacterRole | null)[] = ['주연', '조연', '단역', '기타'];

export function CharactersPage() {
  const params = useParams();
  const pid = Number(params.pid);
  const queryClient = useQueryClient();

  const charactersQuery = useQuery({
    queryKey: ['characters', pid],
    queryFn: () => api.get<Character[]>(`/projects/${pid}/characters`),
    enabled: Number.isFinite(pid),
  });

  // FR-202 역할 필터 + FR-201 검색(이름·별칭·역할 부분일치, 클라이언트 필터)
  const [roleFilter, setRoleFilter] = useState<CharacterRole | '전체'>('전체');
  const [q, setQ] = useState('');

  const list = useMemo(() => {
    let rows = charactersQuery.data ?? [];
    if (roleFilter !== '전체') rows = rows.filter((c) => c.role === roleFilter);
    if (q.trim()) {
      const needle = q.trim().toLowerCase();
      rows = rows.filter((c) =>
        c.name.toLowerCase().includes(needle) ||
        c.role?.toLowerCase().includes(needle) ||
        (c.aliases ?? []).some((a) => a.toLowerCase().includes(needle)),
      );
    }
    return rows;
  }, [charactersQuery.data, q, roleFilter]);

  // 드로어 상태 — editing === null 이면 신규 생성 폼
  const [editingId, setEditingId] = useState<number | 'new' | null>(null);

  return (
    <div className="mx-auto max-w-[900px] px-6 py-4">
      <header className="mb-3 flex flex-wrap items-center gap-2">
        <h1 className="text-lg font-semibold">캐릭터 ({charactersQuery.data?.length ?? 0})</h1>
        <div className="ml-auto flex items-center gap-2">
          <Input
            type="search"
            aria-label="캐릭터 검색"
            placeholder="이름·별칭·역할 검색…"
            className="h-8 w-52"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <Button size="sm" onClick={() => setEditingId('new')}>+ 캐릭터 추가</Button>
        </div>
      </header>

      {/* 역할 필터 */}
      <div className="mb-3 flex gap-1" role="group" aria-label="역할 필터">
        {(['전체', ...ROLES.filter(Boolean)] as string[]).map((r) => (
          <Button
            key={r}
            size="sm"
            variant={roleFilter === r ? 'default' : 'outline'}
            onClick={() => setRoleFilter(r as CharacterRole | '전체')}
          >
            {r}
          </Button>
        ))}
      </div>

      {charactersQuery.isError ? (
        <p className="py-8 text-sm text-destructive">{(charactersQuery.error as Error).message}</p>
      ) : charactersQuery.isPending ? (
        <p className="py-8 text-sm text-muted-foreground">불러오는 중…</p>
      ) : list.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-md border border-dashed border-border py-16">
          <p className="text-sm text-muted-foreground">
            아직 캐릭터가 없습니다. [+ 캐릭터 추가]로 첫 인물을 만들어 보세요.
          </p>
        </div>
      ) : (
        /* FR-205 카드 그리드 */
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {list.map((ch) => (
            <button
              key={ch.id}
              type="button"
              onClick={() => setEditingId(ch.id)}
              className="flex min-h-36 flex-col items-start gap-1.5 rounded-md border border-border bg-card p-3 text-left transition-shadow duration-fast hover:shadow-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`${ch.name} 상세 열기`}
            >
              <span
                aria-hidden="true"
                className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/15 text-base font-semibold text-primary"
              >
                {ch.name.slice(0, 1) || '?'}
              </span>
              <span className="font-medium">{ch.name}</span>
              {(ch.aliases ?? []).length > 0 && (
                <span className="line-clamp-1 text-xs text-muted-foreground">{ch.aliases!.join(', ')}</span>
              )}
              {ch.role && <Badge variant={ch.role === '주연' ? 'default' : 'secondary'}>{ch.role}</Badge>}
            </button>
          ))}
        </div>
      )}

      {/* 상세 드로어 (FR-205) */}
      {editingId !== null && (
        <CharacterDrawer
          pid={pid}
          characterId={editingId}
          onClose={() => {
            setEditingId(null);
            queryClient.invalidateQueries({ queryKey: ['characters', pid] });
          }}
        />
      )}
    </div>
  );
}

function CharacterDrawer({
  pid,
  characterId,
  onClose,
}: {
  pid: number;
  characterId: number | 'new';
  onClose: () => void;
}) {
  const isNew = characterId === 'new';
  const detailQuery = useQuery({
    queryKey: ['character', characterId],
    queryFn: () => api.get<Character>(`/characters/${characterId}`),
    enabled: !isNew && Number.isFinite(characterId as number),
  });

  const initial: CharacterFormValues =
    isNew || !detailQuery.data
      ? { name: '', aliases: '', role: '', appearance: '', personality: '', speech_style: '', background: '' }
      : formFromCharacter(detailQuery.data);

  const [values, setValues] = useState<CharacterFormValues>(initial);
  const [loadedId, setLoadedId] = useState<number | 'new' | null>(isNew ? 'new' : null);
  // 데이터 도착 시 폼 프리필 (id 전환 대응)
  if (!isNew && detailQuery.data && loadedId !== detailQuery.data.id) {
    setLoadedId(detailQuery.data.id);
    setValues(formFromCharacter(detailQuery.data));
  }

  const save = useMutation({
    mutationFn: () => {
      const body = bodyFromForm(values);
      return isNew
        ? api.post<Character>(`/projects/${pid}/characters`, body as CharacterCreate)
        : api.patch<Character>(`/characters/${characterId}`, body satisfies CharacterUpdate as never);
    },
    onSuccess: () => {
      toast(isNew ? '캐릭터가 생성되었습니다.' : '저장되었습니다.', 'success');
      onClose();
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  const remove = useMutation({
    mutationFn: () => api.del(`/characters/${characterId}`),
    onSuccess: () => {
      toast('삭제되었습니다.', 'info');
      onClose();
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  return (
    <Sheet open onOpenChange={(o) => (!o ? onClose() : undefined)}>
      <SheetHeader>
        <SheetTitle>{isNew ? '새 캐릭터' : `캐릭터 — ${detailQuery.data?.name ?? ''}`}</SheetTitle>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="닫기">닫기</Button>
      </SheetHeader>
      <SheetBody className="flex flex-col gap-3">
        <div>
          <Label htmlFor="ch-name">이름 * </Label>
          <Input
            id="ch-name"
            value={values.name}
            onChange={(e) => setValues((v) => ({ ...v, name: e.target.value }))}
          />
        </div>
        <div>
          <Label htmlFor="ch-aliases">별칭 (콤마 구분)</Label>
          <Input
            id="ch-aliases"
            value={values.aliases}
            onChange={(e) => setValues((v) => ({ ...v, aliases: e.target.value }))}
          />
        </div>
        <div>
          <Label htmlFor="ch-role">역할 *</Label>
          <Select
            id="ch-role"
            value={values.role}
            onChange={(e) => setValues((v) => ({ ...v, role: e.target.value }))}
          >
            <option value="">선택…</option>
            {ROLES.filter(Boolean).map((r) => (
              <option key={r} value={r!}>{r}</option>
            ))}
          </Select>
        </div>
        {(
          [
            ['appearance', '외형'],
            ['personality', '성격'],
            ['speech_style', '말투'],
            ['background', '배경'],
          ] as const
        ).map(([key, label]) => (
          <div key={key}>
            <Label htmlFor={`ch-${key}`}>{label}</Label>
            <Textarea
              id={`ch-${key}`}
              rows={2}
              value={values[key]}
              onChange={(e) => setValues((v) => ({ ...v, [key]: e.target.value }))}
            />
          </div>
        ))}

        {/* FR-203 관계 편집 */}
        {!isNew && typeof characterId === 'number' && (
          <RelationsSection pid={pid} characterId={characterId} />
        )}

        <div className="mt-1 flex items-center gap-2">
          <Button
            disabled={save.isPending || !values.name.trim()}
            onClick={() => save.mutate()}
          >
            저장
          </Button>
          <Button variant="ghost" onClick={onClose}>닫기</Button>
          {!isNew && (
            <Button
              variant="ghost"
              className="ml-auto text-destructive hover:text-destructive"
              disabled={remove.isPending}
              onClick={() => {
                if (window.confirm('정말 이 캐릭터를 삭제하시겠습니까?')) remove.mutate();
              }}
            >
              삭제
            </Button>
          )}
        </div>
        {/* AI 초안 생성 진입점은 S5 패널 경유 — 결과는 자동 삽입되지 않음(P1) */}
        {!isNew && (
          <AiDraftButtons character={detailQuery.data} />
        )}
      </SheetBody>
    </Sheet>
  );
}

/** S5 연결 — [AI로 외형 초안] / [AI로 말투 예시] (P1: 끼워넣기는 사용자 클릭으로만) */
function AiDraftButtons({ character }: { character?: Character }) {
  const openAiPanel = useAiPanelStore((s) => s.open);
  const setMode = useAiPanelStore((s) => s.setMode);
  const setContext = useAiPanelStore((s) => s.setContext);
  const setPrompt = useAiPanelStore((s) => s.setPrompt);

  const openWith = (prompt: string) => {
    setMode('ai');
    setContext({
      chapterId: null,
      characterIds: character ? [character.id] : [],
      loreIds: [],
    });
    setPrompt(prompt);
    openAiPanel();
  };

  return (
    <div className="border-t border-border pt-3 text-xs text-muted-foreground">
      <p className="mb-2">AI 보조 (결과는 자동 삽입되지 않습니다 — S5에서 복사해 반영하세요):</p>
      <div className="flex gap-2">
        <Button size="sm" variant="outline" onClick={() => openWith('다음 캐릭터의 외형 묘사 초안을 3문장으로 작성하세요.')}>
          ✨ AI로 외형 초안
        </Button>
        <Button size="sm" variant="outline" onClick={() => openWith('다음 캐릭터의 말투 예시 대사를 3개 작성하세요.')}>
          ✨ AI로 말투 예시
        </Button>
      </div>
    </div>
  );
}

/** FR-203 관계 — 텍스트 라벨 수준 MVP */
function RelationsSection({ pid, characterId }: { pid: number; characterId: number }) {
  const queryClient = useQueryClient();
  const relationsQuery = useQuery({
    queryKey: ['relations', characterId],
    queryFn: () => api.get<Relationship[]>(`/characters/${characterId}/relations`),
  });
  const allQuery = useQuery({
    queryKey: ['characters', pid],
    queryFn: () => api.get<Character[]>(`/projects/${pid}/characters`),
  });

  const [targetId, setTargetId] = useState('');
  const [label, setLabel] = useState('');
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['relations', characterId] });

  const addRelation = useMutation({
    mutationFn: () =>
      api.post<Relationship>(`/projects/${pid}/characters/relations`, {
        from_character_id: characterId,
        to_character_id: Number(targetId),
        label: label.trim() || null,
      }),
    onSuccess: () => {
      setTargetId('');
      setLabel('');
      invalidate();
      toast('관계가 추가되었습니다.', 'success');
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  const deleteRelation = useMutation({
    mutationFn: (rid: number) => api.del(`/relations/${rid}`),
    onSuccess: invalidate,
  });

  const nameOf = (id: number) =>
    (allQuery.data ?? []).find((c) => c.id === id)?.name ?? `#${id}`;
  const others = (allQuery.data ?? []).filter((c) => c.id !== characterId);

  return (
    <section className="rounded-md border border-border p-3">
      <h3 className="mb-2 text-xs font-semibold text-muted-foreground">관계</h3>
      <ul className="mb-2 flex flex-col gap-1">
        {(relationsQuery.data ?? []).map((rel) => {
          const otherId = rel.from_character_id === characterId ? rel.to_character_id : rel.from_character_id;
          return (
            <li key={rel.id} className="flex items-center gap-2 rounded-sm bg-background px-2 py-1 text-sm">
              <span>
                {rel.from_character_id === characterId ? `${nameOf(characterId)} → ${nameOf(otherId)}` : `${nameOf(otherId)} → ${nameOf(characterId)}`}
                {rel.label ? ` · "${rel.label}"` : ''}
              </span>
              <Button
                variant="ghost"
                size="sm"
                className="ml-auto h-6 px-1.5 text-destructive hover:text-destructive"
                aria-label={`관계 ${rel.id} 삭제`}
                onClick={() => deleteRelation.mutate(rel.id)}
              >
                ✕
              </Button>
            </li>
          );
        })}
        {(relationsQuery.data ?? []).length === 0 && (
          <li className="text-xs text-muted-foreground">아직 관계가 없습니다.</li>
        )}
      </ul>
      <div className="flex items-end gap-1.5">
        <div className="w-40">
          <Select aria-label="상대 캐릭터 선택" value={targetId} onChange={(e) => setTargetId(e.target.value)}>
            <option value="">상대 선택…</option>
            {others.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </Select>
        </div>
        <Input
          aria-label="관계 라벨 입력"
          placeholder="예: 주군-가신"
          className="h-8 flex-1"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
        />
        <Button
          size="sm"
          disabled={!targetId || addRelation.isPending}
          onClick={() => addRelation.mutate()}
        >
          + 추가
        </Button>
      </div>
    </section>
  );
}

// ---- 폼 헬퍼 ----
interface CharacterFormValues {
  name: string;
  aliases: string;
  role: string;
  appearance: string;
  personality: string;
  speech_style: string;
  background: string;
}

function formFromCharacter(c: Character): CharacterFormValues {
  return {
    name: c.name,
    aliases: (c.aliases ?? []).join(', '),
    role: c.role ?? '',
    appearance: c.appearance ?? '',
    personality: c.personality ?? '',
    speech_style: c.speech_style ?? '',
    background: c.background ?? '',
  };
}

function bodyFromForm(v: CharacterFormValues): CharacterUpdate & CharacterCreate {
  const aliases = v.aliases.split(',').map((s) => s.trim()).filter(Boolean);
  return {
    name: v.name.trim(),
    aliases: aliases.length > 0 ? aliases : [],
    role: (v.role || null) as CharacterRole | null,
    appearance: v.appearance.trim() || null,
    personality: v.personality.trim() || null,
    speech_style: v.speech_style.trim() || null,
    background: v.background.trim() || null,
  };
}
