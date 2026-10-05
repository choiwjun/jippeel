import { api } from './api';
import type { StoryMapData, StoryMapNode } from './storyMap';

/** Collect bounded metadata pages; never fetch manuscripts or call a provider. */
export async function fetchStoryMapScope(pid: number, scope: 'all' | 'volume', anchor: number | null, signal: AbortSignal): Promise<StoryMapData> {
  let offset = 0;
  let first: StoryMapData | undefined;
  const nodes: StoryMapNode[] = [];
  const seen = new Set<number>();
  while (true) {
    const page = await api.get<StoryMapData>(`/projects/${pid}/story-map?scope=${scope}&offset=${offset}${anchor === null ? '' : `&anchor_id=${anchor}`}`, { signal });
    first ??= page;
    if (page.offset !== offset || page.counts.total !== first.counts.total || page.scope !== scope ||
        page.nodes.some(node => seen.has(node.id))) {
      throw new Error('조회 중 회차 구성이 바뀌었습니다. 전체 지도를 다시 불러와 주세요.');
    }
    page.nodes.forEach(node => { seen.add(node.id); nodes.push(node); });
    if (page.next_offset === null) break;
    if (page.next_offset <= offset || page.next_offset >= first.counts.total || !page.nodes.length) throw new Error('전체 회차를 불러오지 못했습니다. 다시 시도해 주세요.');
    offset = page.next_offset;
  }
  if (nodes.length !== first.counts.total || nodes.some((node, i) => i > 0 && node.position !== nodes[i - 1].position + 1)) {
    throw new Error('조회 중 회차 구성이 바뀌었습니다. 전체 지도를 다시 불러와 주세요.');
  }
  // Keep counters consistent with the displayed nodes, even if a different tab
  // saved/confirmed a chapter between pages. This is not an atomic DB snapshot.
  return { ...first, nodes, counts: { total: nodes.length,
    written: nodes.filter(node => node.word_count > 0).length,
    confirmed: nodes.filter(node => node.flow_stage === 'confirmed').length }, offset: 0, next_offset: null };
}
