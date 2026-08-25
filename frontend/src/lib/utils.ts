/** 경량 className 조합 유틸 (추가 의존성 없음). */
export function cn(...inputs: Array<string | false | null | undefined>): string {
  return inputs.filter(Boolean).join(' ');
}
