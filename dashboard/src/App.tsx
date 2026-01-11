import { useState, useEffect } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import DeviceStatus from './pages/DeviceStatus'
import SignalViewer from './pages/SignalViewer'
import ConfigManager from './pages/ConfigManager'
import Recordings from './pages/Recordings'
import TestRunner from './pages/TestRunner'
import AlgorithmTuning from './pages/AlgorithmTuning'
import Logs from './pages/Logs'
import ShortcutsHelp from './components/common/ShortcutsHelp'
import { ToastContainer } from './components/common/Toast'
import ThemeSwitcher from './components/ThemeSwitcher'
import { useSensorWebSocket } from './hooks/useWebSocket'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'
import { applyTheme, getStoredTheme } from './themes'

export default function App() {
	const [themeSwitcherOpen, setThemeSwitcherOpen] = useState(false)
	const location = useLocation()

	// Dashboard is full-screen, other pages use Layout
	const isDashboard = location.pathname === '/'

	// Apply stored theme on mount
	useEffect(() => {
		applyTheme(getStoredTheme())
	}, [])

	// Listen for theme switcher event
	useEffect(() => {
		const handler = () => setThemeSwitcherOpen(true)
		window.addEventListener('show-theme-switcher', handler)
		return () => window.removeEventListener('show-theme-switcher', handler)
	}, [])

	// Connect to sensor WebSocket globally
	useSensorWebSocket()

	// Enable keyboard shortcuts
	useKeyboardShortcuts()

	// Dashboard has its own layout
	if (isDashboard) {
		return (
			<>
				<ShortcutsHelp />
				<ToastContainer />
				<ThemeSwitcher isOpen={themeSwitcherOpen} onClose={() => setThemeSwitcherOpen(false)} />
				<Dashboard />
			</>
		)
	}

	return (
		<Layout>
			<ShortcutsHelp />
			<ToastContainer />
			<ThemeSwitcher isOpen={themeSwitcherOpen} onClose={() => setThemeSwitcherOpen(false)} />
			<Routes>
				<Route path="/device" element={<DeviceStatus />} />
				<Route path="/signals" element={<SignalViewer />} />
				<Route path="/config" element={<ConfigManager />} />
				<Route path="/recordings" element={<Recordings />} />
				<Route path="/tests" element={<TestRunner />} />
				<Route path="/tuning" element={<AlgorithmTuning />} />
				<Route path="/logs" element={<Logs />} />
			</Routes>
		</Layout>
	)
}
