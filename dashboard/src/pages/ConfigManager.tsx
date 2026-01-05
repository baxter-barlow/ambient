import { useState, useEffect } from 'react'
import { configApi } from '../api/client'
import Button from '../components/common/Button'
import type { ConfigProfile } from '../types'

export default function ConfigManager() {
	const [profiles, setProfiles] = useState<ConfigProfile[]>([])
	const [selected, setSelected] = useState<ConfigProfile | null>(null)
	const [editing, setEditing] = useState(false)
	const [editForm, setEditForm] = useState<ConfigProfile | null>(null)

	const loadProfiles = async () => {
		try {
			const list = await configApi.listProfiles()
			setProfiles(list)
			if (!selected && list.length > 0) {
				setSelected(list[0])
			}
		} catch {
			// ignore
		}
	}

	useEffect(() => {
		loadProfiles()
	}, [])

	const handleSave = async () => {
		if (!editForm) return
		try {
			if (profiles.find(p => p.name === editForm.name)) {
				await configApi.saveProfile(editForm)
			} else {
				await configApi.saveProfile(editForm)
			}
			await loadProfiles()
			setEditing(false)
			setSelected(editForm)
		} catch {
			// ignore
		}
	}

	const handleDelete = async (name: string) => {
		if (name === 'default') return
		if (!confirm(`Delete profile "${name}"?`)) return
		try {
			await configApi.deleteProfile(name)
			await loadProfiles()
			if (selected?.name === name) {
				setSelected(profiles[0] || null)
			}
		} catch {
			// ignore
		}
	}

	const handleFlash = async (name: string) => {
		try {
			await configApi.flash(name)
			alert('Configuration flashed to device')
		} catch {
			alert('Failed to flash configuration')
		}
	}

	const startEdit = (profile: ConfigProfile) => {
		setEditForm({ ...profile })
		setEditing(true)
	}

	const startNew = () => {
		setEditForm({
			name: '',
			description: '',
			chirp: {
				start_freq_ghz: 60.0,
				bandwidth_mhz: 4000.0,
				idle_time_us: 7.0,
				ramp_end_time_us: 60.0,
				adc_samples: 256,
				sample_rate_ksps: 10000,
				rx_gain_db: 30,
			},
			frame: {
				chirps_per_frame: 64,
				frame_period_ms: 50.0,
			},
		})
		setEditing(true)
	}

	return (
		<div className="space-y-6">
			<div className="flex items-center justify-between">
				<h2 className="text-xl font-semibold">Configuration Manager</h2>
				<Button onClick={startNew}>New Profile</Button>
			</div>

			<div className="grid grid-cols-3 gap-6">
				{/* Profile List */}
				<div className="bg-gray-800 rounded-lg p-4">
					<h3 className="text-lg font-medium mb-4">Profiles</h3>
					<div className="space-y-2">
						{profiles.map(profile => (
							<div
								key={profile.name}
								onClick={() => setSelected(profile)}
								className={`p-3 rounded cursor-pointer ${
									selected?.name === profile.name
										? 'bg-radar-600'
										: 'bg-gray-700 hover:bg-gray-600'
								}`}
							>
								<p className="font-medium">{profile.name}</p>
								{profile.description && (
									<p className="text-sm text-gray-400 truncate">{profile.description}</p>
								)}
							</div>
						))}
					</div>
				</div>

				{/* Profile Details / Editor */}
				<div className="col-span-2 bg-gray-800 rounded-lg p-4">
					{editing && editForm ? (
						<>
							<h3 className="text-lg font-medium mb-4">
								{editForm.name ? `Edit: ${editForm.name}` : 'New Profile'}
							</h3>
							<div className="space-y-4">
								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm text-gray-400 mb-1">Name</label>
										<input
											type="text"
											value={editForm.name}
											onChange={e => setEditForm({ ...editForm, name: e.target.value })}
											className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
											disabled={profiles.some(p => p.name === editForm.name)}
										/>
									</div>
									<div>
										<label className="block text-sm text-gray-400 mb-1">Description</label>
										<input
											type="text"
											value={editForm.description}
											onChange={e => setEditForm({ ...editForm, description: e.target.value })}
											className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
										/>
									</div>
								</div>

								<h4 className="font-medium text-gray-300 mt-4">Chirp Parameters</h4>
								<div className="grid grid-cols-3 gap-4">
									{Object.entries(editForm.chirp).map(([key, value]) => (
										<div key={key}>
											<label className="block text-sm text-gray-400 mb-1">{key}</label>
											<input
												type="number"
												value={value}
												onChange={e => setEditForm({
													...editForm,
													chirp: { ...editForm.chirp, [key]: parseFloat(e.target.value) }
												})}
												className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
											/>
										</div>
									))}
								</div>

								<h4 className="font-medium text-gray-300 mt-4">Frame Parameters</h4>
								<div className="grid grid-cols-3 gap-4">
									{Object.entries(editForm.frame).map(([key, value]) => (
										<div key={key}>
											<label className="block text-sm text-gray-400 mb-1">{key}</label>
											<input
												type="number"
												value={value}
												onChange={e => setEditForm({
													...editForm,
													frame: { ...editForm.frame, [key]: parseFloat(e.target.value) }
												})}
												className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
											/>
										</div>
									))}
								</div>

								<div className="flex gap-4 mt-6">
									<Button onClick={handleSave}>Save</Button>
									<Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
								</div>
							</div>
						</>
					) : selected ? (
						<>
							<div className="flex items-center justify-between mb-4">
								<h3 className="text-lg font-medium">{selected.name}</h3>
								<div className="flex gap-2">
									<Button size="sm" onClick={() => handleFlash(selected.name)}>Flash to Device</Button>
									<Button size="sm" variant="secondary" onClick={() => startEdit(selected)}>Edit</Button>
									{selected.name !== 'default' && (
										<Button size="sm" variant="danger" onClick={() => handleDelete(selected.name)}>Delete</Button>
									)}
								</div>
							</div>
							{selected.description && (
								<p className="text-gray-400 mb-4">{selected.description}</p>
							)}
							<div className="grid grid-cols-2 gap-6">
								<div>
									<h4 className="font-medium text-gray-300 mb-2">Chirp</h4>
									<dl className="space-y-1 text-sm">
										{Object.entries(selected.chirp).map(([k, v]) => (
											<div key={k} className="flex justify-between">
												<dt className="text-gray-400">{k}</dt>
												<dd className="font-mono">{v}</dd>
											</div>
										))}
									</dl>
								</div>
								<div>
									<h4 className="font-medium text-gray-300 mb-2">Frame</h4>
									<dl className="space-y-1 text-sm">
										{Object.entries(selected.frame).map(([k, v]) => (
											<div key={k} className="flex justify-between">
												<dt className="text-gray-400">{k}</dt>
												<dd className="font-mono">{v}</dd>
											</div>
										))}
									</dl>
								</div>
							</div>
						</>
					) : (
						<p className="text-gray-400">Select a profile to view details.</p>
					)}
				</div>
			</div>
		</div>
	)
}
