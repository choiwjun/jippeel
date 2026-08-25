/**
 * S7 설정 (`/settings`) — 설계서 §2.7.
 *
 * C-1/NFR-202: api_key는 마스킹만 노출, [표시] 버튼 없음 — 키 변경 Dialog만 제공.
 * NFR-404: 규정·현황 탭 상단 고정 Alert — "공개/비공개 판단은 작가의 몫".
 * FR-401/402/407/409 엔드포인트 CRUD · FR-502 윤문 기본 강도 · §4 테마.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  api,
  type AiEndpoint,
  type AiEndpointCreate,
  type AiEndpointUpdate,
  type PromptPreset,
} from '@/lib/api';
import { useSettingsStore, type RefineRoute } from '@/stores/settingsStore';
import { useUiStore } from '@/stores/uiStore';
import { toast } from '@/components/ui/toast';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Slider } from '@/components/ui/slider';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { CloudUploadIcon } from '@/components/ui/icons';

type TabKey = 'ai' | 'refine' | 'theme' | 'policy' | 'advanced';

export function SettingsPage() {
  const [tab, setTab] = useState<TabKey>('ai');

  return (
    <div className="mx-auto max-w-[860px] px-6 py-4">
      <header className="mb-3 flex items-center gap-3">
        <h1 className="text-lg font-semibold">설정</h1>
        <Link to="/" className="ml-auto text-sm text-muted-foreground hover:text-foreground">← 뒤로</Link>
      </header>

      <Tabs value={tab} onValueChange={(v) => setTab(v as TabKey)}>
        <TabsList>
          <TabsTrigger value="ai">AI 엔드포인트</TabsTrigger>
          <TabsTrigger value="refine">윤문</TabsTrigger>
          <TabsTrigger value="theme">테마</TabsTrigger>
          <TabsTrigger value="policy">규정·현황</TabsTrigger>
          <TabsTrigger value="advanced">고급</TabsTrigger>
        </TabsList>
        <TabsContent value="ai" className="pt-3"><AiEndpointsTab /></TabsContent>
        <TabsContent value="refine" className="pt-3"><RefineTab /></TabsContent>
        <TabsContent value="theme" className="pt-3"><ThemeTab /></TabsContent>
        <TabsContent value="policy" className="pt-3"><PolicyTab /></TabsContent>
        <TabsContent value="advanced" className="pt-3"><AdvancedTab /></TabsContent>
      </Tabs>
    </div>
  );
}

// ---------------- AI 엔드포인트 탭 (C-1) ----------------
function AiEndpointsTab() {
  const queryClient = useQueryClient();
  const endpointsQuery = useQuery({
    queryKey: ['ai-endpoints'],
    queryFn: () => api.get<AiEndpoint[]>('/ai/endpoints'),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['ai-endpoints'] });

  const setDefault = useMutation({
    mutationFn: (eid: number) =>
      api.patch<AiEndpoint>(`/ai/endpoints/${eid}`, { is_default: true }),
    onSuccess: () => { invalidate(); toast('기본 엔드포인트를 변경했습니다.', 'success'); },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  const remove = useMutation({
    mutationFn: (eid: number) => api.del(`/ai/endpoints/${eid}`),
    onSuccess: () => { invalidate(); toast('엔드포인트를 삭제했습니다.', 'info'); },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  const [creating, setCreating] = useState(false);
  const presetsQuery = useQuery({
    queryKey: ['ai-presets'],
    queryFn: () => api.get<PromptPreset[]>('/ai/presets'),
  });
  const removePreset = useMutation({
    mutationFn: (id: number) => api.del(`/ai/presets/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['ai-presets'] }),
  });

  return (
    <div className="flex flex-col gap-4">
      <Alert variant="warning">
        <CloudUploadIcon className="mr-1 inline-block align-text-bottom text-warning" />
        <AlertDescription>
          Ollama 네이티브는 미지원입니다. OpenAI 호환 API(base_url …/v1)만 사용하세요. (FR-409)
        </AlertDescription>
      </Alert>

      {(endpointsQuery.data ?? []).map((ep) => (
        <EndpointCard
          key={ep.id}
          endpoint={ep}
          onSetDefault={() => setDefault.mutate(ep.id)}
          onDelete={() => {
            if (window.confirm(`엔드포인트 "${ep.name}"을(를) 삭제하시겠습니까?`)) remove.mutate(ep.id);
          }}
        />
      ))}

      {!creating ? (
        <Button variant="outline" className="self-start" onClick={() => setCreating(true)}>
          + 새 엔드포인트 추가
        </Button>
      ) : (
        <NewEndpointForm onDone={() => { setCreating(false); invalidate(); }} onCancel={() => setCreating(false)} />
      )}

      {/* 프롬프트 프리셋 (FR-403) */}
      <section className="mt-2 rounded-md border border-border p-4">
        <h2 className="mb-1 text-sm font-semibold">프롬프트 프리셋 (FR-403)</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          빌트인 프리셋은 백엔드 시드에서 관리되며, 아래 사용자 정의 프리셋을 추가할 수 있습니다.
        </p>
        <ul className="mb-3 flex flex-col gap-1.5">
          {(presetsQuery.data ?? []).map((p) => (
            <li key={p.id} className="flex items-center gap-2 rounded-sm bg-background px-2 py-1.5 text-sm">
              <span className="font-medium">{p.name}</span>
              <span className="line-clamp-1 flex-1 text-xs text-muted-foreground">{p.template_text}</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-6 px-1.5 text-destructive hover:text-destructive"
                aria-label={`프리셋 ${p.name} 삭제`}
                onClick={() => removePreset.mutate(p.id)}
              >
                ✕
              </Button>
            </li>
          ))}
          {(presetsQuery.data ?? []).length === 0 && (
            <li className="text-xs text-muted-foreground">등록된 프리셋이 없습니다.</li>
          )}
        </ul>
        <NewPresetForm onDone={() => queryClient.invalidateQueries({ queryKey: ['ai-presets'] })} />
      </section>
    </div>
  );
}

