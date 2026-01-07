import { useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAppStore } from '../stores/appStore'

interface ShortcutHandler {
	key: string
	ctrl?: boolean
	shift?: boolean
	alt?: boolean
	description: string
	handler: () => void
}

export function useKeyboardShortcuts() {
	const navigate = useNavigate()
	const togglePause = useAppStore(s => s.togglePause)

	const shortcuts: ShortcutHandler[] = [
		// Global navigation
		{ key: '1', description: 'Go to Device Status', handler: () => navigate('/') },
		{ key: '2', description: 'Go to Signal Viewer', handler: () => navigate('/signals') },
		{ key: '3', description: 'Go to Configuration', handler: () => navigate('/config') },
		{ key: '4', description: 'Go to Recordings', handler: () => navigate('/recordings') },
		{ key: '5', description: 'Go to Test Runner', handler: () => navigate('/tests') },
		{ key: '6', description: 'Go to Algorithm Tuning', handler: () => navigate('/tuning') },
		{ key: '7', description: 'Go to Logs', handler: () => navigate('/logs') },

		// Streaming controls
		{ key: ' ', description: 'Pause/Resume streaming', handler: togglePause },

		// Help
		{ key: '?', shift: true, description: 'Show keyboard shortcuts', handler: () => {
			// Dispatch custom event for help modal
			window.dispatchEvent(new CustomEvent('show-shortcuts-help'))
		}},
	]

	const handleKeyDown = useCallback((event: KeyboardEvent) => {
		// Don't trigger shortcuts when typing in inputs
		const target = event.target as HTMLElement
		if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') {
			return
		}

		for (const shortcut of shortcuts) {
			const keyMatch = event.key === shortcut.key || event.key.toLowerCase() === shortcut.key.toLowerCase()
			const ctrlMatch = !!shortcut.ctrl === (event.ctrlKey || event.metaKey)
			const shiftMatch = !!shortcut.shift === event.shiftKey
			const altMatch = !!shortcut.alt === event.altKey

			if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
				event.preventDefault()
				shortcut.handler()
				return
			}
		}
	}, [shortcuts])

	useEffect(() => {
		window.addEventListener('keydown', handleKeyDown)
		return () => window.removeEventListener('keydown', handleKeyDown)
	}, [handleKeyDown])

	return shortcuts
}

export function getShortcutsList(): { key: string; description: string }[] {
	return [
		{ key: '1-7', description: 'Navigate to pages' },
		{ key: 'Space', description: 'Pause/Resume streaming' },
		{ key: 'Shift + ?', description: 'Show this help' },
	]
}
