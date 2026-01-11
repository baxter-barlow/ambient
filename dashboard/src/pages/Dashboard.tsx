import { useState, useMemo, useEffect, useRef } from 'react'
import { useAppStore } from '../stores/appStore'
import { useLogsWebSocket } from '../hooks/useWebSocket'
import { deviceApi, recordingApi } from '../api/client'
import { showToast } from '../components/common/Toast'
import DeviceStatusBar from '../components/DeviceStatusBar'
import VitalsPanel from '../components/VitalsPanel'
import RangeProfile from '../components/charts/RangeProfile'
import PhaseSignal from '../components/charts/PhaseSignal'
import VitalsChart from '../components/charts/VitalsChart'
import RangeDoppler from '../components/charts/RangeDoppler'
import QualityMetricsChart from '../components/charts/QualityMetricsChart'
import WaveformChart from '../components/charts/WaveformChart'
import clsx from 'clsx'
import type { RecordingStatus, SensorFrame, VitalSigns, DeviceStatus } from '../types'

type TabId = 'signals' | 'device' | 'record' | 'logs'

const TABS: { id: TabId; label: string; shortcut: string }[] = [
	{ id: 'signals', label: 'Signals', shortcut: '1' },
	{ id: 'device', label: 'Device', shortcut: '2' },
	{ id: 'record', label: 'Record', shortcut: '3' },
	{ id: 'logs', label: 'Logs', shortcut: '4' },
]

/**
 * Unified Developer Dashboard with tabbed interface.
 * Each tab fills the available space for maximum information density.
 */
