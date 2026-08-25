/** FR-104 — 글자 수(공백 포함/제외). 디바운스 후 호출 권장. */
export function countChars(text: string): { total: number; noSpace: number } {
  const total = [...text].length;
  const noSpace = [...text.replace(/\s/g, '')].length;
  return { total, noSpace };
}
