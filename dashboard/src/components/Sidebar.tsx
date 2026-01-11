import { NavLink } from 'react-router-dom'
import clsx from 'clsx'
import { useAppStore } from '../stores/appStore'

// Stroke-based icons - mechanical, not friendly
const Icons = {
	device: (
		<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
			<rect x="3" y="4" width="14" height="10" />
			<line x1="7" y1="17" x2="13" y2="17" />
			<line x1="10" y1="14" x2="10" y2="17" />
		</svg>
	),
	signals: (
		<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
			<polyline points="2,10 5,10 7,5 10,15 13,8 15,10 18,10" />
		</svg>
	),
	config: (
		<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
			<line x1="4" y1="6" x2="16" y2="6" />
			<line x1="4" y1="10" x2="16" y2="10" />
			<line x1="4" y1="14" x2="16" y2="14" />
			<rect x="6" y="4" width="4" height="4" fill="currentColor" />
			<rect x="10" y="8" width="4" height="4" fill="currentColor" />
			<rect x="6" y="12" width="4" height="4" fill="currentColor" />
		</svg>
	),
	recordings: (
		<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
			<circle cx="10" cy="10" r="7" />
			<circle cx="10" cy="10" r="3" />
		</svg>
	),
	tests: (
		<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
			<polyline points="4,10 8,14 16,6" />
		</svg>
	),
	tuning: (
		<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
			<line x1="4" y1="5" x2="16" y2="5" />
			<line x1="4" y1="10" x2="16" y2="10" />
			<line x1="4" y1="15" x2="16" y2="15" />
			<circle cx="7" cy="5" r="2" fill="currentColor" />
			<circle cx="13" cy="10" r="2" fill="currentColor" />
			<circle cx="9" cy="15" r="2" fill="currentColor" />
		</svg>
	),
	logs: (
		<svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5">
			<rect x="4" y="3" width="12" height="14" />
			<line x1="7" y1="7" x2="13" y2="7" />
			<line x1="7" y1="10" x2="13" y2="10" />
			<line x1="7" y1="13" x2="11" y2="13" />
		</svg>
	),
}

const navItems = [
	{ path: '/device', label: 'Device', icon: Icons.device, key: '1' },
	{ path: '/signals', label: 'Signals', icon: Icons.signals, key: '2' },
	{ path: '/config', label: 'Config', icon: Icons.config, key: '3' },
	{ path: '/recordings', label: 'Record', icon: Icons.recordings, key: '4' },
	{ path: '/tests', label: 'Test', icon: Icons.tests, key: '5' },
	{ path: '/tuning', label: 'Tune', icon: Icons.tuning, key: '6' },
	{ path: '/logs', label: 'Log', icon: Icons.logs, key: '7' },
]

export default function Sidebar() {
	const deviceStatus = useAppStore(s => s.deviceStatus)
	const wsConnected = useAppStore(s => s.wsConnected)

	return (
		<nav className="w-[180px] bg-bg-secondary border-r border-border flex flex-col">
			{/* Logo / Brand - links to dashboard */}
			<NavLink
				to="/"
				className="h-12 px-4 border-b border-border flex items-center hover:bg-bg-tertiary transition-all duration-fast"
			>
				<span className="text-h3 text-ink-primary tracking-tight">ambient</span>
			</NavLink>

			{/* Navigation */}
			<div className="flex-1 py-4">
				{navItems.map(item => (
					<NavLink
						key={item.path}
						to={item.path}
						className={({ isActive }) => clsx(
							'flex items-center gap-3 px-4 py-2 text-small transition-all duration-fast ease-out',
							isActive
								? 'bg-ink-primary text-bg-primary'
								: 'text-ink-secondary hover:text-ink-primary hover:bg-bg-tertiary'
						)}
					>
						<span className="w-5 h-5 flex items-center justify-center">
							{item.icon}
						</span>
						<span className="flex-1">{item.label}</span>
						<span className="text-label opacity-50">{item.key}</span>
					</NavLink>
				))}
			</div>

			{/* Status section */}
			<div className="border-t border-border p-4 space-y-3">
				{/* Connection indicator */}
				<div className="flex items-center justify-between">
					<span className="text-label text-ink-muted">STATUS</span>
					<div className="flex items-center gap-2">
						<div className={clsx(
							'w-2 h-2',
							wsConnected ? 'bg-accent-green' : 'bg-accent-red'
						)} />
						<span className="text-label text-ink-muted">
							{wsConnected ? 'ON' : 'OFF'}
						</span>
					</div>
				</div>

				{/* Frame rate when streaming */}
				{deviceStatus?.state === 'streaming' && (
					<div className="flex items-center justify-between">
						<span className="text-label text-ink-muted">RATE</span>
						<span className="font-mono text-small text-ink-primary">
							{deviceStatus.frame_rate.toFixed(1)} Hz
						</span>
					</div>
				)}
			</div>

			{/* Footer */}
			<div className="border-t border-border p-4">
				<div className="flex items-center justify-between">
					<span className="text-label text-ink-muted">v0.1.0</span>
					<span className="font-mono text-label text-ink-muted">
						{deviceStatus?.state === 'streaming' ? 'IWR6843' : '—'}
					</span>
				</div>
			</div>
		</nav>
	)
}