export default function Dashboard() {
	useLogsWebSocket()

	const [activeTab, setActiveTab] = useState<TabId>('signals')
	const sensorFrames = useAppStore(s => s.sensorFrames)
	const vitals = useAppStore(s => s.vitals)
	const vitalsHistory = useAppStore(s => s.vitalsHistory)
	const logs = useAppStore(s => s.logs)
	const clearLogs = useAppStore(s => s.clearLogs)
	const deviceStatus = useAppStore(s => s.deviceStatus)
	const timeWindow = useAppStore(s => s.timeWindow)
	const setTimeWindow = useAppStore(s => s.setTimeWindow)
	const isPaused = useAppStore(s => s.isPaused)
	const togglePause = useAppStore(s => s.togglePause)

	const [recordingStatus, setRecordingStatus] = useState<RecordingStatus | null>(null)
	const [recordingName, setRecordingName] = useState('')
	const [logFilter, setLogFilter] = useState('INFO')

	// Load recording status
	useEffect(() => {
		const load = async () => {
			try {
				const status = await recordingApi.getStatus()
				setRecordingStatus(status)
			} catch {
				// Ignore errors
			}
		}
		load()
		const interval = setInterval(load, 5000)
		return () => clearInterval(interval)
	}, [])

	// Keyboard shortcuts for tabs
	useEffect(() => {
		const handleKeyDown = (e: KeyboardEvent) => {
			if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
				return
			}
			const tab = TABS.find(t => t.shortcut === e.key)
			if (tab && !e.ctrlKey && !e.metaKey && !e.altKey) {
				e.preventDefault()
				setActiveTab(tab.id)
			}
		}
		window.addEventListener('keydown', handleKeyDown)
		return () => window.removeEventListener('keydown', handleKeyDown)
	}, [])

	const latestFrame = sensorFrames[sensorFrames.length - 1]

	const phaseData = useMemo(() => {
		const now = Date.now() / 1000
		const cutoff = now - timeWindow
		const filtered = sensorFrames.filter(f => f.timestamp > cutoff)
		return {
			timestamps: filtered.map(f => f.timestamp),
			phases: filtered.map(f => f.phase ?? 0),
		}
	}, [sensorFrames, timeWindow])

	const vitalsData = useMemo(() => {
		const now = Date.now() / 1000
		const cutoff = now - timeWindow
		const filtered = vitalsHistory.filter(v => v.timestamp > cutoff)
		return {
			timestamps: filtered.map(v => v.timestamp),
			heartRates: filtered.map(v => v.hr),
			respiratoryRates: filtered.map(v => v.rr),
		}
	}, [vitalsHistory, timeWindow])

	const qualityData = useMemo(() => {
		const now = Date.now() / 1000
		const cutoff = now - timeWindow
		const filtered = vitalsHistory.filter(v => v.timestamp > cutoff)
		return {
			timestamps: filtered.map(v => v.timestamp),
			hrSnrDb: filtered.map(v => v.hr_snr_db),
			rrSnrDb: filtered.map(v => v.rr_snr_db),
			phaseStability: filtered.map(v => v.phase_stability),
			signalQuality: filtered.map(v => v.signal_quality),
		}
	}, [vitalsHistory, timeWindow])

	const isStreaming = deviceStatus?.state === 'streaming'

	// Recording handlers
	const handleStartRecording = async () => {
		if (!recordingName.trim()) return
		try {
			await recordingApi.start(recordingName.trim(), 'h5')
			setRecordingName('')
			const status = await recordingApi.getStatus()
			setRecordingStatus(status)
			showToast('Recording started', 'success')
		} catch (e) {
			showToast(`Failed to start: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
		}
	}

	const handleStopRecording = async () => {
		try {
			await recordingApi.stop()
			const status = await recordingApi.getStatus()
			setRecordingStatus(status)
			showToast('Recording stopped', 'success')
		} catch (e) {
			showToast(`Failed to stop: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
		}
	}

	// Log level colors
	const getLevelColor = (level: string) => {
		switch (level) {
			case 'DEBUG': return 'text-ink-muted'
			case 'INFO': return 'text-accent-blue'
			case 'WARNING': return 'text-accent-orange'
			case 'ERROR': return 'text-accent-red'
			default: return 'text-ink-muted'
		}
	}

	const LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
	const filteredLogs = logs.filter(log => {
		const levelIdx = LEVELS.indexOf(log.level)
		const filterIdx = LEVELS.indexOf(logFilter)
		return levelIdx >= filterIdx
	})

	return (
		<div className="h-screen flex flex-col bg-bg-primary">
			{/* Compact status bar */}
			<DeviceStatusBar />

			{/* Tab bar */}
			<div className="bg-bg-secondary border-b border-border flex items-center px-4">
				{TABS.map((tab) => (
					<button
						key={tab.id}
						onClick={() => setActiveTab(tab.id)}
						className={clsx(
							'px-6 py-3 text-small font-medium transition-all duration-fast border-b-2 -mb-px',
							activeTab === tab.id
								? 'border-ink-primary text-ink-primary'
								: 'border-transparent text-ink-secondary hover:text-ink-primary hover:border-border'
						)}
					>
						{tab.label}
						<span className="ml-2 text-label text-ink-muted">{tab.shortcut}</span>
					</button>
				))}

				{/* Spacer */}
				<div className="flex-1" />

				{/* Time window selector (for signals tab) */}
				{activeTab === 'signals' && (
					<div className="flex items-center gap-3">
						<span className="text-label text-ink-muted uppercase">Window</span>
						<div className="flex items-center border border-border">
							{[5, 30, 60, 300].map((tw, idx) => (
								<button
									key={tw}
									onClick={() => setTimeWindow(tw)}
									className={clsx(
										'px-3 py-1 text-label font-mono transition-all duration-fast',
										timeWindow === tw
											? 'bg-ink-primary text-bg-primary'
											: 'bg-bg-secondary text-ink-secondary hover:bg-bg-tertiary',
										idx > 0 && 'border-l border-border'
									)}
								>
									{tw < 60 ? `${tw}s` : `${tw / 60}m`}
								</button>
							))}
						</div>
					</div>
				)}

				{/* Pause/Resume */}
				<button
					onClick={togglePause}
					className={clsx(
						'ml-4 flex items-center gap-2 px-4 py-1.5 border text-small font-medium transition-all duration-fast',
						isPaused
							? 'bg-bg-secondary border-border text-ink-secondary hover:bg-bg-tertiary'
							: 'bg-accent-green border-accent-green text-bg-primary'
					)}
				>
					<div className={clsx('w-2 h-2', isPaused ? 'bg-ink-muted' : 'bg-bg-primary')} />
					{isPaused ? 'Paused' : 'Live'}
				</button>
			</div>

			{/* Vitals panel - always visible */}
			<VitalsPanel />

			{/* Tab content */}
			<div className="flex-1 overflow-auto p-4">
				{activeTab === 'signals' && (
					<SignalsTab
						latestFrame={latestFrame}
						phaseData={phaseData}
						vitalsData={vitalsData}
						qualityData={qualityData}
						vitals={vitals}
						vitalsHistory={vitalsHistory}
					/>
				)}

				{activeTab === 'device' && (
					<DeviceTab deviceStatus={deviceStatus} isStreaming={isStreaming} />
				)}

				{activeTab === 'record' && (
					<RecordTab
						recordingStatus={recordingStatus}
						recordingName={recordingName}
						setRecordingName={setRecordingName}
						handleStartRecording={handleStartRecording}
						handleStopRecording={handleStopRecording}
						isStreaming={isStreaming}
					/>
				)}

				{activeTab === 'logs' && (
					<LogsTab
						logs={filteredLogs}
						logFilter={logFilter}
						setLogFilter={setLogFilter}
						clearLogs={clearLogs}
						getLevelColor={getLevelColor}
					/>
				)}
			</div>
		</div>
	)
}

