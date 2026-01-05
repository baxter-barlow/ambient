import { ReactNode } from 'react'
import Sidebar from './Sidebar'
import { useAppStore } from '../stores/appStore'
import clsx from 'clsx'

interface Props {
	children: ReactNode
}

export default function Layout({ children }: Props) {
	const deviceStatus = useAppStore(s => s.deviceStatus)
	const wsConnected = useAppStore(s => s.wsConnected)

	return (
		<div className="flex h-screen bg-gray-900">
			<Sidebar />
			<div className="flex-1 flex flex-col overflow-hidden">
				{/* Top bar */}
				<header className="h-12 bg-gray-800 border-b border-gray-700 flex items-center px-4 justify-between">
					<h1 className="text-lg font-semibold text-gray-100">Ambient Dashboard</h1>
					<div className="flex items-center gap-4">
						{/* WebSocket status */}
						<div className="flex items-center gap-2 text-sm">
							<span className={clsx(
								'w-2 h-2 rounded-full',
								wsConnected ? 'bg-green-500' : 'bg-red-500'
							)} />
							<span className="text-gray-400">
								{wsConnected ? 'Connected' : 'Disconnected'}
							</span>
						</div>
						{/* Device state */}
						{deviceStatus && (
							<div className="flex items-center gap-2 text-sm">
								<span className={clsx(
									'px-2 py-0.5 rounded text-xs font-medium',
									{
										'bg-gray-600 text-gray-300': deviceStatus.state === 'disconnected',
										'bg-yellow-600 text-yellow-100': deviceStatus.state === 'connecting' || deviceStatus.state === 'configuring',
										'bg-green-600 text-green-100': deviceStatus.state === 'streaming',
										'bg-red-600 text-red-100': deviceStatus.state === 'error',
									}
								)}>
									{deviceStatus.state}
								</span>
								{deviceStatus.state === 'streaming' && (
									<span className="text-gray-400">
										{deviceStatus.frame_rate.toFixed(1)} Hz
									</span>
								)}
							</div>
						)}
					</div>
				</header>
				{/* Main content */}
				<main className="flex-1 overflow-auto p-4">
					{children}
				</main>
			</div>
		</div>
	)
}
