import { diffChars } from 'diff';

export interface DiffPart {
  text: string;
  added: boolean;
  removed: boolean;
}

/** FR-504 — jsdiff 문자 단위 diff (S6 윤문 리포트에서 사용 예정, Sprint 4b) */
export function charDiff(original: string, refined: string): DiffPart[] {
  return diffChars(original, refined).map((p) => ({
    text: p.value,
    added: Boolean(p.added),
    removed: Boolean(p.removed),
  }));
}
