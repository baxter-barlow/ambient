import { useState, useEffect } from 'react'
import { useAppStore } from '../stores/appStore'
import { deviceApi } from '../api/client'
import Button from '../components/common/Button'
import Select from '../components/common/Select'
import StatusIndicator from '../components/common/StatusIndicator'
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
		} catch (e) {
			setError(e instanceof Error ? e.message : 'Connection failed')
		} finally {
			setLoading(false)
		}
	}

	const handleDisconnect = async () => {
		setLoading(true)
		setError(null)
		try {
			await deviceApi.disconnect()
		} catch (e) {
			setError(e instanceof Error ? e.message : 'Disconnect failed')
		} finally {
			setLoading(false)
		}
	}

	const handleStop = async () => {
		setLoading(true)
		try {
			await deviceApi.stop()
		} catch (e) {
			setError(e instanceof Error ? e.message : 'Stop failed')
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
		} catch (e) {
			setError(e instanceof Error ? e.message : 'Verification failed')
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
		<div className="space-y-6">
			<h2 className="text-xl font-semibold">Device Status & Control</h2>

			{/* Connection Status */}
			<div className="bg-gray-800 rounded-lg p-4">
				<h3 className="text-lg font-medium mb-4">Connection Status</h3>
				<div className="grid grid-cols-2 gap-4">
					<div>
						<span className="text-sm text-gray-400">State</span>
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
						<span className="text-sm text-gray-400">Config</span>
						<p className="text-gray-100">{deviceStatus?.config_name || 'default'}</p>
					</div>
					<div>
						<span className="text-sm text-gray-400">CLI Port</span>
						<p className="text-gray-100">{deviceStatus?.cli_port || '-'}</p>
					</div>
					<div>
						<span className="text-sm text-gray-400">Data Port</span>
						<p className="text-gray-100">{deviceStatus?.data_port || '-'}</p>
					</div>
				</div>

				{deviceStatus?.error && (
					<div className="mt-4 p-3 bg-red-900/50 border border-red-700 rounded text-red-200 text-sm">
						{deviceStatus.error}
					</div>
				)}
			</div>

			{/* Sensor Health */}
			{isConnected && (
				<div className="bg-gray-800 rounded-lg p-4">
					<h3 className="text-lg font-medium mb-4">Sensor Health</h3>
					<div className="grid grid-cols-4 gap-4">
						<div>
							<span className="text-sm text-gray-400">Frame Rate</span>
							<p className="text-2xl font-mono text-radar-400">
								{deviceStatus?.frame_rate.toFixed(1)} <span className="text-sm">Hz</span>
							</p>
						</div>
						<div>
							<span className="text-sm text-gray-400">Frames</span>
							<p className="text-2xl font-mono text-gray-100">
								{deviceStatus?.frame_count.toLocaleString()}
							</p>
						</div>
						<div>
							<span className="text-sm text-gray-400">Dropped</span>
							<p className="text-2xl font-mono text-gray-100">
								{deviceStatus?.dropped_frames}
							</p>
						</div>
						<div>
							<span className="text-sm text-gray-400">Buffer</span>
							<p className="text-2xl font-mono text-gray-100">
								{((deviceStatus?.buffer_usage || 0) * 100).toFixed(0)}%
							</p>
						</div>
					</div>
				</div>
			)}

			{/* Port Selection */}
			{!isConnected && (
				<div className="bg-gray-800 rounded-lg p-4">
					<h3 className="text-lg font-medium mb-4">Serial Port Selection</h3>
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
								verifyResult.cli_port.status === 'ok' ? 'bg-green-900/30 border-green-700' :
								verifyResult.cli_port.status === 'warning' ? 'bg-yellow-900/30 border-yellow-700' :
								'bg-red-900/30 border-red-700'
							)}>
								<div className="flex items-center gap-2">
									<span className={clsx(
										'text-lg',
										verifyResult.cli_port.status === 'ok' ? 'text-green-400' :
										verifyResult.cli_port.status === 'warning' ? 'text-yellow-400' : 'text-red-400'
									)}>
										{verifyResult.cli_port.status === 'ok' ? '✓' : verifyResult.cli_port.status === 'warning' ? '⚠' : '✗'}
									</span>
									<span className="font-medium">CLI Port: {verifyResult.cli_port.path}</span>
								</div>
								<p className="text-sm text-gray-300 mt-1">{verifyResult.cli_port.details}</p>
							</div>
							<div className={clsx(
								'p-3 rounded border',
								verifyResult.data_port.status === 'ok' ? 'bg-green-900/30 border-green-700' :
								verifyResult.data_port.status === 'warning' ? 'bg-yellow-900/30 border-yellow-700' :
								'bg-red-900/30 border-red-700'
							)}>
								<div className="flex items-center gap-2">
									<span className={clsx(
										'text-lg',
										verifyResult.data_port.status === 'ok' ? 'text-green-400' :
										verifyResult.data_port.status === 'warning' ? 'text-yellow-400' : 'text-red-400'
									)}>
										{verifyResult.data_port.status === 'ok' ? '✓' : verifyResult.data_port.status === 'warning' ? '⚠' : '✗'}
									</span>
									<span className="font-medium">Data Port: {verifyResult.data_port.path}</span>
								</div>
								<p className="text-sm text-gray-300 mt-1">{verifyResult.data_port.details}</p>
							</div>
						</div>
					)}
				</div>
			)}

			{/* Error display */}
			{error && (
				<div className="p-3 bg-red-900/50 border border-red-700 rounded text-red-200 text-sm">
					{error}
				</div>
			)}

			{/* Controls */}
			<div className="flex gap-4">
				{!isConnected ? (
					<>
						<Button
							variant="secondary"
							onClick={handleVerify}
							disabled={verifying || loading}
						>
							{verifying ? 'Verifying...' : 'Verify Ports'}
						</Button>
						<Button
							onClick={handleConnect}
							disabled={loading || !canConnect || deviceStatus?.state === 'connecting'}
							title={!canConnect ? 'Verify ports first' : undefined}
						>
							{loading ? 'Connecting...' : 'Connect'}
						</Button>
					</>
				) : (
					<Button
						variant="secondary"
						onClick={handleDisconnect}
						disabled={loading}
					>
						Disconnect
					</Button>
				)}

				{isConnected && (
					<Button
						variant="danger"
						onClick={handleStop}
						disabled={loading}
					>
						Emergency Stop
					</Button>
				)}

				<Button
					variant="secondary"
					onClick={() => deviceApi.getPorts().then(setPorts)}
				>
					Refresh Ports
				</Button>
			</div>
		</div>
	)
}
