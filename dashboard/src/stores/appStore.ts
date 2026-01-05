import { create } from 'zustand'
import type { DeviceStatus, SensorFrame, VitalSigns, LogEntry } from '../types'

interface AppState {
	// Device state
	deviceStatus: DeviceStatus | null
	setDeviceStatus: (status: DeviceStatus) => void

	// Sensor data
	sensorFrames: SensorFrame[]
	maxFrames: number
	appendFrame: (frame: SensorFrame) => void
	clearFrames: () => void

	// Vitals
	vitals: VitalSigns | null
	vitalsHistory: { timestamp: number; hr: number | null; rr: number | null }[]
	setVitals: (vitals: VitalSigns) => void

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
	setDeviceStatus: (status) => set({ deviceStatus: status }),

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

	// Vitals
	vitals: null,
	vitalsHistory: [],
	setVitals: (vitals) => set((state) => {
		if (state.isPaused) return { vitals }
		const history = [...state.vitalsHistory, {
			timestamp: Date.now() / 1000,
			hr: vitals.heart_rate_bpm,
			rr: vitals.respiratory_rate_bpm,
		}]
		// Keep 5 minutes of history
		const cutoff = Date.now() / 1000 - 300
		const filtered = history.filter(h => h.timestamp > cutoff)
		return { vitals, vitalsHistory: filtered }
	}),

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
