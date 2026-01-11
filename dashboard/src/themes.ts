// Theme definitions for the Ambient Dashboard
// Each theme defines colors, fonts, and overall aesthetic

export interface Theme {
	id: string
	name: string
	description: string
	colors: {
		// Background hierarchy
		surface0: string  // Page background (darkest)
		surface1: string  // Sidebar/Header
		surface2: string  // Cards/Panels
		surface3: string  // Elevated/Hover
		surface4: string  // Active/Selected
		// Borders
		border: string
		borderSubtle: string
		// Text
		textPrimary: string
		textSecondary: string
		textTertiary: string
		textInverse: string
		// Accents
		accent: string
		accentHover: string
		success: string
		error: string
		warning: string
		info: string
	}
	fonts: {
		sans: string
		mono: string
	}
}

export const themes: Record<string, Theme> = {
	// Current theme - Teal Tech (default)
	'teal-tech': {
		id: 'teal-tech',
		name: 'Teal Tech',
		description: 'Modern dark theme with teal accents - the current default',
		colors: {
			surface0: '#131518',
			surface1: '#18191d',
			surface2: '#1e2024',
			surface3: '#252830',
			surface4: '#2d3138',
			border: '#2a2d32',
			borderSubtle: '#232529',
			textPrimary: '#e5e7eb',
			textSecondary: '#9ca3af',
			textTertiary: '#6b7280',
			textInverse: '#131518',
			accent: '#00a896',
			accentHover: '#00bfa9',
			success: '#22c55e',
			error: '#ef4444',
			warning: '#f59e0b',
			info: '#3b82f6',
		},
		fonts: {
			sans: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
			mono: 'JetBrains Mono, SF Mono, Consolas, monospace',
		},
	},

	// Theme 1: Midnight Corporate - Professional navy blues
	'midnight-corporate': {
		id: 'midnight-corporate',
		name: 'Midnight Corporate',
		description: 'Professional navy blues with silver accents - enterprise feel',
		colors: {
			surface0: '#0a0e14',
			surface1: '#0d1117',
			surface2: '#161b22',
			surface3: '#1c2128',
			surface4: '#262c36',
			border: '#30363d',
			borderSubtle: '#21262d',
			textPrimary: '#e6edf3',
			textSecondary: '#8b949e',
			textTertiary: '#6e7681',
			textInverse: '#0a0e14',
			accent: '#58a6ff',
			accentHover: '#79b8ff',
			success: '#3fb950',
			error: '#f85149',
			warning: '#d29922',
			info: '#58a6ff',
		},
		fonts: {
			sans: 'SF Pro Display, -apple-system, BlinkMacSystemFont, sans-serif',
			mono: 'SF Mono, Menlo, Consolas, monospace',
		},
	},

	// Theme 2: Warm Ember - Cozy warm tones
	'warm-ember': {
		id: 'warm-ember',
		name: 'Warm Ember',
		description: 'Deep charcoal with warm amber/orange accents - inviting and cozy',
		colors: {
			surface0: '#1a1614',
			surface1: '#211c19',
			surface2: '#2a2420',
			surface3: '#352d28',
			surface4: '#3f3631',
			border: '#4a403a',
			borderSubtle: '#382f2a',
			textPrimary: '#f5ebe0',
			textSecondary: '#c4b5a5',
			textTertiary: '#8c7e70',
			textInverse: '#1a1614',
			accent: '#e07a3d',
			accentHover: '#f09052',
			success: '#7cb342',
			error: '#e53935',
			warning: '#ffa726',
			info: '#42a5f5',
		},
		fonts: {
			sans: 'DM Sans, Nunito, -apple-system, sans-serif',
			mono: 'Fira Code, JetBrains Mono, monospace',
		},
	},

	// Theme 3: Neon Pulse - Cyberpunk vibes
	'neon-pulse': {
		id: 'neon-pulse',
		name: 'Neon Pulse',
		description: 'True black with vibrant magenta/cyan neon - high energy cyberpunk',
		colors: {
			surface0: '#000000',
			surface1: '#0a0a0a',
			surface2: '#141414',
			surface3: '#1f1f1f',
			surface4: '#2a2a2a',
			border: '#333333',
			borderSubtle: '#1a1a1a',
			textPrimary: '#ffffff',
			textSecondary: '#b0b0b0',
			textTertiary: '#707070',
			textInverse: '#000000',
			accent: '#ff0080',
			accentHover: '#ff40a0',
			success: '#00ff88',
			error: '#ff3366',
			warning: '#ffcc00',
			info: '#00ccff',
		},
		fonts: {
			sans: 'Space Grotesk, Outfit, -apple-system, sans-serif',
			mono: 'Space Mono, IBM Plex Mono, monospace',
		},
	},

	// Theme 4: Arctic Frost - Clean and minimal
	'arctic-frost': {
		id: 'arctic-frost',
		name: 'Arctic Frost',
		description: 'Cool grays with icy blue accents - clean and minimal',
		colors: {
			surface0: '#f8fafc',
			surface1: '#f1f5f9',
			surface2: '#e2e8f0',
			surface3: '#cbd5e1',
			surface4: '#94a3b8',
			border: '#cbd5e1',
			borderSubtle: '#e2e8f0',
			textPrimary: '#0f172a',
			textSecondary: '#475569',
			textTertiary: '#94a3b8',
			textInverse: '#f8fafc',
			accent: '#0284c7',
			accentHover: '#0369a1',
			success: '#059669',
			error: '#dc2626',
			warning: '#d97706',
			info: '#2563eb',
		},
		fonts: {
			sans: 'Inter, system-ui, -apple-system, sans-serif',
			mono: 'JetBrains Mono, Menlo, monospace',
		},
	},

	// Theme 5: Sage Studio - Calm developer green
	'sage-studio': {
		id: 'sage-studio',
		name: 'Sage Studio',
		description: 'Soft greens with earthy tones - calm and focused',
		colors: {
			surface0: '#1a1d1a',
			surface1: '#1f231f',
			surface2: '#262b26',
			surface3: '#2e352e',
			surface4: '#374037',
			border: '#3d463d',
			borderSubtle: '#2a302a',
			textPrimary: '#e8ede8',
			textSecondary: '#a3b3a3',
			textTertiary: '#6b7c6b',
			textInverse: '#1a1d1a',
			accent: '#6b9f6b',
			accentHover: '#7fb87f',
			success: '#4ade80',
			error: '#f87171',
			warning: '#fbbf24',
			info: '#60a5fa',
		},
		fonts: {
			sans: 'Source Sans 3, Rubik, -apple-system, sans-serif',
			mono: 'Source Code Pro, Fira Code, monospace',
		},
	},
}

