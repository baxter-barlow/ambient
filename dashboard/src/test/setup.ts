import '@testing-library/jest-dom'

// Mock WebSocket for tests
class MockWebSocket {
	onopen: (() => void) | null = null
	onclose: (() => void) | null = null
	onmessage: ((event: { data: string }) => void) | null = null
	onerror: (() => void) | null = null
	readyState = WebSocket.OPEN

	close() {
		this.readyState = WebSocket.CLOSED
	}

	send(_data: string) {
		// Mock send
	}
}

// @ts-expect-error - Mock WebSocket
globalThis.WebSocket = MockWebSocket

// Mock ResizeObserver
globalThis.ResizeObserver = class ResizeObserver {
	observe() {}
	unobserve() {}
	disconnect() {}
}

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
	writable: true,
	value: (query: string) => ({
		matches: false,
		media: query,
		onchange: null,
		addListener: () => {},
		removeListener: () => {},
		addEventListener: () => {},
		removeEventListener: () => {},
		dispatchEvent: () => false,
	}),
})