// ============================================================================
// Tab Components
// ============================================================================

interface VitalsHistoryEntry {
	timestamp: number
	hr: number | null
	rr: number | null
	hr_snr_db: number
	rr_snr_db: number
	phase_stability: number
	signal_quality: number
}

interface SignalsTabProps {
	latestFrame: SensorFrame | undefined
	phaseData: { timestamps: number[]; phases: number[] }
	vitalsData: { timestamps: number[]; heartRates: (number | null)[]; respiratoryRates: (number | null)[] }
	qualityData: { timestamps: number[]; hrSnrDb: number[]; rrSnrDb: number[]; phaseStability: number[]; signalQuality: number[] }
	vitals: VitalSigns | null
	vitalsHistory: VitalsHistoryEntry[]
}

function SignalsTab({ latestFrame, phaseData, vitalsData, qualityData, vitals, vitalsHistory }: SignalsTabProps) {
	return (
		<div className="h-full flex flex-col gap-4">
			{/* Top row: Range Profile + Range-Doppler */}
			<div className="flex gap-4 flex-1 min-h-0">
				<div className="flex-[2]">
					<RangeProfile
						data={latestFrame?.range_profile ?? []}
						source={latestFrame?.range_profile_source}
						isChirpFirmware={latestFrame?.is_chirp_firmware}
						height={280}
					/>
				</div>
				<div className="flex-1">
					<RangeDoppler
						data={latestFrame?.range_doppler}
						isChirpFirmware={latestFrame?.is_chirp_firmware}
						height={280}
					/>
				</div>
			</div>

			{/* Middle row: Phase Signal + Vitals Chart */}
			<div className="flex gap-4 flex-1 min-h-0">
				<div className="flex-1">
					<PhaseSignal
						timestamps={phaseData.timestamps}
						phases={phaseData.phases}
						height={250}
					/>
				</div>
				<div className="flex-1">
					<VitalsChart
						timestamps={vitalsData.timestamps}
						heartRates={vitalsData.heartRates}
						respiratoryRates={vitalsData.respiratoryRates}
						height={250}
					/>
				</div>
			</div>

			{/* Bottom row: Quality Metrics + Waveforms */}
			<div className="flex gap-4 flex-1 min-h-0">
				{vitalsHistory.length > 0 && (
					<div className="flex-1">
						<QualityMetricsChart
							timestamps={qualityData.timestamps}
							hrSnrDb={qualityData.hrSnrDb}
							rrSnrDb={qualityData.rrSnrDb}
							phaseStability={qualityData.phaseStability}
							signalQuality={qualityData.signalQuality}
							height={200}
						/>
					</div>
				)}
				{vitals?.breathing_waveform && (
					<div className="flex-1">
						<WaveformChart
							breathingWaveform={vitals.breathing_waveform}
							heartWaveform={vitals.heart_waveform}
							height={200}
						/>
					</div>
				)}
			</div>
		</div>
	)
}

interface DeviceTabProps {
	deviceStatus: DeviceStatus | null
	isStreaming: boolean
}

