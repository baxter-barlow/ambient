import { useState, useEffect } from 'react'
import { recordingApi } from '../api/client'
import { useAppStore } from '../stores/appStore'
import Button from '../components/common/Button'
import { showToast } from '../components/common/Toast'
import type { RecordingInfo, RecordingStatus } from '../types'

/**
 * Recordings page following TE design principles:
 * - Borders as primary hierarchy
 * - Monospace for data values
 * - Square indicators
 */
export default function Recordings() {
	const [recordings, setRecordings] = useState<RecordingInfo[]>([])
	const [status, setStatus] = useState<RecordingStatus | null>(null)
	const [recordingName, setRecordingName] = useState('')
	const [format, setFormat] = useState<'h5' | 'parquet'>('h5')
	const [loading, setLoading] = useState(false)
	const deviceStatus = useAppStore(s => s.deviceStatus)

	const loadRecordings = async () => {
		try {
			const [list, st] = await Promise.all([recordingApi.list(), recordingApi.getStatus()])
			setRecordings(list)
			setStatus(st)
		} catch (e) {
			console.warn('Failed to load recordings:', e)
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
		} catch (e) {
			showToast(`Failed to start recording: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
		} finally {
			setLoading(false)
		}
	}

	const handleStop = async () => {
		setLoading(true)
		try {
			await recordingApi.stop()
			await loadRecordings()
		} catch (e) {
			showToast(`Failed to stop recording: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
		} finally {
			setLoading(false)
		}
	}

	const handleDelete = async (id: string) => {
		if (!confirm('Delete this recording?')) return
		try {
			await recordingApi.delete(id)
			await loadRecordings()
		} catch (e) {
			showToast(`Failed to delete recording: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
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
		<div className="space-y-6 max-w-4xl">
			<h2 className="text-h2 text-ink-primary">Recording & Playback</h2>

			{/* Recording Status */}
			{status?.is_recording && (
				<div className="bg-bg-secondary border-l-4 border-l-accent-red border border-border p-4">
					<div className="flex items-center justify-between">
						<div className="flex items-center gap-4">
							<span className="w-3 h-3 bg-accent-red animate-pulse" />
							<div>
								<p className="text-small font-medium text-accent-red">Recording: {status.name}</p>
								<p className="text-label text-ink-muted font-mono">
									{formatDuration(status.duration)} | {status.frame_count} frames
								</p>
							</div>
						</div>
						<Button variant="danger" onClick={handleStop} disabled={loading}>Stop Recording</Button>
					</div>
				</div>
			)}

			{/* Start Recording */}
			{!status?.is_recording && (
				<div className="bg-bg-secondary border border-border">
					<div className="px-4 py-3 border-b border-border">
						<span className="text-small font-medium text-ink-primary">Start New Recording</span>
					</div>
					<div className="p-4">
						<div className="flex items-end gap-4">
							<div className="flex-1">
								<label className="block text-label text-ink-muted mb-1 uppercase">Session Name</label>
								<input
									type="text"
									value={recordingName}
									onChange={e => setRecordingName(e.target.value)}
									placeholder="e.g., sleep_test_001"
									className="w-full bg-bg-tertiary border border-border px-3 py-2 text-small text-ink-primary font-mono focus:outline-none focus:border-accent-yellow"
								/>
							</div>
							<div>
								<label className="block text-label text-ink-muted mb-1 uppercase">Format</label>
								<select
									value={format}
									onChange={e => setFormat(e.target.value as 'h5' | 'parquet')}
									className="bg-bg-tertiary border border-border px-3 py-2 text-small text-ink-primary focus:outline-none focus:border-accent-yellow"
								>
									<option value="h5">HDF5 (full data)</option>
									<option value="parquet">Parquet (vitals only)</option>
								</select>
							</div>
							<Button onClick={handleStart} disabled={loading || !recordingName.trim() || !isStreaming}>
								Start Recording
							</Button>
						</div>
						{!isStreaming && (
							<p className="mt-3 text-label text-accent-orange">
								Device must be streaming to start recording.
							</p>
						)}
					</div>
				</div>
			)}

			{/* Recording List */}
			<div className="bg-bg-secondary border border-border">
				<div className="px-4 py-3 border-b border-border">
					<span className="text-small font-medium text-ink-primary">Previous Recordings</span>
				</div>
				<div className="p-4">
					{recordings.length === 0 ? (
						<p className="text-ink-muted">No recordings yet.</p>
					) : (
						<table className="w-full">
							<thead>
								<tr className="text-left text-label text-ink-muted border-b border-border uppercase">
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
									<tr key={rec.id} className="text-small">
										<td className="py-2 font-medium text-ink-primary">{rec.name}</td>
										<td className="py-2 uppercase text-ink-muted font-mono text-label">{rec.format}</td>
										<td className="py-2 text-ink-secondary font-mono">{new Date(rec.created * 1000).toLocaleString()}</td>
										<td className="py-2 text-ink-secondary font-mono">{formatBytes(rec.size_bytes)}</td>
										<td className="py-2 text-ink-secondary font-mono">{rec.frame_count}</td>
										<td className="py-2">
											<div className="flex gap-3">
												<a href={`/api/recordings/${rec.id}/export`} className="text-accent-blue hover:text-ink-primary transition-all duration-fast">Export</a>
												<button onClick={() => handleDelete(rec.id)} className="text-accent-red hover:text-ink-primary transition-all duration-fast">Delete</button>
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
