import { useState, useEffect } from 'react'
import { useAppStore } from '../stores/appStore'
import { deviceApi } from '../api/client'
import Button from '../components/common/Button'
import Select from '../components/common/Select'
import StatusIndicator from '../components/common/StatusIndicator'
import { showToast } from '../components/common/Toast'
import type { SerialPort, PortVerifyResult, PerformanceMetrics } from '../types'
import clsx from 'clsx'

/**
 * Device Status page following TE design principles:
 * - Left-aligned, asymmetric layout
 * - Borders as hierarchy tool
 * - Monospace for data values
 * - Functional accents only
 */
export default function DeviceStatus() {
	const deviceStatus = useAppStore(s => s.deviceStatus)
	const deviceStatusUpdatedAt = useAppStore(s => s.deviceStatusUpdatedAt)
	const wsConnected = useAppStore(s => s.wsConnected)
	const [ports, setPorts] = useState<SerialPort[]>([])
	const [cliPort, setCliPort] = useState('')
	const [dataPort, setDataPort] = useState('')
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState<string | null>(null)
	const [verifying, setVerifying] = useState(false)
	const [verifyResult, setVerifyResult] = useState<PortVerifyResult | null>(null)
	const [metrics, setMetrics] = useState<PerformanceMetrics | null>(null)
	const [showMetrics, setShowMetrics] = useState(false)
	const [now, setNow] = useState(Date.now())

	useEffect(() => {
		deviceApi.getPorts().then(detected => {
			setPorts(detected)
			// Auto-select first two detected ports if not already set
			if (detected.length >= 2 && !cliPort && !dataPort) {
				setCliPort(detected[0].device)
				setDataPort(detected[1].device)
			} else if (detected.length === 1 && !cliPort) {
				// Single port mode (some devices)
				setCliPort(detected[0].device)
				setDataPort(detected[0].device)
			} else if (detected.length === 0 && !cliPort && !dataPort) {
				// No ports detected - use platform-appropriate defaults
				const isLinux = navigator.platform.toLowerCase().includes('linux')
				if (isLinux) {
					setCliPort('/dev/ttyUSB0')
					setDataPort('/dev/ttyUSB1')
				} else {
					// macOS fallback
					setCliPort('/dev/cu.usbserial-0001')
					setDataPort('/dev/cu.usbmodem0001')
				}
			}
		}).catch(console.warn)
	}, [])

	useEffect(() => {
		const interval = setInterval(() => setNow(Date.now()), 1000)
		return () => clearInterval(interval)
	}, [])

	useEffect(() => {
		if (!showMetrics) return
		const fetchMetrics = () => {
			deviceApi.getMetrics().then(setMetrics).catch(console.warn)
		}
		fetchMetrics()
		const interval = setInterval(fetchMetrics, 2000)
		return () => clearInterval(interval)
	}, [showMetrics])

	const handleConnect = async () => {
		setLoading(true)
		setError(null)
		try {
			await deviceApi.connect(cliPort, dataPort)
			showToast('Connected to sensor', 'success')
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'Connection failed'
			setError(msg)
			showToast(msg, 'error')
		} finally {
			setLoading(false)
		}
	}

	const handleDisconnect = async () => {
		setLoading(true)
		try {
			await deviceApi.disconnect()
			showToast('Disconnected', 'info')
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'Disconnect failed'
			setError(msg)
		} finally {
			setLoading(false)
		}
	}

	const handleStop = async () => {
		setLoading(true)
		try {
			await deviceApi.stop()
			showToast('Sensor stopped', 'warning')
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'Stop failed'
			setError(msg)
		} finally {
			setLoading(false)
		}
	}

	const handleVerify = async () => {
		setVerifying(true)
		setVerifyResult(null)
		try {
			const result = await deviceApi.verifyPorts(cliPort, dataPort)
			setVerifyResult(result)
			if (result.overall === 'pass') {
				showToast('Ports verified', 'success')
			} else if (result.overall === 'warning') {
				showToast('Ports verified with warnings', 'warning')
			} else {
				showToast('Verification failed', 'error')
			}
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'Verification failed'
			setError(msg)
		} finally {
			setVerifying(false)
		}
	}

	const isConnected = deviceStatus?.state === 'streaming' || deviceStatus?.state === 'configuring'
	const canConnect = verifyResult?.overall === 'pass' || verifyResult?.overall === 'warning'
	const secondsSinceUpdate = deviceStatusUpdatedAt ? Math.floor((now - deviceStatusUpdatedAt) / 1000) : null

	// Port options: use detected ports or show common patterns for Linux/macOS
	const portOptions = ports.length > 0
		? ports.map(p => ({ value: p.device, label: p.device }))
		: [
			// Linux patterns
			{ value: '/dev/ttyUSB0', label: '/dev/ttyUSB0' },
			{ value: '/dev/ttyUSB1', label: '/dev/ttyUSB1' },
			{ value: '/dev/ttyACM0', label: '/dev/ttyACM0' },
			{ value: '/dev/ttyACM1', label: '/dev/ttyACM1' },
			// macOS patterns (common USB serial adapters)
			{ value: '/dev/cu.usbserial-0001', label: '/dev/cu.usbserial-0001' },
			{ value: '/dev/cu.usbmodem0001', label: '/dev/cu.usbmodem0001' },
		]

	return (
		<div className="space-y-6 max-w-4xl">
			{/* Status Overview */}
			<div className="grid grid-cols-4 gap-4">
				<div className="bg-bg-secondary border border-border p-4">
					<span className="text-label text-ink-muted block mb-2">CONNECTION</span>
					<div className="flex items-center gap-2">
						<div className={clsx('w-3 h-3', wsConnected ? 'bg-accent-green' : 'bg-accent-red')} />
						<span className="font-mono text-body text-ink-primary">
							{wsConnected ? 'ONLINE' : 'OFFLINE'}
						</span>
					</div>
				</div>

				<div className="bg-bg-secondary border border-border p-4">
					<span className="text-label text-ink-muted block mb-2">SENSOR</span>
					<span className={clsx(
						'font-mono text-body',
						{
							'text-ink-muted': !deviceStatus || deviceStatus.state === 'disconnected',
							'text-accent-orange': deviceStatus?.state === 'connecting' || deviceStatus?.state === 'configuring',
							'text-accent-green': deviceStatus?.state === 'streaming',
							'text-accent-red': deviceStatus?.state === 'error',
						}
					)}>
						{deviceStatus?.state?.toUpperCase() ?? 'UNKNOWN'}
					</span>
				</div>

				<div className="bg-bg-secondary border border-border p-4">
					<span className="text-label text-ink-muted block mb-2">FRAME RATE</span>
					<span className="font-mono text-body text-ink-primary">
						{deviceStatus?.frame_rate?.toFixed(1) ?? '0.0'} Hz
					</span>
				</div>

				<div className="bg-bg-secondary border border-border p-4">
					<span className="text-label text-ink-muted block mb-2">FRAMES</span>
					<span className="font-mono text-body text-ink-primary">
						{deviceStatus?.frame_count?.toLocaleString() ?? '0'}
					</span>
				</div>
			</div>

			{/* Main panels */}
			<div className="grid grid-cols-2 gap-6">
				{/* Connection Details */}
				<div className="bg-bg-secondary border border-border">
					<div className="px-4 py-3 border-b border-border flex justify-between items-center">
						<span className="text-small font-medium text-ink-primary">Connection</span>
						{secondsSinceUpdate !== null && (
							<span className={clsx(
								'text-label',
								secondsSinceUpdate > 3 ? 'text-accent-orange' : 'text-ink-muted'
							)}>
								{secondsSinceUpdate}s AGO
							</span>
						)}
					</div>
					<div className="p-4 space-y-4">
						<div className="grid grid-cols-2 gap-4">
							<div>
								<span className="text-label text-ink-muted block mb-1">STATE</span>
								<StatusIndicator
									status={
										deviceStatus?.state === 'streaming' ? 'success' :
										deviceStatus?.state === 'error' ? 'error' :
										deviceStatus?.state === 'connecting' ? 'warning' : 'neutral'
									}
									label={deviceStatus?.state ?? 'unknown'}
								/>
							</div>
							<div>
								<span className="text-label text-ink-muted block mb-1">CONFIG</span>
								<span className="font-mono text-small text-ink-primary">
									{deviceStatus?.config_name || 'default'}
								</span>
							</div>
							<div>
								<span className="text-label text-ink-muted block mb-1">CLI PORT</span>
								<span className="font-mono text-small text-ink-primary">
									{deviceStatus?.cli_port || '—'}
								</span>
							</div>
							<div>
								<span className="text-label text-ink-muted block mb-1">DATA PORT</span>
								<span className="font-mono text-small text-ink-primary">
									{deviceStatus?.data_port || '—'}
								</span>
							</div>
						</div>

						{deviceStatus?.error && (
							<div className="p-3 border border-accent-red bg-bg-tertiary">
								<span className="text-small text-accent-red">{deviceStatus.error}</span>
							</div>
						)}
					</div>
				</div>

				{/* Port Selection / Health */}
				{!isConnected ? (
					<div className="bg-bg-secondary border border-border">
						<div className="px-4 py-3 border-b border-border">
							<span className="text-small font-medium text-ink-primary">Port Selection</span>
						</div>
						<div className="p-4 space-y-4">
							<div className="grid grid-cols-2 gap-4">
								<Select
									label="CLI Port"
									options={portOptions}
									value={cliPort}
									onChange={e => { setCliPort(e.target.value); setVerifyResult(null) }}
								/>
								<Select
									label="Data Port"
									options={portOptions}
									value={dataPort}
									onChange={e => { setDataPort(e.target.value); setVerifyResult(null) }}
								/>
							</div>

							{verifyResult && (
								<div className="space-y-2">
									<div className={clsx(
										'p-3 border',
										verifyResult.cli_port.status === 'ok' ? 'border-accent-green' :
										verifyResult.cli_port.status === 'warning' ? 'border-accent-orange' :
										'border-accent-red'
									)}>
										<div className="flex items-center gap-2 mb-1">
											<div className={clsx(
												'w-2 h-2',
												verifyResult.cli_port.status === 'ok' ? 'bg-accent-green' :
												verifyResult.cli_port.status === 'warning' ? 'bg-accent-orange' : 'bg-accent-red'
											)} />
											<span className="text-small text-ink-primary">CLI: {verifyResult.cli_port.path}</span>
										</div>
										<span className="text-label text-ink-muted">{verifyResult.cli_port.details}</span>
									</div>
									<div className={clsx(
										'p-3 border',
										verifyResult.data_port.status === 'ok' ? 'border-accent-green' :
										verifyResult.data_port.status === 'warning' ? 'border-accent-orange' :
										'border-accent-red'
									)}>
										<div className="flex items-center gap-2 mb-1">
											<div className={clsx(
												'w-2 h-2',
												verifyResult.data_port.status === 'ok' ? 'bg-accent-green' :
												verifyResult.data_port.status === 'warning' ? 'bg-accent-orange' : 'bg-accent-red'
											)} />
											<span className="text-small text-ink-primary">Data: {verifyResult.data_port.path}</span>
										</div>
										<span className="text-label text-ink-muted">{verifyResult.data_port.details}</span>
									</div>
								</div>
							)}
						</div>
					</div>
				) : (
					<div className="bg-bg-secondary border border-border">
						<div className="px-4 py-3 border-b border-border flex justify-between items-center">
							<span className="text-small font-medium text-ink-primary">Sensor Health</span>
							<button
								onClick={() => setShowMetrics(!showMetrics)}
								className="text-label text-ink-muted hover:text-ink-primary transition-all duration-fast"
							>
								{showMetrics ? 'HIDE METRICS' : 'SHOW METRICS'}
							</button>
						</div>
						<div className="p-4">
							<div className="grid grid-cols-2 gap-4">
								<div>
									<span className="text-label text-ink-muted block mb-1">FRAME RATE</span>
									<span className="font-mono text-h3 text-ink-primary">
										{deviceStatus?.frame_rate.toFixed(1)}
										<span className="text-small text-ink-muted ml-1">Hz</span>
									</span>
								</div>
								<div>
									<span className="text-label text-ink-muted block mb-1">FRAMES</span>
									<span className="font-mono text-h3 text-ink-primary">
										{deviceStatus?.frame_count.toLocaleString()}
									</span>
								</div>
								<div>
									<span className="text-label text-ink-muted block mb-1">DROPPED</span>
									<span className={clsx(
										'font-mono text-h3',
										deviceStatus?.dropped_frames ? 'text-accent-orange' : 'text-ink-primary'
									)}>
										{deviceStatus?.dropped_frames ?? 0}
									</span>
								</div>
								<div>
									<span className="text-label text-ink-muted block mb-1">BUFFER</span>
									<span className="font-mono text-h3 text-ink-primary">
										{((deviceStatus?.buffer_usage || 0) * 100).toFixed(0)}%
									</span>
								</div>
							</div>
						</div>
					</div>
				)}
			</div>

			{/* Performance Metrics */}
			{showMetrics && metrics && (
				<div className="bg-bg-secondary border border-border">
					<div className="px-4 py-3 border-b border-border flex justify-between items-center">
						<span className="text-small font-medium text-ink-primary">Performance Metrics</span>
						<button
							onClick={() => { deviceApi.resetMetrics(); showToast('Metrics reset', 'info') }}
							className="text-label text-ink-muted hover:text-ink-primary"
						>
							RESET
						</button>
					</div>
					<div className="p-4 space-y-4">
						{metrics.timing.total && (
							<div>
								<span className="text-label text-ink-muted block mb-2">LATENCY</span>
								<div className="grid grid-cols-4 gap-4 font-mono text-small">
									<div>
										<span className="text-ink-muted">P50</span>
										<span className="ml-2 text-ink-primary">{metrics.timing.total.p50_ms.toFixed(1)}ms</span>
									</div>
									<div>
										<span className="text-ink-muted">P95</span>
										<span className="ml-2 text-ink-primary">{metrics.timing.total.p95_ms.toFixed(1)}ms</span>
									</div>
									<div>
										<span className="text-ink-muted">P99</span>
										<span className={clsx('ml-2', metrics.timing.total.p99_ms > 50 ? 'text-accent-orange' : 'text-ink-primary')}>
											{metrics.timing.total.p99_ms.toFixed(1)}ms
										</span>
									</div>
									<div>
										<span className="text-ink-muted">MAX</span>
										<span className={clsx('ml-2', metrics.timing.total.max_ms > 100 ? 'text-accent-red' : 'text-ink-primary')}>
											{metrics.timing.total.max_ms.toFixed(1)}ms
										</span>
									</div>
								</div>
							</div>
						)}
					</div>
				</div>
			)}

			{/* Error */}
			{error && (
				<div className="p-4 border border-accent-red bg-bg-secondary">
					<div className="flex items-center justify-between">
						<span className="text-small text-accent-red">{error}</span>
						<button onClick={() => setError(null)} className="text-label text-ink-muted hover:text-ink-primary">
							DISMISS
						</button>
					</div>
				</div>
			)}

			{/* Controls */}
			<div className="flex gap-3">
				{!isConnected ? (
					<>
						<Button variant="secondary" onClick={handleVerify} disabled={verifying || loading}>
							{verifying ? 'Verifying...' : 'Verify'}
						</Button>
						<Button onClick={handleConnect} disabled={loading || !canConnect}>
							{loading ? 'Connecting...' : 'Connect'}
						</Button>
					</>
				) : (
					<>
						<Button variant="secondary" onClick={handleDisconnect} disabled={loading}>
							Disconnect
						</Button>
						<Button variant="danger" onClick={handleStop} disabled={loading}>
							Stop
						</Button>
					</>
				)}
				<Button variant="secondary" onClick={() => deviceApi.getPorts().then(setPorts)}>
					Refresh Ports
				</Button>
			</div>
		</div>
	)
}
