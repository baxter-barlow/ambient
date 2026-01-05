import { useEffect, useRef } from 'react'
import { sensorWs, logsWs } from '../api/websocket'
import { useAppStore } from '../stores/appStore'
import type { WSMessage, DeviceStatus, SensorFrame, VitalSigns, LogEntry } from '../types'

export function useSensorWebSocket() {
	const setDeviceStatus = useAppStore(s => s.setDeviceStatus)
	const appendFrame = useAppStore(s => s.appendFrame)
	const setVitals = useAppStore(s => s.setVitals)
	const setWsConnected = useAppStore(s => s.setWsConnected)

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
			}),
			sensorWs.on('vitals', (msg: WSMessage<VitalSigns>) => {
				setVitals(msg.payload)
			}),
		]

		return () => {
			handlersRef.current.forEach(unsub => unsub())
			sensorWs.disconnect()
		}
	}, [setDeviceStatus, appendFrame, setVitals, setWsConnected])
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
