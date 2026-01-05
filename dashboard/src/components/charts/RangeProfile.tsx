import { useEffect, useRef, useState, useMemo } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

interface Props {
	data: number[]
	width?: number
	height?: number
}

export default function RangeProfile({ data, width = 600, height = 300 }: Props) {
	const containerRef = useRef<HTMLDivElement>(null)
	const chartRef = useRef<uPlot | null>(null)
	const [yRange, setYRange] = useState<[number, number]>([0, 1])

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
		return { max: max.toFixed(1), mean: mean.toFixed(1) }
	}, [data])

	useEffect(() => {
		if (!containerRef.current) return

		const opts: uPlot.Options = {
			width,
			height,
			title: 'Range Profile',
			scales: {
				x: { time: false },
				y: { auto: false, range: () => yRange },
			},
			axes: [
				{
					stroke: '#9ca3af',
					grid: { stroke: '#374151', width: 1 },
					ticks: { stroke: '#4b5563' },
					label: 'Range Bin',
					labelSize: 14,
					font: '12px sans-serif',
				},
				{
					stroke: '#9ca3af',
					grid: { stroke: '#374151', width: 1 },
					ticks: { stroke: '#4b5563' },
					label: 'Magnitude (dB)',
					labelSize: 14,
					font: '12px sans-serif',
				},
			],
			series: [
				{},
				{
					stroke: '#22c55e',
					width: 2,
					fill: 'rgba(34, 197, 94, 0.15)',
				},
			],
		}

		chartRef.current = new uPlot(opts, [[], []], containerRef.current)

		return () => {
			chartRef.current?.destroy()
			chartRef.current = null
		}
	}, [width, height])

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

	return (
		<div className="bg-gray-800 rounded-lg p-3">
			<div className="flex justify-between items-center mb-2">
				<span className="text-sm text-gray-400">Range Profile</span>
				{stats && (
					<span className="text-xs text-gray-500">
						Max: {stats.max} | Mean: {stats.mean}
					</span>
				)}
			</div>
			<div ref={containerRef} />
		</div>
	)
}
