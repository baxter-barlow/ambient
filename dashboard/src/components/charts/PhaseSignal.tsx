import { useEffect, useRef, useState, useCallback } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import ChartContainer from '../common/ChartContainer'

interface Props {
	timestamps: number[]
	phases: number[]
	width?: number
	height?: number
	isLoading?: boolean
	compact?: boolean
}

interface CursorData {
	time: number
	value: number
}

// TE color palette for light theme
const COLORS = {
	accent: '#2E7D32',      // accent-green for phase signal
	grid: '#E2E2DF',        // bg-tertiary
	axis: '#4A4A4A',        // ink-secondary
	background: '#ECECEA',  // bg-secondary
	cursor: '#111111',      // ink-primary
}

export default function PhaseSignal({ timestamps, phases, width = 600, height = 200, isLoading = false, compact = false }: Props) {
	const containerRef = useRef<HTMLDivElement>(null)
	const chartRef = useRef<uPlot | null>(null)
	const [cursorData, setCursorData] = useState<CursorData | null>(null)

	const handleCursor = useCallback((u: uPlot) => {
		const idx = u.cursor.idx
		if (idx != null && u.data[0] && u.data[1]) {
			const time = u.data[0][idx]
			const value = u.data[1][idx]
			if (time != null && value != null) {
				setCursorData({ time, value })
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
				y: { auto: true },
			},
			cursor: {
				show: true,
				x: true,
				y: true,
				points: {
					show: true,
					size: 6,
					stroke: COLORS.cursor,
					fill: COLORS.background,
					width: 1.5,
				},
			},
			hooks: {
				setCursor: [handleCursor],
			},
			axes: [
				{
					stroke: COLORS.axis,
					grid: { stroke: COLORS.grid, width: 1 },
					ticks: { stroke: COLORS.grid },
					font: '10px IBM Plex Mono, monospace',
				},
				{
					stroke: COLORS.axis,
					grid: { stroke: COLORS.grid, width: 1 },
					ticks: { stroke: COLORS.grid },
					label: 'Displacement (a.u.)',
					labelSize: 12,
					font: '10px IBM Plex Mono, monospace',
				},
			],
			series: [
				{},
				{
					stroke: COLORS.accent,
					width: 1.5,
				},
			],
		}

		chartRef.current = new uPlot(opts, [[], []], containerRef.current)

		return () => {
			chartRef.current?.destroy()
			chartRef.current = null
		}
	}, [width, height, handleCursor])

	useEffect(() => {
		if (!chartRef.current || timestamps.length === 0) return
		chartRef.current.setData([timestamps, phases])
	}, [timestamps, phases])

	const isEmpty = timestamps.length === 0 && !isLoading

	const formatTime = (ts: number) => {
		const date = new Date(ts * 1000)
		return date.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
	}

	const cursorReadout = cursorData ? (
		<span className="text-label font-mono text-accent-green">
			{formatTime(cursorData.time)}: {cursorData.value.toFixed(3)}
		</span>
	) : null

	return (
		<ChartContainer
			title="Displacement Signal"
			subtitle={
				<>
					{cursorReadout}
					{cursorReadout && timestamps.length > 0 && <span className="mx-2 text-ink-muted">|</span>}
					{timestamps.length > 0 && <span className="text-label font-mono text-ink-secondary">{timestamps.length} samples</span>}
				</>
			}
			isLoading={isLoading}
			isEmpty={isEmpty}
			emptyMessage="Waiting for phase data..."
			loadingMessage="Loading displacement signal..."
			width={width}
			height={height}
			compact={compact}
		>
			<div ref={containerRef} />
		</ChartContainer>
	)
}