function DeviceTab({ deviceStatus, isStreaming }: DeviceTabProps) {
	return (
		<div className="h-full grid grid-cols-2 gap-4">
			{/* Device Status */}
			<div className="bg-bg-secondary border border-border flex flex-col">
				<div className="px-4 py-3 border-b border-border">
					<span className="text-small font-medium text-ink-primary">Device Status</span>
				</div>
				<div className="p-4 flex-1">
					<div className="grid grid-cols-2 gap-4">
						<div>
							<span className="text-label text-ink-muted block uppercase">State</span>
							<span className={clsx(
								'text-h3 font-mono',
								deviceStatus?.state === 'streaming' ? 'text-accent-green' :
								deviceStatus?.state === 'error' ? 'text-accent-red' : 'text-ink-primary'
							)}>
								{deviceStatus?.state?.toUpperCase() ?? 'UNKNOWN'}
							</span>
						</div>
						<div>
							<span className="text-label text-ink-muted block uppercase">Config</span>
							<span className="text-h3 font-mono text-ink-primary">
								{deviceStatus?.config_name ?? '--'}
							</span>
						</div>
						<div>
							<span className="text-label text-ink-muted block uppercase">CLI Port</span>
							<span className="text-body font-mono text-ink-primary">
								{deviceStatus?.cli_port ?? '--'}
							</span>
						</div>
						<div>
							<span className="text-label text-ink-muted block uppercase">Data Port</span>
							<span className="text-body font-mono text-ink-primary">
								{deviceStatus?.data_port ?? '--'}
							</span>
						</div>
					</div>

					{deviceStatus?.error && (
						<div className="mt-4 p-3 bg-accent-red/10 border border-accent-red">
							<span className="text-small text-accent-red">{deviceStatus.error}</span>
						</div>
					)}

					<div className="mt-6 flex gap-3">
						{isStreaming && (
							<button
								onClick={() => deviceApi.stop()}
								className="px-4 py-2 bg-accent-red text-bg-primary border border-accent-red text-small font-medium hover:bg-transparent hover:text-accent-red transition-all duration-fast"
							>
								Stop Streaming
							</button>
						)}
						{deviceStatus?.state !== 'disconnected' && (
							<button
								onClick={() => deviceApi.disconnect()}
								className="px-4 py-2 border border-ink-muted text-ink-muted text-small font-medium hover:bg-ink-muted hover:text-bg-primary transition-all duration-fast"
							>
								Disconnect
							</button>
						)}
					</div>
				</div>
			</div>

			{/* Performance Metrics */}
			<div className="bg-bg-secondary border border-border flex flex-col">
				<div className="px-4 py-3 border-b border-border">
					<span className="text-small font-medium text-ink-primary">Performance</span>
				</div>
				<div className="p-4 flex-1">
					<div className="grid grid-cols-2 gap-4">
						<div>
							<span className="text-label text-ink-muted block uppercase">Frame Rate</span>
							<span className="text-h2 font-mono text-ink-primary">
								{deviceStatus?.frame_rate?.toFixed(1) ?? '0.0'}
								<span className="text-small text-ink-muted ml-1">Hz</span>
							</span>
						</div>
						<div>
							<span className="text-label text-ink-muted block uppercase">Frame Count</span>
							<span className="text-h2 font-mono text-ink-primary">
								{deviceStatus?.frame_count?.toLocaleString() ?? '0'}
							</span>
						</div>
						<div>
							<span className="text-label text-ink-muted block uppercase">Dropped Frames</span>
							<span className={clsx(
								'text-h2 font-mono',
								(deviceStatus?.dropped_frames ?? 0) > 0 ? 'text-accent-red' : 'text-ink-primary'
							)}>
								{deviceStatus?.dropped_frames ?? 0}
							</span>
						</div>
						<div>
							<span className="text-label text-ink-muted block uppercase">Buffer Usage</span>
							<span className={clsx(
								'text-h2 font-mono',
								(deviceStatus?.buffer_usage ?? 0) > 80 ? 'text-accent-red' :
								(deviceStatus?.buffer_usage ?? 0) > 50 ? 'text-accent-orange' : 'text-ink-primary'
							)}>
								{deviceStatus?.buffer_usage?.toFixed(0) ?? '0'}%
							</span>
						</div>
					</div>
				</div>
			</div>
		</div>
	)
}

