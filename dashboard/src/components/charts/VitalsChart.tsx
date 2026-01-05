import { useEffect, useRef } from 'react'
import uPlot from 'uplot'
import 'uplot/dist/uPlot.min.css'

interface Props {
	timestamps: number[]
	heartRates: (number | null)[]
	respiratoryRates: (number | null)[]
	width?: number
	height?: number
}

export default function VitalsChart({
	timestamps,
	heartRates,
	respiratoryRates,
	width = 600,
	height = 250,
}: Props) {
	const containerRef = useRef<HTMLDivElement>(null)
	const chartRef = useRef<uPlot | null>(null)

	useEffect(() => {
		if (!containerRef.current) return

		const opts: uPlot.Options = {
			width,
			height,
			title: 'Vital Signs',
			scales: {
				x: { time: true },
				hr: { auto: true, range: [40, 120] },
				rr: { auto: true, range: [6, 30] },
			},
			axes: [
				{
					stroke: '#6b7280',
					grid: { stroke: '#374151' },
					ticks: { stroke: '#4b5563' },
					font: '11px sans-serif',
				},
				{
					scale: 'hr',
					stroke: '#ef4444',
					grid: { stroke: '#374151' },
					ticks: { stroke: '#4b5563' },
					label: 'HR (BPM)',
					labelSize: 12,
					font: '11px sans-serif',
					side: 3,
				},
				{
					scale: 'rr',
					stroke: '#3b82f6',
					grid: { show: false },
					ticks: { stroke: '#4b5563' },
					label: 'RR (BPM)',
					labelSize: 12,
					font: '11px sans-serif',
					side: 1,
				},
			],
			series: [
				{},
				{
					label: 'Heart Rate',
					scale: 'hr',
					stroke: '#ef4444',
					width: 2,
					points: { show: false },
				},
				{
					label: 'Respiratory Rate',
					scale: 'rr',
					stroke: '#3b82f6',
					width: 2,
					points: { show: false },
				},
			],
			legend: {
				show: true,
			},
		}

		chartRef.current = new uPlot(opts, [[], [], []], containerRef.current)

		return () => {
			chartRef.current?.destroy()
			chartRef.current = null
		}
	}, [width, height])

	useEffect(() => {
		if (!chartRef.current || timestamps.length === 0) return

		// Convert nulls to undefined for uPlot
		const hr = heartRates.map(v => v ?? undefined) as number[]
		const rr = respiratoryRates.map(v => v ?? undefined) as number[]

		chartRef.current.setData([timestamps, hr, rr])
	}, [timestamps, heartRates, respiratoryRates])

	return (
		<div
			ref={containerRef}
			className="bg-gray-800 rounded-lg p-2"
		/>
	)
}
