import { useState, useEffect, ReactNode, memo } from 'react'
import clsx from 'clsx'

interface Tab {
	id: string
	label: string
	shortcut?: string
	content: ReactNode
}

interface Props {
	tabs: Tab[]
	defaultTab?: string
	defaultExpanded?: boolean
	onExpandedChange?: (expanded: boolean) => void
}

/**
 * Collapsible tabbed panel following TE design principles.
 * Minimal height when collapsed, expandable for secondary tools.
 */
export default memo(function CollapsiblePanel({
	tabs,
	defaultTab,
	defaultExpanded = false,
	onExpandedChange,
}: Props) {
	const [expanded, setExpanded] = useState(defaultExpanded)
	const [activeTab, setActiveTab] = useState(defaultTab || tabs[0]?.id || '')

	// Notify parent of expansion changes
	useEffect(() => {
		onExpandedChange?.(expanded)
	}, [expanded, onExpandedChange])

	// Keyboard shortcuts
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			// Don't trigger if user is typing in an input
			if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
				return
			}

			// Find tab by shortcut
			for (const tab of tabs) {
				if (tab.shortcut && e.key.toLowerCase() === tab.shortcut.toLowerCase() && !e.ctrlKey && !e.metaKey && !e.altKey) {
					e.preventDefault()
					if (expanded && activeTab === tab.id) {
						// Collapse if clicking the same tab
						setExpanded(false)
					} else {
						setActiveTab(tab.id)
						setExpanded(true)
					}
					return
				}
			}

			// Escape to collapse
			if (e.key === 'Escape' && expanded) {
				e.preventDefault()
				setExpanded(false)
			}
		}

		window.addEventListener('keydown', handleKeyDown)
		return () => window.removeEventListener('keydown', handleKeyDown)
	}, [tabs, expanded, activeTab])

	const activeContent = tabs.find(t => t.id === activeTab)?.content

	return (
		<div className="bg-bg-secondary border-t border-border flex flex-col">
			{/* Tab bar */}
			<div className="flex items-center border-b border-border">
				{/* Expand/collapse toggle */}
				<button
					onClick={() => setExpanded(prev => !prev)}
					className="px-3 py-2 text-ink-muted hover:text-ink-primary transition-all duration-fast"
					aria-label={expanded ? 'Collapse panel' : 'Expand panel'}
					title={expanded ? 'Collapse (Esc)' : 'Expand'}
				>
					<svg
						className={clsx('w-4 h-4 transition-transform duration-fast', expanded ? 'rotate-180' : '')}
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						strokeWidth={2}
					>
						<path strokeLinecap="square" strokeLinejoin="miter" d="M5 15l7-7 7 7" />
					</svg>
				</button>

				{/* Tabs */}
				<div className="flex-1 flex items-center">
					{tabs.map((tab) => (
						<button
							key={tab.id}
							onClick={() => {
								setActiveTab(tab.id)
								if (!expanded) setExpanded(true)
							}}
							className={clsx(
								'px-4 py-2 text-label uppercase font-mono transition-all duration-fast border-r border-border',
								activeTab === tab.id && expanded
									? 'bg-ink-primary text-bg-primary'
									: 'text-ink-secondary hover:text-ink-primary hover:bg-bg-tertiary'
							)}
						>
							{tab.label}
							{tab.shortcut && (
								<span className={clsx(
									'ml-2 text-[10px] px-1 border',
									activeTab === tab.id && expanded
										? 'border-bg-secondary text-bg-secondary'
										: 'border-ink-muted text-ink-muted'
								)}>
									{tab.shortcut.toUpperCase()}
								</span>
							)}
						</button>
					))}
				</div>
			</div>

			{/* Content area */}
			{expanded && (
				<div className="h-48 overflow-auto">
					{activeContent}
				</div>
			)}
		</div>
	)
})
