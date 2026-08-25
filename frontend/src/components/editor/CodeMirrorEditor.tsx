import { useEffect, useRef } from 'react';
import { EditorState, Compartment } from '@codemirror/state';
import { EditorView, keymap, lineNumbers, highlightActiveLine } from '@codemirror/view';
import { markdown } from '@codemirror/lang-markdown';
import { useSettingsStore } from '@/stores/settingsStore';
import { useEditorStore } from '@/stores/editorStore';

interface Props {
  value: string;
  /** 문서 변경 콜백 — 부모에서 디바운스(자동저장 FR-106·글자수 FR-104) 처리 */
  onChange: (text: string) => void;
  /** Ctrl/Cmd+S 수동 저장 (debounce 우회 즉시 PUT) */
  onSave: () => void;
  ariaLabel?: string;
}

/** m-7 — lineNumbers 기본 OFF + Compartment로 런타임 토글 (에디터 재생성 없음) */
const lineNumbersCompartment = new Compartment();

/**
 * CodeMirror 6 래퍼 — NFR-101 가상 스크롤(수만~십만 자 무지연),
 * §4 토큰 기반 저채도 세리프 테마.
 */
export function CodeMirrorEditor({ value, onChange, onSave, ariaLabel = '원고 에디터' }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange);
  const onSaveRef = useRef(onSave);
  onChangeRef.current = onChange;
  onSaveRef.current = onSave;

  // 마운트 1회 — View 생성
  useEffect(() => {
    if (!containerRef.current) return;

    const lineNumbersOn = useSettingsStore.getState().lineNumbers;
    const view = new EditorView({
      state: EditorState.create({
        doc: value,
        extensions: [
          lineNumbersCompartment.of(lineNumbersOn ? lineNumbers() : []),
          highlightActiveLine(),
          markdown(),
          EditorView.lineWrapping,
          EditorView.contentAttributes.of({ 'aria-label': ariaLabel }),
          keymap.of([
            { key: 'Mod-s', run: () => { onSaveRef.current(); return true; } },
          ]),
          EditorView.theme({
            '&': {
              fontFamily: 'var(--font-serif, "Noto Serif KR", serif)',
              fontSize: '1.0625rem',
              lineHeight: '1.85',
              letterSpacing: '0.005em',
              backgroundColor: 'hsl(var(--background))',
              color: 'hsl(var(--foreground))',
            },
            '&.cm-focused': { outline: 'none' },
            '.cm-content': { caretColor: 'hsl(var(--primary))' },
            '.cm-cursor': { borderLeftColor: 'hsl(var(--primary))' },
            '.cm-gutters': { background: 'transparent', borderRight: '1px solid hsl(var(--border))', color: 'hsl(var(--muted-foreground))' },
            '.cm-activeLine': { background: 'hsl(var(--muted) / 0.35)' },
            '.cm-selectionBackground': { background: 'hsl(var(--primary) / 0.18) !important' },
            '&.cm-focused .cm-selectionBackground': { background: 'hsl(var(--primary) / 0.18) !important' },
          }),
          EditorView.updateListener.of((u) => {
            if (u.docChanged) onChangeRef.current(u.state.doc.toString());
          }),
        ],
      }),
      parent: containerRef.current,
    });
    viewRef.current = view;
    // S5 [끼워넣기]/[선택 교체]가 전역으로 View 핸들을 사용할 수 있도록 등록
    useEditorStore.getState().setView(view);

    return () => {
      useEditorStore.getState().setView(null);
      view.destroy();
      viewRef.current = null;
    };
    // 최초 마운트에서만 생성 — 이후 값 동기화는 아래 effect에서 처리
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 외부 값(회차 전환/윤문 수락 등 서버 진실 변경) → 에디터 동기화.
  // 사용자가 방금 입력으로 만든 변경은 덮어쓰지 않음(문서가 이미 같으면 skip).
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const current = view.state.doc.toString();
    if (current !== value) {
      view.dispatch({
        changes: { from: 0, to: current.length, insert: value },
      });
    }
  }, [value]);

  // m-7 — settingsStore.lineNumbers 변경 → Compartment 재구성 (인스턴스 재생성 X)
  useEffect(() => {
    const lineNumbersModule = lineNumbers;
    const unsub = useSettingsStore.subscribe((state, prev) => {
      if (state.lineNumbers === prev.lineNumbers) return;
      viewRef.current?.dispatch({
        effects: lineNumbersCompartment.reconfigure(
          state.lineNumbers ? lineNumbersModule() : [],
        ),
      });
    });
    return unsub;
  }, []);

  return <div ref={containerRef} className="min-h-full" />;
}
