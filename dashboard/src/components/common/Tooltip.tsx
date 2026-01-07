import { ReactNode, useState } from 'react'
import clsx from 'clsx'

interface Props {
	content: ReactNode
	shortcut?: string
	children: ReactNode
	position?: 'top' | 'bottom' | 'left' | 'right'
	delay?: number
}

export default function Tooltip({
	content,
	shortcut,
	children,
	position = 'top',
	delay = 300,
}: Props) {
	const [visible, setVisible] = useState(false)
	const [timeoutId, setTimeoutId] = useState<ReturnType<typeof setTimeout> | null>(null)

	const showTooltip = () => {
		const id = setTimeout(() => setVisible(true), delay)
		setTimeoutId(id)
	}

	const hideTooltip = () => {
		if (timeoutId) {
			clearTimeout(timeoutId)
			setTimeoutId(null)
		}
		setVisible(false)
	}

	const positionClasses = {
		top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
		bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
		left: 'right-full top-1/2 -translate-y-1/2 mr-2',
		right: 'left-full top-1/2 -translate-y-1/2 ml-2',
	}

	const arrowClasses = {
		top: 'top-full left-1/2 -translate-x-1/2 border-t-surface-4 border-x-transparent border-b-transparent',
		bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-surface-4 border-x-transparent border-t-transparent',
		left: 'left-full top-1/2 -translate-y-1/2 border-l-surface-4 border-y-transparent border-r-transparent',
		right: 'right-full top-1/2 -translate-y-1/2 border-r-surface-4 border-y-transparent border-l-transparent',
	}

	return (
		<div
			className="relative inline-flex"
			onMouseEnter={showTooltip}
			onMouseLeave={hideTooltip}
			onFocus={showTooltip}
			onBlur={hideTooltip}
		>
			{children}
			{visible && (
				<div
					className={clsx(
						'absolute z-50 px-2 py-1.5 text-xs bg-surface-4 text-text-primary rounded shadow-lg whitespace-nowrap',
						'pointer-events-none',
						positionClasses[position]
					)}
					role="tooltip"
				>
					<span>{content}</span>
					{shortcut && (
						<span className="ml-2 px-1 py-0.5 bg-surface-3 rounded text-text-tertiary font-mono text-micro">
							{shortcut}
						</span>
					)}
					<div
						className={clsx(
							'absolute w-0 h-0 border-4',
							arrowClasses[position]
						)}
					/>
				</div>
			)}
		</div>
	)
}
