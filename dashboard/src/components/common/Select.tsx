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
				<label className="text-sm text-gray-400">{label}</label>
			)}
			<select
				className={clsx(
					'bg-gray-700 border border-gray-600 rounded px-3 py-2 text-sm text-gray-100',
					'focus:outline-none focus:ring-2 focus:ring-radar-500 focus:border-transparent',
					className
				)}
				{...props}
			>
				{options.map(opt => (
					<option key={opt.value} value={opt.value}>
						{opt.label}
					</option>
				))}
			</select>
		</div>
	)
}
