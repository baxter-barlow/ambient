import clsx from 'clsx'

interface Props {
	message: string
	title?: string
	onDismiss?: () => void
	variant?: 'error' | 'warning' | 'info'
	className?: string
}

export default function ErrorMessage({
	message,
	title,
	onDismiss,
	variant = 'error',
	className,
}: Props) {
	const variantClasses = {
		error: 'bg-accent-red/12 border-accent-red/25 text-accent-red',
		warning: 'bg-accent-amber/12 border-accent-amber/25 text-accent-amber',
		info: 'bg-accent-blue/12 border-accent-blue/25 text-accent-blue',
	}

	const iconPaths = {
		error: 'M12 9v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
		warning: 'M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z',
		info: 'M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
	}

	return (
		<div
			className={clsx(
				'p-3 border rounded flex items-start gap-3',
				variantClasses[variant],
				className
			)}
			role="alert"
		>
			<svg
				width="20"
				height="20"
				viewBox="0 0 24 24"
				fill="none"
				stroke="currentColor"
				strokeWidth="2"
				strokeLinecap="round"
				strokeLinejoin="round"
				className="flex-shrink-0 mt-0.5"
			>
				<path d={iconPaths[variant]} />
			</svg>
			<div className="flex-1 min-w-0">
				{title && (
					<p className="font-medium text-sm mb-0.5">{title}</p>
				)}
				<p className="text-sm break-words">{message}</p>
			</div>
			{onDismiss && (
				<button
					onClick={onDismiss}
					className="flex-shrink-0 p-1 rounded hover:bg-white/10 transition-colors"
					aria-label="Dismiss"
				>
					<svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2">
						<path d="M3 3l8 8M11 3l-8 8" />
					</svg>
				</button>
			)}
		</div>
	)
}
