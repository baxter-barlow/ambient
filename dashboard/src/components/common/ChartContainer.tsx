import { ReactNode } from 'react'
import clsx from 'clsx'

interface Props {
	title: string
	subtitle?: ReactNode
	isLoading?: boolean
	isEmpty?: boolean
	emptyMessage?: string
	loadingMessage?: string
	width?: number
	height?: number
	children: ReactNode
	actions?: ReactNode
}

export default function ChartContainer({
	title,
	subtitle,
	isLoading = false,
	isEmpty = false,
	emptyMessage = 'No data available',
	loadingMessage = 'Loading...',
	width,
	height,
	children,
	actions,
}: Props) {
	return (
		<div className="bg-surface-2 border border-border rounded-card overflow-hidden">
			<div className="flex justify-between items-center px-4 py-3 border-b border-border">
				<span className="text-base text-text-primary font-medium">{title}</span>
				<div className="flex items-center gap-4">
					{subtitle && (
						<span className="text-micro font-mono text-text-tertiary">{subtitle}</span>
					)}
					{actions}
				</div>
			</div>
			<div className="p-4 relative" style={width && height ? { minHeight: height } : undefined}>
				{isLoading ? (
					<div
						className={clsx(
							'flex flex-col items-center justify-center text-text-tertiary',
							width && height && 'absolute inset-4'
						)}
						style={width && height ? { width, height } : { minHeight: 200 }}
					>
						<LoadingSpinner />
						<span className="mt-3 text-sm">{loadingMessage}</span>
					</div>
				) : isEmpty ? (
					<div
						className={clsx(
							'flex flex-col items-center justify-center text-text-tertiary',
							width && height && 'absolute inset-4'
						)}
						style={width && height ? { width, height } : { minHeight: 200 }}
					>
						<EmptyIcon />
						<span className="mt-3 text-sm">{emptyMessage}</span>
					</div>
				) : (
					children
				)}
			</div>
		</div>
	)
}

function LoadingSpinner() {
	return (
		<svg
			className="animate-spin"
			width="24"
			height="24"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			strokeWidth="2"
		>
			<circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
			<path
				d="M12 2a10 10 0 0 1 10 10"
				strokeLinecap="round"
			/>
		</svg>
	)
}

function EmptyIcon() {
	return (
		<svg
			width="32"
			height="32"
			viewBox="0 0 32 32"
			fill="none"
			stroke="currentColor"
			strokeWidth="1.5"
		>
			<rect x="4" y="8" width="24" height="16" rx="2" strokeOpacity="0.5" />
			<path d="M4 20l6-4 4 3 8-6 6 5" strokeOpacity="0.5" />
			<circle cx="22" cy="13" r="2" strokeOpacity="0.5" />
		</svg>
	)
}
