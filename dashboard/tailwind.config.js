/** @type {import('tailwindcss').Config} */
export default {
	content: [
		"./index.html",
		"./src/**/*.{js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			colors: {
				// Base neutrals (warm, never pure)
				bg: {
					primary: 'var(--bg-primary)',
					secondary: 'var(--bg-secondary)',
					tertiary: 'var(--bg-tertiary)',
					elevated: 'var(--bg-elevated)',
				},
				// Ink (text) colors
				ink: {
					primary: 'var(--ink-primary)',
					secondary: 'var(--ink-secondary)',
					muted: 'var(--ink-muted)',
				},
				// Functional accents - signals only
				accent: {
					yellow: 'var(--accent-yellow)',
					red: 'var(--accent-red)',
					blue: 'var(--accent-blue)',
					green: 'var(--accent-green)',
					orange: 'var(--accent-orange)',
					purple: 'var(--accent-purple)',
				},
				// Borders
				border: {
					DEFAULT: 'var(--border-default)',
					strong: 'var(--border-strong)',
				},
			},
			fontFamily: {
				sans: ['IBM Plex Sans', 'system-ui', 'sans-serif'],
				mono: ['IBM Plex Mono', 'ui-monospace', 'monospace'],
			},
			// Strict spacing scale
			spacing: {
				'1': '4px',
				'2': '8px',
				'3': '12px',
				'4': '16px',
				'6': '24px',
				'8': '32px',
				'12': '48px',
				'16': '64px',
			},
			borderRadius: {
				'none': '0',
				'sm': '2px',
				DEFAULT: '4px',
			},
			fontSize: {
				'display': ['40px', { lineHeight: '1.1', fontWeight: '700' }],
				'h1': ['32px', { lineHeight: '1.2', fontWeight: '700' }],
				'h2': ['24px', { lineHeight: '1.25', fontWeight: '600' }],
				'h3': ['18px', { lineHeight: '1.3', fontWeight: '600' }],
				'body': ['15px', { lineHeight: '1.5', fontWeight: '400' }],
				'small': ['13px', { lineHeight: '1.4', fontWeight: '400' }],
				'label': ['11px', { lineHeight: '1.3', fontWeight: '500', letterSpacing: '0.05em' }],
				'mono': ['13px', { lineHeight: '1.4', fontWeight: '500' }],
			},
			transitionDuration: {
				'fast': '150ms',
			},
			transitionTimingFunction: {
				'out': 'ease-out',
			},
		},
	},
	plugins: [],
}
