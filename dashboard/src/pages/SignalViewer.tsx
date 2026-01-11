import { useMemo } from 'react'
import { useAppStore } from '../stores/appStore'
import RangeProfile from '../components/charts/RangeProfile'
import PhaseSignal from '../components/charts/PhaseSignal'
import VitalsChart from '../components/charts/VitalsChart'
import QualityMetricsChart from '../components/charts/QualityMetricsChart'
import RangeDoppler from '../components/charts/RangeDoppler'
import WaveformChart from '../components/charts/WaveformChart'
import clsx from 'clsx'

const TIME_WINDOWS = [
	{ value: 5, label: '5s' },
	{ value: 30, label: '30s' },
	{ value: 60, label: '1m' },
	{ value: 300, label: '5m' },
]

/**
 * Signal Viewer page following TE design principles:
 * - Borders as primary hierarchy tool
 * - Monospace for all data values
 * - Square indicators, no rounded corners
 * - One accent per chart, neutrals for everything else
 */
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

	// Stability percentage (inverse - lower is better)
	const stabilityPercent = vitals?.phase_stability !== undefined
		? Math.max(0, Math.min(100, (1 - vitals.phase_stability / 2) * 100))
		: 50

	const getStabilityColor = (val: number | undefined) => {
		if (val === undefined) return 'bg-ink-muted'
		if (val < 0.5) return 'bg-accent-green'
		if (val < 1.0) return 'bg-accent-orange'
		return 'bg-accent-red'
	}

	const getQualityColor = (val: number) => {
		if (val >= 0.7) return 'text-accent-green'
		if (val >= 0.4) return 'text-accent-orange'
		return 'text-accent-red'
	}

	return (
		<div className="space-y-6 max-w-6xl">
			{/* Page header */}
			<div className="flex items-center justify-between">
				<h2 className="text-h2 text-ink-primary">Signal Viewer</h2>
				<div className="flex items-center gap-6">
					{/* Time window selector */}
					<div className="flex items-center gap-3">
						<span className="text-label text-ink-muted uppercase">Window</span>
						<div className="flex items-center border border-border">
							{TIME_WINDOWS.map((tw, idx) => (
								<button
									key={tw.value}
									onClick={() => setTimeWindow(tw.value)}
									className={clsx(
										'px-3 py-1 text-label font-mono transition-all duration-fast',
										timeWindow === tw.value
											? 'bg-ink-primary text-bg-primary'
											: 'bg-bg-secondary text-ink-secondary hover:bg-bg-tertiary',
										idx > 0 && 'border-l border-border'
									)}
								>
									{tw.label}
								</button>
							))}
						</div>
					</div>

					{/* Pause/Resume toggle */}
					<button
						onClick={togglePause}
						className={clsx(
							'flex items-center gap-2 px-4 py-2 border transition-all duration-fast',
							isPaused
								? 'bg-bg-secondary border-border text-ink-secondary hover:bg-bg-tertiary'
								: 'bg-accent-green border-accent-green text-bg-primary'
						)}
					>
						<div className={clsx(
							'w-2 h-2',
							isPaused ? 'bg-ink-muted' : 'bg-bg-primary'
						)} />
						<span className="text-small font-medium uppercase">
							{isPaused ? 'Paused' : 'Live'}
						</span>
					</button>
				</div>
			</div>

			{/* Warning banner when not streaming */}
			{!isStreaming && (
				<div className="p-4 border-l-4 border-l-accent-orange border border-border bg-bg-secondary flex items-center gap-3">
					<div className="w-3 h-3 bg-accent-orange" />
					<span className="text-small text-ink-primary">
						Device is not streaming. Connect to the sensor to view real-time data.
					</span>
				</div>
			)}

			{/* Vitals Display Card */}
			{vitals && (
				<div className="bg-bg-secondary border border-border">
					<div className="flex items-center justify-between px-4 py-3 border-b border-border">
						<span className="text-small font-medium text-ink-primary">Vital Signs</span>
						<span className={clsx(
							'px-2 py-1 text-label font-mono uppercase border',
							vitals.source === 'firmware'
								? 'border-accent-green text-accent-green bg-bg-tertiary'
								: vitals.source === 'chirp'
								? 'border-accent-blue text-accent-blue bg-bg-tertiary'
								: 'border-accent-orange text-accent-orange bg-bg-tertiary'
						)}>
							{vitals.source === 'firmware' ? 'FW' : vitals.source === 'chirp' ? 'CHIRP' : 'EST'}
						</span>
					</div>
					<div className="p-4">
						{/* Primary Vitals Row */}
						<div className="grid grid-cols-4 gap-6">
							{/* Heart Rate */}
							<div>
								<span className="text-label text-ink-muted block mb-1">HEART RATE</span>
								<p className="font-mono text-h2 text-accent-red">
									{vitals.heart_rate_bpm?.toFixed(0) ?? '--'}
									<span className="text-small text-ink-muted ml-1">BPM</span>
								</p>
								<div className="mt-2 h-1 bg-bg-tertiary">
									<div
										className="h-full bg-accent-red transition-all duration-150"
										style={{ width: `${vitals.heart_rate_confidence * 100}%` }}
									/>
								</div>
								<span className="text-label font-mono text-ink-muted">
									{(vitals.heart_rate_confidence * 100).toFixed(0)}% conf
									{vitals.hr_snr_db !== undefined && vitals.hr_snr_db > 0 && (
										<span className="ml-2 text-accent-blue">
											{vitals.hr_snr_db.toFixed(1)} dB
										</span>
									)}
								</span>
							</div>

							{/* Respiratory Rate */}
							<div>
								<span className="text-label text-ink-muted block mb-1">RESPIRATORY RATE</span>
								<p className="font-mono text-h2 text-accent-blue">
									{vitals.respiratory_rate_bpm?.toFixed(0) ?? '--'}
									<span className="text-small text-ink-muted ml-1">BPM</span>
								</p>
								<div className="mt-2 h-1 bg-bg-tertiary">
									<div
										className="h-full bg-accent-blue transition-all duration-150"
										style={{ width: `${vitals.respiratory_rate_confidence * 100}%` }}
									/>
								</div>
								<span className="text-label font-mono text-ink-muted">
									{(vitals.respiratory_rate_confidence * 100).toFixed(0)}% conf
									{vitals.rr_snr_db !== undefined && vitals.rr_snr_db > 0 && (
										<span className="ml-2 text-accent-blue">
											{vitals.rr_snr_db.toFixed(1)} dB
										</span>
									)}
								</span>
							</div>

							{/* Signal Quality */}
							<div>
								<span className="text-label text-ink-muted block mb-1">SIGNAL QUALITY</span>
								<p className={clsx(
									'font-mono text-h2',
									getQualityColor(vitals.signal_quality)
								)}>
									{(vitals.signal_quality * 100).toFixed(0)}%
								</p>
								<div className="mt-2 h-1 bg-bg-tertiary">
									<div
										className={clsx(
											'h-full transition-all duration-150',
											vitals.signal_quality >= 0.7 ? 'bg-accent-green' :
											vitals.signal_quality >= 0.4 ? 'bg-accent-orange' : 'bg-accent-red'
										)}
										style={{ width: `${vitals.signal_quality * 100}%` }}
									/>
								</div>
								{vitals.signal_quality < 0.4 && (
									<span className="text-label text-accent-red">
										Low signal - check positioning
									</span>
								)}
							</div>

							{/* Phase Stability */}
							<div>
								<span className="text-label text-ink-muted block mb-1">PHASE STABILITY</span>
								<p className={clsx(
									'font-mono text-h2',
									vitals.phase_stability !== undefined && vitals.phase_stability < 0.5
										? 'text-accent-green'
										: vitals.phase_stability !== undefined && vitals.phase_stability < 1.0
										? 'text-accent-orange'
										: 'text-accent-red'
								)}>
									{vitals.phase_stability !== undefined
										? vitals.phase_stability < 0.5 ? 'GOOD'
										: vitals.phase_stability < 1.0 ? 'FAIR' : 'POOR'
										: '--'}
								</p>
								<div className="mt-2 h-1 bg-bg-tertiary">
									<div
										className={clsx(
											'h-full transition-all duration-150',
											getStabilityColor(vitals.phase_stability)
										)}
										style={{ width: `${stabilityPercent}%` }}
									/>
								</div>
								<span className="text-label font-mono text-ink-muted">
									{vitals.phase_stability?.toFixed(3) ?? '--'}
									{vitals.motion_detected && (
										<span className="ml-2 text-accent-orange">MOTION</span>
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
					source={latestFrame?.range_profile_source}
					isChirpFirmware={latestFrame?.is_chirp_firmware}
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

			{/* Firmware Waveforms */}
			{vitals?.source === 'firmware' && (
				<WaveformChart
					breathingWaveform={vitals.breathing_waveform}
					heartWaveform={vitals.heart_waveform}
					width={1180}
					height={250}
				/>
			)}

			{/* Chirp Waveforms */}
			{vitals?.source === 'chirp' && (vitals.breathing_waveform || vitals.heart_waveform) && (
				<WaveformChart
					breathingWaveform={vitals.breathing_waveform}
					heartWaveform={vitals.heart_waveform}
					width={1180}
					height={250}
				/>
			)}
		</div>
	)
}
