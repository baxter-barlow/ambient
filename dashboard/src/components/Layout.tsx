import { ReactNode, useState, useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import { useAppStore } from '../stores/appStore'
import clsx from 'clsx'

interface Props {
	children: ReactNode
}

const pageTitles: Record<string, string> = {
	'/device': 'Device',
	'/signals': 'Signals',
	'/config': 'Config',
	'/recordings': 'Record',
	'/tests': 'Test',
	'/tuning': 'Tune',
	'/logs': 'Log',
}

export default function Layout({ children }: Props) {
	const location = useLocation()
	const isPaused = useAppStore(s => s.isPaused)
	const togglePause = useAppStore(s => s.togglePause)
	const deviceStatus = useAppStore(s => s.deviceStatus)
	const wsConnected = useAppStore(s => s.wsConnected)
	const sensorFrames = useAppStore(s => s.sensorFrames)
	const [uptime, setUptime] = useState(0)

	useEffect(() => {
		const interval = setInterval(() => setUptime(u => u + 1), 1000)
		return () => clearInterval(interval)
	}, [])

	const formatUptime = (seconds: number) => {
		const h = Math.floor(seconds / 3600)
		const m = Math.floor((seconds % 3600) / 60)
		const s = seconds % 60
		return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
	}

	const currentPage = pageTitles[location.pathname] || 'Dashboard'

	return (
		<div className="flex h-screen bg-bg-primary">
			<Sidebar />

			<div className="flex-1 flex flex-col overflow-hidden">
				{/* Header - minimal, instrument-like */}
				<header className="h-12 bg-bg-secondary border-b border-border flex items-center justify-between px-6">
					{/* Left: Page title */}
					<div className="flex items-center gap-4">
						<h1 className="text-h3 text-ink-primary">{currentPage}</h1>
						{deviceStatus?.config_name && deviceStatus.config_name !== 'default' && (
							<span className="text-label text-ink-muted">
								{deviceStatus.config_name}
							</span>
						)}
					</div>

					{/* Right: Status indicators */}
					<div className="flex items-center gap-6">
						{/* Streaming control */}
						{deviceStatus?.state === 'streaming' && (
							<button
								onClick={togglePause}
								className={clsx(
									'flex items-center gap-2 px-3 py-1 border transition-all duration-fast ease-out',
									isPaused
										? 'border-accent-orange bg-accent-orange text-ink-primary'
										: 'border-border-strong bg-transparent text-ink-primary hover:bg-bg-tertiary'
								)}
							>
								<span className="text-label">{isPaused ? 'PAUSED' : 'LIVE'}</span>
							</button>
						)}

						{/* Connection status */}
						<div className="flex items-center gap-2">
							<div className={clsx(
								'w-2 h-2',
								wsConnected ? 'bg-accent-green' : 'bg-accent-red'
							)} />
							<span className="text-label text-ink-muted">
								{wsConnected ? 'CONNECTED' : 'OFFLINE'}
							</span>
						</div>

						{/* Device state */}
						{deviceStatus && (
							<div className={clsx(
								'px-2 py-1 border text-label',
								{
									'border-border text-ink-muted': deviceStatus.state === 'disconnected',
									'border-accent-orange text-accent-orange': deviceStatus.state === 'connecting' || deviceStatus.state === 'configuring',
									'border-accent-green text-accent-green': deviceStatus.state === 'streaming',
									'border-accent-red text-accent-red': deviceStatus.state === 'error',
								}
							)}>
								{deviceStatus.state.toUpperCase()}
								{deviceStatus.state === 'streaming' && (
									<span className="ml-2 font-mono">{deviceStatus.frame_rate.toFixed(1)}Hz</span>
								)}
							</div>
						)}

						{/* Help */}
						<button
							onClick={() => window.dispatchEvent(new CustomEvent('show-shortcuts-help'))}
							className="w-8 h-8 flex items-center justify-center text-ink-muted hover:text-ink-primary hover:bg-bg-tertiary transition-all duration-fast ease-out"
							aria-label="Keyboard shortcuts"
						>
							<span className="text-body">?</span>
						</button>
					</div>
				</header>

				{/* Main content */}
				<main className="flex-1 overflow-auto p-6">
					{children}
				</main>

				{/* Footer - data readout style */}
				<footer className="h-8 bg-bg-secondary border-t border-border px-6 flex items-center justify-between font-mono text-small text-ink-muted">
					<div className="flex items-center gap-8">
						<span>FRM {deviceStatus?.frame_count?.toLocaleString() ?? '0'}</span>
						<span>HZ {deviceStatus?.frame_rate?.toFixed(1) ?? '0.0'}</span>
						<span className={deviceStatus?.dropped_frames ? 'text-accent-orange' : ''}>
							DROP {deviceStatus?.dropped_frames ?? 0}
						</span>
						<span>BUF {sensorFrames.length}/200</span>
					</div>

					<div className="flex items-center gap-8">
						<span>CLI {deviceStatus?.cli_port?.split('/').pop() ?? '—'}</span>
						<span>DATA {deviceStatus?.data_port?.split('/').pop() ?? '—'}</span>
						<span>UP {formatUptime(uptime)}</span>
					</div>
				</footer>
			</div>
		</div>
	)
}
