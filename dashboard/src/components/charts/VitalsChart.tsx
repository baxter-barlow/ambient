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
}

interface CursorData {
	time: number
	hr: number | null
	rr: number | null
}

export default function VitalsChart({
	timestamps,
	heartRates,
	respiratoryRates,
	width = 600,
	height = 250,
	isLoading = false,
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
					size: 8,
					width: 2,
				},
			},
			hooks: {
				setCursor: [handleCursor],
			},
			axes: [
				{
					stroke: '#6b7280',
					grid: { stroke: '#2a2d32' },
					ticks: { stroke: '#2a2d32' },
					font: '9px JetBrains Mono, monospace',
				},
				{
					scale: 'hr',
					stroke: '#ef4444',
					grid: { stroke: '#2a2d32' },
					ticks: { stroke: '#2a2d32' },
					label: 'HR (BPM)',
					labelSize: 12,
					font: '9px JetBrains Mono, monospace',
					side: 3,
				},
				{
					scale: 'rr',
					stroke: '#3b82f6',
					grid: { show: false },
					ticks: { stroke: '#2a2d32' },
					label: 'RR (BPM)',
					labelSize: 12,
					font: '9px JetBrains Mono, monospace',
					side: 1,
				},
			],
			series: [
				{},
				{
					label: 'Heart Rate',
					scale: 'hr',
					stroke: '#ef4444',
					width: 1.5,
					points: { show: false },
				},
				{
					label: 'Respiratory Rate',
					scale: 'rr',
					stroke: '#3b82f6',
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
		<span className="text-micro font-mono">
			<span className="text-text-tertiary">{formatTime(cursorData.time)}:</span>
			{cursorData.hr != null && (
				<span className="ml-2 text-accent-red">{cursorData.hr.toFixed(0)} BPM</span>
			)}
			{cursorData.rr != null && (
				<span className="ml-2 text-accent-blue">{cursorData.rr.toFixed(1)} BPM</span>
			)}
		</span>
	) : null

	const legend = (
		<div className="flex items-center gap-4 text-micro">
			{cursorReadout}
			{cursorReadout && <span className="text-border">|</span>}
			<span className="flex items-center gap-1.5">
				<span className="w-4 h-0.5 bg-accent-red rounded"></span>
				<span className="text-accent-red">HR</span>
			</span>
			<span className="flex items-center gap-1.5">
				<span className="w-4 h-0.5 bg-accent-blue rounded"></span>
				<span className="text-accent-blue">RR</span>
			</span>
		</div>
	)

	return (
		<ChartContainer
			title="Vital Signs History"
			actions={legend}
			isLoading={isLoading}
			isEmpty={isEmpty}
			emptyMessage="Waiting for vital signs data..."
			loadingMessage="Loading vital signs history..."
			width={width}
			height={height}
		>
			<div ref={containerRef} />
		</ChartContainer>
	)
}
