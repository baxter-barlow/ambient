import { WS_MAX_RECONNECT_ATTEMPTS, WS_RECONNECT_DELAY_MS } from '../constants'
import type { WSMessage } from '../types'

type MessageHandler<T = unknown> = (message: WSMessage<T>) => void

export class WebSocketClient {
	private ws: WebSocket | null = null
	private url: string
	private handlers: Map<string, Set<MessageHandler<unknown>>> = new Map()
	private reconnectAttempts = 0
	private maxReconnectAttempts = WS_MAX_RECONNECT_ATTEMPTS
	private reconnectDelay = WS_RECONNECT_DELAY_MS
	private shouldReconnect = true
	private onConnectChange?: (connected: boolean) => void

	constructor(path: string) {
		const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
		this.url = `${protocol}//${window.location.host}${path}`
	}

	connect(onConnectChange?: (connected: boolean) => void) {
		this.onConnectChange = onConnectChange
		this.shouldReconnect = true
		this.doConnect()
	}

	private doConnect() {
		if (this.ws?.readyState === WebSocket.OPEN) return

		try {
			this.ws = new WebSocket(this.url)

			this.ws.onopen = () => {
				this.reconnectAttempts = 0
				this.onConnectChange?.(true)
			}

			this.ws.onclose = () => {
				this.onConnectChange?.(false)
				if (this.shouldReconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
					this.reconnectAttempts++
					const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)
					setTimeout(() => this.doConnect(), Math.min(delay, 30000))
				}
			}

			this.ws.onerror = () => {
				// Error handling done in onclose
			}

			this.ws.onmessage = (event) => {
				try {
					const message = JSON.parse(event.data) as WSMessage
					this.dispatch(message)
				} catch (e) {
					console.debug('WebSocket parse error:', e)
				}
			}
		} catch (e) {
			console.debug('WebSocket connection failed:', e)
		}
	}

	disconnect() {
		this.shouldReconnect = false
		this.ws?.close()
		this.ws = null
	}

	send(message: object) {
		if (this.ws?.readyState === WebSocket.OPEN) {
			this.ws.send(JSON.stringify(message))
		}
	}

	on<T = unknown>(type: string, handler: MessageHandler<T>) {
		if (!this.handlers.has(type)) {
			this.handlers.set(type, new Set())
		}
		this.handlers.get(type)!.add(handler as MessageHandler<unknown>)
		return () => this.off(type, handler)
	}

	off<T = unknown>(type: string, handler: MessageHandler<T>) {
		this.handlers.get(type)?.delete(handler as MessageHandler<unknown>)
	}

	private dispatch(message: WSMessage) {
		// Dispatch to type-specific handlers
		this.handlers.get(message.type)?.forEach(h => h(message))
		// Dispatch to wildcard handlers
		this.handlers.get('*')?.forEach(h => h(message))
	}

	get isConnected() {
		return this.ws?.readyState === WebSocket.OPEN
	}
}

// Singleton instances
export const sensorWs = new WebSocketClient('/ws/sensor')
export const logsWs = new WebSocketClient('/ws/logs')
export const testsWs = new WebSocketClient('/ws/tests')
