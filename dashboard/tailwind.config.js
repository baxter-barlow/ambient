/** @type {import('tailwindcss').Config} */
export default {
	content: [
		"./index.html",
		"./src/**/*.{js,ts,jsx,tsx}",
	],
	theme: {
		extend: {
			colors: {
				// Background hierarchy (neutral grays, no blue tint)
				surface: {
					0: '#131518',  // Page background (darkest)
					1: '#18191d',  // Sidebar/Header
					2: '#1e2024',  // Cards/Panels
					3: '#252830',  // Elevated/Hover
					4: '#2d3138',  // Active/Selected
				},
				// Border colors
				border: {
					DEFAULT: '#2a2d32',  // Primary border
					subtle: '#232529',   // Internal dividers
				},
				// Text hierarchy
				text: {
					primary: '#e5e7eb',
					secondary: '#9ca3af',
					tertiary: '#6b7280',
					inverse: '#131518',
				},
				// Semantic colors
				accent: {
					teal: '#00a896',      // Primary accent, streaming active
					'teal-hover': '#00bfa9',
					green: '#22c55e',     // Connected, healthy, pass
					red: '#ef4444',       // Heart rate, errors, disconnect
					blue: '#3b82f6',      // Respiratory rate, info
					amber: '#f59e0b',     // Warnings, temperature
					purple: '#a855f7',    // Debug mode
				},
				// Legacy radar colors (kept for compatibility)
				radar: {
					400: '#00a896',
					500: '#00a896',
					600: '#00a896',
				},
			},
			fontFamily: {
				sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
				mono: ['JetBrains Mono', 'SF Mono', 'Fira Code', 'Consolas', 'monospace'],
			},
			borderRadius: {
				DEFAULT: '4px',
				card: '8px',
			},
			fontSize: {
				'micro': ['9px', { lineHeight: '12px', fontWeight: '600' }],
				'xs': ['11px', { lineHeight: '16px' }],
				'sm': ['12px', { lineHeight: '16px' }],
				'base': ['13px', { lineHeight: '20px' }],
				'lg': ['14px', { lineHeight: '20px', fontWeight: '600' }],
				'xl': ['16px', { lineHeight: '24px', fontWeight: '600', letterSpacing: '-0.01em' }],
				// Metric values
				'metric-sm': ['14px', { lineHeight: '20px', fontWeight: '500' }],
				'metric-md': ['20px', { lineHeight: '28px', fontWeight: '600' }],
				'metric-lg': ['28px', { lineHeight: '36px', fontWeight: '600', letterSpacing: '-0.02em' }],
			},
			spacing: {
				'4.5': '18px',
			},
		},
	},
	plugins: [],
}