export const themeIds = Object.keys(themes) as Array<keyof typeof themes>

export function applyTheme(themeId: string) {
	const theme = themes[themeId]
	if (!theme) return

	const root = document.documentElement

	// Apply colors as CSS variables
	root.style.setProperty('--color-surface-0', theme.colors.surface0)
	root.style.setProperty('--color-surface-1', theme.colors.surface1)
	root.style.setProperty('--color-surface-2', theme.colors.surface2)
	root.style.setProperty('--color-surface-3', theme.colors.surface3)
	root.style.setProperty('--color-surface-4', theme.colors.surface4)
	root.style.setProperty('--color-border', theme.colors.border)
	root.style.setProperty('--color-border-subtle', theme.colors.borderSubtle)
	root.style.setProperty('--color-text-primary', theme.colors.textPrimary)
	root.style.setProperty('--color-text-secondary', theme.colors.textSecondary)
	root.style.setProperty('--color-text-tertiary', theme.colors.textTertiary)
	root.style.setProperty('--color-text-inverse', theme.colors.textInverse)
	root.style.setProperty('--color-accent', theme.colors.accent)
	root.style.setProperty('--color-accent-hover', theme.colors.accentHover)
	root.style.setProperty('--color-success', theme.colors.success)
	root.style.setProperty('--color-error', theme.colors.error)
	root.style.setProperty('--color-warning', theme.colors.warning)
	root.style.setProperty('--color-info', theme.colors.info)

	// Apply fonts
	root.style.setProperty('--font-sans', theme.fonts.sans)
	root.style.setProperty('--font-mono', theme.fonts.mono)

	// Store preference
	localStorage.setItem('ambient-theme', themeId)
}

export function getStoredTheme(): string {
	return localStorage.getItem('ambient-theme') || 'teal-tech'
}
