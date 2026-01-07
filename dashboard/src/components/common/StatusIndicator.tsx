import clsx from 'clsx'

interface Props {
	status: 'success' | 'warning' | 'error' | 'neutral' | 'info'
	label?: string
	pulse?: boolean
	size?: 'sm' | 'md'
}

export default function StatusIndicator({ status, label, pulse, size = 'md' }: Props) {
	return (
		<div className="flex items-center gap-2">
			<span className={clsx(
				'rounded-full',
				{
					'w-2 h-2': size === 'sm',
					'w-3 h-3': size === 'md',
				},
				{
					'bg-accent-green shadow-[0_0_8px_rgba(34,197,94,0.4)]': status === 'success',
					'bg-accent-amber shadow-[0_0_8px_rgba(245,158,11,0.4)]': status === 'warning',
					'bg-accent-red shadow-[0_0_8px_rgba(239,68,68,0.4)]': status === 'error',
					'bg-text-tertiary': status === 'neutral',
					'bg-accent-blue shadow-[0_0_8px_rgba(59,130,246,0.4)]': status === 'info',
				},
				pulse && 'animate-pulse'
			)} />
			{label && (
				<span className={clsx(
					'text-text-secondary',
					size === 'sm' ? 'text-xs' : 'text-sm'
				)}>
					{label}
				</span>
			)}
		</div>
	)
}
