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
export async function refreshMemoriesAfterRevision(projectId: number, previous: number, next: number | undefined) {
  if (next === undefined || next === previous) return;
  try {
    await queryClient.invalidateQueries({ queryKey: ["memories", projectId] });
  } catch {
    console.error("Memory cache refresh failed after an acknowledged manuscript revision.");
  }
}
