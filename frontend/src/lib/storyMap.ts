import type { ChapterGoalPayload, FlowStage } from './api';

export type StoryMapScope = 'near' | 'volume' | 'all';
export interface StoryMapCounts { total: number; written: number; confirmed: number }
export interface StoryMapNode {
  id: number;
  position: number;
  volume: number | null;
  title: string;
  flow_stage: FlowStage;
  word_count: number;
  revision: number;
  goal: ChapterGoalPayload | null;
  goal_version: number | null;
  goal_base_revision: number | null;
  scene_count: number;
}
export interface StoryMapData {
  project_id: number;
  anchor_id: number | null;
  scope: StoryMapScope;
  counts: StoryMapCounts;
  volumes: (StoryMapCounts & { volume: number | null; first_chapter_id: number })[];
  nodes: StoryMapNode[];
  offset: number;
  next_offset: number | null;
}