function EndpointCard({ endpoint, onSetDefault, onDelete }: {
  endpoint: AiEndpoint;
  onSetDefault: () => void;
  onDelete: () => void;
}) {
  const queryClient = useQueryClient();

  // 인라인 편집 필드
  const [name, setName] = useState(endpoint.name);
  const [baseUrl, setBaseUrl] = useState(endpoint.base_url);
  const [defaultModel, setDefaultModel] = useState(endpoint.default_model ?? '');
  const [temperature, setTemperature] = useState(String(endpoint.temperature));

  // 모델 목록 조회 == 테스트 연결 겸용
  const modelsQuery = useQuery({
    queryKey: ['endpoint-models', endpoint.id],
    queryFn: () => api.get<{ data: Array<{ id: string }> }>(`/ai/endpoints/${endpoint.id}/models`),
    enabled: false,
    retry: false,
  });

  const save = useMutation({
    mutationFn: () =>
      api.patch<AiEndpoint>(`/ai/endpoints/${endpoint.id}`, {
        name: name.trim(),
        base_url: baseUrl.trim(),
        default_model: defaultModel.trim() || null,
        temperature: Number(temperature) || 0.7,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-endpoints'] });
      toast('저장되었습니다.', 'success');
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  return (
    <section className="rounded-md border border-border p-4">
      <header className="mb-3 flex items-center gap-2">
        <Input aria-label="엔드포인트 이름" className="h-8 w-48 font-semibold" value={name}
               onChange={(e) => setName(e.target.value)} />
        {endpoint.is_default && <Badge>기본</Badge>}
        <div className="ml-auto flex items-center gap-1.5">
          {!endpoint.is_default && (
            <Button size="sm" variant="outline" onClick={onSetDefault}>기본으로 설정</Button>
          )}
          <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={onDelete}>
            삭제
          </Button>
        </div>
      </header>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div>
          <Label htmlFor={`base-${endpoint.id}`}>base_url</Label>
          <Input id={`base-${endpoint.id}`} className="h-8" placeholder="http://localhost:1234/v1"
                 value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
        </div>
        <div>
          <Label htmlFor={`model-${endpoint.id}`}>default_model</Label>
          <Input id={`model-${endpoint.id}`} className="h-8" placeholder="예: qwen2.5-7b-instruct"
                 value={defaultModel} onChange={(e) => setDefaultModel(e.target.value)} />
        </div>
        <div>
          <Label htmlFor={`temp-${endpoint.id}`}>temperature</Label>
          <Input id={`temp-${endpoint.id}`} className="h-8 w-24" type="number" min={0} max={2} step={0.1}
                 value={temperature} onChange={(e) => setTemperature(e.target.value)} />
        </div>
        {/* C-1/NFR-202 — api_key 마스킹만 노출, [표시] 버튼 없음 */}
        <div>
          <Label htmlFor={`key-${endpoint.id}`}>api_key</Label>
          <div className="flex items-center gap-2">
            <Input
              id={`key-${endpoint.id}`}
              readOnly
              disabled
              className="h-8 w-44 font-mono"
              value={endpoint.has_api_key ? '••••••••••••' : '(미설정)'}
            />
            <ApiKeyChangeDialog endpointId={endpoint.id} hasKey={endpoint.has_api_key} />
          </div>
          <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
            ※ 저장된 키는 보안 정책상 마스킹만 노출됩니다. 재표시 불가 — 변경하려면 새 값을 입력하세요.
          </p>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" disabled={save.isPending} onClick={() => save.mutate()}>
          저장
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            void modelsQuery.refetch().then((r) =>
              r.isSuccess
                ? toast(`연결 성공 — 모델 ${r.data.data.length}개`, 'success')
                : toast(r.error ? (r.error as Error).message : '연결 실패', 'error'),
            );
          }}
        >
          테스트 연결 / 모델 새로고침
        </Button>
        {modelsQuery.isFetched && modelsQuery.data && (
          <span className="text-xs text-muted-foreground">
            {modelsQuery.data.data.map((m) => m.id).slice(0, 5).join(', ') || '모델 없음'}
          </span>
        )}
      </div>
    </section>
  );
}

/** FR-402/NFR-202 — 키 변경은 별도 입력 흐름(Dialog)으로만 가능 */
function ApiKeyChangeDialog({ endpointId, hasKey }: { endpointId: number; hasKey: boolean }) {
  const [open, setOpen] = useState(false);
  const [newKey, setNewKey] = useState('');
  const queryClient = useQueryClient();

  const change = useMutation({
    mutationFn: () =>
      api.patch<AiEndpoint>(`/ai/endpoints/${endpointId}`, { api_key: newKey }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-endpoints'] });
      setOpen(false);
      setNewKey('');
      toast('API 키가 변경되었습니다.', 'success');
    },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  if (!open) {
    return (
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        🔑 키 변경{hasKey ? '' : '(등록)'}
      </Button>
    );
  }
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={() => setOpen(false)} aria-hidden="true" />
      <div role="dialog" aria-modal="true" aria-label="API 키 변경"
           className="relative z-10 w-[380px] rounded-md border border-border bg-card p-4 shadow-soft">
        <h2 className="mb-1 text-sm font-semibold">API 키 변경</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          저장된 키는 다시 볼 수 없습니다. 새 키를 입력하면 기존 값이 교체됩니다.
        </p>
        <Input type="password" autoFocus value={newKey}
               onChange={(e) => setNewKey(e.target.value)}
               onKeyDown={(e) => { if (e.key === 'Enter' && newKey) change.mutate(); }} />
        <div className="mt-3 flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>취소</Button>
          <Button size="sm" disabled={!newKey || change.isPending} onClick={() => change.mutate()}>
            변경
          </Button>
        </div>
      </div>
    </div>
  );
}

function NewEndpointForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const [form, setForm] = useState<AiEndpointCreate>({
    name: '', base_url: '', api_key: '', default_model: '', temperature: 0.7, is_default: false,
  });
  const create = useMutation({
    mutationFn: () =>
      api.post<AiEndpoint>('/ai/endpoints', {
        ...form,
        name: form.name.trim(),
        base_url: form.base_url.trim(),
        default_model: form.default_model?.trim() || null,
        api_key: form.api_key?.trim() || null,
      }),
    onSuccess: () => { toast('엔드포인트가 추가되었습니다.', 'success'); onDone(); },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  return (
    <section className="rounded-md border border-border p-4">
      <h2 className="mb-3 text-sm font-semibold">새 엔드포인트</h2>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div>
          <Label htmlFor="ne-name">이름 *</Label>
          <Input id="ne-name" className="h-8" value={form.name}
                 onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
        </div>
        <div>
          <Label htmlFor="ne-url">base_url *</Label>
          <Input id="ne-url" className="h-8" placeholder="http://localhost:1234/v1" value={form.base_url}
                 onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))} />
        </div>
        <div>
          <Label htmlFor="ne-key">api_key (선택)</Label>
          <Input id="ne-key" type="password" className="h-8" value={form.api_key ?? ''}
                 onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))} />
        </div>
        <div>
          <Label htmlFor="ne-model">default_model (선택)</Label>
          <Input id="ne-model" className="h-8" value={form.default_model ?? ''}
                 onChange={(e) => setForm((f) => ({ ...f, default_model: e.target.value }))} />
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <Button size="sm" disabled={create.isPending || !form.name.trim() || !form.base_url.trim()}
                onClick={() => create.mutate()}>추가</Button>
        <Button size="sm" variant="ghost" onClick={onCancel}>취소</Button>
      </div>
    </section>
  );
}

