import { useMemo } from 'react'
import { useAppStore } from '../stores/appStore'
import RangeProfile from '../components/charts/RangeProfile'
import PhaseSignal from '../components/charts/PhaseSignal'
import VitalsChart from '../components/charts/VitalsChart'
import RangeDoppler from '../components/charts/RangeDoppler'
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

	const isStreaming = deviceStatus?.state === 'streaming'

	return (
		<div className="space-y-4">
			<div className="flex items-center justify-between">
				<h2 className="text-xl font-semibold">Real-Time Signal Viewer</h2>
				<div className="flex items-center gap-4">
					{/* Time window selector */}
					<div className="flex items-center gap-2">
						<span className="text-sm text-gray-400">Window:</span>
						{TIME_WINDOWS.map(tw => (
							<button
								key={tw.value}
								onClick={() => setTimeWindow(tw.value)}
								className={clsx(
									'px-2 py-1 text-sm rounded',
									timeWindow === tw.value
										? 'bg-radar-600 text-white'
										: 'bg-gray-700 text-gray-300 hover:bg-gray-600'
								)}
							>
								{tw.label}
							</button>
						))}
					</div>

					{/* Pause/Resume */}
					<Button
						variant={isPaused ? 'primary' : 'secondary'}
						size="sm"
						onClick={togglePause}
					>
						{isPaused ? 'Resume' : 'Pause'}
					</Button>
				</div>
			</div>

			{!isStreaming && (
				<div className="bg-yellow-900/30 border border-yellow-700 rounded p-4 text-yellow-200 text-sm">
					Device is not streaming. Connect to the sensor to view real-time data.
				</div>
			)}

			{/* Vitals Display */}
			{vitals && (
				<div className="bg-gray-800 rounded-lg p-4">
					<div className="grid grid-cols-4 gap-6">
						<div>
							<span className="text-sm text-gray-400">Heart Rate</span>
							<p className="text-3xl font-mono text-red-400">
								{vitals.heart_rate_bpm?.toFixed(0) ?? '--'}
								<span className="text-lg ml-1">BPM</span>
							</p>
							<div className="mt-1 h-1 bg-gray-700 rounded overflow-hidden">
								<div
									className="h-full bg-red-500 transition-all"
									style={{ width: `${vitals.heart_rate_confidence * 100}%` }}
								/>
							</div>
						</div>
						<div>
							<span className="text-sm text-gray-400">Respiratory Rate</span>
							<p className="text-3xl font-mono text-blue-400">
								{vitals.respiratory_rate_bpm?.toFixed(0) ?? '--'}
								<span className="text-lg ml-1">BPM</span>
							</p>
							<div className="mt-1 h-1 bg-gray-700 rounded overflow-hidden">
								<div
									className="h-full bg-blue-500 transition-all"
									style={{ width: `${vitals.respiratory_rate_confidence * 100}%` }}
								/>
							</div>
						</div>
						<div>
							<span className="text-sm text-gray-400">Signal Quality</span>
							<p className="text-3xl font-mono text-radar-400">
								{(vitals.signal_quality * 100).toFixed(0)}%
							</p>
						</div>
						<div>
							<span className="text-sm text-gray-400">Motion</span>
							<p className={clsx(
								'text-3xl font-mono',
								vitals.motion_detected ? 'text-yellow-400' : 'text-gray-400'
							)}>
								{vitals.motion_detected ? 'Detected' : 'None'}
							</p>
						</div>
					</div>
				</div>
			)}

			{/* Charts Grid */}
			<div className="grid grid-cols-2 gap-4">
				<RangeProfile
					data={latestFrame?.range_profile ?? []}
					width={550}
					height={200}
				/>
				<RangeDoppler
					data={latestFrame?.range_doppler}
					width={250}
					height={200}
				/>
				<PhaseSignal
					timestamps={phaseData.timestamps}
					phases={phaseData.phases}
					width={550}
					height={200}
				/>
				<VitalsChart
					timestamps={vitalsData.timestamps}
					heartRates={vitalsData.heartRates}
					respiratoryRates={vitalsData.respiratoryRates}
					width={550}
					height={200}
				/>
			</div>
		</div>
	)
}
