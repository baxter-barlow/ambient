import { useRef, useMemo, useEffect } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { OrbitControls, Grid, Text } from '@react-three/drei'
import * as THREE from 'three'
import ChartContainer from '../common/ChartContainer'
import type { Point3DWithAge, TrackedObject } from '../../types'

interface PointCloudProps {
	points: Point3DWithAge[]
	trackedObjects?: TrackedObject[]
	colorMode?: 'velocity' | 'snr' | 'height' | 'age' | 'track'
	maxAge?: number
	maxRange?: number
	showGrid?: boolean
	showAxes?: boolean
	showTracks?: boolean
}

interface Props extends PointCloudProps {
	width?: number
	height?: number
	isLoading?: boolean
}

// Color mapping functions matching backend point_cloud.py
function velocityToColor(velocity: number, maxVelocity: number = 5): THREE.Color {
	const t = Math.max(-1, Math.min(1, velocity / maxVelocity))
	if (t < 0) {
		// Approaching: blue
		return new THREE.Color(0, 0, 1 + t)
	} else {
		// Receding: red
		return new THREE.Color(t, 0, 0)
	}
}

function snrToColor(snr: number, minSnr: number = 0, maxSnr: number = 30): THREE.Color {
	const t = Math.max(0, Math.min(1, (snr - minSnr) / (maxSnr - minSnr)))
	if (t < 0.5) {
		// Blue -> Green
		return new THREE.Color(0, t * 2, 1 - t * 2)
	} else {
		// Green -> Red
		return new THREE.Color((t - 0.5) * 2, 1 - (t - 0.5) * 2, 0)
	}
}

function heightToColor(z: number, minZ: number = -1, maxZ: number = 2): THREE.Color {
	const t = Math.max(0, Math.min(1, (z - minZ) / (maxZ - minZ)))
	// Purple -> Cyan gradient
	return new THREE.Color(1 - t, t, 1)
}

function ageToOpacity(age: number, maxAge: number): number {
	return Math.max(0.1, 1.0 - (age / maxAge))
}

// Track colors (consistent colors per track ID)
const TRACK_COLORS = [
	new THREE.Color(0.2, 0.8, 0.2),  // Green
	new THREE.Color(0.8, 0.2, 0.2),  // Red
	new THREE.Color(0.2, 0.2, 0.8),  // Blue
	new THREE.Color(0.8, 0.8, 0.2),  // Yellow
	new THREE.Color(0.8, 0.2, 0.8),  // Magenta
	new THREE.Color(0.2, 0.8, 0.8),  // Cyan
	new THREE.Color(1.0, 0.5, 0.0),  // Orange
	new THREE.Color(0.5, 0.0, 1.0),  // Purple
]

function getTrackColor(trackId: number): THREE.Color {
	if (trackId < 0) return new THREE.Color(0.5, 0.5, 0.5) // Untracked = gray
	return TRACK_COLORS[trackId % TRACK_COLORS.length]
}

// Point cloud rendering component
function PointCloudPoints({
	points,
	colorMode,
	maxAge,
}: {
	points: Point3DWithAge[]
	colorMode: string
	maxAge: number
}) {
	const meshRef = useRef<THREE.InstancedMesh>(null)
	const tempObject = useMemo(() => new THREE.Object3D(), [])
	const tempColor = useMemo(() => new THREE.Color(), [])

	// Update instances
	useEffect(() => {
		if (!meshRef.current || points.length === 0) return

		points.forEach((point, i) => {
			// Position
			tempObject.position.set(point.x, point.z, -point.y) // Swap Y/Z for proper 3D view

			// Scale based on age (newer = larger)
			const scale = 0.02 + 0.02 * ageToOpacity(point.age, maxAge)
			tempObject.scale.set(scale, scale, scale)

			tempObject.updateMatrix()
			meshRef.current!.setMatrixAt(i, tempObject.matrix)

			// Color based on mode
			switch (colorMode) {
				case 'velocity':
					tempColor.copy(velocityToColor(point.velocity))
					break
				case 'snr':
					tempColor.copy(snrToColor(point.snr))
					break
				case 'height':
					tempColor.copy(heightToColor(point.z))
					break
				case 'track':
					tempColor.copy(getTrackColor(point.track_id ?? -1))
					break
				case 'age':
				default:
					// Age-based: white fading to gray
					const brightness = ageToOpacity(point.age, maxAge)
					tempColor.setRGB(brightness, brightness, brightness)
					break
			}
			meshRef.current!.setColorAt(i, tempColor)
		})

		meshRef.current.instanceMatrix.needsUpdate = true
		if (meshRef.current.instanceColor) {
			meshRef.current.instanceColor.needsUpdate = true
		}
	}, [points, colorMode, maxAge, tempObject, tempColor])

	if (points.length === 0) return null

	return (
		<instancedMesh ref={meshRef} args={[undefined, undefined, points.length]}>
			<sphereGeometry args={[1, 8, 8]} />
			<meshBasicMaterial toneMapped={false} />
		</instancedMesh>
	)
}