function NewPresetForm({ onDone }: { onDone: () => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [templateText, setTemplateText] = useState('');
  const create = useMutation({
    mutationFn: () =>
      api.post<PromptPreset>('/ai/presets', {
        name: name.trim(), template_text: templateText.trim(),
        context_flags: ['chapter'],
      }),
    onSuccess: () => { setOpen(false); setName(''); setTemplateText(''); onDone(); toast('프리셋이 추가되었습니다.', 'success'); },
    onError: (e) => toast((e as Error).message, 'error'),
  });

  if (!open) {
    return <Button size="sm" variant="outline" onClick={() => setOpen(true)}>+ 사용자 프리셋 추가</Button>;
  }
  return (
    <div className="flex flex-col gap-2">
      <Input className="h-8" placeholder="프리셋 이름" value={name} onChange={(e) => setName(e.target.value)} />
      <textarea
        className="min-h-16 rounded-md border border-input bg-background p-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        placeholder="템플릿 텍스트…"
        value={templateText}
        onChange={(e) => setTemplateText(e.target.value)}
      />
      <div className="flex gap-2">
        <Button size="sm" disabled={!name.trim() || !templateText.trim() || create.isPending} onClick={() => create.mutate()}>
          추가
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>취소</Button>
      </div>
    </div>
  );
}

// ---------------- 윤문 탭 ----------------
const ROUTES: Array<{ v: RefineRoute; label: string }> = [
  { v: 'auto', label: '자동 (route_hint 자동 판정)' },
  { v: 'light', label: 'light — 가볍게' },
  { v: 'standard', label: 'standard — 표준' },
  { v: 'heavy', label: 'heavy — 강하게' },
];

function RefineTab() {
  const defaultRoute = useSettingsStore((s) => s.defaultRefineRoute);
  const setDefaultRefineRoute = useSettingsStore((s) => s.setDefaultRefineRoute);

  return (
    <section className="rounded-md border border-border p-4">
      <h2 className="mb-1 text-sm font-semibold">윤문 기본 강도 (FR-502)</h2>
      <fieldset className="mt-2 flex flex-col gap-1.5">
        <legend className="sr-only">윤문 기본 강도 선택</legend>
        {ROUTES.map((r) => (
          <label key={r.v} className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="radio"
              name="refine-route"
              checked={defaultRoute === r.v}
              onChange={() => setDefaultRefineRoute(r.v)}
              className="accent-[hsl(var(--primary))]"
            />
            {r.label}
          </label>
        ))}
      </fieldset>

      <Alert variant="info" className="mt-4">
        <AlertDescription>
          윤문은 "품질 다듬기" 목적입니다. AI 탐지 회피를 의미하지 않습니다. (NFR-401 · im-not-ai 4대 철칙)
          <br />변경률 게이트는 고정값입니다: <strong>30% 경고 / 50% 차단</strong> (FR-505).
          차단 시에는 윤문 재실행 또는 폐지만 가능합니다.
        </AlertDescription>
      </Alert>
    </section>
  );
}

// ---------------- 테마 탭 ----------------
function ThemeTab() {
  const theme = useUiStore((s) => s.theme);
  const setTheme = useUiStore((s) => s.setTheme);
  const fontFamily = useSettingsStore((s) => s.fontFamily);
  const setFontFamily = useSettingsStore((s) => s.setFontFamily);
  const lineHeight = useSettingsStore((s) => s.lineHeight);
  const setLineHeight = useSettingsStore((s) => s.setLineHeight);

  return (
    <section className="rounded-md border border-border p-4">
      <h2 className="mb-3 text-sm font-semibold">테마</h2>
      <fieldset className="mb-4 flex flex-col gap-1.5">
        <legend className="text-xs font-medium text-muted-foreground">모드</legend>
        {(['dark', 'light'] as const).map((t) => (
          <label key={t} className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="radio"
              name="theme-mode"
              checked={theme === t}
              onChange={() => setTheme(t)}
              className="accent-[hsl(var(--primary))]"
            />
            {t === 'dark' ? '다크' : '라이트'}
          </label>
        ))}
      </fieldset>

      <div className="mb-4">
        <Label htmlFor="set-font">본문 폰트</Label>
        <Select id="set-font" className="mt-1 max-w-xs" value={fontFamily}
                onChange={(e) => setFontFamily(e.target.value as typeof fontFamily)}>
          <option value="pretendard">Pretendard (고딕)</option>
          <option value="noto-serif-kr">Noto Serif KR (세리프)</option>
        </Select>
      </div>

      <div>
        <Label htmlFor="set-lh">본문 행간 — 현재 {lineHeight.toFixed(1)}</Label>
        <Slider id="set-lh" className="mt-2 max-w-xs" min={1.6} max={2} step={0.05} value={lineHeight}
                onChange={(e) => setLineHeight(Number(e.target.value))} />
      </div>
    </section>
  );
}

// ---------------- 규정·현황 탭 (NFR-404 / FR-601·602) ----------------
function PolicyTab() {
  return (
    <div className="flex flex-col gap-4">
      {/* NFR-404 안내 — 탭 최상단 고정 */}
      <Alert variant="warning">
        <AlertDescription>
          <strong>AI 사용 여부의 공개/비공개 판단은 작가의 몫입니다.</strong>
          <br />앱은 안내 의무만 부담하며, 권장 방침을 유도하지 않습니다.
        </AlertDescription>
      </Alert>

      <section className="rounded-md border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold">플랫폼 AI 규정 요약 (FR-601)</h2>
        <ul className="flex flex-col gap-2 text-sm">
          {['노벨피아', '문피아', '조아라'].map((platform) => (
            <li key={platform} className="flex items-center gap-2 rounded-sm bg-background px-3 py-2">
              📄 {platform} AI 규정 요약
              <Badge variant="secondary" className="ml-auto">요약 준비 중</Badge>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-muted-foreground">
          각 플랫폼의 최신 AI 이용 규정은 반드시 원문(공식 공지)을 직접 확인하세요.
        </p>
      </section>

      <section className="rounded-md border border-border p-4">
        <h2 className="mb-2 text-sm font-semibold">노벨피아 PLUS 충족 현황 (FR-602)</h2>
        <ul className="list-inside list-disc text-sm text-muted-foreground">
          <li>작품 수 15편 이상 — 홈 화면에서 총 작품 수로 확인</li>
          <li>회차당 3,000자(공백 제외) — 에디터 푸터의 "공백제외" 글자 수로 확인</li>
        </ul>
      </section>
    </div>
  );
}

// ---------------- 고급 탭 ----------------
function AdvancedTab() {
  const lineNumbers = useSettingsStore((s) => s.lineNumbers);
  const setLineNumbers = useSettingsStore((s) => s.setLineNumbers);
  const intervalMs = useSettingsStore((s) => s.autoSaveIntervalMs);
  const setAutoSaveInterval = useSettingsStore((s) => s.setAutoSaveInterval);

  // 에디터 lineNumbers 런타임 토글(m-7) — Compartment 재구성은 CodeMirrorEditor에서 감지
  useEffect(() => { /* store 구독만으로 충분 — CM 래퍼가 store를 구독 */ }, []);

  return (
    <section className="flex flex-col gap-4 rounded-md border border-border p-4">
      <h2 className="text-sm font-semibold">고급</h2>

      <label className="flex cursor-pointer items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={lineNumbers}
          onChange={(e) => setLineNumbers(e.target.checked)}
          className="h-4 w-4 accent-[hsl(var(--primary))]"
        />
        에디터 줄 번호 표시 (m-7 — 기본 OFF, 집중 모드)
      </label>

      <div className="max-w-sm">
        <Label htmlFor="adv-autosave">자동 저장 주기 — 현재 {(intervalMs / 1000).toFixed(1)}초 (FR-106)</Label>
        <Slider id="adv-autosave" className="mt-2" min={500} max={5000} step={250} value={intervalMs}
                onChange={(e) => setAutoSaveInterval(Number(e.target.value))} />
      </div>

      <p className="text-xs text-muted-foreground">
        설정은 이 브라우저(localStorage)에 저장됩니다. 백업·복원(SQLite 파일 단위, NFR-203)은 백로그입니다.
      </p>
    </section>
  );
}
