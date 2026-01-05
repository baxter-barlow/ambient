import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

interface Props {
	timestamps: number[]
	phases: number[]
	width?: number
	height?: number
}

export default function PhaseSignal({ timestamps, phases, width = 600, height = 200 }: Props) {
	const containerRef = useRef<HTMLDivElement>(null)
	const chartRef = useRef<uPlot | null>(null)

	useEffect(() => {
		if (!containerRef.current) return

		const opts: uPlot.Options = {
			width,
			height,
			title: 'Displacement Signal',
			scales: {
				x: { time: true },
				y: { auto: true },
			},
			axes: [
				{
					stroke: '#9ca3af',
					grid: { stroke: '#374151', width: 1 },
					ticks: { stroke: '#4b5563' },
					font: '12px sans-serif',
				},
				{
					stroke: '#9ca3af',
					grid: { stroke: '#374151', width: 1 },
					ticks: { stroke: '#4b5563' },
					label: 'Displacement (a.u.)',
					labelSize: 14,
					font: '12px sans-serif',
				},
			],
			series: [
				{},
				{
					stroke: '#3b82f6',
					width: 2,
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
		if (!chartRef.current || timestamps.length === 0) return
		chartRef.current.setData([timestamps, phases])
	}, [timestamps, phases])

	return (
		<div
			ref={containerRef}
			className="bg-gray-800 rounded-lg p-2"
		/>
	)
}
