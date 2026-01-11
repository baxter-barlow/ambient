import clsx from 'clsx'
import { SelectHTMLAttributes } from 'react'

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
	options: { value: string; label: string }[]
	label?: string
}

/**
 * Select component following TE design principles:
 * - Minimal styling, bg-secondary
 * - 1px border, 2px radius
 * - Yellow focus ring
 */
export default function Select({ options, label, className, ...props }: Props) {
	return (
		<div className="flex flex-col gap-1">
			{label && (
				<label className="text-label text-ink-muted uppercase">{label}</label>
			)}
			<select
				className={clsx(
					'bg-bg-secondary border border-ink-muted rounded-sm px-3 py-2 text-small text-ink-primary',
					'focus:outline-none focus:border-accent-yellow',
					'hover:border-ink-secondary transition-all duration-fast ease-out',
					'appearance-none cursor-pointer',
					className
				)}
				style={{
					backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath fill='%234A4A4A' d='M3 4l3 4 3-4H3z'/%3E%3C/svg%3E")`,
					backgroundRepeat: 'no-repeat',
					backgroundPosition: 'right 12px center',
					paddingRight: '36px',
				}}
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
