import type { Config } from 'tailwindcss';

/**
 * 디자인_화면설계서 v1.x §4.1 토큰 매핑 — 저채도 세리프 톤.
 * shadcn 기본 뉴트럴 팔레트 미사용(P7).
 */
export default {
  darkMode: ['class', '.light'], // 다크가 기본(:root), 라이트는 .light 클래스
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: { DEFAULT: 'hsl(var(--primary))', foreground: 'hsl(var(--primary-foreground))' },
        secondary: { DEFAULT: 'hsl(var(--secondary))', foreground: 'hsl(var(--secondary-foreground))' },
        destructive: { DEFAULT: 'hsl(var(--destructive))', foreground: 'hsl(var(--destructive-foreground))' },
        muted: { DEFAULT: 'hsl(var(--muted))', foreground: 'hsl(var(--muted-foreground))' },
        accent: { DEFAULT: 'hsl(var(--accent))', foreground: 'hsl(var(--accent-foreground))' },
        popover: { DEFAULT: 'hsl(var(--popover))', foreground: 'hsl(var(--popover-foreground))' },
        card: { DEFAULT: 'hsl(var(--card))', foreground: 'hsl(var(--card-foreground))' },
        warning: { DEFAULT: 'hsl(var(--warning))', foreground: 'hsl(var(--warning-foreground))' },
        info: { DEFAULT: 'hsl(var(--info))', foreground: 'hsl(var(--info-foreground))' },
        status: {
          draft: 'hsl(var(--status-draft))',
          revising: 'hsl(var(--status-revising))',
          done: 'hsl(var(--status-done))',
        },
        cat: {
          A: 'hsl(var(--cat-A))', B: 'hsl(var(--cat-B))',
          C: 'hsl(var(--cat-C))', D: 'hsl(var(--cat-D))',
          E: 'hsl(var(--cat-E))', F: 'hsl(var(--cat-F))',
          G: 'hsl(var(--cat-G))', H: 'hsl(var(--cat-H))',
          I: 'hsl(var(--cat-I))', J: 'hsl(var(--cat-J))',
        },
        diff: {
          add: 'hsl(var(--diff-add))', del: 'hsl(var(--diff-del))',
          addBg: 'hsl(var(--diff-add-bg))', delBg: 'hsl(var(--diff-del-bg))',
        },
      },
      fontFamily: {
        // 본문 — 한글 웹소설 원고용 세리프 (§4.2)
        serif: ['"Noto Serif KR"', '"Source Serif Pro"', '"Pretendard"', 'Georgia', 'serif'],
        sans: ['"Pretendard"', '"Inter"', '"system-ui"', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', '"D2Coding"', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        prose: ['1.0625rem', { lineHeight: '1.85', letterSpacing: '0.005em' }],
        'prose-lg': ['1.1875rem', { lineHeight: '1.9', letterSpacing: '0.01em' }],
        'prose-sm': ['0.9375rem', { lineHeight: '1.7' }],
      },
      borderRadius: { lg: '0.5rem', md: '0.375rem', sm: '0.25rem' },
      boxShadow: {
        soft: '0 1px 2px hsl(var(--foreground) / 0.04), 0 4px 12px hsl(var(--foreground) / 0.06)',
      },
      transitionDuration: { DEFAULT: '120ms', fast: '80ms' },
    },
  },
  plugins: [],
} satisfies Config;
