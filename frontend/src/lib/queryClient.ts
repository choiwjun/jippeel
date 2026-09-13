import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
      refetchOnWindowFocus: false,
    },
  },
});

// Cache-only acknowledgement survives editor unmount; a refresh failure is not a failed write.
export async function refreshMemoriesAfterRevision(projectId: number, chapterId: number, previous: number, next: number | undefined) {
  if (next === undefined || next === previous) return;
  try {
    await queryClient.invalidateQueries({ queryKey: ["memories", projectId] });
    // D03-2: revision이 바뀌면 재개 드리프트(원고 변경됨)도 갱신 대상이다.
    await queryClient.invalidateQueries({ queryKey: ["chapter-resume", chapterId] });
    // D03-4: 원문이 바뀌면 근거 링크의 excerpt 포함 여부도 갱신 대상이다.
    await queryClient.invalidateQueries({ queryKey: ["evidence-links", chapterId] });
  } catch {
    console.error("Memory cache refresh failed after an acknowledged manuscript revision.");
  }
}
