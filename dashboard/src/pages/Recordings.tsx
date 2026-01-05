import { useState, useEffect } from 'react'
import { recordingApi } from '../api/client'
import { useAppStore } from '../stores/appStore'
import Button from '../components/common/Button'
import type { RecordingInfo, RecordingStatus } from '../types'

export default function Recordings() {
	const [recordings, setRecordings] = useState<RecordingInfo[]>([])
	const [status, setStatus] = useState<RecordingStatus | null>(null)
	const [recordingName, setRecordingName] = useState('')
	const [format, setFormat] = useState<'h5' | 'parquet'>('h5')
	const [loading, setLoading] = useState(false)
	const deviceStatus = useAppStore(s => s.deviceStatus)

	const loadRecordings = async () => {
		try {
			const [list, st] = await Promise.all([
				recordingApi.list(),
				recordingApi.getStatus(),
			])
			setRecordings(list)
			setStatus(st)
		} catch {
			// ignore
		}
	}

	useEffect(() => {
		loadRecordings()
		const interval = setInterval(loadRecordings, 5000)
		return () => clearInterval(interval)
	}, [])

	const handleStart = async () => {
		if (!recordingName.trim()) return
		setLoading(true)
		try {
			await recordingApi.start(recordingName.trim(), format)
			setRecordingName('')
			await loadRecordings()
		} catch {
			// ignore
		} finally {
			setLoading(false)
		}
	}

	const handleStop = async () => {
		setLoading(true)
		try {
			await recordingApi.stop()
			await loadRecordings()
		} catch {
			// ignore
		} finally {
			setLoading(false)
		}
	}

	const handleDelete = async (id: string) => {
		if (!confirm('Delete this recording?')) return
		try {
			await recordingApi.delete(id)
			await loadRecordings()
		} catch {
			// ignore
		}
	}

	const formatBytes = (bytes: number) => {
		if (bytes < 1024) return `${bytes} B`
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
	}

	const formatDuration = (seconds: number) => {
		const m = Math.floor(seconds / 60)
		const s = Math.floor(seconds % 60)
		return `${m}:${s.toString().padStart(2, '0')}`
	}

	const isStreaming = deviceStatus?.state === 'streaming'

	return (
		<div className="space-y-6">
			<h2 className="text-xl font-semibold">Recording & Playback</h2>

			{/* Recording Status */}
			{status?.is_recording && (
				<div className="bg-red-900/30 border border-red-700 rounded-lg p-4">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-4">
							<span className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
							<div>
								<p className="font-medium text-red-200">Recording: {status.name}</p>
								<p className="text-sm text-red-300">
									{formatDuration(status.duration)} | {status.frame_count} frames
								</p>
							</div>
						</div>
						<Button variant="danger" onClick={handleStop} disabled={loading}>
							Stop Recording
						</Button>
					</div>
				</div>
			)}

			{/* Start Recording */}
			{!status?.is_recording && (
				<div className="bg-gray-800 rounded-lg p-4">
					<h3 className="text-lg font-medium mb-4">Start New Recording</h3>
					<div className="flex items-end gap-4">
						<div className="flex-1">
							<label className="block text-sm text-gray-400 mb-1">Session Name</label>
							<input
								type="text"
								value={recordingName}
								onChange={e => setRecordingName(e.target.value)}
								placeholder="e.g., sleep_test_001"
								className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2 text-gray-100"
							/>
						</div>
						<div>
							<label className="block text-sm text-gray-400 mb-1">Format</label>
							<select
								value={format}
								onChange={e => setFormat(e.target.value as 'h5' | 'parquet')}
								className="bg-gray-700 border border-gray-600 rounded px-3 py-2 text-gray-100"
							>
								<option value="h5">HDF5 (full data)</option>
								<option value="parquet">Parquet (vitals only)</option>
							</select>
						</div>
						<Button
							onClick={handleStart}
							disabled={loading || !recordingName.trim() || !isStreaming}
						>
							Start Recording
						</Button>
					</div>
					{!isStreaming && (
						<p className="mt-2 text-sm text-yellow-400">
							Device must be streaming to start recording.
						</p>
					)}
				</div>
			)}

			{/* Recording List */}
			<div className="bg-gray-800 rounded-lg p-4">
				<h3 className="text-lg font-medium mb-4">Previous Recordings</h3>
				{recordings.length === 0 ? (
					<p className="text-gray-400">No recordings yet.</p>
				) : (
					<table className="w-full">
						<thead>
							<tr className="text-left text-sm text-gray-400 border-b border-gray-700">
								<th className="pb-2">Name</th>
								<th className="pb-2">Format</th>
								<th className="pb-2">Date</th>
								<th className="pb-2">Size</th>
								<th className="pb-2">Frames</th>
								<th className="pb-2">Actions</th>
							</tr>
						</thead>
						<tbody className="divide-y divide-gray-700">
							{recordings.map(rec => (
								<tr key={rec.id} className="text-sm">
									<td className="py-2 font-medium">{rec.name}</td>
									<td className="py-2 uppercase text-gray-400">{rec.format}</td>
									<td className="py-2 text-gray-400">
										{new Date(rec.created * 1000).toLocaleString()}
									</td>
									<td className="py-2 text-gray-400">{formatBytes(rec.size_bytes)}</td>
									<td className="py-2 text-gray-400">{rec.frame_count}</td>
									<td className="py-2">
										<div className="flex gap-2">
											<a
												href={`/api/recordings/${rec.id}/export`}
												className="text-radar-400 hover:text-radar-300"
											>
												Export
											</a>
											<button
												onClick={() => handleDelete(rec.id)}
												className="text-red-400 hover:text-red-300"
											>
												Delete
											</button>
										</div>
									</td>
								</tr>
							))}
						</tbody>
					</table>
				)}
			</div>
		</div>
	)
}
