import { useState, useEffect, useRef } from 'react'
import { useAppStore } from '../stores/appStore'
import { useLogsWebSocket } from '../hooks/useWebSocket'
import Button from '../components/common/Button'
import clsx from 'clsx'

const LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR'] as const

export default function Logs() {
	useLogsWebSocket()

	const logs = useAppStore(s => s.logs)
	const clearLogs = useAppStore(s => s.clearLogs)
	const [filter, setFilter] = useState<string>('INFO')
	const [search, setSearch] = useState('')
	const [autoScroll, setAutoScroll] = useState(true)
	const containerRef = useRef<HTMLDivElement>(null)

	useEffect(() => {
		if (autoScroll && containerRef.current) {
			containerRef.current.scrollTop = containerRef.current.scrollHeight
		}
	}, [logs, autoScroll])

	const filteredLogs = logs.filter(log => {
		const levelIdx = LEVELS.indexOf(log.level as typeof LEVELS[number])
		const filterIdx = LEVELS.indexOf(filter as typeof LEVELS[number])
		if (levelIdx < filterIdx) return false
		if (search && !log.message.toLowerCase().includes(search.toLowerCase())) return false
		return true
	})

	const getLevelColor = (level: string) => {
		switch (level) {
			case 'DEBUG': return 'text-gray-400'
			case 'INFO': return 'text-blue-400'
			case 'WARNING': return 'text-yellow-400'
			case 'ERROR': return 'text-red-400'
			default: return 'text-gray-400'
		}
	}

	const formatTime = (timestamp: number) => {
		const date = new Date(timestamp * 1000)
		return date.toLocaleTimeString('en-US', { hour12: false }) +
			'.' + date.getMilliseconds().toString().padStart(3, '0')
	}

	const exportLogs = () => {
		const content = filteredLogs.map(log =>
			`${formatTime(log.timestamp)} [${log.level}] ${log.logger}: ${log.message}`
		).join('\n')

		const blob = new Blob([content], { type: 'text/plain' })
		const url = URL.createObjectURL(blob)
		const a = document.createElement('a')
		a.href = url
		a.download = `ambient-logs-${Date.now()}.txt`
		a.click()
		URL.revokeObjectURL(url)
	}

	return (
		<div className="space-y-4 h-full flex flex-col">
			<div className="flex items-center justify-between">
				<h2 className="text-xl font-semibold">Logs & Debugging</h2>
				<div className="flex items-center gap-4">
					{/* Level filter */}
					<div className="flex items-center gap-2">
						<span className="text-sm text-gray-400">Level:</span>
						{LEVELS.map(level => (
							<button
								key={level}
								onClick={() => setFilter(level)}
								className={clsx(
									'px-2 py-1 text-xs rounded',
									filter === level
										? 'bg-radar-600 text-white'
										: 'bg-gray-700 text-gray-300 hover:bg-gray-600'
								)}
							>
								{level}
							</button>
						))}
					</div>

					{/* Search */}
					<input
						type="text"
						value={search}
						onChange={e => setSearch(e.target.value)}
						placeholder="Search..."
						className="bg-gray-700 border border-gray-600 rounded px-3 py-1 text-sm w-48"
					/>

					{/* Auto-scroll toggle */}
					<label className="flex items-center gap-2 text-sm">
						<input
							type="checkbox"
							checked={autoScroll}
							onChange={e => setAutoScroll(e.target.checked)}
						/>
						Auto-scroll
					</label>

					<Button size="sm" variant="secondary" onClick={exportLogs}>Export</Button>
					<Button size="sm" variant="secondary" onClick={clearLogs}>Clear</Button>
				</div>
			</div>

			{/* Log viewer */}
			<div
				ref={containerRef}
				className="flex-1 bg-gray-800 rounded-lg p-4 overflow-auto font-mono text-sm"
			>
				{filteredLogs.length === 0 ? (
					<p className="text-gray-500">No logs matching filter.</p>
				) : (
					<table className="w-full">
						<tbody>
							{filteredLogs.map((log, i) => (
								<tr key={i} className="hover:bg-gray-700/50">
									<td className="py-0.5 pr-4 text-gray-500 whitespace-nowrap">
										{formatTime(log.timestamp)}
									</td>
									<td className={clsx('py-0.5 pr-4 whitespace-nowrap', getLevelColor(log.level))}>
										{log.level}
									</td>
									<td className="py-0.5 pr-4 text-gray-400 whitespace-nowrap">
										{log.logger}
									</td>
									<td className="py-0.5 text-gray-200">
										{log.message}
									</td>
								</tr>
							))}
						</tbody>
					</table>
				)}
			</div>
		</div>
	)
}
