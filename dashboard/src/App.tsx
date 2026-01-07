import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import DeviceStatus from './pages/DeviceStatus'
import SignalViewer from './pages/SignalViewer'
import ConfigManager from './pages/ConfigManager'
import Recordings from './pages/Recordings'
import TestRunner from './pages/TestRunner'
import AlgorithmTuning from './pages/AlgorithmTuning'
import Logs from './pages/Logs'
import ShortcutsHelp from './components/common/ShortcutsHelp'
import { ToastContainer } from './components/common/Toast'
import { useSensorWebSocket } from './hooks/useWebSocket'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'

export default function App() {
	// Connect to sensor WebSocket globally
	useSensorWebSocket()

	// Enable keyboard shortcuts
	useKeyboardShortcuts()

	return (
		<Layout>
			<ShortcutsHelp />
			<ToastContainer />
			<Routes>
				<Route path="/" element={<DeviceStatus />} />
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
