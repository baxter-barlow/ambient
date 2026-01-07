import { useEffect, useRef } from 'react'
import ChartContainer from '../common/ChartContainer'

interface Props {
	data: number[][] | undefined
	width?: number
	height?: number
	isLoading?: boolean
}

// Perceptually uniform colormap: dark gray -> teal -> orange -> yellow/white
function valueToColor(value: number, min: number, max: number): string {
	const normalized = Math.max(0, Math.min(1, (value - min) / (max - min)))

	if (normalized < 0.25) {
		// Dark gray to dark teal
		const t = normalized / 0.25
		const r = Math.round(50 + t * (-50 + 0))
		const g = Math.round(53 + t * (-53 + 100))
		const b = Math.round(64 + t * (-64 + 90))
		return `rgb(${r}, ${g}, ${b})`
	} else if (normalized < 0.5) {
		// Dark teal to teal
		const t = (normalized - 0.25) / 0.25
		const r = Math.round(0 + t * 0)
		const g = Math.round(100 + t * 68)
		const b = Math.round(90 + t * 60)
		return `rgb(${r}, ${g}, ${b})`
	} else if (normalized < 0.75) {
		// Teal to orange
		const t = (normalized - 0.5) / 0.25
		const r = Math.round(0 + t * 239)
		const g = Math.round(168 + t * (-62))
		const b = Math.round(150 + t * (-82))
		return `rgb(${r}, ${g}, ${b})`
	} else {
		// Orange to yellow/white
		const t = (normalized - 0.75) / 0.25
		const r = Math.round(239 + t * 16)
		const g = Math.round(106 + t * 85)
		const b = Math.round(68 + t * 68)
		return `rgb(${r}, ${g}, ${b})`
	}
}

export default function RangeDoppler({ data, width = 300, height = 300, isLoading = false }: Props) {
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

	const hasDimensions = data && data.length > 0 && data[0]?.length > 0
	const isEmpty = !hasDimensions && !isLoading

	return (
		<ChartContainer
			title="Range-Doppler Map"
			subtitle={hasDimensions ? `${data.length} x ${data[0].length}` : undefined}
			isLoading={isLoading}
			isEmpty={isEmpty}
			emptyMessage="Waiting for range-Doppler data..."
			loadingMessage="Loading range-Doppler map..."
			width={width}
			height={height}
		>
			<canvas
				ref={canvasRef}
				width={width}
				height={height}
				className="border border-border"
			/>
		</ChartContainer>
	)
}
