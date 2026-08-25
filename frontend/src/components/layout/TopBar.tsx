import { Link, useLocation, useParams } from 'react-router-dom';
import { useUiStore } from '@/stores/uiStore';
import { useEditorStore } from '@/stores/editorStore';
import { Button } from '@/components/ui/button';

/** §1.1 TopBar 56px — 로고 / 프로젝트 셀렉터 / 저장 상태(FR-106) / 테마 토글 */
export function TopBar() {
  const theme = useUiStore((s) => s.theme);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
  const saveState = useEditorStore((s) => s.saveState);
  const { pid } = useParams();
  const location = useLocation();
  const onEditorPage = location.pathname.includes('/write') && pid;

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4">
      <Link to="/" className="text-base font-semibold tracking-tight">
        Jippeel
      </Link>

      {onEditorPage ? (
        <span className="text-sm text-muted-foreground">
          프로젝트 #{pid}
        </span>
      ) : null}

      <div className="ml-auto flex items-center gap-2">
        {onEditorPage && (
          <span className="text-xs text-muted-foreground" aria-live="polite">
            {saveState === 'saving' ? '저장 중…' : saveState === 'error' ? '저장 실패' : '자동저장: ON'}
          </span>
        )}
        <Button variant="ghost" size="sm" onClick={toggleTheme} aria-label="테마 전환 (다크/라이트)">
          {theme === 'dark' ? '라이트 모드' : '다크 모드'}
        </Button>
      </div>
    </header>
  );
}
