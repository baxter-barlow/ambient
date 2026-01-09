import { useMemo } from 'react'
import { useAppStore } from '../stores/appStore'
import RangeProfile from '../components/charts/RangeProfile'
import PhaseSignal from '../components/charts/PhaseSignal'
import VitalsChart from '../components/charts/VitalsChart'
import QualityMetricsChart from '../components/charts/QualityMetricsChart'
import RangeDoppler from '../components/charts/RangeDoppler'
import WaveformChart from '../components/charts/WaveformChart'
import Button from '../components/common/Button'
import clsx from 'clsx'

const TIME_WINDOWS = [
	{ value: 5, label: '5s' },
	{ value: 30, label: '30s' },
	{ value: 60, label: '1m' },
	{ value: 300, label: '5m' },
]

export default function SignalViewer() {
	const sensorFrames = useAppStore(s => s.sensorFrames)
	const vitals = useAppStore(s => s.vitals)
	const vitalsHistory = useAppStore(s => s.vitalsHistory)
	const isPaused = useAppStore(s => s.isPaused)
	const togglePause = useAppStore(s => s.togglePause)
	const timeWindow = useAppStore(s => s.timeWindow)
	const setTimeWindow = useAppStore(s => s.setTimeWindow)
	const deviceStatus = useAppStore(s => s.deviceStatus)

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

	// Quality metrics data for trending chart
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

	// Calculate stability percentage for progress bar (inverse - lower is better)
	const stabilityPercent = vitals?.phase_stability !== undefined
		? Math.max(0, Math.min(100, (1 - vitals.phase_stability / 2) * 100))
		: 50

	// Get stability color based on value
	const getStabilityColor = (val: number | undefined) => {
		if (val === undefined) return 'bg-text-tertiary'
		if (val < 0.5) return 'bg-accent-green'
		if (val < 1.0) return 'bg-accent-amber'
		return 'bg-accent-red'
	}

	// Get signal quality color
	const getQualityColor = (val: number) => {
		if (val >= 0.7) return 'text-accent-green'
		if (val >= 0.4) return 'text-accent-amber'
		return 'text-accent-red'
	}

	return (
		<div className="space-y-5">
			{/* Page header */}
			<div className="flex items-center justify-between">
				<h2 className="text-xl text-text-primary">Real-Time Signal Viewer</h2>
				<div className="flex items-center gap-4">
					{/* Time window selector */}
					<div className="flex items-center gap-2">
						<span className="text-sm text-text-secondary">Window:</span>
						<div className="flex items-center gap-1.5">
							{TIME_WINDOWS.map(tw => (
								<button
									key={tw.value}
									onClick={() => setTimeWindow(tw.value)}
									className={clsx(
										'px-2.5 py-1 text-xs rounded transition-colors duration-150',
										timeWindow === tw.value
											? 'bg-accent-teal text-text-inverse font-semibold'
											: 'bg-surface-3 text-text-secondary hover:bg-surface-4'
									)}
								>
									{tw.label}
								</button>
							))}
						</div>
					</div>

					{/* Pause/Resume toggle */}
					<Button
						variant="toggle"
						active={!isPaused}
						size="sm"
						onClick={togglePause}
						className="flex items-center gap-2"
					>
						<span className={clsx(
							'w-1.5 h-1.5 rounded-full',
							isPaused ? 'bg-text-tertiary' : 'bg-accent-teal'
						)} />
						{isPaused ? 'Paused' : 'Live'}
					</Button>
				</div>
			</div>

			{/* Warning banner when not streaming */}
			{!isStreaming && (
				<div className="p-3 rounded bg-accent-amber/12 border border-accent-amber/25 text-accent-amber text-sm flex items-center gap-2.5">
					<span className="text-base">!</span>
					Device is not streaming. Connect to the sensor to view real-time data.
				</div>
			)}

			{/* Vitals Display Card */}
			{vitals && (
				<div className="bg-surface-2 border border-border rounded-card">
					<div className="flex items-center justify-between px-4 py-3 border-b border-border">
						<span className="text-base text-text-primary font-medium">Vital Signs</span>
						<span className={clsx(
							'px-2 py-0.5 rounded text-micro font-semibold uppercase tracking-wide',
							vitals.source === 'firmware'
								? 'bg-accent-green/15 text-accent-green border border-accent-green/25'
								: vitals.source === 'chirp'
								? 'bg-accent-teal/15 text-accent-teal border border-accent-teal/25'
								: 'bg-accent-amber/15 text-accent-amber border border-accent-amber/25'
						)}>
							{vitals.source === 'firmware' ? 'Firmware' : vitals.source === 'chirp' ? 'Chirp' : 'Estimated'}
						</span>
					</div>
					<div className="p-4">
						{/* Primary Vitals Row */}
						<div className="grid grid-cols-4 gap-6">
							{/* Heart Rate */}
							<div>
								<span className="text-sm text-text-secondary">Heart Rate</span>
								<p className="text-metric-lg font-mono text-accent-red mt-1">
									{vitals.heart_rate_bpm?.toFixed(0) ?? '--'}
									<span className="text-sm text-text-tertiary ml-1">BPM</span>
								</p>
								<div className="mt-2 h-1 bg-surface-3 rounded overflow-hidden">
									<div
										className="h-full bg-accent-red transition-all duration-300"
										style={{ width: `${vitals.heart_rate_confidence * 100}%` }}
									/>
								</div>
								<span className="text-xs font-mono text-text-tertiary">
									{(vitals.heart_rate_confidence * 100).toFixed(0)}% conf
									{vitals.hr_snr_db !== undefined && vitals.hr_snr_db > 0 && (
										<span className="ml-1.5 text-accent-teal">
											{vitals.hr_snr_db.toFixed(1)} dB
										</span>
									)}
								</span>
							</div>

							{/* Respiratory Rate */}
							<div>
								<span className="text-sm text-text-secondary">Respiratory Rate</span>
								<p className="text-metric-lg font-mono text-accent-blue mt-1">
									{vitals.respiratory_rate_bpm?.toFixed(0) ?? '--'}
									<span className="text-sm text-text-tertiary ml-1">BPM</span>
								</p>
								<div className="mt-2 h-1 bg-surface-3 rounded overflow-hidden">
									<div
										className="h-full bg-accent-blue transition-all duration-300"
										style={{ width: `${vitals.respiratory_rate_confidence * 100}%` }}
									/>
								</div>
								<span className="text-xs font-mono text-text-tertiary">
									{(vitals.respiratory_rate_confidence * 100).toFixed(0)}% conf
									{vitals.rr_snr_db !== undefined && vitals.rr_snr_db > 0 && (
										<span className="ml-1.5 text-accent-teal">
											{vitals.rr_snr_db.toFixed(1)} dB
										</span>
									)}
								</span>
							</div>

							{/* Signal Quality - Enhanced */}
							<div>
								<span className="text-sm text-text-secondary">Signal Quality</span>
								<p className={clsx(
									'text-metric-lg font-mono mt-1',
									getQualityColor(vitals.signal_quality)
								)}>
									{(vitals.signal_quality * 100).toFixed(0)}%
								</p>
								<div className="mt-2 h-1 bg-surface-3 rounded overflow-hidden">
									<div
										className={clsx(
											'h-full transition-all duration-300',
											vitals.signal_quality >= 0.7 ? 'bg-accent-green' :
											vitals.signal_quality >= 0.4 ? 'bg-accent-amber' : 'bg-accent-red'
										)}
										style={{ width: `${vitals.signal_quality * 100}%` }}
									/>
								</div>
								{vitals.signal_quality < 0.4 && (
									<span className="text-xs text-accent-red">
										Low signal - check positioning
									</span>
								)}
							</div>

							{/* Phase Stability - Enhanced with progress bar */}
							<div>
								<span className="text-sm text-text-secondary">Phase Stability</span>
								<p className={clsx(
									'text-metric-lg font-mono mt-1',
									vitals.phase_stability !== undefined && vitals.phase_stability < 0.5
										? 'text-accent-green'
										: vitals.phase_stability !== undefined && vitals.phase_stability < 1.0
										? 'text-accent-amber'
										: 'text-accent-red'
								)}>
									{vitals.phase_stability !== undefined
										? vitals.phase_stability < 0.5 ? 'Good'
										: vitals.phase_stability < 1.0 ? 'Fair' : 'Poor'
										: '--'}
								</p>
								<div className="mt-2 h-1 bg-surface-3 rounded overflow-hidden">
									<div
										className={clsx(
											'h-full transition-all duration-300',
											getStabilityColor(vitals.phase_stability)
										)}
										style={{ width: `${stabilityPercent}%` }}
									/>
								</div>
								<span className="text-xs font-mono text-text-tertiary">
									{vitals.phase_stability?.toFixed(3) ?? '--'}
									{vitals.motion_detected && (
										<span className="ml-1.5 text-accent-amber">Motion!</span>
									)}
								</span>
							</div>
						</div>
					</div>
				</div>
			)}

			{/* Charts Grid */}
			<div className="grid grid-cols-2 gap-4">
				<RangeProfile
					data={latestFrame?.range_profile ?? []}
					width={580}
					height={280}
				/>
				<RangeDoppler
					data={latestFrame?.range_doppler}
					width={280}
					height={280}
					isChirpFirmware={latestFrame?.is_chirp_firmware}
				/>
				<PhaseSignal
					timestamps={phaseData.timestamps}
					phases={phaseData.phases}
					width={580}
					height={280}
				/>
				<VitalsChart
					timestamps={vitalsData.timestamps}
					heartRates={vitalsData.heartRates}
					respiratoryRates={vitalsData.respiratoryRates}
					width={580}
					height={280}
				/>
			</div>

			{/* Quality Metrics Trend Chart */}
			{vitalsHistory.length > 0 && (
				<QualityMetricsChart
					timestamps={qualityData.timestamps}
					hrSnrDb={qualityData.hrSnrDb}
					rrSnrDb={qualityData.rrSnrDb}
					phaseStability={qualityData.phaseStability}
					signalQuality={qualityData.signalQuality}
					width={1180}
					height={200}
				/>
			)}

			{/* Firmware Waveforms (only shown when using vital signs firmware) */}
			{vitals?.source === 'firmware' && (
				<div className="mt-4">
					<WaveformChart
						breathingWaveform={vitals.breathing_waveform}
						heartWaveform={vitals.heart_waveform}
						width={1180}
						height={250}
					/>
				</div>
			)}

			{/* Chirp Waveforms (shown when using chirp firmware with waveform data) */}
			{vitals?.source === 'chirp' && (vitals.breathing_waveform || vitals.heart_waveform) && (
				<div className="mt-4">
					<WaveformChart
						breathingWaveform={vitals.breathing_waveform}
						heartWaveform={vitals.heart_waveform}
						width={1180}
						height={250}
					/>
				</div>
			)}
		</div>
	)
}
