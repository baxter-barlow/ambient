import { useEffect, useState } from 'react'
import { getShortcutsList } from '../../hooks/useKeyboardShortcuts'

export default function ShortcutsHelp() {
	const [visible, setVisible] = useState(false)
	const shortcuts = getShortcutsList()

	useEffect(() => {
		const handleShowHelp = () => setVisible(true)
		window.addEventListener('show-shortcuts-help', handleShowHelp)
		return () => window.removeEventListener('show-shortcuts-help', handleShowHelp)
	}, [])

	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.key === 'Escape' && visible) {
				setVisible(false)
			}
		}
		window.addEventListener('keydown', handleKeyDown)
		return () => window.removeEventListener('keydown', handleKeyDown)
	}, [visible])

	if (!visible) return null

	return (
		<div
			className="fixed inset-0 z-50 flex items-center justify-center bg-surface-0/80"
			onClick={() => setVisible(false)}
		>
			<div
				className="bg-surface-2 border border-border rounded-card p-6 max-w-md w-full mx-4 shadow-xl"
				onClick={e => e.stopPropagation()}
			>
				<div className="flex items-center justify-between mb-4">
					<h2 className="text-lg text-text-primary font-medium">Keyboard Shortcuts</h2>
					<button
						onClick={() => setVisible(false)}
						className="text-text-tertiary hover:text-text-primary transition-colors"
						aria-label="Close"
					>
						<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2">
							<path d="M5 5l10 10M15 5l-10 10" />
						</svg>
					</button>
				</div>

				<div className="space-y-2">
					{shortcuts.map(({ key, description }) => (
						<div
							key={key}
							className="flex items-center justify-between py-2 border-b border-border last:border-0"
						>
							<span className="text-sm text-text-secondary">{description}</span>
							<kbd className="px-2 py-1 bg-surface-3 rounded text-xs font-mono text-text-primary">
								{key}
							</kbd>
						</div>
					))}
				</div>

				<p className="mt-4 text-xs text-text-tertiary">
					Press <kbd className="px-1 py-0.5 bg-surface-3 rounded font-mono">Esc</kbd> to close
				</p>
			</div>
		</div>
	)
}
