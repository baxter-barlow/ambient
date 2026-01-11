import { useMemo } from 'react'
import clsx from 'clsx'
import ChartContainer from '../common/ChartContainer'
import type { VitalsQualityMetrics, VitalSigns, MultiPatientVitals } from '../../types'

interface Props {
	vitals: VitalSigns | null
	qualityMetrics?: VitalsQualityMetrics | null
	multiPatientVitals?: MultiPatientVitals | null
	width?: number
	height?: number
	isLoading?: boolean
}

// Quality level thresholds
const QUALITY_THRESHOLDS = {
	snr: { good: 10, fair: 5 },      // dB
	confidence: { good: 0.7, fair: 0.4 },
	stability: { good: 0.5, fair: 1.0 }, // Lower is better
	quality: { good: 0.7, fair: 0.4 },
}

type QualityLevel = 'good' | 'fair' | 'poor' | 'unknown'

function getQualityLevel(
	value: number | undefined | null,
	thresholds: { good: number; fair: number },
	lowerIsBetter: boolean = false,
): QualityLevel {
	if (value === undefined || value === null) return 'unknown'

	if (lowerIsBetter) {
		if (value <= thresholds.good) return 'good'
		if (value <= thresholds.fair) return 'fair'
		return 'poor'
	}

	if (value >= thresholds.good) return 'good'
	if (value >= thresholds.fair) return 'fair'
	return 'poor'
}

function QualityBadge({ level, label }: { level: QualityLevel; label: string }) {
	return (
		<span
			className={clsx(
				'px-2 py-0.5 rounded text-xs font-medium uppercase tracking-wide',
				{
					'bg-accent-green/20 text-accent-green': level === 'good',
					'bg-accent-amber/20 text-accent-amber': level === 'fair',
					'bg-accent-red/20 text-accent-red': level === 'poor',
					'bg-surface-hover text-text-tertiary': level === 'unknown',
				}
			)}
		>
			{label}
		</span>
	)
}

function MetricRow({
	label,
	value,
	unit,
	level,
	showBadge = true,
}: {
	label: string
	value: string | number
	unit?: string
	level: QualityLevel
	showBadge?: boolean
}) {
	return (
		<div className="flex items-center justify-between py-1.5 border-b border-border last:border-0">
			<span className="text-text-secondary text-sm">{label}</span>
			<div className="flex items-center gap-2">
				<span
					className={clsx('font-mono text-sm', {
						'text-accent-green': level === 'good',
						'text-accent-amber': level === 'fair',
						'text-accent-red': level === 'poor',
						'text-text-tertiary': level === 'unknown',
					})}
				>
					{value}
					{unit && <span className="text-text-tertiary ml-1">{unit}</span>}
				</span>
				{showBadge && <QualityBadge level={level} label={level} />}
			</div>
		</div>
	)
}

function StatusIndicator({
	active,
	label,
	colorActive = 'bg-accent-green',
	colorInactive = 'bg-surface-hover',
}: {
	active: boolean
	label: string
	colorActive?: string
	colorInactive?: string
}) {
	return (
		<div className="flex items-center gap-2">
			<div
				className={clsx(
					'w-2 h-2 rounded-full',
					active ? colorActive : colorInactive
				)}
			/>
			<span className={clsx('text-xs', active ? 'text-text-primary' : 'text-text-tertiary')}>
				{label}
			</span>
		</div>
	)
}

function OverallQualityGauge({ quality }: { quality: number }) {
	const percentage = Math.round(quality * 100)
	const level = getQualityLevel(quality, QUALITY_THRESHOLDS.quality)

	return (
		<div className="flex flex-col items-center">
			<div className="relative w-24 h-24">
				{/* Background circle */}
				<svg className="w-full h-full transform -rotate-90">
					<circle
						cx="48"
						cy="48"
						r="40"
						fill="none"
						stroke="currentColor"
						strokeWidth="8"
						className="text-surface-hover"
					/>
					{/* Progress circle */}
					<circle
						cx="48"
						cy="48"
						r="40"
						fill="none"
						stroke="currentColor"
						strokeWidth="8"
						strokeDasharray={`${quality * 251.2} 251.2`}
						strokeLinecap="round"
						className={clsx({
							'text-accent-green': level === 'good',
							'text-accent-amber': level === 'fair',
							'text-accent-red': level === 'poor',
							'text-text-tertiary': level === 'unknown',
						})}
					/>
				</svg>
				{/* Center text */}
				<div className="absolute inset-0 flex flex-col items-center justify-center">
					<span
						className={clsx('text-2xl font-bold', {
							'text-accent-green': level === 'good',
							'text-accent-amber': level === 'fair',
							'text-accent-red': level === 'poor',
							'text-text-tertiary': level === 'unknown',
						})}
					>
						{percentage}
					</span>
					<span className="text-xs text-text-tertiary">%</span>
				</div>
			</div>
			<span className="mt-2 text-sm text-text-secondary">Signal Quality</span>
		</div>
	)
}

