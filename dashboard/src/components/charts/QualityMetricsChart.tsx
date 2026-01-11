import { useEffect, useRef, useState, useCallback } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import ChartContainer from '../common/ChartContainer'

interface Props {
	timestamps: number[]
	hrSnrDb: number[]
	rrSnrDb: number[]
	phaseStability: number[]
	signalQuality: number[]
	width?: number
	height?: number
	isLoading?: boolean
}

interface CursorData {
	time: number
	hrSnr: number
	rrSnr: number
	stability: number
	quality: number
}

// TE color palette for light theme
const COLORS = {
	hr: '#E53935',          // accent-red
	rr: '#1976D2',          // accent-blue
	stability: '#F57C00',   // accent-orange
	quality: '#2E7D32',     // accent-green
	grid: '#E2E2DF',        // bg-tertiary
	axis: '#4A4A4A',        // ink-secondary
}

export default function QualityMetricsChart({
	timestamps,
	hrSnrDb,
	rrSnrDb,
	phaseStability,
	signalQuality,
	width = 600,
	height = 200,
	isLoading = false,
}: Props) {
	const containerRef = useRef<HTMLDivElement>(null)
	const chartRef = useRef<uPlot | null>(null)
	const [cursorData, setCursorData] = useState<CursorData | null>(null)

	const handleCursor = useCallback((u: uPlot) => {
		const idx = u.cursor.idx
		if (idx != null && u.data[0]) {
			const time = u.data[0][idx]
			const hrSnr = u.data[1]?.[idx] ?? 0
			const rrSnr = u.data[2]?.[idx] ?? 0
			const stability = u.data[3]?.[idx] ?? 0
			const quality = u.data[4]?.[idx] ?? 0
			if (time != null) {
				setCursorData({
					time,
					hrSnr: hrSnr as number,
					rrSnr: rrSnr as number,
					stability: stability as number,
					quality: quality as number,
				})
			}
		} else {
			setCursorData(null)
		}
	}, [])

	useEffect(() => {
		if (!containerRef.current) return

		const opts: uPlot.Options = {
			width,
			height,
			scales: {
				x: { time: true },
				snr: { auto: true, range: [-5, 30] },
				stability: { auto: true, range: [0, 2] },
			},
			cursor: {
				show: true,
				x: true,
				y: true,
				points: {
					show: true,
					size: 6,
					width: 1.5,
				},
			},
			hooks: {
				setCursor: [handleCursor],
			},
			axes: [
				{
					stroke: COLORS.axis,
					grid: { stroke: COLORS.grid },
					ticks: { stroke: COLORS.grid },
					font: '10px IBM Plex Mono, monospace',
				},
				{
					scale: 'snr',
					stroke: COLORS.axis,
					grid: { stroke: COLORS.grid },
					ticks: { stroke: COLORS.grid },
					label: 'SNR (dB)',
					labelSize: 12,
					font: '10px IBM Plex Mono, monospace',
					side: 3,
				},
				{
					scale: 'stability',
					stroke: COLORS.stability,
					grid: { show: false },
					ticks: { stroke: COLORS.grid },
					label: 'Stability',
					labelSize: 12,
					font: '10px IBM Plex Mono, monospace',
					side: 1,
				},
			],
			series: [
				{},
				{
					label: 'HR SNR',
					scale: 'snr',
					stroke: COLORS.hr,
					width: 1.5,
					points: { show: false },
				},
				{
					label: 'RR SNR',
					scale: 'snr',
					stroke: COLORS.rr,
					width: 1.5,
					points: { show: false },
				},
				{
					label: 'Phase Stability',
					scale: 'stability',
					stroke: COLORS.stability,
					width: 1.5,
					points: { show: false },
					dash: [4, 2],
				},
				{
					label: 'Signal Quality',
					scale: 'stability',
					stroke: COLORS.quality,
					width: 1.5,
					points: { show: false },
				},
			],
			legend: {
				show: false,
			},
		}

		chartRef.current = new uPlot(opts, [[], [], [], [], []], containerRef.current)

		return () => {
			chartRef.current?.destroy()
			chartRef.current = null
		}
	}, [width, height, handleCursor])

	useEffect(() => {
		if (!chartRef.current || timestamps.length === 0) return
		chartRef.current.setData([timestamps, hrSnrDb, rrSnrDb, phaseStability, signalQuality])
	}, [timestamps, hrSnrDb, rrSnrDb, phaseStability, signalQuality])

	const isEmpty = timestamps.length === 0 && !isLoading

	const formatTime = (ts: number) => {
		const date = new Date(ts * 1000)
		return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
	}

	const getStabilityLabel = (val: number) => {
		if (val < 0.5) return 'Good'
		if (val < 1.0) return 'Fair'
		return 'Poor'
	}

	const cursorReadout = cursorData ? (
		<span className="text-label font-mono">
			<span className="text-ink-muted">{formatTime(cursorData.time)}:</span>
			<span className="ml-2 text-accent-red">{cursorData.hrSnr.toFixed(1)} dB</span>
			<span className="ml-2 text-accent-blue">{cursorData.rrSnr.toFixed(1)} dB</span>
			<span className="ml-2 text-accent-orange">{getStabilityLabel(cursorData.stability)}</span>
		</span>
	) : null

	const legend = (
		<div className="flex items-center gap-4 text-label flex-wrap">
			{cursorReadout}
			{cursorReadout && <span className="text-ink-muted">|</span>}
			<span className="flex items-center gap-2">
				<span className="w-4 h-[2px] bg-accent-red"></span>
				<span className="text-accent-red font-mono">HR SNR</span>
			</span>
			<span className="flex items-center gap-2">
				<span className="w-4 h-[2px] bg-accent-blue"></span>
				<span className="text-accent-blue font-mono">RR SNR</span>
			</span>
			<span className="flex items-center gap-2">
				<span className="w-4 h-[2px] bg-accent-orange border-dashed border-t-2 border-accent-orange"></span>
				<span className="text-accent-orange font-mono">Stability</span>
			</span>
			<span className="flex items-center gap-2">
				<span className="w-4 h-[2px] bg-accent-green"></span>
				<span className="text-accent-green font-mono">Quality</span>
			</span>
		</div>
	)

	return (
		<ChartContainer
			title="Signal Quality Metrics"
			actions={legend}
			isLoading={isLoading}
			isEmpty={isEmpty}
			emptyMessage="Waiting for quality metrics..."
			loadingMessage="Loading quality history..."
			width={width}
			height={height}
		>
			<div ref={containerRef} />
		</ChartContainer>
	)
}
