import { useEffect, useRef } from 'react'
import ChartContainer from '../common/ChartContainer'

interface Props {
	data: number[][] | undefined
	width?: number
	height?: number
	isLoading?: boolean
	isChirpFirmware?: boolean
	compact?: boolean
}

// TE-inspired colormap: cool neutrals to warm accents
// Neutral grays -> blue -> accent yellow for highlights
function valueToColor(value: number, min: number, max: number): string {
	const normalized = Math.max(0, Math.min(1, (value - min) / (max - min)))

	if (normalized < 0.25) {
		// Light gray (bg-tertiary) to muted blue-gray
		const t = normalized / 0.25
		const r = Math.round(226 + t * (-126))  // E2 -> 64
		const g = Math.round(226 + t * (-126))  // E2 -> 64
		const b = Math.round(223 + t * (-73))   // DF -> 96
		return `rgb(${r}, ${g}, ${b})`
	} else if (normalized < 0.5) {
		// Muted blue-gray to accent-blue
		const t = (normalized - 0.25) / 0.25
		const r = Math.round(100 + t * (-75))   // 64 -> 25
		const g = Math.round(100 + t * (18))    // 64 -> 118
		const b = Math.round(150 + t * (60))    // 96 -> 210
		return `rgb(${r}, ${g}, ${b})`
	} else if (normalized < 0.75) {
		// Accent-blue to accent-orange
		const t = (normalized - 0.5) / 0.25
		const r = Math.round(25 + t * (220))    // 19 -> 245
		const g = Math.round(118 + t * (6))     // 76 -> 124
		const b = Math.round(210 + t * (-210))  // D2 -> 0
		return `rgb(${r}, ${g}, ${b})`
	} else {
		// Accent-orange to accent-yellow
		const t = (normalized - 0.75) / 0.25
		const r = Math.round(245 + t * (10))    // F5 -> FF
		const g = Math.round(124 + t * (88))    // 7C -> D4
		const b = Math.round(0 + t * (0))       // 00 -> 00
		return `rgb(${r}, ${g}, ${b})`
	}
}

export default function RangeDoppler({ data, width = 300, height = 300, isLoading = false, isChirpFirmware = false, compact = false }: Props) {
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

	// Different message for chirp firmware vs waiting for data
	const emptyMessage = isChirpFirmware
		? "Not available with Chirp firmware"
		: "Waiting for range-Doppler data..."

	return (
		<ChartContainer
			title="Range-Doppler Map"
			subtitle={hasDimensions ? <span className="text-label font-mono text-ink-secondary">{data.length} x {data[0].length}</span> : undefined}
			isLoading={isLoading}
			isEmpty={isEmpty}
			emptyMessage={emptyMessage}
			loadingMessage="Loading range-Doppler map..."
			width={width}
			height={height}
			compact={compact}
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
