import { useEffect, useRef, useState, useCallback } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import ChartContainer from '../common/ChartContainer'

interface Props {
	timestamps: number[]
	heartRates: (number | null)[]
	respiratoryRates: (number | null)[]
	width?: number
	height?: number
	isLoading?: boolean
	compact?: boolean
}

interface CursorData {
	time: number
	hr: number | null
	rr: number | null
}

// TE color palette for light theme
const COLORS = {
	hr: '#E53935',          // accent-red for heart rate
	rr: '#1976D2',          // accent-blue for respiratory rate
	grid: '#E2E2DF',        // bg-tertiary
	axis: '#4A4A4A',        // ink-secondary
	background: '#ECECEA',  // bg-secondary
}

export default function VitalsChart({
	timestamps,
	heartRates,
	respiratoryRates,
	width = 600,
	height = 250,
	isLoading = false,
	compact = false,
}: Props) {
	const containerRef = useRef<HTMLDivElement>(null)
	const chartRef = useRef<uPlot | null>(null)
	const [cursorData, setCursorData] = useState<CursorData | null>(null)

	const handleCursor = useCallback((u: uPlot) => {
		const idx = u.cursor.idx
		if (idx != null && u.data[0]) {
			const time = u.data[0][idx]
			const hr = u.data[1]?.[idx] ?? null
			const rr = u.data[2]?.[idx] ?? null
			if (time != null) {
				setCursorData({ time, hr: hr as number | null, rr: rr as number | null })
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
				hr: { auto: true, range: [40, 120] },
				rr: { auto: true, range: [6, 30] },
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
					scale: 'hr',
					stroke: COLORS.hr,
					grid: { stroke: COLORS.grid },
					ticks: { stroke: COLORS.grid },
					label: 'HR (BPM)',
					labelSize: 12,
					font: '10px IBM Plex Mono, monospace',
					side: 3,
				},
				{
					scale: 'rr',
					stroke: COLORS.rr,
					grid: { show: false },
					ticks: { stroke: COLORS.grid },
					label: 'RR (BPM)',
					labelSize: 12,
					font: '10px IBM Plex Mono, monospace',
					side: 1,
				},
			],
			series: [
				{},
				{
					label: 'Heart Rate',
					scale: 'hr',
					stroke: COLORS.hr,
					width: 1.5,
					points: { show: false },
				},
				{
					label: 'Respiratory Rate',
					scale: 'rr',
					stroke: COLORS.rr,
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
	}, [width, height, handleCursor])

	useEffect(() => {
		if (!chartRef.current || timestamps.length === 0) return

		// Convert nulls to undefined for uPlot
		const hr = heartRates.map(v => v ?? undefined) as number[]
		const rr = respiratoryRates.map(v => v ?? undefined) as number[]

		chartRef.current.setData([timestamps, hr, rr])
	}, [timestamps, heartRates, respiratoryRates])

	const isEmpty = timestamps.length === 0 && !isLoading

	const formatTime = (ts: number) => {
		const date = new Date(ts * 1000)
		return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
	}

	const cursorReadout = cursorData ? (
		<span className="text-label font-mono">
			<span className="text-ink-muted">{formatTime(cursorData.time)}:</span>
			{cursorData.hr != null && (
				<span className="ml-2 text-accent-red">{cursorData.hr.toFixed(0)} BPM</span>
			)}
			{cursorData.rr != null && (
				<span className="ml-2 text-accent-blue">{cursorData.rr.toFixed(1)} BPM</span>
			)}
		</span>
	) : null

	const legend = (
		<div className="flex items-center gap-4 text-label">
			{cursorReadout}
			{cursorReadout && <span className="text-ink-muted">|</span>}
			<span className="flex items-center gap-2">
				<span className="w-4 h-[2px] bg-accent-red"></span>
				<span className="text-accent-red font-mono">HR</span>
			</span>
			<span className="flex items-center gap-2">
				<span className="w-4 h-[2px] bg-accent-blue"></span>
				<span className="text-accent-blue font-mono">RR</span>
			</span>
		</div>
	)

	return (
		<ChartContainer
			title="Vital Signs History"
			actions={compact ? undefined : legend}
			isLoading={isLoading}
			isEmpty={isEmpty}
			emptyMessage="Waiting for vital signs data..."
			loadingMessage="Loading vital signs history..."
			width={width}
			height={height}
			compact={compact}
		>
			<div ref={containerRef} />
		</ChartContainer>
	)
}
