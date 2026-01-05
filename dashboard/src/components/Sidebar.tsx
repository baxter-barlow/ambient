import { NavLink } from 'react-router-dom'
import clsx from 'clsx'

const navItems = [
	{ path: '/', label: 'Device Status', icon: '◉' },
	{ path: '/signals', label: 'Signal Viewer', icon: '〜' },
	{ path: '/config', label: 'Configuration', icon: '⚙' },
	{ path: '/recordings', label: 'Recordings', icon: '●' },
	{ path: '/tests', label: 'Test Runner', icon: '▶' },
	{ path: '/tuning', label: 'Algorithm Tuning', icon: '◈' },
	{ path: '/logs', label: 'Logs', icon: '☰' },
]

export default function Sidebar() {
	return (
		<nav className="w-48 bg-gray-800 border-r border-gray-700 flex flex-col">
			<div className="p-4 border-b border-gray-700">
				<span className="text-lg font-bold text-radar-400">ambient</span>
			</div>
			<div className="flex-1 py-2">
				{navItems.map(item => (
					<NavLink
						key={item.path}
						to={item.path}
						className={({ isActive }) => clsx(
							'flex items-center gap-3 px-4 py-2 text-sm transition-colors',
							isActive
								? 'bg-gray-700 text-white border-l-2 border-radar-500'
								: 'text-gray-400 hover:text-gray-200 hover:bg-gray-700/50'
						)}
					>
						<span className="text-base">{item.icon}</span>
						{item.label}
					</NavLink>
				))}
			</div>
			<div className="p-4 border-t border-gray-700 text-xs text-gray-500">
				v0.1.0
			</div>
		</nav>
	)
}
