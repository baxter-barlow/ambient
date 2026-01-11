import { useEffect, useRef } from 'react'
import { sensorWs, logsWs } from '../api/websocket'
import { useAppStore } from '../stores/appStore'
import type {
	WSMessage,
	DeviceStatus,
	SensorFrame,
	VitalSigns,
	LogEntry,
	TrackedObject,
	Point3DWithAge,
	MultiPatientVitals,
	PresenceIndication,
} from '../types'

export function useSensorWebSocket() {
	const setDeviceStatus = useAppStore(s => s.setDeviceStatus)
	const appendFrame = useAppStore(s => s.appendFrame)
	const setVitals = useAppStore(s => s.setVitals)
	const setWsConnected = useAppStore(s => s.setWsConnected)
	const appendPointCloud = useAppStore(s => s.appendPointCloud)
	const setTrackedObjects = useAppStore(s => s.setTrackedObjects)
	const setMultiPatientVitals = useAppStore(s => s.setMultiPatientVitals)
	const setPresence = useAppStore(s => s.setPresence)

	const handlersRef = useRef<(() => void)[]>([])

	useEffect(() => {
		// Connect to sensor WebSocket
		sensorWs.connect((connected) => {
			setWsConnected(connected)
		})

		// Register handlers
		handlersRef.current = [
			sensorWs.on('device_state', (msg: WSMessage<DeviceStatus>) => {
				setDeviceStatus(msg.payload)
			}),
			sensorWs.on('sensor_frame', (msg: WSMessage<SensorFrame>) => {
				appendFrame(msg.payload)
				// Also extract point cloud from detected_points
				if (msg.payload.detected_points && msg.payload.detected_points.length > 0) {
					const points: Point3DWithAge[] = msg.payload.detected_points.map(p => ({
						...p,
						age: 0,
					}))
					appendPointCloud(points)
				}
			}),
			sensorWs.on('vitals', (msg: WSMessage<VitalSigns>) => {
				setVitals(msg.payload)
			}),
			sensorWs.on('tracked_objects', (msg: WSMessage<{ objects: TrackedObject[] }>) => {
				setTrackedObjects(msg.payload.objects)
			}),
			sensorWs.on('point_cloud', (msg: WSMessage<{ points: Point3DWithAge[] }>) => {
				appendPointCloud(msg.payload.points)
			}),
			sensorWs.on('multi_patient_vitals', (msg: WSMessage<MultiPatientVitals>) => {
				setMultiPatientVitals(msg.payload)
			}),
			sensorWs.on('presence', (msg: WSMessage<PresenceIndication>) => {
				setPresence(msg.payload)
			}),
		]

		return () => {
			handlersRef.current.forEach(unsub => unsub())
			sensorWs.disconnect()
		}
	}, [
		setDeviceStatus,
		appendFrame,
		setVitals,
		setWsConnected,
		appendPointCloud,
		setTrackedObjects,
		setMultiPatientVitals,
		setPresence,
	])
}

export function useLogsWebSocket() {
	const appendLog = useAppStore(s => s.appendLog)
	const handlersRef = useRef<(() => void)[]>([])

	useEffect(() => {
		logsWs.connect()

		handlersRef.current = [
			logsWs.on('log', (msg: WSMessage<LogEntry>) => {
				appendLog(msg.payload)
			}),
		]

		return () => {
			handlersRef.current.forEach(unsub => unsub())
			logsWs.disconnect()
		}
	}, [appendLog])
}