interface RecordTabProps {
	recordingStatus: RecordingStatus | null
	recordingName: string
	setRecordingName: (name: string) => void
	handleStartRecording: () => void
	handleStopRecording: () => void
	isStreaming: boolean
}

function RecordTab({ recordingStatus, recordingName, setRecordingName, handleStartRecording, handleStopRecording, isStreaming }: RecordTabProps) {
	return (
		<div className="h-full flex flex-col gap-4">
			{/* Recording Status */}
			{recordingStatus?.is_recording && (
				<div className="bg-bg-secondary border-l-4 border-l-accent-red border border-border p-6">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-4">
							<span className="w-4 h-4 bg-accent-red animate-pulse" />
							<div>
								<p className="text-h3 font-medium text-accent-red">Recording: {recordingStatus.name}</p>
								<p className="text-body text-ink-muted font-mono mt-1">
									{Math.floor(recordingStatus.duration / 60)}:{String(Math.floor(recordingStatus.duration % 60)).padStart(2, '0')} | {recordingStatus.frame_count} frames
								</p>
							</div>
						</div>
						<button
							onClick={handleStopRecording}
							className="px-6 py-3 bg-accent-red text-bg-primary text-body font-medium hover:bg-transparent hover:text-accent-red border border-accent-red transition-all duration-fast"
						>
							Stop Recording
						</button>
					</div>
				</div>
			)}

			{/* Start New Recording */}
			{!recordingStatus?.is_recording && (
				<div className="bg-bg-secondary border border-border">
					<div className="px-4 py-3 border-b border-border">
						<span className="text-small font-medium text-ink-primary">Start New Recording</span>
					</div>
					<div className="p-6">
						<div className="flex items-end gap-4 max-w-2xl">
							<div className="flex-1">
								<label className="block text-label text-ink-muted mb-2 uppercase">Session Name</label>
								<input
									type="text"
									value={recordingName}
									onChange={e => setRecordingName(e.target.value)}
									placeholder="e.g., sleep_test_001"
									className="w-full bg-bg-tertiary border border-border px-4 py-3 text-body text-ink-primary font-mono focus:outline-none focus:border-accent-yellow"
								/>
							</div>
							<button
								onClick={handleStartRecording}
								disabled={!recordingName.trim() || !isStreaming}
								className={clsx(
									'px-6 py-3 text-body font-medium border transition-all duration-fast',
									!recordingName.trim() || !isStreaming
										? 'bg-bg-tertiary text-ink-muted border-border cursor-not-allowed'
										: 'bg-accent-green text-bg-primary border-accent-green hover:bg-transparent hover:text-accent-green'
								)}
							>
								Start Recording
							</button>
						</div>
						{!isStreaming && (
							<p className="mt-4 text-small text-accent-orange">Device must be streaming to start recording.</p>
						)}
					</div>
				</div>
			)}

			{/* Recordings would be listed here */}
			<div className="bg-bg-secondary border border-border flex-1">
				<div className="px-4 py-3 border-b border-border">
					<span className="text-small font-medium text-ink-primary">Previous Recordings</span>
				</div>
				<div className="p-4 text-ink-muted text-small">
					Previous recordings would be listed here. Navigate to /recordings for full management.
				</div>
			</div>
		</div>
	)
}

interface LogsTabProps {
	logs: { timestamp: number; level: string; logger: string; message: string }[]
	logFilter: string
	setLogFilter: (filter: string) => void
	clearLogs: () => void
	getLevelColor: (level: string) => string
}

