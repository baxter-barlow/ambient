import { memo } from 'react'
import { useAppStore } from '../stores/appStore'
import clsx from 'clsx'

/**
 * Compact horizontal vitals panel following TE design principles.
 * Shows HR, RR, and quality metrics in a dense, scannable format.
 */
export default memo(function VitalsPanel() {
	const vitals = useAppStore(s => s.vitals)
	const presence = useAppStore(s => s.presence)

	const getQualityColor = (value: number, thresholds: { good: number; warn: number }) => {
		if (value >= thresholds.good) return 'text-accent-green'
		if (value >= thresholds.warn) return 'text-accent-yellow'
		return 'text-accent-red'
	}

	const getSnrColor = (snr: number) => {
		if (snr >= 10) return 'text-accent-green'
		if (snr >= 5) return 'text-accent-yellow'
		return 'text-accent-red'
	}

	const presenceDetected = presence?.presence_detected ?? false

	return (
		<div className="h-12 bg-bg-secondary border-t border-border flex items-center px-4 gap-8 font-mono text-small">
			{/* Presence indicator */}
			<div className="flex items-center gap-2">
				<span className={clsx(
					'w-2.5 h-2.5',
					presenceDetected ? 'bg-accent-green' : 'bg-ink-muted'
				)} />
				<span className={clsx(
					'text-label uppercase',
					presenceDetected ? 'text-accent-green' : 'text-ink-muted'
				)}>
					{presenceDetected ? 'Present' : 'No Target'}
				</span>
			</div>

			{/* Divider */}
			<div className="w-px h-6 bg-border" />

			{/* Heart Rate */}
			<div className="flex items-center gap-3">
				<span className="text-accent-red text-label uppercase">HR</span>
				<span className={clsx(
					'text-h3 tabular-nums',
					vitals?.heart_rate_bpm ? 'text-ink-primary' : 'text-ink-muted'
				)}>
					{vitals?.heart_rate_bpm?.toFixed(0) ?? '--'}
				</span>
				<span className="text-ink-muted text-label">BPM</span>
				{vitals?.heart_rate_confidence !== undefined && (
					<span className={clsx(
						'text-label',
						getQualityColor(vitals.heart_rate_confidence, { good: 0.7, warn: 0.4 })
					)}>
						{(vitals.heart_rate_confidence * 100).toFixed(0)}%
					</span>
				)}
			</div>

			{/* Divider */}
			<div className="w-px h-6 bg-border" />

			{/* Respiratory Rate */}
			<div className="flex items-center gap-3">
				<span className="text-accent-blue text-label uppercase">RR</span>
				<span className={clsx(
					'text-h3 tabular-nums',
					vitals?.respiratory_rate_bpm ? 'text-ink-primary' : 'text-ink-muted'
				)}>
					{vitals?.respiratory_rate_bpm?.toFixed(0) ?? '--'}
				</span>
				<span className="text-ink-muted text-label">BPM</span>
				{vitals?.respiratory_rate_confidence !== undefined && (
					<span className={clsx(
						'text-label',
						getQualityColor(vitals.respiratory_rate_confidence, { good: 0.7, warn: 0.4 })
					)}>
						{(vitals.respiratory_rate_confidence * 100).toFixed(0)}%
					</span>
				)}
			</div>

			{/* Divider */}
			<div className="w-px h-6 bg-border" />

			{/* Quality Metrics */}
			<div className="flex items-center gap-4 text-label">
				{/* HR SNR */}
				<div className="flex items-center gap-1.5">
					<span className="text-ink-muted uppercase">HR SNR</span>
					<span className={clsx(
						'tabular-nums',
						getSnrColor(vitals?.hr_snr_db ?? 0)
					)}>
						{vitals?.hr_snr_db?.toFixed(1) ?? '--'} dB
					</span>
				</div>

				{/* RR SNR */}
				<div className="flex items-center gap-1.5">
					<span className="text-ink-muted uppercase">RR SNR</span>
					<span className={clsx(
						'tabular-nums',
						getSnrColor(vitals?.rr_snr_db ?? 0)
					)}>
						{vitals?.rr_snr_db?.toFixed(1) ?? '--'} dB
					</span>
				</div>

				{/* Phase Stability */}
				<div className="flex items-center gap-1.5">
					<span className="text-ink-muted uppercase">Phase</span>
					<span className={clsx(
						'tabular-nums',
						getQualityColor(vitals?.phase_stability ?? 0, { good: 0.8, warn: 0.5 })
					)}>
						{vitals?.phase_stability?.toFixed(2) ?? '--'}
					</span>
				</div>

				{/* Signal Quality */}
				<div className="flex items-center gap-1.5">
					<span className="text-ink-muted uppercase">Quality</span>
					<span className={clsx(
						'tabular-nums',
						getQualityColor(vitals?.signal_quality ?? 0, { good: 0.7, warn: 0.4 })
					)}>
						{vitals?.signal_quality !== undefined
							? (vitals.signal_quality * 100).toFixed(0) + '%'
							: '--'}
					</span>
				</div>
			</div>

			{/* Spacer */}
			<div className="flex-1" />

			{/* Motion indicator */}
			{vitals?.motion_detected && (
				<div className="flex items-center gap-2">
					<span className="w-2 h-2 bg-accent-orange animate-pulse" />
					<span className="text-accent-orange text-label uppercase">Motion</span>
				</div>
			)}

			{/* Source indicator */}
			{vitals?.source && (
				<div className="flex items-center gap-1.5 text-label">
					<span className="text-ink-muted uppercase">SRC</span>
					<span className="text-ink-secondary uppercase">{vitals.source}</span>
				</div>
			)}
		</div>
	)
})
