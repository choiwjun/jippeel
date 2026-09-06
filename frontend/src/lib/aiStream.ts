/**
 * S5 AI 생성 SSE 클라이언트 (FR-405 / 설계서 §7.3 v1.2 R-2).
 * EventSource 금지 — POST fetch + ReadableStream getReader()로 파싱한다.
 * 백엔드(sse-starlette) 이벤트: start {model, injected_lore} / message {delta} / error {detail} / done [DONE]
 */

export interface InjectedLore {
  id: number;
  title: string;
}

/** G-001 — 목차 자동 주입 정보(start 이벤트 투명성) */
export interface InjectedOutline {
  current?: boolean;
  next_chapter_id?: number;
  next_title?: string;
}

export interface StreamHandlers {
  onStart?: (info: {
    model: string;
    injectedLore: InjectedLore[];
    injectedForeshadows: InjectedLore[];
    injectedOutline: InjectedOutline | null;
    reviewEnabled: boolean;
  }) => void;
  onChunk: (delta: string) => void;
  /** 감수 패스 개시 — 초안 스트림이 정상 종료된 직후 발화 */
  onReviewStart?: (info: { model: string; endpoint: string; reasoningEffort: string | null }) => void;
  /** 감수 의견(지적 사항) delta */
  onReviewChunk?: (delta: string) => void;
  /** 감수 반영 수정본 delta */
  onRefinedChunk?: (delta: string) => void;
  /** 감수 실패 — 초안은 이미 수신 완료, 스트림은 계속 진행 */
  onReviewError?: (message: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

function parseInjectedLore(raw: unknown): InjectedLore[] {
  if (!Array.isArray(raw)) return [];
  return raw.filter(
    (x): x is InjectedLore =>
      typeof x === 'object' && x !== null &&
      typeof (x as InjectedLore).id === 'number' &&
      typeof (x as InjectedLore).title === 'string',
  );
}

/** @returns abort 함수 — [중단] 버튼이 호출해 스트림을 끊는다 */
export function streamGenerate(
  body: unknown,
  handlers: StreamHandlers,
): () => void {
  const ctrl = new AbortController();

  void (async () => {
    let res: Response;
    try {
      res = await fetch('/api/v1/ai/generate', {
        method: 'POST',
        headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
        body: JSON.stringify(body),
        signal: ctrl.signal,
      });
    } catch (e) {
      if ((e as Error).name === 'AbortError') return; // 사용자 중단은 에러 아님
      handlers.onError('백엔드에 연결할 수 없습니다. 서버 실행 여부를 확인하세요.');
      return;
    }
    if (!res.ok || !res.body) {
      let msg = `HTTP ${res.status}`;
      try {
        const j = await res.json();
        if (typeof j?.detail === 'string') msg = j.detail;
      } catch { /* noop */ }
      handlers.onError(msg);
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';
    let finished = false;

    const handleEvent = (eventName: string, data: string) => {
      if (eventName === 'start') {
        try {
          const parsed = JSON.parse(data);
          handlers.onStart?.({
            model: parsed.model ?? '',
            injectedLore: parseInjectedLore(parsed.injected_lore),
            injectedForeshadows: parseInjectedLore(parsed.injected_foreshadows),
            injectedOutline: typeof parsed.injected_outline === 'object'
              && parsed.injected_outline !== null ? parsed.injected_outline : null,
            reviewEnabled: parsed.review_enabled === true,
          });
        } catch { /* noop */ }
      } else if (eventName === 'message') {
        try {
          const delta = JSON.parse(data).delta;
          if (typeof delta === 'string' && delta.length > 0) handlers.onChunk(delta);
        } catch { /* noop */ }
      } else if (eventName === 'review_start') {
        try {
          const parsed = JSON.parse(data);
          handlers.onReviewStart?.({
            model: parsed.model ?? '',
            endpoint: parsed.endpoint ?? '',
            reasoningEffort: parsed.reasoning_effort ?? null,
          });
        } catch { /* noop */ }
      } else if (eventName === 'review') {
        try {
          const delta = JSON.parse(data).delta;
          if (typeof delta === 'string' && delta.length > 0) handlers.onReviewChunk?.(delta);
        } catch { /* noop */ }
      } else if (eventName === 'refined') {
        try {
          const delta = JSON.parse(data).delta;
          if (typeof delta === 'string' && delta.length > 0) handlers.onRefinedChunk?.(delta);
        } catch { /* noop */ }
      } else if (eventName === 'review_error') {
        let detail = '감수 패스 실패 (초안은 보존됩니다).';
        try { detail = JSON.parse(data).detail ?? detail; } catch { /* noop */ }
        handlers.onReviewError?.(detail);
      } else if (eventName === 'error') {
        finished = true;
        let detail = '스트리밍 중 오류가 발생했습니다.';
        try { detail = JSON.parse(data).detail ?? detail; } catch { /* noop */ }
        handlers.onError(detail);
      } else if (eventName === 'done' || data.trim() === '[DONE]') {
        finished = true;
        handlers.onDone();
      }
    };

    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        // SSE 프레임 구분: 빈 줄(\n\n). CRLF 대응.
        const frames = buf.split(/\n\n|\r\n\r\n/);
        buf = frames.pop() ?? '';
        for (const frame of frames) {
          let eventName = 'message';
          const dataLines: string[] = [];
          for (const line of frame.split(/\n|\r\n/)) {
            if (line.startsWith('event:')) eventName = line.slice(6).trim();
            else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
          }
          handleEvent(eventName, dataLines.join('\n'));
          if (finished) return;
        }
      }
      // 남은 버퍼 처리
      if (!finished && buf.trim()) {
        let eventName = 'message';
        const dataLines: string[] = [];
        for (const line of buf.split(/\n|\r\n/)) {
          if (line.startsWith('event:')) eventName = line.slice(6).trim();
          else if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
        }
        handleEvent(eventName, dataLines.join('\n'));
      }
      if (!finished) handlers.onDone(); // 서버가 done 없이 종료한 경우
    } catch (e) {
      if ((e as Error).name !== 'AbortError') {
        handlers.onError(`스트리밍 실패: ${(e as Error).message}`);
      }
    }
  })();

  return () => ctrl.abort();
}
