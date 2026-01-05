import clsx from 'clsx'

interface Props {
	status: 'success' | 'warning' | 'error' | 'neutral'
	label?: string
	pulse?: boolean
}

export default function StatusIndicator({ status, label, pulse }: Props) {
	return (
		<div className="flex items-center gap-2">
			<span className={clsx(
				'w-3 h-3 rounded-full',
				{
					'bg-green-500': status === 'success',
					'bg-yellow-500': status === 'warning',
					'bg-red-500': status === 'error',
					'bg-gray-500': status === 'neutral',
				},
				pulse && 'animate-pulse'
			)} />
			{label && <span className="text-sm text-gray-300">{label}</span>}
		</div>
	)
}
