import { useEffect, useState } from 'react'
import clsx from 'clsx'

interface ToastMessage {
	id: string
	message: string
	variant: 'success' | 'error' | 'warning' | 'info'
}

// Global toast state
let toastListeners: ((toasts: ToastMessage[]) => void)[] = []
let toasts: ToastMessage[] = []

function updateListeners() {
	toastListeners.forEach(listener => listener([...toasts]))
}

export function showToast(message: string, variant: ToastMessage['variant'] = 'info') {
	const id = Math.random().toString(36).slice(2)
	toasts = [...toasts, { id, message, variant }]
	updateListeners()

	// Auto-dismiss after 4 seconds
	setTimeout(() => {
		toasts = toasts.filter(t => t.id !== id)
		updateListeners()
	}, 4000)
}

/**
 * Toast container following TE design principles:
 * - No rounded corners, no shadows
 * - Clear accent colors as signals
 * - Minimal, functional design
 */
export function ToastContainer() {
	const [currentToasts, setCurrentToasts] = useState<ToastMessage[]>([])

	useEffect(() => {
		toastListeners.push(setCurrentToasts)
		return () => {
			toastListeners = toastListeners.filter(l => l !== setCurrentToasts)
		}
	}, [])

	if (currentToasts.length === 0) return null

	const variantStyles = {
		success: 'border-accent-green bg-bg-secondary',
		error: 'border-accent-red bg-bg-secondary',
		warning: 'border-accent-orange bg-bg-secondary',
		info: 'border-ink-primary bg-bg-secondary',
	}

	const accentColors = {
		success: 'bg-accent-green',
		error: 'bg-accent-red',
		warning: 'bg-accent-orange',
		info: 'bg-ink-primary',
	}

	return (
		<div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2">
			{currentToasts.map(toast => (
				<div
					key={toast.id}
					className={clsx(
						'flex items-center gap-3 px-4 py-3 border',
						'animate-slide-in-right',
						variantStyles[toast.variant]
					)}
					role="alert"
				>
					{/* Color indicator bar */}
					<div className={clsx('w-1 h-4', accentColors[toast.variant])} />
					<span className="text-small text-ink-primary">{toast.message}</span>
				</div>
			))}
		</div>
	)
}
