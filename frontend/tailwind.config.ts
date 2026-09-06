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
        border: 'hsl(var(--border) / <alpha-value>)',
        input: 'hsl(var(--input) / <alpha-value>)',
        ring: 'hsl(var(--ring) / <alpha-value>)',
        background: 'hsl(var(--background) / <alpha-value>)',
        foreground: 'hsl(var(--foreground) / <alpha-value>)',
        primary: { DEFAULT: 'hsl(var(--primary) / <alpha-value>)', foreground: 'hsl(var(--primary-foreground) / <alpha-value>)' },
        secondary: { DEFAULT: 'hsl(var(--secondary) / <alpha-value>)', foreground: 'hsl(var(--secondary-foreground) / <alpha-value>)' },
        destructive: { DEFAULT: 'hsl(var(--destructive) / <alpha-value>)', foreground: 'hsl(var(--destructive-foreground) / <alpha-value>)' },
        muted: { DEFAULT: 'hsl(var(--muted) / <alpha-value>)', foreground: 'hsl(var(--muted-foreground) / <alpha-value>)' },
        accent: { DEFAULT: 'hsl(var(--accent) / <alpha-value>)', foreground: 'hsl(var(--accent-foreground) / <alpha-value>)' },
        popover: { DEFAULT: 'hsl(var(--popover) / <alpha-value>)', foreground: 'hsl(var(--popover-foreground) / <alpha-value>)' },
        card: { DEFAULT: 'hsl(var(--card) / <alpha-value>)', foreground: 'hsl(var(--card-foreground) / <alpha-value>)' },
        warning: { DEFAULT: 'hsl(var(--warning) / <alpha-value>)', foreground: 'hsl(var(--warning-foreground) / <alpha-value>)' },
        info: { DEFAULT: 'hsl(var(--info) / <alpha-value>)', foreground: 'hsl(var(--info-foreground) / <alpha-value>)' },
        status: {
          draft: 'hsl(var(--status-draft) / <alpha-value>)',
          revising: 'hsl(var(--status-revising) / <alpha-value>)',
          done: 'hsl(var(--status-done) / <alpha-value>)',
        },
        cat: {
          A: 'hsl(var(--cat-A))', B: 'hsl(var(--cat-B))',
          C: 'hsl(var(--cat-C))', D: 'hsl(var(--cat-D))',
          E: 'hsl(var(--cat-E))', F: 'hsl(var(--cat-F))',
          G: 'hsl(var(--cat-G))', H: 'hsl(var(--cat-H))',
          I: 'hsl(var(--cat-I))', J: 'hsl(var(--cat-J))',
        },
        diff: {
          add: 'hsl(var(--diff-add) / <alpha-value>)', del: 'hsl(var(--diff-del) / <alpha-value>)',
          addBg: 'hsl(var(--diff-add-bg) / <alpha-value>)', delBg: 'hsl(var(--diff-del-bg) / <alpha-value>)',
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
