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
			case 'DEBUG': return 'text-text-tertiary'
			case 'INFO': return 'text-accent-blue'
			case 'WARNING': return 'text-accent-amber'
			case 'ERROR': return 'text-accent-red'
			default: return 'text-text-tertiary'
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
				<h2 className="text-xl text-text-primary">Logs & Debugging</h2>
				<div className="flex items-center gap-4">
					{/* Level filter */}
					<div className="flex items-center gap-2">
						<span className="text-sm text-text-secondary">Level:</span>
						{LEVELS.map(level => (
							<button
								key={level}
								onClick={() => setFilter(level)}
								className={clsx(
									'px-2.5 py-1 text-xs rounded transition-colors duration-150',
									filter === level
										? 'bg-accent-teal text-text-inverse font-semibold'
										: 'bg-surface-3 text-text-secondary hover:bg-surface-4'
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
						className="bg-surface-3 border border-border rounded px-3 py-1.5 text-sm w-48 text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-teal"
					/>

					{/* Auto-scroll toggle */}
					<label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer">
						<input
							type="checkbox"
							checked={autoScroll}
							onChange={e => setAutoScroll(e.target.checked)}
							className="accent-accent-teal"
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
				className="flex-1 bg-surface-2 border border-border rounded-card p-4 overflow-auto font-mono text-sm"
			>
				{filteredLogs.length === 0 ? (
					<p className="text-text-tertiary">No logs matching filter.</p>
				) : (
					<table className="w-full">
						<tbody>
							{filteredLogs.map((log, i) => (
								<tr key={i} className="hover:bg-surface-3/50">
									<td className="py-0.5 pr-4 text-text-tertiary whitespace-nowrap">
										{formatTime(log.timestamp)}
									</td>
									<td className={clsx('py-0.5 pr-4 whitespace-nowrap', getLevelColor(log.level))}>
										{log.level}
									</td>
									<td className="py-0.5 pr-4 text-text-tertiary whitespace-nowrap">
										{log.logger}
									</td>
									<td className="py-0.5 text-text-primary">
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
