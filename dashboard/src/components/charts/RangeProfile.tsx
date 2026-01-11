import { useEffect, useRef, useState, useMemo, useCallback } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'
import ChartContainer from '../common/ChartContainer'

interface Props {
	data: number[]
	source?: 'tlv2' | 'iq' | null
	isChirpFirmware?: boolean
	width?: number
	height?: number
	isLoading?: boolean
	compact?: boolean
}

interface CursorData {
	bin: number
	value: number
}

// TE color palette for light theme
const COLORS = {
	accent: '#1976D2',      // accent-blue for range profile
	grid: '#E2E2DF',        // bg-tertiary
	axis: '#4A4A4A',        // ink-secondary
	background: '#ECECEA',  // bg-secondary
	cursor: '#111111',      // ink-primary
}

export default function RangeProfile({ data, source, isChirpFirmware, width = 600, height = 300, isLoading = false, compact = false }: Props) {
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
					label: 'Range Bin',
					labelSize: 12,
					font: '10px IBM Plex Mono, monospace',
				},
				{
					stroke: COLORS.axis,
					grid: { stroke: COLORS.grid, width: 1 },
					ticks: { stroke: COLORS.grid },
					label: 'Magnitude (dB)',
					labelSize: 12,
					font: '10px IBM Plex Mono, monospace',
				},
			],
			series: [
				{},
				{
					stroke: COLORS.accent,
					width: 1.5,
					fill: 'rgba(25, 118, 210, 0.1)',
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
		<span className="text-label font-mono text-accent-blue">
			Bin {cursorData.bin}: {cursorData.value.toFixed(1)} dB
		</span>
	) : null

	// Source badge for data origin
	const sourceBadge = source ? (
		<span className={`px-2 py-1 text-label font-mono uppercase border ${
			source === 'iq'
				? 'border-accent-blue text-accent-blue bg-bg-tertiary'
				: 'border-accent-green text-accent-green bg-bg-tertiary'
		}`}>
			{source === 'iq' ? 'I/Q' : 'TLV'}
		</span>
	) : null

	// Empty message based on firmware type
	const emptyMessage = isChirpFirmware
		? 'Waiting for I/Q data (TLV 0x0500)...'
		: 'Waiting for range data...'

	return (
		<ChartContainer
			title="Range Profile"
			subtitle={
				<>
					{sourceBadge}
					{sourceBadge && (cursorReadout || stats) && <span className="mx-2 text-ink-muted">|</span>}
					{cursorReadout}
					{cursorReadout && stats && <span className="mx-2 text-ink-muted">|</span>}
					{stats && <span className="text-label font-mono text-ink-secondary">{stats.bins} bins | max: {stats.max} dB | mean: {stats.mean} dB</span>}
				</>
			}
			isLoading={isLoading}
			isEmpty={data.length === 0 && !isLoading}
			emptyMessage={emptyMessage}
			loadingMessage="Loading range profile..."
			width={width}
			height={height}
			compact={compact}
		>
			<div ref={containerRef} />
		</ChartContainer>
	)
}
