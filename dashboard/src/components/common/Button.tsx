import clsx from 'clsx'
import { ButtonHTMLAttributes, ReactNode, memo } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
	variant?: 'primary' | 'secondary' | 'danger'
	size?: 'sm' | 'md' | 'lg'
	children: ReactNode
}

/**
 * Button component following TE design principles:
 * - No shadows
 * - No gradients
 * - Hover = color inversion or underline
 * - Instant state changes
 */
export default memo(function Button({
	variant = 'primary',
	size = 'md',
	className,
	children,
	disabled,
	...props
}: Props) {
	return (
		<button
			className={clsx(
				'font-medium transition-all duration-fast ease-out',
				// Variant styles
				{
					// Primary - inverted colors
					'bg-ink-primary text-bg-primary border border-ink-primary hover:bg-transparent hover:text-ink-primary': variant === 'primary' && !disabled,
					// Secondary - outlined
					'bg-transparent text-ink-primary border border-ink-primary hover:bg-ink-primary hover:text-bg-primary': variant === 'secondary' && !disabled,
					// Danger - red accent
					'bg-accent-red text-bg-primary border border-accent-red hover:bg-transparent hover:text-accent-red': variant === 'danger' && !disabled,
				},
				// Size styles
				{
					'px-3 py-1 text-small': size === 'sm',
					'px-4 py-2 text-body': size === 'md',
					'px-6 py-3 text-body': size === 'lg',
				},
				// Disabled state - reduced contrast, no glow
				disabled && 'bg-bg-tertiary text-ink-muted border-border cursor-not-allowed opacity-50',
				className
			)}
			disabled={disabled}
			{...props}
		>
			{children}
		</button>
	)
})
