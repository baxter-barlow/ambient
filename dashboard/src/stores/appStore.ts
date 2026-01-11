import { create } from 'zustand'
import { LOG_RETENTION_SECONDS, MAX_LOG_ENTRIES } from '../constants'
import type {
	DeviceStatus,
	SensorFrame,
	VitalSigns,
	LogEntry,
	Point3DWithAge,
	TrackedObject,
	MultiPatientVitals,
	PresenceIndication,
} from '../types'

// Extended history entry with quality metrics
interface VitalsHistoryEntry {
	timestamp: number
	hr: number | null
	rr: number | null
	hr_snr_db: number
	rr_snr_db: number
	phase_stability: number
	signal_quality: number
	source: string
}

interface AppState {
	// Device state
	deviceStatus: DeviceStatus | null
	deviceStatusUpdatedAt: number | null  // Unix timestamp of last update
	setDeviceStatus: (status: DeviceStatus) => void

	// Sensor data
	sensorFrames: SensorFrame[]
	maxFrames: number
	appendFrame: (frame: SensorFrame) => void
	clearFrames: () => void

	// Vitals
	vitals: VitalSigns | null
	vitalsHistory: VitalsHistoryEntry[]
	setVitals: (vitals: VitalSigns) => void
	clearVitalsHistory: () => void

	// UI state
	isPaused: boolean
	togglePause: () => void
	timeWindow: number
	setTimeWindow: (window: number) => void

	// Logs
	logs: LogEntry[]
	appendLog: (log: LogEntry) => void
	clearLogs: () => void

	// WebSocket
	wsConnected: boolean
	setWsConnected: (connected: boolean) => void

	// Point cloud with persistence
	pointCloud: Point3DWithAge[]
	pointCloudConfig: {
		maxAge: number
		maxPoints: number
	}
	appendPointCloud: (points: Point3DWithAge[]) => void
	clearPointCloud: () => void

	// Tracked objects
	trackedObjects: TrackedObject[]
	setTrackedObjects: (objects: TrackedObject[]) => void

	// Multi-patient vitals
	multiPatientVitals: MultiPatientVitals | null
	setMultiPatientVitals: (vitals: MultiPatientVitals) => void

	// Presence detection
	presence: PresenceIndication | null
	setPresence: (presence: PresenceIndication) => void
}

export const useAppStore = create<AppState>((set) => ({
	// Device
	deviceStatus: null,
	deviceStatusUpdatedAt: null,
	setDeviceStatus: (status) => set({ deviceStatus: status, deviceStatusUpdatedAt: Date.now() }),

	// Sensor data (keep last N frames for plotting)
	sensorFrames: [],
	maxFrames: 200, // 10 seconds at 20 Hz
	appendFrame: (frame) => set((state) => {
		if (state.isPaused) return state
		const frames = [...state.sensorFrames, frame]
		if (frames.length > state.maxFrames) {
			frames.shift()
		}
		return { sensorFrames: frames }
	}),
	clearFrames: () => set({ sensorFrames: [] }),

	// Vitals with extended history tracking
	vitals: null,
	vitalsHistory: [],
	setVitals: (vitals) => set((state) => {
		if (state.isPaused) return { vitals }

		const entry: VitalsHistoryEntry = {
			timestamp: Date.now() / 1000,
			hr: vitals.heart_rate_bpm,
			rr: vitals.respiratory_rate_bpm,
			hr_snr_db: vitals.hr_snr_db ?? 0,
			rr_snr_db: vitals.rr_snr_db ?? 0,
			phase_stability: vitals.phase_stability ?? 0,
			signal_quality: vitals.signal_quality,
			source: vitals.source,
		}

		const history = [...state.vitalsHistory, entry]

		// Keep configurable duration of history
		const cutoff = Date.now() / 1000 - LOG_RETENTION_SECONDS
		const filtered = history.filter(h => h.timestamp > cutoff)

		return { vitals, vitalsHistory: filtered }
	}),
	clearVitalsHistory: () => set({ vitalsHistory: [] }),

	// UI
	isPaused: false,
	togglePause: () => set((state) => ({ isPaused: !state.isPaused })),
	timeWindow: 30,
	setTimeWindow: (window) => set({ timeWindow: window }),

	// Logs
	logs: [],
	appendLog: (log) => set((state) => {
		const logs = [...state.logs, log]
		if (logs.length > MAX_LOG_ENTRIES) logs.shift()
		return { logs }
	}),
	clearLogs: () => set({ logs: [] }),

	// WebSocket
	wsConnected: false,
	setWsConnected: (connected) => set({ wsConnected: connected }),

	// Point cloud with persistence
	pointCloud: [],
	pointCloudConfig: {
		maxAge: 15,    // Frames to retain points
		maxPoints: 500, // Max points to store
	},
	appendPointCloud: (newPoints) => set((state) => {
		if (state.isPaused) return state

		// Age existing points
		const aged = state.pointCloud.map(p => ({
			...p,
			age: p.age + 1,
		}))

		// Remove points that exceed max age
		const filtered = aged.filter(p => p.age < state.pointCloudConfig.maxAge)

		// Add new points with age 0
		const combined = [...filtered, ...newPoints.map(p => ({ ...p, age: 0 }))]

		// Limit total points
		const limited = combined.slice(-state.pointCloudConfig.maxPoints)

		return { pointCloud: limited }
	}),
	clearPointCloud: () => set({ pointCloud: [] }),

	// Tracked objects
	trackedObjects: [],
	setTrackedObjects: (objects) => set((state) => {
		if (state.isPaused) return state
		return { trackedObjects: objects }
	}),

	// Multi-patient vitals
	multiPatientVitals: null,
	setMultiPatientVitals: (vitals) => set((state) => {
		if (state.isPaused) return { multiPatientVitals: vitals }
		return { multiPatientVitals: vitals }
	}),

	// Presence detection
	presence: null,
	setPresence: (presence) => set({ presence }),
}))
