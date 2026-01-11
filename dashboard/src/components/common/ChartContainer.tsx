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
	compact?: boolean
}

/**
 * Chart container following TE design principles:
 * - Borders as primary hierarchy tool
 * - No shadows or decorative elements
 * - Clear, readable labels
 * - Compact mode for dashboard grid layouts
 */
export default function ChartContainer({
	title,
	subtitle,
	isLoading = false,
	isEmpty = false,
	emptyMessage = 'No data',
	loadingMessage = 'Loading...',
	width,
	height,
	children,
	actions,
	compact = false,
}: Props) {
	return (
		<div className="bg-bg-secondary border border-border h-full flex flex-col">
			{/* Header */}
			<div className={clsx(
				'flex justify-between items-center border-b border-border',
				compact ? 'px-2 py-1.5' : 'px-4 py-3'
			)}>
				<div className={clsx('flex items-center', compact ? 'gap-2' : 'gap-4')}>
					<span className={clsx(
						'font-medium text-ink-primary',
						compact ? 'text-label' : 'text-small'
					)}>{title}</span>
					{subtitle && !compact && (
						<span className="text-label text-ink-muted">{subtitle}</span>
					)}
				</div>
				{actions && (
					<div className="flex items-center gap-2">
						{actions}
					</div>
				)}
			</div>

			{/* Content */}
			<div
				className={clsx('flex-1', compact ? 'p-1' : 'p-4')}
				style={width && height ? { minHeight: height } : undefined}
			>
				{isLoading ? (
					<div
						className="flex flex-col items-center justify-center text-ink-muted h-full"
						style={width && height ? { width, height } : { minHeight: compact ? 100 : 200 }}
					>
						<span className={compact ? 'text-label' : 'text-small'}>{loadingMessage}</span>
					</div>
				) : isEmpty ? (
					<div
						className="flex flex-col items-center justify-center text-ink-muted h-full"
						style={width && height ? { width, height } : { minHeight: compact ? 100 : 200 }}
					>
						<span className={compact ? 'text-label' : 'text-small'}>{emptyMessage}</span>
					</div>
				) : (
					children
				)}
			</div>
		</div>
	)
}
