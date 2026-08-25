import { useMemo } from 'react';
import MarkdownIt from 'markdown-it';
import DOMPurify from 'dompurify';

/** FR-103 미리보기 탭 — markdown-it → DOMPurify sanitize (XSS 방지, 사양 §2.1) */
export function EditorPreview({ content }: { content: string }) {
  const html = useMemo(() => {
    const md = new MarkdownIt({ html: false, linkify: true, breaks: true });
    return DOMPurify.sanitize(md.render(content));
  }, [content]);

  return (
    <div
      className="mx-auto max-w-[720px] px-8 py-6 font-serif font-prose [&_h1,&_h2,&_h3]:font-sans [&_h1,&_h2,&_h3]:font-semibold"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
