import { useEffect, useRef } from 'react'

interface Props {
	data: number[][] | undefined
	width?: number
	height?: number
}

function valueToColor(value: number, min: number, max: number): string {
	const normalized = Math.max(0, Math.min(1, (value - min) / (max - min)))
	const hue = (1 - normalized) * 240 // Blue to red
	return `hsl(${hue}, 80%, ${30 + normalized * 40}%)`
}

export default function RangeDoppler({ data, width = 300, height = 300 }: Props) {
	const canvasRef = useRef<HTMLCanvasElement>(null)

	useEffect(() => {
		if (!canvasRef.current || !data || data.length === 0) return

		const canvas = canvasRef.current
		const ctx = canvas.getContext('2d')
		if (!ctx) return

		const rows = data.length
		const cols = data[0].length

		// Find min/max for scaling
		let min = Infinity
		let max = -Infinity
		for (const row of data) {
			for (const val of row) {
				if (val < min) min = val
				if (val > max) max = val
			}
		}

		// Draw heatmap
		const cellWidth = width / cols
		const cellHeight = height / rows

		for (let y = 0; y < rows; y++) {
			for (let x = 0; x < cols; x++) {
				ctx.fillStyle = valueToColor(data[y][x], min, max)
				ctx.fillRect(x * cellWidth, y * cellHeight, cellWidth + 1, cellHeight + 1)
			}
		}
	}, [data, width, height])

	return (
		<div className="bg-gray-800 rounded-lg p-3">
			<div className="text-sm text-gray-400 mb-2">Range-Doppler Map</div>
			<div className="relative">
				<canvas
					ref={canvasRef}
					width={width}
					height={height}
					className="border border-gray-700"
				/>
				{(!data || data.length === 0) && (
					<div className="absolute inset-0 flex items-center justify-center text-gray-500 bg-gray-900/50">
						No data
					</div>
				)}
			</div>
		</div>
	)
}
