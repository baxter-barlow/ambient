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
		<div className="space-y-5">
			<h2 className="text-xl text-text-primary">Recording & Playback</h2>

			{/* Recording Status */}
			{status?.is_recording && (
				<div className="bg-accent-red/12 border border-accent-red/25 rounded-card p-4">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-4">
							<span className="w-3 h-3 bg-accent-red rounded-full animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.4)]" />
							<div>
								<p className="font-medium text-accent-red">Recording: {status.name}</p>
								<p className="text-sm text-text-secondary font-mono">
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
				<div className="bg-surface-2 border border-border rounded-card">
					<div className="px-4 py-3 border-b border-border">
						<span className="text-base text-text-primary font-medium">Start New Recording</span>
					</div>
					<div className="p-4">
						<div className="flex items-end gap-4">
							<div className="flex-1">
								<label className="block text-sm text-text-secondary mb-1">Session Name</label>
								<input
									type="text"
									value={recordingName}
									onChange={e => setRecordingName(e.target.value)}
									placeholder="e.g., sleep_test_001"
									className="w-full bg-surface-3 border border-border rounded px-3 py-2 text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-teal"
								/>
							</div>
							<div>
								<label className="block text-sm text-text-secondary mb-1">Format</label>
								<select
									value={format}
									onChange={e => setFormat(e.target.value as 'h5' | 'parquet')}
									className="bg-surface-3 border border-border rounded px-3 py-2 text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-teal"
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
							<p className="mt-3 text-sm text-accent-amber">
								Device must be streaming to start recording.
							</p>
						)}
					</div>
				</div>
			)}

			{/* Recording List */}
			<div className="bg-surface-2 border border-border rounded-card">
				<div className="px-4 py-3 border-b border-border">
					<span className="text-base text-text-primary font-medium">Previous Recordings</span>
				</div>
				<div className="p-4">
					{recordings.length === 0 ? (
						<p className="text-text-tertiary">No recordings yet.</p>
					) : (
						<table className="w-full">
							<thead>
								<tr className="text-left text-sm text-text-tertiary border-b border-border">
									<th className="pb-2 font-medium">Name</th>
									<th className="pb-2 font-medium">Format</th>
									<th className="pb-2 font-medium">Date</th>
									<th className="pb-2 font-medium">Size</th>
									<th className="pb-2 font-medium">Frames</th>
									<th className="pb-2 font-medium">Actions</th>
								</tr>
							</thead>
							<tbody className="divide-y divide-border">
								{recordings.map(rec => (
									<tr key={rec.id} className="text-sm">
										<td className="py-2 font-medium text-text-primary">{rec.name}</td>
										<td className="py-2 uppercase text-text-tertiary font-mono text-xs">{rec.format}</td>
										<td className="py-2 text-text-secondary">
											{new Date(rec.created * 1000).toLocaleString()}
										</td>
										<td className="py-2 text-text-secondary font-mono">{formatBytes(rec.size_bytes)}</td>
										<td className="py-2 text-text-secondary font-mono">{rec.frame_count}</td>
										<td className="py-2">
											<div className="flex gap-3">
												<a
													href={`/api/recordings/${rec.id}/export`}
													className="text-accent-teal hover:text-accent-teal-hover transition-colors"
												>
													Export
												</a>
												<button
													onClick={() => handleDelete(rec.id)}
													className="text-accent-red hover:text-red-400 transition-colors"
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
		</div>
	)
}
