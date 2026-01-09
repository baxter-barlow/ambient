export type DeviceState = 'disconnected' | 'connecting' | 'configuring' | 'streaming' | 'error'

export interface DeviceStatus {
	state: DeviceState
	cli_port: string | null
	data_port: string | null
	frame_rate: number
	frame_count: number
	dropped_frames: number
	buffer_usage: number
	error: string | null
	config_name: string | null
}

export interface SerialPort {
	device: string
	description: string
}

export interface PortStatus {
	path: string
	status: 'ok' | 'warning' | 'error' | 'unknown'
	details: string
}

export interface PortVerifyResult {
	cli_port: PortStatus
	data_port: PortStatus
	overall: 'pass' | 'warning' | 'fail'
}

export interface DetectedPoint {
	x: number
	y: number
	z: number
	velocity: number
	snr: number
}

export interface SensorFrame {
	frame_number: number
	timestamp: number
	range_profile: number[]
	range_doppler?: number[][]
	detected_points: DetectedPoint[]
	phase?: number
}

export interface VitalSigns {
	heart_rate_bpm: number | null
	heart_rate_confidence: number
	respiratory_rate_bpm: number | null
	respiratory_rate_confidence: number
	signal_quality: number
	motion_detected: boolean
	source: 'firmware' | 'estimated' | 'chirp'
	breathing_waveform?: number[]
	heart_waveform?: number[]
	phase_signal?: number[]  // Raw phase signal for visualization
	unwrapped_phase?: number
	// Enhanced quality metrics
	hr_snr_db?: number
	rr_snr_db?: number
	phase_stability?: number
}

export interface WSMessage<T = unknown> {
	type: string
	timestamp: number
	payload: T
}

export interface RecordingInfo {
	id: string
	name: string
	path: string
	format: string
	created: number
	duration: number | null
	frame_count: number
	size_bytes: number
}

export interface RecordingStatus {
	is_recording: boolean
	recording_id: string | null
	name: string | null
	duration: number
	frame_count: number
}

export interface ConfigProfile {
	name: string
	description: string
	chirp: ChirpParams
	frame: FrameParams
}

export interface ChirpParams {
	start_freq_ghz: number
	bandwidth_mhz: number
	idle_time_us: number
	ramp_end_time_us: number
	adc_samples: number
	sample_rate_ksps: number
	rx_gain_db: number
}

export interface FrameParams {
	chirps_per_frame: number
	frame_period_ms: number
}

export interface AlgorithmParams {
	hr_low_hz: number
	hr_high_hz: number
	rr_low_hz: number
	rr_high_hz: number
	window_seconds: number
	clutter_method: string
}

export interface LogEntry {
	timestamp: number
	level: string
	logger: string
	message: string
	extra: Record<string, unknown>
}

export interface TimingStats {
	count: number
	mean_ms: number
	min_ms: number
	max_ms: number
	p50_ms: number
	p95_ms: number
	p99_ms: number
	last_ms: number
}

export interface QueueStats {
	current_depth: number
	max_depth: number
	avg_depth: number
	total_enqueued: number
	total_dropped: number
	drop_rate_percent: number
}

export interface WSChannelMetrics {
	messages_sent: number
	messages_dropped: number
	bytes_sent: number
	send_errors: number
	avg_send_time_ms: number
	queue_depth: number
}

export interface PerformanceMetrics {
	enabled: boolean
	frame_count: number
	sampled_count: number
	dropped_frames: number
	sample_rate: number
	timing: Record<string, TimingStats>
	queues: Record<string, QueueStats>
	websocket: {
		total: WSChannelMetrics
		by_channel: Record<string, WSChannelMetrics>
		connections: Record<string, number>
	}
}
