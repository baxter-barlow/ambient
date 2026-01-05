import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

interface Props {
	data: number[]
	width?: number
	height?: number
}

export default function RangeProfile({ data, width = 600, height = 200 }: Props) {
	const containerRef = useRef<HTMLDivElement>(null)
	const chartRef = useRef<uPlot | null>(null)

	useEffect(() => {
		if (!containerRef.current) return

		const opts: uPlot.Options = {
			width,
			height,
			title: 'Range Profile',
			scales: {
				x: { time: false },
				y: { auto: true },
			},
			axes: [
				{
					stroke: '#6b7280',
					grid: { stroke: '#374151' },
					ticks: { stroke: '#4b5563' },
					label: 'Range Bin',
					labelSize: 12,
					font: '11px sans-serif',
				},
				{
					stroke: '#6b7280',
					grid: { stroke: '#374151' },
					ticks: { stroke: '#4b5563' },
					label: 'Magnitude',
					labelSize: 12,
					font: '11px sans-serif',
				},
			],
			series: [
				{},
				{
					stroke: '#22c55e',
					width: 1.5,
					fill: 'rgba(34, 197, 94, 0.1)',
				},
			],
		}

		chartRef.current = new uPlot(opts, [[], []], containerRef.current)

		return () => {
			chartRef.current?.destroy()
			chartRef.current = null
		}
	}, [width, height])

	useEffect(() => {
		if (!chartRef.current || data.length === 0) return

		const xData = Array.from({ length: data.length }, (_, i) => i)
		chartRef.current.setData([xData, data])
	}, [data])

	return (
		<div
			ref={containerRef}
			className="bg-gray-800 rounded-lg p-2"
		/>
	)
}