// Tracked objects visualization (show as larger spheres with velocity vectors)
function TrackedObjectsViz({
	objects,
	showVelocity = true,
}: {
	objects: TrackedObject[]
	showVelocity?: boolean
}) {
	return (
		<group>
			{objects.map((obj) => {
				const color = getTrackColor(obj.track_id)
				const velocityMag = Math.sqrt(obj.vx ** 2 + obj.vy ** 2 + obj.vz ** 2)

				return (
					<group key={obj.track_id} position={[obj.x, obj.z, -obj.y]}>
						{/* Main sphere */}
						<mesh>
							<sphereGeometry args={[0.1, 16, 16]} />
							<meshBasicMaterial color={color} transparent opacity={0.8} />
						</mesh>

						{/* Track ID label */}
						<Text
							position={[0, 0.2, 0]}
							fontSize={0.1}
							color="white"
							anchorX="center"
							anchorY="bottom"
						>
							{`T${obj.track_id}`}
						</Text>

						{/* Velocity vector */}
						{showVelocity && velocityMag > 0.1 && (
							<arrowHelper
								args={[
									new THREE.Vector3(obj.vx, obj.vz, -obj.vy).normalize(),
									new THREE.Vector3(0, 0, 0),
									velocityMag * 0.2,
									color.getHex(),
									0.05,
									0.03,
								]}
							/>
						)}
					</group>
				)
			})}
		</group>
	)
}

// Axis labels
function AxisLabels({ maxRange }: { maxRange: number }) {
	return (
		<group>
			{/* X axis label */}
			<Text position={[maxRange + 0.3, 0, 0]} fontSize={0.15} color="#888">
				X (m)
			</Text>
			{/* Y axis label (shown as Z in world space) */}
			<Text position={[0, 0, -maxRange - 0.3]} fontSize={0.15} color="#888">
				Y (m)
			</Text>
			{/* Z axis label (shown as Y in world space) */}
			<Text position={[0, maxRange / 2 + 0.3, 0]} fontSize={0.15} color="#888">
				Z (m)
			</Text>
		</group>
	)
}

// Camera auto-fit
function CameraController({ maxRange }: { maxRange: number }) {
	const { camera } = useThree()

	useEffect(() => {
		camera.position.set(maxRange * 1.5, maxRange, maxRange * 1.5)
		camera.lookAt(0, 0, 0)
	}, [camera, maxRange])

	return null
}

// Main 3D scene
function PointCloudScene({
	points,
	trackedObjects,
	colorMode = 'velocity',
	maxAge = 10,
	maxRange = 5,
	showGrid = true,
	showAxes = true,
	showTracks = true,
}: PointCloudProps) {
	return (
		<>
			<CameraController maxRange={maxRange} />
			<OrbitControls
				enablePan={true}
				enableZoom={true}
				enableRotate={true}
				minDistance={1}
				maxDistance={maxRange * 4}
			/>

			{/* Lighting */}
			<ambientLight intensity={0.6} />
			<directionalLight position={[5, 5, 5]} intensity={0.4} />

			{/* Ground grid */}
			{showGrid && (
				<Grid
					args={[maxRange * 2, maxRange * 2]}
					cellSize={0.5}
					cellThickness={0.5}
					cellColor="#404040"
					sectionSize={1}
					sectionThickness={1}
					sectionColor="#606060"
					fadeDistance={maxRange * 3}
					position={[0, 0, 0]}
					rotation={[Math.PI / 2, 0, 0]}
				/>
			)}

			{/* Axes */}
			{showAxes && (
				<>
					<axesHelper args={[maxRange]} />
					<AxisLabels maxRange={maxRange} />
				</>
			)}

			{/* Point cloud */}
			<PointCloudPoints
				points={points}
				colorMode={colorMode}
				maxAge={maxAge}
			/>

			{/* Tracked objects */}
			{showTracks && trackedObjects && trackedObjects.length > 0 && (
				<TrackedObjectsViz objects={trackedObjects} />
			)}

			{/* Radar position indicator */}
			<mesh position={[0, 0, 0]}>
				<boxGeometry args={[0.05, 0.05, 0.05]} />
				<meshBasicMaterial color="#00ff00" />
			</mesh>
		</>
	)
}

export default function PointCloud3D({
	points,
	trackedObjects,
	colorMode = 'velocity',
	maxAge = 10,
	maxRange = 5,
	showGrid = true,
	showAxes = true,
	showTracks = true,
	width = 400,
	height = 400,
	isLoading = false,
}: Props) {
	const isEmpty = points.length === 0 && !isLoading

	return (
		<ChartContainer
			title="3D Point Cloud"
			subtitle={points.length > 0 ? `${points.length} points` : undefined}
			isLoading={isLoading}
			isEmpty={isEmpty}
			emptyMessage="Waiting for point cloud data..."
			loadingMessage="Loading point cloud..."
			width={width}
			height={height}
		>
			<div style={{ width, height }} className="border border-border bg-black">
				<Canvas
					camera={{ position: [5, 3, 5], fov: 60 }}
					style={{ background: '#1a1a1a' }}
				>
					<PointCloudScene
						points={points}
						trackedObjects={trackedObjects}
						colorMode={colorMode}
						maxAge={maxAge}
						maxRange={maxRange}
						showGrid={showGrid}
						showAxes={showAxes}
						showTracks={showTracks}
					/>
				</Canvas>
			</div>
		</ChartContainer>
	)
}

// Color mode selector component
export function ColorModeSelector({
	value,
	onChange,
}: {
	value: string
	onChange: (mode: string) => void
}) {
	return (
		<select
			value={value}
			onChange={(e) => onChange(e.target.value)}
			className="px-2 py-1 bg-surface border border-border rounded text-sm"
		>
			<option value="velocity">Velocity (Blue=Approaching, Red=Receding)</option>
			<option value="snr">SNR (Blue=Low, Red=High)</option>
			<option value="height">Height (Purple=Low, Cyan=High)</option>
			<option value="age">Age (White=New, Gray=Old)</option>
			<option value="track">Track ID (Colored by track)</option>
		</select>
	)
}
