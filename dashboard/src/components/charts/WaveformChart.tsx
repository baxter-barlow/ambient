import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

interface Props {
	breathingWaveform?: number[]
	heartWaveform?: number[]
	width?: number
	height?: number
}

export default function WaveformChart({
	breathingWaveform,
	heartWaveform,
	width = 580,
	height = 200,
}: Props) {
	const containerRef = useRef<HTMLDivElement>(null)
	const chartRef = useRef<uPlot | null>(null)

	useEffect(() => {
		if (!containerRef.current) return

		const opts: uPlot.Options = {
			width,
			height,
			scales: {
				x: { time: false },
				breath: { auto: true },
				heart: { auto: true },
			},
			axes: [
				{
					stroke: '#6b7280',
					grid: { stroke: '#2a2d32', width: 1 },
					ticks: { stroke: '#2a2d32' },
					font: '9px JetBrains Mono, monospace',
					label: 'Sample',
					labelSize: 12,
				},
				{
					scale: 'breath',
					stroke: '#3b82f6',
					grid: { stroke: '#2a2d32', width: 1 },
					ticks: { stroke: '#2a2d32' },
					label: 'Breathing',
					labelSize: 12,
					font: '9px JetBrains Mono, monospace',
					side: 3,
				},
				{
					scale: 'heart',
					stroke: '#ef4444',
					grid: { show: false },
					ticks: { stroke: '#2a2d32' },
					label: 'Heart',
					labelSize: 12,
					font: '9px JetBrains Mono, monospace',
					side: 1,
				},
			],
			series: [
				{},
				{
					label: 'Breathing',
					scale: 'breath',
					stroke: '#3b82f6',
					width: 1.5,
					points: { show: false },
				},
				{
					label: 'Heart',
					scale: 'heart',
					stroke: '#ef4444',
					width: 1.5,
					points: { show: false },
				},
			],
			legend: {
				show: false,
			},
		}

		chartRef.current = new uPlot(opts, [[], [], []], containerRef.current)

		return () => {
			chartRef.current?.destroy()
			chartRef.current = null
		}
	}, [width, height])

	useEffect(() => {
		if (!chartRef.current) return

		const breathLen = breathingWaveform?.length ?? 0
		const heartLen = heartWaveform?.length ?? 0
		const maxLen = Math.max(breathLen, heartLen)

		if (maxLen === 0) return

		const indices = Array.from({ length: maxLen }, (_, i) => i)
		const breath = breathingWaveform ?? Array(maxLen).fill(null)
		const heart = heartWaveform ?? Array(maxLen).fill(null)

		chartRef.current.setData([indices, breath, heart])
	}, [breathingWaveform, heartWaveform])

	const hasData = (breathingWaveform?.length ?? 0) > 0 || (heartWaveform?.length ?? 0) > 0

	if (!hasData) {
		return (
			<div
				className="bg-surface-2 border border-border rounded-card flex items-center justify-center"
				style={{ width, height: height + 60 }}
			>
				<span className="text-text-tertiary text-sm">
					Firmware waveforms not available (requires Vital Signs firmware)
				</span>
			</div>
		)
	}

	return (
		<div className="bg-surface-2 border border-border rounded-card overflow-hidden">
			<div className="flex justify-between items-center px-4 py-3 border-b border-border">
				<span className="text-base text-text-primary font-medium">Vital Signs Waveforms</span>
				<div className="flex items-center gap-4 text-micro">
					<span className="flex items-center gap-1.5">
						<span className="w-4 h-0.5 bg-accent-blue rounded"></span>
						<span className="text-accent-blue">Breathing</span>
					</span>
					<span className="flex items-center gap-1.5">
						<span className="w-4 h-0.5 bg-accent-red rounded"></span>
						<span className="text-accent-red">Heart</span>
					</span>
					<span className="px-1.5 py-0.5 rounded bg-accent-purple/15 text-accent-purple border border-accent-purple/25 text-micro uppercase">
						Firmware
					</span>
				</div>
			</div>
			<div className="p-4" ref={containerRef} />
		</div>
	)
}
