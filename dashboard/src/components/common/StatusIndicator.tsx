import { memo } from 'react'
import clsx from 'clsx'

interface Props {
	status: 'success' | 'warning' | 'error' | 'neutral' | 'info'
	label?: string
	size?: 'sm' | 'md'
}

/**
 * Status indicator following TE design principles:
 * - Square indicators (not rounded)
 * - Clear accent colors as signals
 * - No glow or soft effects
 */
export default memo(function StatusIndicator({ status, label, size = 'md' }: Props) {
	const statusColors = {
		success: 'bg-accent-green',
		warning: 'bg-accent-orange',
		error: 'bg-accent-red',
		neutral: 'bg-ink-muted',
		info: 'bg-accent-blue',
	}

	return (
		<div className="flex items-center gap-2">
			<div className={clsx(
				statusColors[status],
				size === 'sm' ? 'w-2 h-2' : 'w-3 h-3'
			)} />
			{label && (
				<span className={clsx(
					'text-ink-secondary uppercase',
					size === 'sm' ? 'text-label' : 'text-small'
				)}>
					{label}
				</span>
			)}
		</div>
	)
})
