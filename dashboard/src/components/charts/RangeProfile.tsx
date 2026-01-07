import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import ChartContainer from '../common/ChartContainer'

interface Props {
	data: number[]
	width?: number
	height?: number
	isLoading?: boolean
}

interface CursorData {
	bin: number
	value: number
}

export default function RangeProfile({ data, width = 600, height = 300, isLoading = false }: Props) {
	const containerRef = useRef<HTMLDivElement>(null)
	const chartRef = useRef<uPlot | null>(null)
	const [yRange, setYRange] = useState<[number, number]>([0, 1])
	const [cursorData, setCursorData] = useState<CursorData | null>(null)

	// Stabilize Y-axis with smoothing
	useEffect(() => {
		if (data.length === 0) return
		const max = Math.max(...data)
		const min = Math.min(...data)
		setYRange(prev => [
			prev[0] * 0.9 + min * 0.1,
			Math.max(prev[1] * 0.9 + max * 0.1, max * 1.1),
		])
	}, [data])

	// Stats for display
	const stats = useMemo(() => {
		if (data.length === 0) return null
		const max = Math.max(...data)
		const mean = data.reduce((a, b) => a + b, 0) / data.length
		return { max: max.toFixed(1), mean: mean.toFixed(1), bins: data.length }
	}, [data])

	const handleCursor = useCallback((u: uPlot) => {
		const idx = u.cursor.idx
		if (idx != null && u.data[0] && u.data[1]) {
			const bin = u.data[0][idx]
			const value = u.data[1][idx]
			if (bin != null && value != null) {
				setCursorData({ bin, value })
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
				x: { time: false },
				y: { auto: false, range: () => yRange },
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
					label: 'Range Bin',
					labelSize: 12,
					font: '9px JetBrains Mono, monospace',
				},
				{
					stroke: '#6b7280',
					grid: { stroke: '#2a2d32', width: 1 },
					ticks: { stroke: '#2a2d32' },
					label: 'Magnitude (dB)',
					labelSize: 12,
					font: '9px JetBrains Mono, monospace',
				},
			],
			series: [
				{},
				{
					stroke: '#00a896',
					width: 1.5,
					fill: 'rgba(0, 168, 150, 0.15)',
				},
			],
		}

		chartRef.current = new uPlot(opts, [[], []], containerRef.current)

		return () => {
			chartRef.current?.destroy()
			chartRef.current = null
		}
	}, [width, height, handleCursor])

	// Update Y range when it changes
	useEffect(() => {
		if (chartRef.current) {
			chartRef.current.scales.y.range = () => yRange
		}
	}, [yRange])

	useEffect(() => {
		if (!chartRef.current || data.length === 0) return

		const xData = Array.from({ length: data.length }, (_, i) => i)
		chartRef.current.setData([xData, data])
	}, [data])

	const cursorReadout = cursorData ? (
		<span className="text-micro font-mono text-accent-teal">
			Bin {cursorData.bin}: {cursorData.value.toFixed(1)} dB
		</span>
	) : null

	return (
		<ChartContainer
			title="Range Profile"
			subtitle={
				<>
					{cursorReadout}
					{cursorReadout && stats && <span className="mx-2 text-border">|</span>}
					{stats && <span>{stats.bins} bins | max: {stats.max} dB | mean: {stats.mean} dB</span>}
				</>
			}
			isLoading={isLoading}
			isEmpty={data.length === 0 && !isLoading}
			emptyMessage="Waiting for range data..."
			loadingMessage="Loading range profile..."
			width={width}
			height={height}
		>
			<div ref={containerRef} />
		</ChartContainer>
	)
}
