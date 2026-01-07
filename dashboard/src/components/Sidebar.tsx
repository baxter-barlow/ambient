import { NavLink } from 'react-router-dom'
import clsx from 'clsx'
import Tooltip from './common/Tooltip'

const navItems = [
	{ path: '/', label: 'Device Status', icon: '◉', shortcut: '1' },
	{ path: '/signals', label: 'Signal Viewer', icon: '〜', shortcut: '2' },
	{ path: '/config', label: 'Configuration', icon: '⚙', shortcut: '3' },
	{ path: '/recordings', label: 'Recordings', icon: '●', shortcut: '4' },
	{ path: '/tests', label: 'Test Runner', icon: '▶', shortcut: '5' },
	{ path: '/tuning', label: 'Algorithm Tuning', icon: '◈', shortcut: '6' },
	{ path: '/logs', label: 'Logs', icon: '☰', shortcut: '7' },
]

export default function Sidebar() {
	return (
		<nav className="w-[200px] bg-surface-1 border-r border-border flex flex-col">
			{/* Logo */}
			<div className="px-5 py-4 border-b border-border flex items-center gap-2.5">
				<div className="w-7 h-7 bg-accent-teal rounded-md flex items-center justify-center">
					<span className="text-sm font-bold text-text-inverse">A</span>
				</div>
				<span className="text-lg text-text-primary">ambient</span>
			</div>

			{/* Navigation */}
			<div className="flex-1 py-3 px-2">
				{navItems.map(item => (
					<Tooltip key={item.path} content={item.label} shortcut={item.shortcut} position="right" delay={500}>
						<NavLink
							to={item.path}
							className={({ isActive }) => clsx(
								'w-full flex items-center gap-2.5 px-3 py-2.5 mb-0.5 rounded-md text-base transition-colors duration-150',
								isActive
									? 'bg-surface-3 text-accent-teal'
									: 'text-text-secondary hover:bg-surface-3 hover:text-text-primary'
							)}
						>
							<span className={clsx(
								'w-4 text-center text-sm',
								'opacity-60'
							)}>{item.icon}</span>
							{item.label}
						</NavLink>
					</Tooltip>
				))}
			</div>

			{/* Footer */}
			<div className="px-4 py-4 border-t border-border">
				<div className="text-xs text-text-tertiary">v0.1.0</div>
				<div className="text-micro font-mono text-text-tertiary opacity-70 mt-1">
					IWR6843AOP
				</div>
			</div>
		</nav>
	)
}
