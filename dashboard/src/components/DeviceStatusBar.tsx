import { memo, useState, useEffect, useRef } from 'react'
import { useAppStore } from '../stores/appStore'
import { deviceApi } from '../api/client'
import { showToast } from './common/Toast'
import clsx from 'clsx'
import type { SerialPort, PortVerifyResult } from '../types'

/**
 * Compact device status bar following TE design principles.
 * Single-line display of all critical device metrics.
 * Includes connection dropdown for port selection with auto-detection.
 */
export default memo(function DeviceStatusBar() {
	const deviceStatus = useAppStore(s => s.deviceStatus)
	const wsConnected = useAppStore(s => s.wsConnected)
	const isPaused = useAppStore(s => s.isPaused)
	const togglePause = useAppStore(s => s.togglePause)

	// Connection panel state
	const [showConnectPanel, setShowConnectPanel] = useState(false)
	const [ports, setPorts] = useState<SerialPort[]>([])
	const [cliPort, setCliPort] = useState('')
	const [dataPort, setDataPort] = useState('')
	const [verifying, setVerifying] = useState(false)
	const [scanning, setScanning] = useState(false)
	const [connecting, setConnecting] = useState(false)
	const [verifyResult, setVerifyResult] = useState<PortVerifyResult | null>(null)
	const [scanStatus, setScanStatus] = useState<string | null>(null)
	const panelRef = useRef<HTMLDivElement>(null)

	const isConnected = deviceStatus?.state === 'streaming' || deviceStatus?.state === 'configuring'
	const isStreaming = deviceStatus?.state === 'streaming'
	const isDisconnected = !deviceStatus || deviceStatus.state === 'disconnected'

	// Load available ports when panel opens and auto-select if only 2 ports
	useEffect(() => {
		if (showConnectPanel) {
			loadPorts()
		}
	}, [showConnectPanel])

	const loadPorts = async () => {
		try {
			const portList = await deviceApi.getPorts()
			setPorts(portList)

			// Auto-select ports if exactly 2 are available
			if (portList.length === 2 && !cliPort && !dataPort) {
				// Sort by device name - lower number usually CLI
				const sorted = [...portList].sort((a, b) => a.device.localeCompare(b.device))
				setCliPort(sorted[0].device)
				setDataPort(sorted[1].device)
				setScanStatus('2 ports detected - verify to confirm assignment')
			} else if (portList.length === 1) {
				setScanStatus('Only 1 port detected - need 2 ports for CLI and Data')
			} else if (portList.length === 0) {
				setScanStatus('No serial ports detected')
			} else if (!cliPort && !dataPort) {
				// Default to first two if more than 2 ports
				setCliPort(portList[0]?.device || '')
				setDataPort(portList[1]?.device || '')
			}
		} catch (e) {
			console.warn('Failed to load ports:', e)
		}
	}

	// Close panel on click outside
	useEffect(() => {
		const handleClickOutside = (e: MouseEvent) => {
			if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
				setShowConnectPanel(false)
			}
		}
		if (showConnectPanel) {
			document.addEventListener('mousedown', handleClickOutside)
			return () => document.removeEventListener('mousedown', handleClickOutside)
		}
	}, [showConnectPanel])

	// Auto-detect which port is CLI and which is Data
	const handleAutoDetect = async () => {
		if (ports.length < 2) {
			showToast('Need at least 2 serial ports for auto-detection', 'error')
			return
		}

		setScanning(true)
		setScanStatus('Scanning ports...')
		setVerifyResult(null)

		let detectedCli: string | null = null
		let detectedData: string | null = null
		const results: { port: string; isCli: boolean; isData: boolean; details: string }[] = []

		// Test each port to identify CLI vs Data
		for (const port of ports) {
			setScanStatus(`Testing ${port.device}...`)

			try {
				// Try as CLI port first (with itself as data to test CLI response)
				const result = await deviceApi.verifyPorts(port.device, port.device)

				if (result.cli_port.status === 'ok' && result.cli_port.details.toLowerCase().includes('mmwave')) {
					detectedCli = port.device
					results.push({
						port: port.device,
						isCli: true,
						isData: false,
						details: 'Responds to CLI commands (mmWave device)'
					})
				} else if (result.cli_port.status === 'ok') {
					// Port responded but not as CLI - likely data port
					detectedData = port.device
					results.push({
						port: port.device,
						isCli: false,
						isData: true,
						details: 'Accessible (likely data port)'
					})
				} else if (result.cli_port.status === 'warning') {
					// Port opened but no CLI response - might be data
					if (!detectedData) detectedData = port.device
					results.push({
						port: port.device,
						isCli: false,
						isData: true,
						details: result.cli_port.details
					})
				} else {
					results.push({
						port: port.device,
						isCli: false,
						isData: false,
						details: result.cli_port.details
					})
				}
			} catch (e) {
				results.push({
					port: port.device,
					isCli: false,
					isData: false,
					details: e instanceof Error ? e.message : 'Error testing port'
				})
			}
		}

		// If we found a CLI port, set the other as data
		if (detectedCli) {
			setCliPort(detectedCli)
			// Find the best data port (not the CLI port)
			const dataCandidate = ports.find(p => p.device !== detectedCli)
			if (dataCandidate) {
				setDataPort(dataCandidate.device)
			}
			setScanStatus(`Detected CLI: ${detectedCli.split('/').pop()}`)
			showToast('Ports auto-detected successfully', 'success')

			// Auto-verify after detection
			setTimeout(() => handleVerify(), 100)
		} else if (results.length >= 2) {
			// Couldn't identify CLI - use heuristics (lower port number = CLI)
			const sorted = [...ports].sort((a, b) => a.device.localeCompare(b.device))
			setCliPort(sorted[0].device)
			setDataPort(sorted[1].device)
			setScanStatus('Could not auto-detect - using default assignment. Verify to confirm.')
			showToast('Auto-detection inconclusive - please verify manually', 'warning')
		} else {
			setScanStatus('Auto-detection failed - not enough accessible ports')
			showToast('Auto-detection failed', 'error')
		}

		setScanning(false)
	}

	const handleVerify = async () => {
		if (!cliPort || !dataPort) {
			showToast('Please select both CLI and Data ports', 'error')
			return
		}

		if (cliPort === dataPort) {
			showToast('CLI and Data ports must be different', 'error')
			return
		}

		setVerifying(true)
		setVerifyResult(null)
		setScanStatus('Verifying port configuration...')

		try {
			const result = await deviceApi.verifyPorts(cliPort, dataPort)
			setVerifyResult(result)

			// Check if ports might be swapped
			const cliLooksLikeData = result.cli_port.status === 'warning' &&
				result.cli_port.details.toLowerCase().includes('no response')
			const dataFailed = result.data_port.status === 'error'

			if (result.overall === 'pass') {
				setScanStatus('Ports verified - ready to connect')
				showToast('Ports verified successfully', 'success')
			} else if (result.overall === 'warning') {
				if (cliLooksLikeData) {
					setScanStatus('Warning: CLI port not responding - ports may be swapped')
				} else {
					setScanStatus('Verified with warnings - connection may work')
				}
				showToast('Ports verified with warnings', 'warning')
			} else {
				if (cliLooksLikeData && dataFailed) {
					setScanStatus('Verification failed - try swapping ports')
				} else {
					setScanStatus('Verification failed - check port selection')
				}
				showToast('Port verification failed', 'error')
			}
		} catch (e) {
			setScanStatus('Verification error')
			showToast(`Verification failed: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
		} finally {
			setVerifying(false)
		}
	}

	const handleSwapPorts = () => {
		const temp = cliPort
		setCliPort(dataPort)
		setDataPort(temp)
		setVerifyResult(null)
		setScanStatus('Ports swapped - verify to confirm')
	}

	const handleConnect = async () => {
		setConnecting(true)
		try {
			await deviceApi.connect(cliPort, dataPort)
			showToast('Connected to sensor', 'success')
			setShowConnectPanel(false)
			setVerifyResult(null)
			setScanStatus(null)
		} catch (e) {
			showToast(`Connection failed: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
		} finally {
			setConnecting(false)
		}
	}

	const handleStop = async () => {
		try {
			await deviceApi.stop()
		} catch (e) {
			console.error('Failed to stop:', e)
		}
	}

	const handleDisconnect = async () => {
		try {
			await deviceApi.disconnect()
		} catch (e) {
			console.error('Failed to disconnect:', e)
		}
	}

	const getStateColor = () => {
		if (!deviceStatus) return 'bg-ink-muted'
		switch (deviceStatus.state) {
			case 'streaming': return 'bg-accent-green'
			case 'configuring': return 'bg-accent-yellow'
			case 'connecting': return 'bg-accent-blue'
			case 'error': return 'bg-accent-red'
			default: return 'bg-ink-muted'
		}
	}

	const getStateLabel = () => {
		if (!deviceStatus) return 'No Device'
		switch (deviceStatus.state) {
			case 'streaming': return 'Streaming'
			case 'configuring': return 'Configuring'
			case 'connecting': return 'Connecting'
			case 'error': return 'Error'
			case 'disconnected': return 'Disconnected'
			default: return deviceStatus.state
		}
	}

	const canConnect = verifyResult?.overall === 'pass' || verifyResult?.overall === 'warning'

	const getStatusIcon = (status: 'ok' | 'warning' | 'error' | 'unknown') => {
		switch (status) {
			case 'ok': return { color: 'bg-accent-green', text: 'PASS' }
			case 'warning': return { color: 'bg-accent-orange', text: 'WARN' }
			case 'error': return { color: 'bg-accent-red', text: 'FAIL' }
			default: return { color: 'bg-ink-muted', text: '?' }
		}
	}

	return (
		<div className="h-8 bg-bg-secondary border-b border-border flex items-center px-4 gap-6 text-small font-mono relative">
			{/* Connection Status */}
			<div className="flex items-center gap-2">
				<span className={clsx('w-2 h-2', getStateColor())} />
				<span className="text-ink-primary">{getStateLabel()}</span>
			</div>

			{/* WebSocket indicator */}
			<div className="flex items-center gap-2">
				<span className={clsx('w-2 h-2', wsConnected ? 'bg-accent-green' : 'bg-accent-red')} />
				<span className="text-ink-muted">WS</span>
			</div>

			{/* Device info */}
			{deviceStatus?.config_name && (
				<div className="flex items-center gap-2 text-ink-secondary">
					<span className="text-ink-muted">CFG:</span>
					<span>{deviceStatus.config_name}</span>
				</div>
			)}

			{/* Frame rate */}
			{isStreaming && (
				<>
					<div className="flex items-center gap-2">
						<span className="text-ink-muted">FPS:</span>
						<span className={clsx(
							deviceStatus.frame_rate < 15 ? 'text-accent-orange' : 'text-ink-primary'
						)}>
							{deviceStatus.frame_rate.toFixed(1)}
						</span>
					</div>

					{/* Buffer usage */}
					<div className="flex items-center gap-2">
						<span className="text-ink-muted">BUF:</span>
						<span className={clsx(
							deviceStatus.buffer_usage > 80 ? 'text-accent-red' :
							deviceStatus.buffer_usage > 50 ? 'text-accent-orange' : 'text-ink-primary'
						)}>
							{deviceStatus.buffer_usage.toFixed(0)}%
						</span>
					</div>

					{/* Dropped frames */}
					<div className="flex items-center gap-2">
						<span className="text-ink-muted">DROP:</span>
						<span className={clsx(
							deviceStatus.dropped_frames > 0 ? 'text-accent-red' : 'text-ink-primary'
						)}>
							{deviceStatus.dropped_frames}
						</span>
					</div>

					{/* Frame count */}
					<div className="flex items-center gap-2">
						<span className="text-ink-muted">FRAMES:</span>
						<span className="text-ink-secondary">{deviceStatus.frame_count}</span>
					</div>
				</>
			)}

			{/* Spacer */}
			<div className="flex-1" />

			{/* Control buttons */}
			<div className="flex items-center gap-3">
				{/* Connect button - shown when disconnected */}
				{isDisconnected && (
					<button
						onClick={() => setShowConnectPanel(!showConnectPanel)}
						className={clsx(
							'px-2 py-0.5 border text-label uppercase transition-all duration-fast',
							showConnectPanel
								? 'bg-accent-blue border-accent-blue text-bg-primary'
								: 'border-accent-blue text-accent-blue hover:bg-accent-blue hover:text-bg-primary'
						)}
					>
						Connect
					</button>
				)}

				{isStreaming && (
					<>
						<button
							onClick={togglePause}
							className={clsx(
								'px-2 py-0.5 border text-label uppercase transition-all duration-fast',
								isPaused
									? 'border-accent-green text-accent-green hover:bg-accent-green hover:text-bg-primary'
									: 'border-accent-yellow text-accent-yellow hover:bg-accent-yellow hover:text-bg-primary'
							)}
						>
							{isPaused ? 'Resume' : 'Pause'}
						</button>
						<button
							onClick={handleStop}
							className="px-2 py-0.5 border border-accent-red text-accent-red text-label uppercase hover:bg-accent-red hover:text-bg-primary transition-all duration-fast"
						>
							Stop
						</button>
					</>
				)}
				{isConnected && (
					<button
						onClick={handleDisconnect}
						className="px-2 py-0.5 border border-ink-muted text-ink-muted text-label uppercase hover:bg-ink-muted hover:text-bg-primary transition-all duration-fast"
					>
						Disconnect
					</button>
				)}
			</div>

			{/* Connection Panel Dropdown */}
			{showConnectPanel && (
				<div
					ref={panelRef}
					className="absolute top-full right-4 mt-1 w-[420px] bg-bg-secondary border border-border shadow-lg z-50"
				>
					<div className="px-4 py-3 border-b border-border flex items-center justify-between">
						<span className="text-small font-medium text-ink-primary">Connect to Sensor</span>
						<div className="flex items-center gap-3">
							<span className="text-label text-ink-muted">{ports.length} ports</span>
							<button
								onClick={() => setShowConnectPanel(false)}
								className="text-ink-muted hover:text-ink-primary text-label"
							>
								ESC
							</button>
						</div>
					</div>

					<div className="p-4 space-y-4">
						{/* Status Message */}
						{scanStatus && (
							<div className={clsx(
								'px-3 py-2 text-small border-l-2',
								scanStatus.includes('ready') || scanStatus.includes('Detected') ? 'border-l-accent-green bg-accent-green/5 text-accent-green' :
								scanStatus.includes('Warning') || scanStatus.includes('swapped') ? 'border-l-accent-orange bg-accent-orange/5 text-accent-orange' :
								scanStatus.includes('failed') || scanStatus.includes('error') ? 'border-l-accent-red bg-accent-red/5 text-accent-red' :
								'border-l-accent-blue bg-accent-blue/5 text-ink-secondary'
							)}>
								{scanStatus}
							</div>
						)}

						{/* Port Selection */}
						<div className="grid grid-cols-2 gap-4">
							<div>
								<label className="block text-label text-ink-muted mb-1 uppercase">CLI Port</label>
								<select
									value={cliPort}
									onChange={e => { setCliPort(e.target.value); setVerifyResult(null); setScanStatus(null) }}
									className="w-full bg-bg-tertiary border border-border px-3 py-2 text-small text-ink-primary font-mono focus:outline-none focus:border-accent-yellow"
								>
									<option value="">Select port...</option>
									{ports.map(p => (
										<option key={p.device} value={p.device}>
											{p.device.split('/').pop()}
										</option>
									))}
								</select>
							</div>
							<div>
								<label className="block text-label text-ink-muted mb-1 uppercase">Data Port</label>
								<select
									value={dataPort}
									onChange={e => { setDataPort(e.target.value); setVerifyResult(null); setScanStatus(null) }}
									className="w-full bg-bg-tertiary border border-border px-3 py-2 text-small text-ink-primary font-mono focus:outline-none focus:border-accent-yellow"
								>
									<option value="">Select port...</option>
									{ports.map(p => (
										<option key={p.device} value={p.device}>
											{p.device.split('/').pop()}
										</option>
									))}
								</select>
							</div>
						</div>

						{/* Swap button */}
						{cliPort && dataPort && (
							<button
								onClick={handleSwapPorts}
								className="w-full px-3 py-1.5 border border-border text-ink-muted text-label hover:bg-bg-tertiary transition-all duration-fast flex items-center justify-center gap-2"
							>
								<span>↔</span>
								<span>Swap CLI / Data</span>
							</button>
						)}

						{/* Verification Results */}
						{verifyResult && (
							<div className="space-y-2">
								<div className={clsx(
									'p-3 border',
									verifyResult.cli_port.status === 'ok' ? 'border-accent-green bg-accent-green/5' :
									verifyResult.cli_port.status === 'warning' ? 'border-accent-orange bg-accent-orange/5' : 'border-accent-red bg-accent-red/5'
								)}>
									<div className="flex items-center justify-between mb-1">
										<div className="flex items-center gap-2">
											<span className={clsx('w-2 h-2', getStatusIcon(verifyResult.cli_port.status).color)} />
											<span className="text-small font-medium text-ink-primary">CLI Port</span>
										</div>
										<span className={clsx(
											'text-label font-mono',
											verifyResult.cli_port.status === 'ok' ? 'text-accent-green' :
											verifyResult.cli_port.status === 'warning' ? 'text-accent-orange' : 'text-accent-red'
										)}>
											{getStatusIcon(verifyResult.cli_port.status).text}
										</span>
									</div>
									<p className="text-label text-ink-muted font-mono">{verifyResult.cli_port.path}</p>
									<p className="text-label text-ink-secondary mt-1">{verifyResult.cli_port.details}</p>
								</div>

								<div className={clsx(
									'p-3 border',
									verifyResult.data_port.status === 'ok' ? 'border-accent-green bg-accent-green/5' :
									verifyResult.data_port.status === 'warning' ? 'border-accent-orange bg-accent-orange/5' : 'border-accent-red bg-accent-red/5'
								)}>
									<div className="flex items-center justify-between mb-1">
										<div className="flex items-center gap-2">
											<span className={clsx('w-2 h-2', getStatusIcon(verifyResult.data_port.status).color)} />
											<span className="text-small font-medium text-ink-primary">Data Port</span>
										</div>
										<span className={clsx(
											'text-label font-mono',
											verifyResult.data_port.status === 'ok' ? 'text-accent-green' :
											verifyResult.data_port.status === 'warning' ? 'text-accent-orange' : 'text-accent-red'
										)}>
											{getStatusIcon(verifyResult.data_port.status).text}
										</span>
									</div>
									<p className="text-label text-ink-muted font-mono">{verifyResult.data_port.path}</p>
									<p className="text-label text-ink-secondary mt-1">{verifyResult.data_port.details}</p>
								</div>
							</div>
						)}

						{/* Action Buttons */}
						<div className="flex items-center gap-2 pt-2 border-t border-border">
							<button
								onClick={loadPorts}
								className="px-3 py-1.5 border border-ink-muted text-ink-muted text-label uppercase hover:bg-ink-muted hover:text-bg-primary transition-all duration-fast"
								title="Refresh port list"
							>
								Refresh
							</button>
							<button
								onClick={handleAutoDetect}
								disabled={scanning || ports.length < 2}
								className="px-3 py-1.5 border border-accent-blue text-accent-blue text-label uppercase hover:bg-accent-blue hover:text-bg-primary transition-all duration-fast disabled:opacity-50"
							>
								{scanning ? 'Scanning...' : 'Auto-Detect'}
							</button>
							<button
								onClick={handleVerify}
								disabled={verifying || !cliPort || !dataPort || cliPort === dataPort}
								className="px-3 py-1.5 border border-accent-orange text-accent-orange text-label uppercase hover:bg-accent-orange hover:text-bg-primary transition-all duration-fast disabled:opacity-50"
							>
								{verifying ? 'Verifying...' : 'Verify'}
							</button>
							<button
								onClick={handleConnect}
								disabled={connecting || !canConnect}
								className={clsx(
									'flex-1 px-3 py-1.5 border text-label uppercase transition-all duration-fast',
									canConnect
										? 'border-accent-green text-accent-green hover:bg-accent-green hover:text-bg-primary'
										: 'border-ink-muted text-ink-muted cursor-not-allowed opacity-50'
								)}
							>
								{connecting ? 'Connecting...' : 'Connect'}
							</button>
						</div>
					</div>
				</div>
			)}
		</div>
	)
})
