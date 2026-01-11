import { useState, useEffect } from 'react'
import { themes, themeIds, applyTheme, getStoredTheme, Theme } from '../themes'
import clsx from 'clsx'

interface Props {
	isOpen: boolean
	onClose: () => void
}

function ThemePreview({ theme, isActive, onClick }: { theme: Theme; isActive: boolean; onClick: () => void }) {
	return (
		<button
			onClick={onClick}
			className={clsx(
				'w-full text-left p-4 rounded-lg border-2 transition-all duration-200',
				isActive
					? 'border-[var(--color-accent)] bg-[var(--color-surface-3)]'
					: 'border-transparent bg-[var(--color-surface-2)] hover:bg-[var(--color-surface-3)] hover:border-[var(--color-border)]'
			)}
		>
			{/* Theme color preview */}
			<div className="flex gap-1.5 mb-3">
				{/* Surface colors */}
				<div
					className="w-6 h-6 rounded"
					style={{ backgroundColor: theme.colors.surface0 }}
					title="Surface 0"
				/>
				<div
					className="w-6 h-6 rounded"
					style={{ backgroundColor: theme.colors.surface2 }}
					title="Surface 2"
				/>
				<div
					className="w-6 h-6 rounded"
					style={{ backgroundColor: theme.colors.surface4 }}
					title="Surface 4"
				/>
				<div className="w-px bg-[var(--color-border)] mx-1" />
				{/* Accent colors */}
				<div
					className="w-6 h-6 rounded"
					style={{ backgroundColor: theme.colors.accent }}
					title="Accent"
				/>
				<div
					className="w-6 h-6 rounded"
					style={{ backgroundColor: theme.colors.success }}
					title="Success"
				/>
				<div
					className="w-6 h-6 rounded"
					style={{ backgroundColor: theme.colors.error }}
					title="Error"
				/>
				<div
					className="w-6 h-6 rounded"
					style={{ backgroundColor: theme.colors.warning }}
					title="Warning"
				/>
			</div>

			{/* Theme info */}
			<div className="flex items-center gap-2 mb-1">
				<span className="font-semibold text-[var(--color-text-primary)]">{theme.name}</span>
				{isActive && (
					<span className="px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide rounded bg-[var(--color-accent)] text-[var(--color-text-inverse)]">
						Active
					</span>
				)}
			</div>
			<p className="text-xs text-[var(--color-text-tertiary)]">{theme.description}</p>

			{/* Font preview */}
			<div className="mt-3 pt-3 border-t border-[var(--color-border-subtle)]">
				<div className="flex items-center gap-4 text-xs text-[var(--color-text-secondary)]">
					<span style={{ fontFamily: theme.fonts.sans }}>Sans: Aa</span>
					<span style={{ fontFamily: theme.fonts.mono }}>Mono: 0x</span>
				</div>
			</div>
		</button>
	)
}

export default function ThemeSwitcher({ isOpen, onClose }: Props) {
	const [activeTheme, setActiveTheme] = useState(getStoredTheme())

	useEffect(() => {
		if (isOpen) {
			// Prevent body scroll when modal is open
			document.body.style.overflow = 'hidden'
		}
		return () => {
			document.body.style.overflow = ''
		}
	}, [isOpen])

	// Handle escape key
	useEffect(() => {
		const handleEscape = (e: KeyboardEvent) => {
			if (e.key === 'Escape' && isOpen) {
				onClose()
			}
		}
		window.addEventListener('keydown', handleEscape)
		return () => window.removeEventListener('keydown', handleEscape)
	}, [isOpen, onClose])

	const handleThemeSelect = (themeId: string) => {
		applyTheme(themeId)
		setActiveTheme(themeId)
	}

	if (!isOpen) return null

	return (
		<div className="fixed inset-0 z-50 flex items-center justify-center">
			{/* Backdrop */}
			<div
				className="absolute inset-0 bg-black/60 backdrop-blur-sm"
				onClick={onClose}
			/>

			{/* Modal */}
			<div className="relative w-full max-w-3xl max-h-[85vh] bg-[var(--color-surface-1)] border border-[var(--color-border)] rounded-xl shadow-2xl overflow-hidden">
				{/* Header */}
				<div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border)]">
					<div>
						<h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Theme Switcher</h2>
						<p className="text-sm text-[var(--color-text-tertiary)]">Choose a theme for your dashboard</p>
					</div>
					<button
						onClick={onClose}
						className="w-8 h-8 flex items-center justify-center rounded-md text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-surface-3)] transition-colors"
						aria-label="Close"
					>
						<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2">
							<path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
						</svg>
					</button>
				</div>

				{/* Theme grid */}
				<div className="p-6 overflow-y-auto max-h-[calc(85vh-80px)]">
					<div className="grid grid-cols-2 gap-4">
						{themeIds.map((themeId) => (
							<ThemePreview
								key={themeId}
								theme={themes[themeId]}
								isActive={activeTheme === themeId}
								onClick={() => handleThemeSelect(themeId)}
							/>
						))}
					</div>

					{/* Current theme details */}
					<div className="mt-6 p-4 bg-[var(--color-surface-2)] rounded-lg border border-[var(--color-border)]">
						<h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-3">
							Current: {themes[activeTheme]?.name}
						</h3>
						<div className="grid grid-cols-4 gap-3 text-xs">
							<div>
								<span className="text-[var(--color-text-tertiary)] block mb-1">Accent</span>
								<div className="flex items-center gap-2">
									<div
										className="w-4 h-4 rounded"
										style={{ backgroundColor: themes[activeTheme]?.colors.accent }}
									/>
									<code className="text-[var(--color-text-secondary)] font-mono">
										{themes[activeTheme]?.colors.accent}
									</code>
								</div>
							</div>
							<div>
								<span className="text-[var(--color-text-tertiary)] block mb-1">Success</span>
								<div className="flex items-center gap-2">
									<div
										className="w-4 h-4 rounded"
										style={{ backgroundColor: themes[activeTheme]?.colors.success }}
									/>
									<code className="text-[var(--color-text-secondary)] font-mono">
										{themes[activeTheme]?.colors.success}
									</code>
								</div>
							</div>
							<div>
								<span className="text-[var(--color-text-tertiary)] block mb-1">Error</span>
								<div className="flex items-center gap-2">
									<div
										className="w-4 h-4 rounded"
										style={{ backgroundColor: themes[activeTheme]?.colors.error }}
									/>
									<code className="text-[var(--color-text-secondary)] font-mono">
										{themes[activeTheme]?.colors.error}
									</code>
								</div>
							</div>
							<div>
								<span className="text-[var(--color-text-tertiary)] block mb-1">Warning</span>
								<div className="flex items-center gap-2">
									<div
										className="w-4 h-4 rounded"
										style={{ backgroundColor: themes[activeTheme]?.colors.warning }}
									/>
									<code className="text-[var(--color-text-secondary)] font-mono">
										{themes[activeTheme]?.colors.warning}
									</code>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	)
}
