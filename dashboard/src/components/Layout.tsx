import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import { useAppStore } from '../stores/appStore'
import Tooltip from './common/Tooltip'
import clsx from 'clsx'

interface Props {
	children: ReactNode
}

export default function Layout({ children }: Props) {
	const isPaused = useAppStore(s => s.isPaused)
	const togglePause = useAppStore(s => s.togglePause)
	const deviceStatus = useAppStore(s => s.deviceStatus)
	const wsConnected = useAppStore(s => s.wsConnected)
	const sensorFrames = useAppStore(s => s.sensorFrames)

	return (
		<div className="flex h-screen bg-surface-0">
			<Sidebar />
			<div className="flex-1 flex flex-col overflow-hidden">
				{/* Header */}
				<header className="h-14 bg-surface-1 border-b border-border flex items-center px-6 justify-between">
					<h1 className="text-xl text-text-primary">Ambient Dashboard</h1>
					<div className="flex items-center gap-4">
						{/* Streaming control */}
						{deviceStatus?.state === 'streaming' && (
							<Tooltip content={isPaused ? 'Resume streaming' : 'Pause streaming'} shortcut="Space">
								<button
									onClick={togglePause}
									className={clsx(
										'flex items-center gap-2 px-3 py-1.5 rounded transition-colors',
										isPaused
											? 'bg-accent-amber/15 text-accent-amber border border-accent-amber/25 hover:bg-accent-amber/20'
											: 'bg-surface-3 text-text-secondary hover:bg-surface-4 hover:text-text-primary'
									)}
								>
									{isPaused ? (
										<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
											<path d="M4 2.5l9 5.5-9 5.5V2.5z" />
										</svg>
									) : (
										<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
											<rect x="3" y="2" width="4" height="12" rx="1" />
											<rect x="9" y="2" width="4" height="12" rx="1" />
										</svg>
									)}
									<span className="text-sm font-medium">{isPaused ? 'Resume' : 'Pause'}</span>
								</button>
							</Tooltip>
						)}

						{/* Help button */}
						<Tooltip content="Keyboard shortcuts" shortcut="Shift+?">
							<button
								onClick={() => window.dispatchEvent(new CustomEvent('show-shortcuts-help'))}
								className="w-8 h-8 flex items-center justify-center rounded text-text-tertiary hover:text-text-primary hover:bg-surface-3 transition-colors"
								aria-label="Show keyboard shortcuts"
							>
								<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5">
									<circle cx="9" cy="9" r="7" />
									<path d="M6.5 6.5a2.5 2.5 0 1 1 3.5 2.3c-.5.3-1 .7-1 1.2v1" strokeLinecap="round" />
									<circle cx="9" cy="13" r="0.5" fill="currentColor" />
								</svg>
							</button>
						</Tooltip>

						<div className="w-px h-6 bg-border" />

						{/* Status indicators */}
						{/* WebSocket status */}
						<div className={clsx(
							'flex items-center gap-2 px-3 py-1.5 rounded',
							wsConnected
								? 'bg-accent-green/10 border border-accent-green/20'
								: 'bg-accent-red/10 border border-accent-red/20'
						)}>
							<span className={clsx(
								'w-2 h-2 rounded-full',
								wsConnected
									? 'bg-accent-green shadow-[0_0_8px_rgba(34,197,94,0.4)]'
									: 'bg-accent-red shadow-[0_0_8px_rgba(239,68,68,0.4)]'
							)} />
							<span className={clsx(
								'text-sm font-medium',
								wsConnected ? 'text-accent-green' : 'text-accent-red'
							)}>
								{wsConnected ? 'Connected' : 'Disconnected'}
							</span>
						</div>
						{/* Device state badge */}
						{deviceStatus && (
							<div className="flex items-center gap-3">
								<span className={clsx(
									'px-2 py-1 rounded text-xs font-semibold uppercase tracking-wide',
									{
										'bg-surface-3 text-text-secondary': deviceStatus.state === 'disconnected',
										'bg-accent-amber/15 text-accent-amber border border-accent-amber/25': deviceStatus.state === 'connecting' || deviceStatus.state === 'configuring',
										'bg-accent-teal/15 text-accent-teal border border-accent-teal/25': deviceStatus.state === 'streaming',
										'bg-accent-red/15 text-accent-red border border-accent-red/25': deviceStatus.state === 'error',
									}
								)}>
									{deviceStatus.state}
								</span>
								{deviceStatus.state === 'streaming' && (
									<span className="text-sm font-mono text-text-secondary">
										{deviceStatus.frame_rate.toFixed(1)} <span className="text-text-tertiary">Hz</span>
									</span>
								)}
							</div>
						)}
					</div>
				</header>

				{/* Main content */}
				<main className="flex-1 overflow-auto p-6">
					{children}
				</main>

				{/* Status bar */}
				<footer className="h-9 bg-surface-1 border-t border-border px-6 flex items-center justify-between text-xs font-mono text-text-tertiary">
					<div className="flex items-center gap-6">
						<span>
							Frames: <span className="text-text-secondary">{deviceStatus?.frame_count?.toLocaleString() ?? '0'}</span>
						</span>
						<span>
							Rate: <span className={clsx(
								deviceStatus?.frame_rate && deviceStatus.frame_rate > 0 ? 'text-accent-teal' : 'text-text-secondary'
							)}>{deviceStatus?.frame_rate?.toFixed(1) ?? '0.0'} Hz</span>
						</span>
						<span>
							Dropped: <span className={clsx(
								deviceStatus?.dropped_frames && deviceStatus.dropped_frames > 0 ? 'text-accent-amber' : 'text-text-secondary'
							)}>{deviceStatus?.dropped_frames ?? 0}</span>
						</span>
						<span>
							Buffer: <span className="text-text-secondary">{sensorFrames.length}</span>
						</span>
					</div>
					<div className="flex items-center gap-6">
						<span>
							CLI: <span className="text-text-secondary">{deviceStatus?.cli_port ?? '-'}</span>
						</span>
						<span>
							Data: <span className="text-text-secondary">{deviceStatus?.data_port ?? '-'}</span>
						</span>
					</div>
				</footer>
			</div>
		</div>
	)
}
