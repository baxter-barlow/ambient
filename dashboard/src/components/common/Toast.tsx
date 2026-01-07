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

export function ToastContainer() {
	const [currentToasts, setCurrentToasts] = useState<ToastMessage[]>([])

	useEffect(() => {
		toastListeners.push(setCurrentToasts)
		return () => {
			toastListeners = toastListeners.filter(l => l !== setCurrentToasts)
		}
	}, [])

	if (currentToasts.length === 0) return null

	const variantClasses = {
		success: 'bg-accent-green/95 text-white',
		error: 'bg-accent-red/95 text-white',
		warning: 'bg-accent-amber/95 text-surface-0',
		info: 'bg-surface-4/95 text-text-primary',
	}

	const icons = {
		success: (
			<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
				<path d="M4 9l3.5 3.5L14 5" strokeLinecap="round" strokeLinejoin="round" />
			</svg>
		),
		error: (
			<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
				<circle cx="9" cy="9" r="7" />
				<path d="M6 6l6 6M12 6l-6 6" strokeLinecap="round" />
			</svg>
		),
		warning: (
			<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
				<path d="M9 6v4m0 2h.01" strokeLinecap="round" />
				<path d="M9 16.5L1.5 3.5h15L9 16.5z" />
			</svg>
		),
		info: (
			<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="2">
				<circle cx="9" cy="9" r="7" />
				<path d="M9 8v5m0-8h.01" strokeLinecap="round" />
			</svg>
		),
	}

	return (
		<div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
			{currentToasts.map(toast => (
				<div
					key={toast.id}
					className={clsx(
						'flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg',
						'animate-slide-in-right',
						variantClasses[toast.variant]
					)}
					role="alert"
				>
					{icons[toast.variant]}
					<span className="text-sm font-medium">{toast.message}</span>
				</div>
			))}
		</div>
	)
}
