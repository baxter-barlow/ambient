/**
 * Application-wide constants for the Ambient dashboard.
 *
 * Centralizes magic numbers and configuration values that are used
 * across multiple components.
 */

// =============================================================================
// Polling & Timing
// =============================================================================

/** Interval for refreshing device status (ms) */
export const STATUS_POLL_INTERVAL_MS = 1000

/** Interval for refreshing metrics data (ms) */
export const METRICS_POLL_INTERVAL_MS = 2000

/** Interval for refreshing recordings list (ms) */
export const RECORDINGS_POLL_INTERVAL_MS = 5000

/** WebSocket reconnection delay (ms) */
export const WS_RECONNECT_DELAY_MS = 1000

/** Maximum WebSocket reconnect attempts */
export const WS_MAX_RECONNECT_ATTEMPTS = 10

// =============================================================================
// Buffers & Limits
// =============================================================================

/** Maximum number of log entries to retain */
export const MAX_LOG_ENTRIES = 1000

/** Log retention window in seconds */
export const LOG_RETENTION_SECONDS = 300

// =============================================================================
// Performance Thresholds
// =============================================================================

/** Frame processing time threshold for warning (ms) */
export const FRAME_TIME_WARNING_MS = 100

/** Minimum confidence level to display (0-1) */
export const MIN_DISPLAY_CONFIDENCE = 0.3

// =============================================================================
// UI Constants
// =============================================================================

/** Signal viewer window size options in seconds */
export const SIGNAL_WINDOW_OPTIONS = [
	{ value: 10, label: '10s' },
	{ value: 30, label: '30s' },
	{ value: 60, label: '1m' },
] as const

/** Default signal window size in seconds */
export const DEFAULT_SIGNAL_WINDOW_SECONDS = 30

// =============================================================================
// API Endpoints (relative to base URL)
// =============================================================================

export const API_ROUTES = {
	device: {
		status: '/api/device/status',
		ports: '/api/device/ports',
		connect: '/api/device/connect',
		disconnect: '/api/device/disconnect',
		stop: '/api/device/stop',
		metrics: '/api/device/metrics',
	},
	recordings: {
		list: '/api/recordings',
		status: '/api/recordings/status',
		start: '/api/recordings/start',
		stop: '/api/recordings/stop',
	},
	config: {
		list: '/api/config/profiles',
		files: '/api/config/files',
	},
} as const
