import clsx from 'clsx'
import { SelectHTMLAttributes } from 'react'

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
	options: { value: string; label: string }[]
	label?: string
}

export default function Select({ options, label, className, ...props }: Props) {
	return (
		<div className="flex flex-col gap-1">
			{label && (
				<label className="text-sm text-text-secondary">{label}</label>
			)}
			<select
				className={clsx(
					'bg-surface-3 border border-border rounded px-3 py-2 text-sm text-text-primary',
					'focus:outline-none focus:ring-2 focus:ring-accent-teal focus:border-transparent',
					'hover:bg-surface-4 transition-colors duration-150',
					className
				)}
				{...props}
			>
				{options.map(opt => (
					<option key={opt.value} value={opt.value} className="bg-surface-2">
						{opt.label}
					</option>
				))}
			</select>
		</div>
	)
}
