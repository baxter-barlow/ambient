import clsx from 'clsx'
import { ButtonHTMLAttributes, ReactNode } from 'react'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
	variant?: 'primary' | 'secondary' | 'danger'
	size?: 'sm' | 'md' | 'lg'
	children: ReactNode
}

export default function Button({
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
				'font-medium rounded transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800',
				{
					'bg-radar-600 hover:bg-radar-700 text-white focus:ring-radar-500': variant === 'primary',
					'bg-gray-600 hover:bg-gray-500 text-white focus:ring-gray-400': variant === 'secondary',
					'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500': variant === 'danger',
				},
				{
					'px-2 py-1 text-xs': size === 'sm',
					'px-4 py-2 text-sm': size === 'md',
					'px-6 py-3 text-base': size === 'lg',
				},
				disabled && 'opacity-50 cursor-not-allowed',
				className
			)}
			disabled={disabled}
			{...props}
		>
			{children}
		</button>
	)
}
