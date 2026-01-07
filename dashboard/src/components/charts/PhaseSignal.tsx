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
}

interface CursorData {
	time: number
	value: number
}

export default function PhaseSignal({ timestamps, phases, width = 600, height = 200, isLoading = false }: Props) {
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
					size: 8,
					stroke: '#00a896',
					fill: '#1e2024',
					width: 2,
				},
			},
			hooks: {
				setCursor: [handleCursor],
			},
			axes: [
				{
					stroke: '#6b7280',
					grid: { stroke: '#2a2d32', width: 1 },
					ticks: { stroke: '#2a2d32' },
					font: '9px JetBrains Mono, monospace',
				},
				{
					stroke: '#6b7280',
					grid: { stroke: '#2a2d32', width: 1 },
					ticks: { stroke: '#2a2d32' },
					label: 'Displacement (a.u.)',
					labelSize: 12,
					font: '9px JetBrains Mono, monospace',
				},
			],
			series: [
				{},
				{
					stroke: '#00a896',
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
		<span className="text-micro font-mono text-accent-teal">
			{formatTime(cursorData.time)}: {cursorData.value.toFixed(3)}
		</span>
	) : null

	return (
		<ChartContainer
			title="Displacement Signal"
			subtitle={
				<>
					{cursorReadout}
					{cursorReadout && timestamps.length > 0 && <span className="mx-2 text-border">|</span>}
					{timestamps.length > 0 && <span>{timestamps.length} samples</span>}
				</>
			}
			isLoading={isLoading}
			isEmpty={isEmpty}
			emptyMessage="Waiting for phase data..."
			loadingMessage="Loading displacement signal..."
			width={width}
			height={height}
		>
			<div ref={containerRef} />
		</ChartContainer>
	)
}
