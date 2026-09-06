import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AppShell } from '@/components/layout/AppShell';
import { HomePage } from '@/pages/HomePage';
import { EditorPage } from '@/pages/EditorPage';
import { CharactersPage } from '@/pages/CharactersPage';
import { LorebookPage } from '@/pages/LorebookPage';
import { ForeshadowsPage } from '@/pages/ForeshadowsPage';
import { PlanPage } from '@/pages/PlanPage';
import { SettingsPage } from '@/pages/SettingsPage';

/**
 * App 셸 + 라우팅 — 사양 §2.2 / 설계서 §1.3 컴포넌트 트리.
 * Sprint 4a: S1 홈(`/`) · S2 에디터(`/projects/{id}/write`).
 * Sprint 4b: S3 캐릭터 · S4 로어북 · S5/S6 RightPanel · S7 설정.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/projects/:pid/write" element={<EditorPage />} />
            <Route path="/projects/:pid/characters" element={<CharactersPage />} />
            <Route path="/projects/:pid/lore" element={<LorebookPage />} />
            <Route path="/projects/:pid/foreshadows" element={<ForeshadowsPage />} />
            <Route path="/projects/:pid/plan" element={<PlanPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="*" element={<HomePage />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
