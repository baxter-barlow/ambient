import { create } from 'zustand'
import type { DeviceStatus, SensorFrame, VitalSigns, LogEntry } from '../types'

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

		// Keep 5 minutes of history
		const cutoff = Date.now() / 1000 - 300
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
		if (logs.length > 1000) logs.shift()
		return { logs }
	}),
	clearLogs: () => set({ logs: [] }),

	// WebSocket
	wsConnected: false,
	setWsConnected: (connected) => set({ wsConnected: connected }),
}))
