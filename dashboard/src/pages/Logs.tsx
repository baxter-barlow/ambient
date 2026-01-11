import { useState, useEffect, useRef } from 'react'
import { useAppStore } from '../stores/appStore'
import { useLogsWebSocket } from '../hooks/useWebSocket'
import Button from '../components/common/Button'
import clsx from 'clsx'

const LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR'] as const

/**
 * Logs page following TE design principles:
 * - Monospace for all log data
 * - Borders as hierarchy
 * - Functional accent colors for log levels
 */
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
			case 'DEBUG': return 'text-ink-muted'
			case 'INFO': return 'text-accent-blue'
			case 'WARNING': return 'text-accent-orange'
			case 'ERROR': return 'text-accent-red'
			default: return 'text-ink-muted'
		}
	}

	const formatTime = (timestamp: number) => {
		const date = new Date(timestamp * 1000)
		return date.toLocaleTimeString('en-US', { hour12: false }) + '.' + date.getMilliseconds().toString().padStart(3, '0')
	}

	const exportLogs = () => {
		const content = filteredLogs.map(log => `${formatTime(log.timestamp)} [${log.level}] ${log.logger}: ${log.message}`).join('\n')
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
				<h2 className="text-h2 text-ink-primary">Logs & Debugging</h2>
				<div className="flex items-center gap-6">
					{/* Level filter */}
					<div className="flex items-center gap-3">
						<span className="text-label text-ink-muted uppercase">Level</span>
						<div className="flex items-center border border-border">
							{LEVELS.map((level, idx) => (
								<button
									key={level}
									onClick={() => setFilter(level)}
									aria-label={`Filter by ${level} level`}
									aria-pressed={filter === level}
									className={clsx(
										'px-3 py-1 text-label font-mono transition-all duration-fast',
										filter === level
											? 'bg-ink-primary text-bg-primary'
											: 'bg-bg-secondary text-ink-secondary hover:bg-bg-tertiary',
										idx > 0 && 'border-l border-border'
									)}
								>
									{level}
								</button>
							))}
						</div>
					</div>

					{/* Search */}
					<input
						type="text"
						value={search}
						onChange={e => setSearch(e.target.value)}
						placeholder="Search..."
						aria-label="Search logs"
						className="bg-bg-tertiary border border-border px-3 py-1 text-small w-48 text-ink-primary font-mono focus:outline-none focus:border-accent-yellow"
					/>

					{/* Auto-scroll toggle */}
					<label className="flex items-center gap-2 text-label text-ink-muted cursor-pointer uppercase">
						<input
							type="checkbox"
							checked={autoScroll}
							onChange={e => setAutoScroll(e.target.checked)}
							className="accent-accent-yellow w-4 h-4"
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
				role="log"
				aria-label="Application logs"
				aria-live="polite"
				className="flex-1 bg-bg-secondary border border-border p-4 overflow-auto font-mono text-small"
			>
				{filteredLogs.length === 0 ? (
					<p className="text-ink-muted">No logs matching filter.</p>
				) : (
					<table className="w-full">
						<tbody>
							{filteredLogs.map((log, i) => (
								<tr key={i} className="hover:bg-bg-tertiary">
									<td className="py-0.5 pr-4 text-ink-muted whitespace-nowrap">{formatTime(log.timestamp)}</td>
									<td className={clsx('py-0.5 pr-4 whitespace-nowrap', getLevelColor(log.level))}>{log.level}</td>
									<td className="py-0.5 pr-4 text-ink-muted whitespace-nowrap">{log.logger}</td>
									<td className="py-0.5 text-ink-primary">{log.message}</td>
								</tr>
							))}
						</tbody>
					</table>
				)}
			</div>
		</div>
	)
}
