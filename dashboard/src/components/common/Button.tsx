import clsx from 'clsx'
import { ButtonHTMLAttributes, ReactNode } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
	variant?: 'primary' | 'secondary' | 'danger' | 'toggle'
	size?: 'sm' | 'md' | 'lg'
	active?: boolean
	children: ReactNode
}

export default function Button({
	variant = 'primary',
	size = 'md',
	active = false,
	className,
	children,
	disabled,
	...props
}: Props) {
	return (
		<button
			className={clsx(
				'font-semibold rounded transition-colors duration-150',
				// Variant styles
				{
					// Primary - teal accent
					'bg-accent-teal hover:bg-accent-teal-hover text-text-inverse': variant === 'primary' && !disabled,
					// Secondary - subtle
					'bg-surface-3 hover:bg-surface-4 border border-border text-text-secondary hover:text-text-primary': variant === 'secondary',
					// Danger - red
					'bg-accent-red hover:bg-red-600 text-white': variant === 'danger' && !disabled,
					// Toggle - state-based
					'bg-accent-teal/15 border border-accent-teal text-accent-teal': variant === 'toggle' && active,
					'bg-surface-3 border border-border text-text-secondary hover:bg-surface-4': variant === 'toggle' && !active,
				},
				// Size styles
				{
					'px-3.5 py-1.5 text-xs': size === 'sm',
					'px-4 py-2 text-sm': size === 'md',
					'px-5 py-2.5 text-base': size === 'lg',
				},
				// Disabled state
				disabled && 'bg-surface-3 text-text-tertiary cursor-not-allowed border-none',
				className
			)}
			disabled={disabled}
			{...props}
		>
			{children}
		</button>
	)
}