export default function QualityMetricsDashboard({
	vitals,
	qualityMetrics,
	multiPatientVitals,
	width = 400,
	height = 300,
	isLoading = false,
}: Props) {
	// Derive metrics from vitals if qualityMetrics not provided
	const metrics = useMemo(() => {
		if (qualityMetrics) return qualityMetrics

		if (vitals) {
			return {
				hr_snr_db: vitals.hr_snr_db ?? 0,
				rr_snr_db: vitals.rr_snr_db ?? 0,
				hr_confidence: vitals.heart_rate_confidence,
				rr_confidence: vitals.respiratory_rate_confidence,
				phase_stability: vitals.phase_stability ?? 0,
				motion_detected: vitals.motion_detected,
				patient_present: true,
				holding_breath: false,
				signal_quality: vitals.signal_quality,
			}
		}

		return null
	}, [vitals, qualityMetrics])

	const isEmpty = !metrics && !isLoading

	// Calculate quality levels
	const hrSnrLevel = getQualityLevel(metrics?.hr_snr_db, QUALITY_THRESHOLDS.snr)
	const rrSnrLevel = getQualityLevel(metrics?.rr_snr_db, QUALITY_THRESHOLDS.snr)
	const hrConfLevel = getQualityLevel(metrics?.hr_confidence, QUALITY_THRESHOLDS.confidence)
	const rrConfLevel = getQualityLevel(metrics?.rr_confidence, QUALITY_THRESHOLDS.confidence)
	const stabilityLevel = getQualityLevel(metrics?.phase_stability, QUALITY_THRESHOLDS.stability, true)
	// qualityLevel is used inside OverallQualityGauge via metrics?.signal_quality

	return (
		<ChartContainer
			title="Quality Metrics"
			subtitle={vitals?.source ? `Source: ${vitals.source}` : undefined}
			isLoading={isLoading}
			isEmpty={isEmpty}
			emptyMessage="Waiting for quality metrics..."
			loadingMessage="Loading quality metrics..."
			width={width}
			height={height}
		>
			<div className="p-3 space-y-4">
				{/* Top section: Overall quality gauge + status indicators */}
				<div className="flex items-start justify-between">
					<OverallQualityGauge quality={metrics?.signal_quality ?? 0} />

					<div className="flex flex-col gap-2">
						<StatusIndicator
							active={metrics?.patient_present ?? false}
							label="Patient Present"
							colorActive="bg-accent-green"
						/>
						<StatusIndicator
							active={metrics?.motion_detected ?? false}
							label="Motion Detected"
							colorActive="bg-accent-amber"
						/>
						<StatusIndicator
							active={metrics?.holding_breath ?? false}
							label="Holding Breath"
							colorActive="bg-accent-blue"
						/>
						{multiPatientVitals && (
							<StatusIndicator
								active={multiPatientVitals.active_count > 0}
								label={`${multiPatientVitals.active_count} Patient${multiPatientVitals.active_count !== 1 ? 's' : ''}`}
								colorActive="bg-accent-teal"
							/>
						)}
					</div>
				</div>

				{/* Metrics grid */}
				<div className="grid grid-cols-2 gap-x-4">
					{/* Heart Rate metrics */}
					<div>
						<h4 className="text-xs font-medium text-text-tertiary uppercase tracking-wide mb-1">
							Heart Rate
						</h4>
						<MetricRow
							label="SNR"
							value={(metrics?.hr_snr_db ?? 0).toFixed(1)}
							unit="dB"
							level={hrSnrLevel}
						/>
						<MetricRow
							label="Confidence"
							value={Math.round((metrics?.hr_confidence ?? 0) * 100)}
							unit="%"
							level={hrConfLevel}
						/>
					</div>

					{/* Respiratory Rate metrics */}
					<div>
						<h4 className="text-xs font-medium text-text-tertiary uppercase tracking-wide mb-1">
							Respiratory Rate
						</h4>
						<MetricRow
							label="SNR"
							value={(metrics?.rr_snr_db ?? 0).toFixed(1)}
							unit="dB"
							level={rrSnrLevel}
						/>
						<MetricRow
							label="Confidence"
							value={Math.round((metrics?.rr_confidence ?? 0) * 100)}
							unit="%"
							level={rrConfLevel}
						/>
					</div>
				</div>

				{/* Phase stability */}
				<div>
					<MetricRow
						label="Phase Stability"
						value={(metrics?.phase_stability ?? 0).toFixed(2)}
						unit="rad"
						level={stabilityLevel}
					/>
				</div>

				{/* Multi-patient summary if available */}
				{multiPatientVitals && multiPatientVitals.patients.length > 0 && (
					<div className="border-t border-border pt-3">
						<h4 className="text-xs font-medium text-text-tertiary uppercase tracking-wide mb-2">
							Multi-Patient Status
						</h4>
						<div className="space-y-1">
							{multiPatientVitals.patients.map((patient) => (
								<div
									key={patient.patient_id}
									className="flex items-center justify-between text-sm"
								>
									<span className="text-text-secondary">
										Patient {patient.patient_id + 1}
									</span>
									<div className="flex items-center gap-2">
										<span className={clsx('font-mono', {
											'text-accent-green': patient.status === 'present',
											'text-accent-amber': patient.status === 'holding_breath',
											'text-text-tertiary': patient.status === 'not_detected',
										})}>
											{patient.status === 'present' && patient.heart_rate_bpm
												? `${Math.round(patient.heart_rate_bpm)} bpm`
												: patient.status.replace('_', ' ')}
										</span>
										<QualityBadge
											level={patient.status === 'present' ? 'good' : patient.status === 'holding_breath' ? 'fair' : 'poor'}
											label={patient.status === 'present' ? 'OK' : patient.status === 'holding_breath' ? 'HOLD' : 'N/A'}
										/>
									</div>
								</div>
							))}
						</div>
					</div>
				)}
			</div>
		</ChartContainer>
	)
}