function LogsTab({ logs, logFilter, setLogFilter, clearLogs, getLevelColor }: LogsTabProps) {
	const LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR']
	const [search, setSearch] = useState('')
	const [autoScroll, setAutoScroll] = useState(true)
	const containerRef = useRef<HTMLDivElement>(null)

	// Filter logs by search term
	const displayedLogs = search
		? logs.filter(log =>
			log.message.toLowerCase().includes(search.toLowerCase()) ||
			log.logger.toLowerCase().includes(search.toLowerCase())
		)
		: logs

	// Auto-scroll to bottom when new logs arrive
	useEffect(() => {
		if (autoScroll && containerRef.current) {
			containerRef.current.scrollTop = containerRef.current.scrollHeight
		}
	}, [logs, autoScroll])

	// Format timestamp with milliseconds
	const formatTime = (timestamp: number) => {
		const date = new Date(timestamp * 1000)
		return date.toLocaleTimeString('en-US', { hour12: false }) + '.' +
			date.getMilliseconds().toString().padStart(3, '0')
	}

	// Export logs to file
	const exportLogs = () => {
		const content = displayedLogs
			.map(log => `${formatTime(log.timestamp)} [${log.level}] ${log.logger}: ${log.message}`)
			.join('\n')
		const blob = new Blob([content], { type: 'text/plain' })
		const url = URL.createObjectURL(blob)
		const a = document.createElement('a')
		a.href = url
		a.download = `ambient-logs-${Date.now()}.txt`
		a.click()
		URL.revokeObjectURL(url)
	}

	return (
		<div className="h-full flex flex-col bg-bg-secondary border border-border">
			{/* Header */}
			<div className="px-4 py-3 border-b border-border flex items-center justify-between">
				<span className="text-small font-medium text-ink-primary">Application Logs</span>
				<div className="flex items-center gap-4">
					{/* Search */}
					<input
						type="text"
						value={search}
						onChange={e => setSearch(e.target.value)}
						placeholder="Search logs..."
						className="bg-bg-tertiary border border-border px-3 py-1 text-small w-48 text-ink-primary font-mono focus:outline-none focus:border-accent-yellow"
					/>

					{/* Level filter */}
					<div className="flex items-center gap-3">
						<span className="text-label text-ink-muted uppercase">Level</span>
						<div className="flex items-center border border-border">
							{LEVELS.map((level, idx) => (
								<button
									key={level}
									onClick={() => setLogFilter(level)}
									className={clsx(
										'px-3 py-1 text-label font-mono transition-all duration-fast',
										logFilter === level
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

					<span className="text-label text-ink-muted font-mono">{displayedLogs.length} entries</span>

					<button
						onClick={exportLogs}
						className="px-3 py-1 border border-accent-blue text-accent-blue text-label hover:bg-accent-blue hover:text-bg-primary transition-all duration-fast"
					>
						Export
					</button>
					<button
						onClick={clearLogs}
						className="px-3 py-1 border border-ink-muted text-ink-muted text-label hover:bg-ink-muted hover:text-bg-primary transition-all duration-fast"
					>
						Clear
					</button>
				</div>
			</div>

			{/* Log content */}
			<div ref={containerRef} className="flex-1 overflow-auto p-4 font-mono text-small">
				{displayedLogs.length === 0 ? (
					<p className="text-ink-muted">
						{search ? `No logs matching "${search}".` : 'No logs matching filter.'}
					</p>
				) : (
					<table className="w-full">
						<tbody>
							{displayedLogs.map((log, i) => (
								<tr key={i} className="hover:bg-bg-tertiary">
									<td className="py-0.5 pr-4 text-ink-muted whitespace-nowrap">
										{formatTime(log.timestamp)}
									</td>
									<td className={clsx('py-0.5 pr-4 whitespace-nowrap', getLevelColor(log.level))}>
										{log.level}
									</td>
									<td className="py-0.5 pr-4 text-ink-muted whitespace-nowrap">{log.logger}</td>
									<td className="py-0.5 text-ink-primary">
										{search ? (
											<HighlightedText text={log.message} search={search} />
										) : (
											log.message
										)}
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

// Helper component to highlight search matches
function HighlightedText({ text, search }: { text: string; search: string }) {
	if (!search) return <>{text}</>

	const parts = text.split(new RegExp(`(${search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi'))

	return (
		<>
			{parts.map((part, i) =>
				part.toLowerCase() === search.toLowerCase() ? (
					<span key={i} className="bg-accent-yellow/30 text-accent-yellow">{part}</span>
				) : (
					<span key={i}>{part}</span>
				)
			)}
		</>
	)
}
