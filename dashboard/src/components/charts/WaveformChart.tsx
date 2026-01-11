import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

interface Props {
	breathingWaveform?: number[]
	heartWaveform?: number[]
	width?: number
	height?: number
}

// TE color palette for light theme
const COLORS = {
	breath: '#1976D2',      // accent-blue
	heart: '#E53935',       // accent-red
	grid: '#E2E2DF',        // bg-tertiary
	axis: '#4A4A4A',        // ink-secondary
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
					stroke: COLORS.axis,
					grid: { stroke: COLORS.grid, width: 1 },
					ticks: { stroke: COLORS.grid },
					font: '10px IBM Plex Mono, monospace',
					label: 'Sample',
					labelSize: 12,
				},
				{
					scale: 'breath',
					stroke: COLORS.breath,
					grid: { stroke: COLORS.grid, width: 1 },
					ticks: { stroke: COLORS.grid },
					label: 'Breathing',
					labelSize: 12,
					font: '10px IBM Plex Mono, monospace',
					side: 3,
				},
				{
					scale: 'heart',
					stroke: COLORS.heart,
					grid: { show: false },
					ticks: { stroke: COLORS.grid },
					label: 'Heart',
					labelSize: 12,
					font: '10px IBM Plex Mono, monospace',
					side: 1,
				},
			],
			series: [
				{},
				{
					label: 'Breathing',
					scale: 'breath',
					stroke: COLORS.breath,
					width: 1.5,
					points: { show: false },
				},
				{
					label: 'Heart',
					scale: 'heart',
					stroke: COLORS.heart,
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
				className="bg-bg-secondary border border-border flex items-center justify-center"
				style={{ width, height: height + 60 }}
			>
				<span className="text-ink-muted text-small">
					Firmware waveforms not available (requires Vital Signs firmware)
				</span>
			</div>
		)
	}

	return (
		<div className="bg-bg-secondary border border-border">
			<div className="flex justify-between items-center px-4 py-3 border-b border-border">
				<span className="text-small font-medium text-ink-primary">Vital Signs Waveforms</span>
				<div className="flex items-center gap-4 text-label">
					<span className="flex items-center gap-2">
						<span className="w-4 h-[2px] bg-accent-blue"></span>
						<span className="text-accent-blue font-mono">Breathing</span>
					</span>
					<span className="flex items-center gap-2">
						<span className="w-4 h-[2px] bg-accent-red"></span>
						<span className="text-accent-red font-mono">Heart</span>
					</span>
					<span className="px-2 py-1 border border-accent-purple text-accent-purple bg-bg-tertiary text-label font-mono uppercase">
						FW
					</span>
				</div>
			</div>
			<div className="p-4" ref={containerRef} />
		</div>
	)
}
