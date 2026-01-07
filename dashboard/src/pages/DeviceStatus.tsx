import { useState, useEffect } from 'react'
import { useAppStore } from '../stores/appStore'
import { deviceApi } from '../api/client'
import Button from '../components/common/Button'
import Select from '../components/common/Select'
import StatusIndicator from '../components/common/StatusIndicator'
import Tooltip from '../components/common/Tooltip'
import ErrorMessage from '../components/common/ErrorMessage'
import { showToast } from '../components/common/Toast'
import type { SerialPort, PortVerifyResult } from '../types'
import clsx from 'clsx'

export default function DeviceStatus() {
	const deviceStatus = useAppStore(s => s.deviceStatus)
	const [ports, setPorts] = useState<SerialPort[]>([])
	const [cliPort, setCliPort] = useState('/dev/ttyUSB0')
	const [dataPort, setDataPort] = useState('/dev/ttyUSB1')
	const [loading, setLoading] = useState(false)
	const [error, setError] = useState<string | null>(null)
	const [verifying, setVerifying] = useState(false)
	const [verifyResult, setVerifyResult] = useState<PortVerifyResult | null>(null)

	useEffect(() => {
		deviceApi.getPorts().then(setPorts).catch(() => {})
	}, [])

	const handleConnect = async () => {
		setLoading(true)
		setError(null)
		try {
			await deviceApi.connect(cliPort, dataPort)
			showToast('Connected to radar sensor', 'success')
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
		setError(null)
		try {
			await deviceApi.disconnect()
			showToast('Disconnected from sensor', 'info')
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'Disconnect failed'
			setError(msg)
			showToast(msg, 'error')
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
			showToast(msg, 'error')
		} finally {
			setLoading(false)
		}
	}

	const handleVerify = async () => {
		setVerifying(true)
		setVerifyResult(null)
		setError(null)
		try {
			const result = await deviceApi.verifyPorts(cliPort, dataPort)
			setVerifyResult(result)
			if (result.overall === 'pass') {
				showToast('Ports verified successfully', 'success')
			} else if (result.overall === 'warning') {
				showToast('Ports verified with warnings', 'warning')
			} else {
				showToast('Port verification failed', 'error')
			}
		} catch (e) {
			const msg = e instanceof Error ? e.message : 'Verification failed'
			setError(msg)
			showToast(msg, 'error')
		} finally {
			setVerifying(false)
		}
	}

	const isConnected = deviceStatus?.state === 'streaming' || deviceStatus?.state === 'configuring'
	const canConnect = verifyResult?.overall === 'pass' || verifyResult?.overall === 'warning'
	const portOptions = ports.length > 0
		? ports.map(p => ({ value: p.device, label: p.device }))
		: [
			{ value: '/dev/ttyUSB0', label: '/dev/ttyUSB0' },
			{ value: '/dev/ttyUSB1', label: '/dev/ttyUSB1' },
			{ value: '/dev/ttyACM0', label: '/dev/ttyACM0' },
			{ value: '/dev/ttyACM1', label: '/dev/ttyACM1' },
		]

	return (
		<div className="space-y-5">
			<h2 className="text-xl text-text-primary">Device Status & Control</h2>

			{/* Connection Status Card */}
			<div className="bg-surface-2 border border-border rounded-card">
				<div className="px-4 py-3 border-b border-border">
					<span className="text-base text-text-primary font-medium">Connection Status</span>
				</div>
				<div className="p-4">
					<div className="grid grid-cols-2 gap-4">
						<div>
							<span className="text-sm text-text-secondary">State</span>
							<div className="mt-1">
								<StatusIndicator
									status={
										deviceStatus?.state === 'streaming' ? 'success' :
										deviceStatus?.state === 'error' ? 'error' :
										deviceStatus?.state === 'connecting' || deviceStatus?.state === 'configuring' ? 'warning' :
										'neutral'
									}
									label={deviceStatus?.state || 'unknown'}
									pulse={deviceStatus?.state === 'connecting' || deviceStatus?.state === 'configuring'}
								/>
							</div>
						</div>
						<div>
							<span className="text-sm text-text-secondary">Config</span>
							<p className="text-text-primary font-mono text-sm mt-1">{deviceStatus?.config_name || 'default'}</p>
						</div>
						<div>
							<span className="text-sm text-text-secondary">CLI Port</span>
							<p className="text-text-primary font-mono text-sm mt-1">{deviceStatus?.cli_port || '-'}</p>
						</div>
						<div>
							<span className="text-sm text-text-secondary">Data Port</span>
							<p className="text-text-primary font-mono text-sm mt-1">{deviceStatus?.data_port || '-'}</p>
						</div>
					</div>

					{deviceStatus?.error && (
						<div className="mt-4 p-3 bg-accent-red/12 border border-accent-red/25 rounded text-accent-red text-sm">
							{deviceStatus.error}
						</div>
					)}
				</div>
			</div>

			{/* Sensor Health Card */}
			{isConnected && (
				<div className="bg-surface-2 border border-border rounded-card">
					<div className="px-4 py-3 border-b border-border">
						<span className="text-base text-text-primary font-medium">Sensor Health</span>
					</div>
					<div className="p-4">
						<div className="grid grid-cols-4 gap-4">
							<div>
								<span className="text-sm text-text-secondary">Frame Rate</span>
								<p className="text-metric-md font-mono text-accent-teal mt-1">
									{deviceStatus?.frame_rate.toFixed(1)} <span className="text-sm text-text-tertiary">Hz</span>
								</p>
							</div>
							<div>
								<span className="text-sm text-text-secondary">Frames</span>
								<p className="text-metric-md font-mono text-text-primary mt-1">
									{deviceStatus?.frame_count.toLocaleString()}
								</p>
							</div>
							<div>
								<span className="text-sm text-text-secondary">Dropped</span>
								<p className={clsx(
									'text-metric-md font-mono mt-1',
									deviceStatus?.dropped_frames && deviceStatus.dropped_frames > 0
										? 'text-accent-amber'
										: 'text-text-primary'
								)}>
									{deviceStatus?.dropped_frames}
								</p>
							</div>
							<div>
								<span className="text-sm text-text-secondary">Buffer</span>
								<p className="text-metric-md font-mono text-text-primary mt-1">
									{((deviceStatus?.buffer_usage || 0) * 100).toFixed(0)}%
								</p>
							</div>
						</div>
					</div>
				</div>
			)}

			{/* Port Selection Card */}
			{!isConnected && (
				<div className="bg-surface-2 border border-border rounded-card">
					<div className="px-4 py-3 border-b border-border">
						<span className="text-base text-text-primary font-medium">Serial Port Selection</span>
					</div>
					<div className="p-4">
						<div className="grid grid-cols-2 gap-4 mb-4">
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

						{/* Verification Results */}
						{verifyResult && (
							<div className="mt-4 space-y-2">
								<div className={clsx(
									'p-3 rounded border',
									verifyResult.cli_port.status === 'ok' ? 'bg-accent-green/12 border-accent-green/25' :
									verifyResult.cli_port.status === 'warning' ? 'bg-accent-amber/12 border-accent-amber/25' :
									'bg-accent-red/12 border-accent-red/25'
								)}>
									<div className="flex items-center gap-2">
										<span className={clsx(
											'text-base font-mono',
											verifyResult.cli_port.status === 'ok' ? 'text-accent-green' :
											verifyResult.cli_port.status === 'warning' ? 'text-accent-amber' : 'text-accent-red'
										)}>
											{verifyResult.cli_port.status === 'ok' ? '+' : verifyResult.cli_port.status === 'warning' ? '!' : 'x'}
										</span>
										<span className="font-medium text-text-primary">CLI Port: <span className="font-mono">{verifyResult.cli_port.path}</span></span>
									</div>
									<p className="text-sm text-text-secondary mt-1">{verifyResult.cli_port.details}</p>
								</div>
								<div className={clsx(
									'p-3 rounded border',
									verifyResult.data_port.status === 'ok' ? 'bg-accent-green/12 border-accent-green/25' :
									verifyResult.data_port.status === 'warning' ? 'bg-accent-amber/12 border-accent-amber/25' :
									'bg-accent-red/12 border-accent-red/25'
								)}>
									<div className="flex items-center gap-2">
										<span className={clsx(
											'text-base font-mono',
											verifyResult.data_port.status === 'ok' ? 'text-accent-green' :
											verifyResult.data_port.status === 'warning' ? 'text-accent-amber' : 'text-accent-red'
										)}>
											{verifyResult.data_port.status === 'ok' ? '+' : verifyResult.data_port.status === 'warning' ? '!' : 'x'}
										</span>
										<span className="font-medium text-text-primary">Data Port: <span className="font-mono">{verifyResult.data_port.path}</span></span>
									</div>
									<p className="text-sm text-text-secondary mt-1">{verifyResult.data_port.details}</p>
								</div>
							</div>
						)}
					</div>
				</div>
			)}

			{/* Error display */}
			{error && (
				<ErrorMessage
					message={error}
					onDismiss={() => setError(null)}
				/>
			)}

			{/* Controls */}
			<div className="flex gap-3">
				{!isConnected ? (
					<>
						<Tooltip content="Check if ports are valid TI radar devices" position="bottom">
							<Button
								variant="secondary"
								onClick={handleVerify}
								disabled={verifying || loading}
							>
								{verifying ? 'Verifying...' : 'Verify Ports'}
							</Button>
						</Tooltip>
						<Tooltip
							content={!canConnect ? 'Verify ports first before connecting' : 'Connect to radar sensor'}
							position="bottom"
						>
							<Button
								onClick={handleConnect}
								disabled={loading || !canConnect || deviceStatus?.state === 'connecting'}
							>
								{loading ? 'Connecting...' : 'Connect'}
							</Button>
						</Tooltip>
					</>
				) : (
					<Tooltip content="Gracefully disconnect from sensor" position="bottom">
						<Button
							variant="secondary"
							onClick={handleDisconnect}
							disabled={loading}
						>
							Disconnect
						</Button>
					</Tooltip>
				)}

				{isConnected && (
					<Tooltip content="Immediately stop sensor streaming" position="bottom">
						<Button
							variant="danger"
							onClick={handleStop}
							disabled={loading}
						>
							Emergency Stop
						</Button>
					</Tooltip>
				)}

				<Tooltip content="Scan for available serial ports" position="bottom">
					<Button
						variant="secondary"
						onClick={() => deviceApi.getPorts().then(setPorts)}
					>
						Refresh Ports
					</Button>
				</Tooltip>
			</div>
		</div>
	)
}
