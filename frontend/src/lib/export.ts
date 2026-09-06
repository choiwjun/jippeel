/**
 * FR-109 내보내기 — 회차 .txt/.md 다운로드 + 프로젝트 묶음 내보내기.
 * .txt는 markdown-it 렌더 → DOMPurify sanitize → 텍스트 추출(마크다운 기호 제거).
 * 외부 호출 없음, 브라우저 Blob 다운로드만 수행.
 */
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';
import { volumeSortKey, type ChapterDetail } from './api';

const md = new MarkdownIt({ html: false, breaks: true });

/** 마크다운 → plain text (FR-109 .txt 변환) */
export function mdToPlainText(mdText: string): string {
  const html = DOMPurify.sanitize(md.render(mdText));
  const el = document.createElement('div');
  el.innerHTML = html;
  // 블록 요소 사이 개행 유지
  const text = el.textContent ?? '';
  return text.replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

function triggerDownload(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function safeName(name: string): string {
  return (name.trim().replace(/[\\/:*?"<>|]/g, '_')) || 'untitled';
}

export function exportChapter(chapter: ChapterDetail, ext: 'txt' | 'md') {
  const filename = safeName(chapter.title || `chapter-${chapter.id}`) + '.' + ext;
  const content = ext === 'txt' ? mdToPlainText(chapter.content_md) : chapter.content_md;
  triggerDownload(content, filename, 'text/plain');
}

/** 프로젝트 묶음 — 전 회차를 하나의 파일로 연결(zip 미사용 단일 파일 묶음, FR-109) */
export function exportProjectBundle(
  projectTitle: string,
  chapters: ChapterDetail[],
  ext: 'txt' | 'md',
) {
  const sorted = [...chapters].sort(
    (a, b) => volumeSortKey(a.volume) - volumeSortKey(b.volume) || a.sort_order - b.sort_order,
  );
  const parts = sorted.map((ch) => {
    const volumePrefix = ch.volume != null ? `${ch.volume}권 ` : '';
    const heading = `${volumePrefix}${ch.title.trim() || `${ch.id}화`}`;
    const body = ext === 'txt' ? mdToPlainText(ch.content_md) : ch.content_md;
    return ext === 'md'
      ? `# ${heading}\n\n${body}\n\n---\n\n`
      : `${heading}\n\n${'='.repeat(24)}\n\n${body}\n\n`;
  });
  const header = ext === 'md' ? `# ${projectTitle}\n\n` : `${projectTitle}\n\n${'='.repeat(24)}\n\n`;
  triggerDownload(header + parts.join(''), safeName(projectTitle) + '.' + ext, 'text/plain');
}
