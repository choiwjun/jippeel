/**
 * FR-104 — 글자 수(공백 포함/제외/노벨피아 기준). 디바운스 후 호출 권장.
 *
 * novelpia ("노벨피아 모드", 부록06 근거): 공백에 더해 문장부호·특수문자까지
 * 제외하고 문자(\p{L})·숫자(\p{N})만 집계한다. 커뮤니티 다중 실측 보고상
 * 일반 공백제외 대비 약 -10% 내외이며, 정확한 제외 문자집합은 비공개라
 * 최종 확정은 G7 테스트 회차 실측으로 검증한다.
 */
const NOVELPIA_EXCLUDE = /[^\p{L}\p{N}]/gu;

export function countNovelpia(text: string): number {
  return [...(text ?? '').replace(NOVELPIA_EXCLUDE, '')].length;
}

export function countChars(text: string): {
  total: number;
  noSpace: number;
  novelpia: number;
} {
  const total = [...text].length;
  const noSpace = [...text.replace(/\s/g, '')].length;
  return { total, noSpace, novelpia: countNovelpia(text) };
}
