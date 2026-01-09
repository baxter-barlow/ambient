import { useState, useEffect, useMemo } from 'react'
import { configApi } from '../api/client'
import Button from '../components/common/Button'
import type { ConfigProfile, ChirpParams, FrameParams } from '../types'
import clsx from 'clsx'

// Parameter definitions with metadata for better UX
const CHIRP_PARAMS: {
	key: keyof ChirpParams
	label: string
	unit: string
	description: string
	min: number
	max: number
	step: number
}[] = [
	{
		key: 'start_freq_ghz',
		label: 'Start Frequency',
		unit: 'GHz',
		description: 'Chirp starting frequency (typically 60-64 GHz for IWR6843)',
		min: 60,
		max: 64,
		step: 0.25,
	},
	{
		key: 'bandwidth_mhz',
		label: 'Bandwidth',
		unit: 'MHz',
		description: 'Chirp bandwidth affects range resolution (higher = better)',
		min: 500,
		max: 4000,
		step: 100,
	},
	{
		key: 'idle_time_us',
		label: 'Idle Time',
		unit: 'us',
		description: 'Time between chirps for settling',
		min: 2,
		max: 100,
		step: 1,
	},
	{
		key: 'ramp_end_time_us',
		label: 'Ramp End Time',
		unit: 'us',
		description: 'Chirp duration (longer = better SNR, lower max velocity)',
		min: 20,
		max: 200,
		step: 5,
	},
	{
		key: 'adc_samples',
		label: 'ADC Samples',
		unit: '',
		description: 'Samples per chirp (power of 2, affects range bins)',
		min: 64,
		max: 512,
		step: 64,
	},
	{
		key: 'sample_rate_ksps',
		label: 'Sample Rate',
		unit: 'ksps',
		description: 'ADC sampling rate (typically 5000-15000)',
		min: 2000,
		max: 15000,
		step: 500,
	},
	{
		key: 'rx_gain_db',
		label: 'RX Gain',
		unit: 'dB',
		description: 'Receiver gain (higher for longer range, lower for close)',
		min: 24,
		max: 48,
		step: 2,
	},
]

const FRAME_PARAMS: {
	key: keyof FrameParams
	label: string
	unit: string
	description: string
	min: number
	max: number
	step: number
}[] = [
	{
		key: 'chirps_per_frame',
		label: 'Chirps/Frame',
		unit: '',
		description: 'Number of chirps per frame (affects velocity resolution)',
		min: 16,
		max: 256,
		step: 16,
	},
	{
		key: 'frame_period_ms',
		label: 'Frame Period',
		unit: 'ms',
		description: 'Time between frames (50ms = 20 Hz frame rate)',
		min: 20,
		max: 200,
		step: 5,
	},
]

// Quick preset configurations
const PRESETS: { name: string; description: string; chirp: ChirpParams; frame: FrameParams }[] = [
	{
		name: 'Vital Signs (Close)',
		description: 'Optimized for vital signs at 0.5-1.5m distance',
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
	},
	{
		name: 'Vital Signs (Far)',
		description: 'For vital signs at 1.5-3m distance',
		chirp: {
			start_freq_ghz: 60.0,
			bandwidth_mhz: 3000.0,
			idle_time_us: 10.0,
			ramp_end_time_us: 80.0,
			adc_samples: 256,
			sample_rate_ksps: 8000,
			rx_gain_db: 42,
		},
		frame: {
			chirps_per_frame: 64,
			frame_period_ms: 50.0,
		},
	},
	{
		name: 'High Resolution',
		description: 'Maximum range resolution for fine detail',
		chirp: {
			start_freq_ghz: 60.0,
			bandwidth_mhz: 4000.0,
			idle_time_us: 5.0,
			ramp_end_time_us: 50.0,
			adc_samples: 512,
			sample_rate_ksps: 12000,
			rx_gain_db: 30,
		},
		frame: {
			chirps_per_frame: 128,
			frame_period_ms: 66.0,
		},
	},
	{
		name: 'Low Power',
		description: 'Reduced frame rate for battery operation',
		chirp: {
			start_freq_ghz: 60.0,
			bandwidth_mhz: 3000.0,
			idle_time_us: 20.0,
			ramp_end_time_us: 60.0,
			adc_samples: 128,
			sample_rate_ksps: 6000,
			rx_gain_db: 36,
		},
		frame: {
			chirps_per_frame: 32,
			frame_period_ms: 100.0,
		},
	},
]

// Calculate derived radar parameters
function computeDerivedParams(chirp: ChirpParams, frame: FrameParams) {
	const c = 3e8 // speed of light m/s
	const freqSlope = (chirp.bandwidth_mhz * 1e6) / (chirp.ramp_end_time_us * 1e-6) // Hz/s
	const rangeResolution = c / (2 * chirp.bandwidth_mhz * 1e6) // meters
	const maxRange = (chirp.sample_rate_ksps * 1e3 * c) / (2 * freqSlope) // meters
	const wavelength = c / (chirp.start_freq_ghz * 1e9)
	const maxVelocity = wavelength / (4 * chirp.ramp_end_time_us * 1e-6) // m/s
	const frameRate = 1000 / frame.frame_period_ms // Hz
	const velocityResolution = wavelength / (2 * frame.chirps_per_frame * chirp.ramp_end_time_us * 1e-6) // m/s

	return {
		rangeResolution: rangeResolution * 100, // cm
		maxRange: Math.min(maxRange, 10), // cap at 10m practical
		maxVelocity: maxVelocity, // m/s
		velocityResolution: velocityResolution, // m/s
		frameRate,
		rangeBins: chirp.adc_samples,
	}
}

export default function ConfigManager() {
	const [profiles, setProfiles] = useState<ConfigProfile[]>([])
	const [selected, setSelected] = useState<ConfigProfile | null>(null)
	const [editing, setEditing] = useState(false)
	const [editForm, setEditForm] = useState<ConfigProfile | null>(null)
	const [showPresets, setShowPresets] = useState(false)

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

	// Compute derived values when editing
	const derived = useMemo(() => {
		if (!editForm) return null
		return computeDerivedParams(editForm.chirp, editForm.frame)
	}, [editForm])

	const selectedDerived = useMemo(() => {
		if (!selected) return null
		return computeDerivedParams(selected.chirp, selected.frame)
	}, [selected])

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
		setEditForm(JSON.parse(JSON.stringify(profile)))
		setEditing(true)
	}

	const startNew = () => {
		setEditForm({
			name: '',
			description: '',
			chirp: { ...PRESETS[0].chirp },
			frame: { ...PRESETS[0].frame },
		})
		setEditing(true)
	}

	const applyPreset = (preset: typeof PRESETS[number]) => {
		if (!editForm) return
		setEditForm({
			...editForm,
			chirp: { ...preset.chirp },
			frame: { ...preset.frame },
		})
		setShowPresets(false)
	}

	const updateChirp = (key: keyof ChirpParams, value: number) => {
		if (!editForm) return
		setEditForm({
			...editForm,
			chirp: { ...editForm.chirp, [key]: value },
		})
	}

	const updateFrame = (key: keyof FrameParams, value: number) => {
		if (!editForm) return
		setEditForm({
			...editForm,
			frame: { ...editForm.frame, [key]: value },
		})
	}

	return (
		<div className="space-y-5">
			<div className="flex items-center justify-between">
				<h2 className="text-xl text-text-primary">Configuration Manager</h2>
				<Button onClick={startNew}>New Profile</Button>
			</div>

			<div className="grid grid-cols-3 gap-4">
				{/* Profile List */}
				<div className="bg-surface-2 border border-border rounded-card">
					<div className="px-4 py-3 border-b border-border">
						<span className="text-base text-text-primary font-medium">Profiles</span>
					</div>
					<div className="p-3 space-y-1">
						{profiles.map(profile => (
							<div
								key={profile.name}
								onClick={() => setSelected(profile)}
								className={clsx(
									'p-3 rounded cursor-pointer transition-colors duration-150',
									selected?.name === profile.name
										? 'bg-accent-teal text-text-inverse'
										: 'bg-surface-3 hover:bg-surface-4 text-text-primary'
								)}
							>
								<p className="font-medium">{profile.name}</p>
								{profile.description && (
									<p className={clsx(
										'text-sm truncate',
										selected?.name === profile.name ? 'text-text-inverse/70' : 'text-text-secondary'
									)}>
										{profile.description}
									</p>
								)}
							</div>
						))}
					</div>
				</div>

				{/* Profile Details / Editor */}
				<div className="col-span-2 bg-surface-2 border border-border rounded-card max-h-[calc(100vh-200px)] overflow-y-auto">
					{editing && editForm ? (
						<>
							<div className="px-4 py-3 border-b border-border flex items-center justify-between sticky top-0 bg-surface-2 z-10">
								<span className="text-base text-text-primary font-medium">
									{editForm.name ? `Edit: ${editForm.name}` : 'New Profile'}
								</span>
								<Button size="sm" variant="secondary" onClick={() => setShowPresets(!showPresets)}>
									Load Preset
								</Button>
							</div>

							{/* Presets dropdown */}
							{showPresets && (
								<div className="mx-4 mt-2 p-2 bg-surface-3 rounded-lg border border-border">
									<div className="grid grid-cols-2 gap-2">
										{PRESETS.map(preset => (
											<button
												key={preset.name}
												onClick={() => applyPreset(preset)}
												className="text-left p-2 rounded hover:bg-surface-4 transition-colors"
											>
												<p className="text-sm font-medium text-text-primary">{preset.name}</p>
												<p className="text-xs text-text-secondary">{preset.description}</p>
											</button>
										))}
									</div>
								</div>
							)}

							<div className="p-4 space-y-4">
								{/* Name and description */}
								<div className="grid grid-cols-2 gap-4">
									<div>
										<label className="block text-sm text-text-secondary mb-1">Profile Name</label>
										<input
											type="text"
											value={editForm.name}
											onChange={e => setEditForm({ ...editForm, name: e.target.value })}
											className="w-full bg-surface-3 border border-border rounded px-3 py-2 text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-teal"
											placeholder="my-config"
											disabled={profiles.some(p => p.name === editForm.name)}
										/>
									</div>
									<div>
										<label className="block text-sm text-text-secondary mb-1">Description</label>
										<input
											type="text"
											value={editForm.description}
											onChange={e => setEditForm({ ...editForm, description: e.target.value })}
											className="w-full bg-surface-3 border border-border rounded px-3 py-2 text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-teal"
											placeholder="Optimized for..."
										/>
									</div>
								</div>

								{/* Derived parameters display */}
								{derived && (
									<div className="bg-surface-3 rounded-lg p-3 border border-border">
										<h4 className="text-sm font-medium text-text-secondary mb-2">Computed Parameters</h4>
										<div className="grid grid-cols-3 gap-3 text-sm">
											<div>
												<span className="text-text-tertiary">Range Res:</span>
												<span className="ml-2 font-mono text-accent-teal">{derived.rangeResolution.toFixed(1)} cm</span>
											</div>
											<div>
												<span className="text-text-tertiary">Max Range:</span>
												<span className="ml-2 font-mono text-accent-teal">{derived.maxRange.toFixed(1)} m</span>
											</div>
											<div>
												<span className="text-text-tertiary">Range Bins:</span>
												<span className="ml-2 font-mono text-accent-teal">{derived.rangeBins}</span>
											</div>
											<div>
												<span className="text-text-tertiary">Max Velocity:</span>
												<span className="ml-2 font-mono text-accent-blue">{derived.maxVelocity.toFixed(2)} m/s</span>
											</div>
											<div>
												<span className="text-text-tertiary">Vel Res:</span>
												<span className="ml-2 font-mono text-accent-blue">{(derived.velocityResolution * 100).toFixed(1)} cm/s</span>
											</div>
											<div>
												<span className="text-text-tertiary">Frame Rate:</span>
												<span className="ml-2 font-mono text-accent-green">{derived.frameRate.toFixed(0)} Hz</span>
											</div>
										</div>
									</div>
								)}

								{/* Chirp parameters */}
								<div>
									<h4 className="font-medium text-text-secondary mb-3 flex items-center gap-2">
										Chirp Parameters
										<span className="text-micro text-text-tertiary font-normal">(radar waveform)</span>
									</h4>
									<div className="grid grid-cols-2 gap-4">
										{CHIRP_PARAMS.map(param => (
											<div key={param.key}>
												<div className="flex items-baseline justify-between mb-1">
													<label className="text-sm text-text-tertiary" title={param.description}>
														{param.label}
													</label>
													<span className="text-micro text-text-tertiary">{param.unit}</span>
												</div>
												<input
													type="number"
													value={editForm.chirp[param.key]}
													onChange={e => updateChirp(param.key, parseFloat(e.target.value) || 0)}
													min={param.min}
													max={param.max}
													step={param.step}
													className="w-full bg-surface-3 border border-border rounded px-3 py-2 font-mono text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-teal"
												/>
												<p className="text-micro text-text-tertiary mt-0.5">{param.description}</p>
											</div>
										))}
									</div>
								</div>

								{/* Frame parameters */}
								<div>
									<h4 className="font-medium text-text-secondary mb-3 flex items-center gap-2">
										Frame Parameters
										<span className="text-micro text-text-tertiary font-normal">(timing)</span>
									</h4>
									<div className="grid grid-cols-2 gap-4">
										{FRAME_PARAMS.map(param => (
											<div key={param.key}>
												<div className="flex items-baseline justify-between mb-1">
													<label className="text-sm text-text-tertiary" title={param.description}>
														{param.label}
													</label>
													<span className="text-micro text-text-tertiary">{param.unit}</span>
												</div>
												<input
													type="number"
													value={editForm.frame[param.key]}
													onChange={e => updateFrame(param.key, parseFloat(e.target.value) || 0)}
													min={param.min}
													max={param.max}
													step={param.step}
													className="w-full bg-surface-3 border border-border rounded px-3 py-2 font-mono text-text-primary focus:outline-none focus:ring-2 focus:ring-accent-teal"
												/>
												<p className="text-micro text-text-tertiary mt-0.5">{param.description}</p>
											</div>
										))}
									</div>
								</div>

								<div className="flex gap-3 pt-4 border-t border-border">
									<Button onClick={handleSave} disabled={!editForm.name}>Save Profile</Button>
									<Button variant="secondary" onClick={() => setEditing(false)}>Cancel</Button>
								</div>
							</div>
						</>
					) : selected ? (
						<>
							<div className="flex items-center justify-between px-4 py-3 border-b border-border sticky top-0 bg-surface-2 z-10">
								<span className="text-base text-text-primary font-medium">{selected.name}</span>
								<div className="flex gap-2">
									<Button size="sm" onClick={() => handleFlash(selected.name)}>Flash to Device</Button>
									<Button size="sm" variant="secondary" onClick={() => startEdit(selected)}>Edit</Button>
									{selected.name !== 'default' && (
										<Button size="sm" variant="danger" onClick={() => handleDelete(selected.name)}>Delete</Button>
									)}
								</div>
							</div>
							<div className="p-4">
								{selected.description && (
									<p className="text-text-secondary mb-4">{selected.description}</p>
								)}

								{/* Derived parameters for selected profile */}
								{selectedDerived && (
									<div className="bg-surface-3 rounded-lg p-3 border border-border mb-4">
										<h4 className="text-sm font-medium text-text-secondary mb-2">Computed Parameters</h4>
										<div className="grid grid-cols-3 gap-3 text-sm">
											<div>
												<span className="text-text-tertiary">Range Res:</span>
												<span className="ml-2 font-mono text-accent-teal">{selectedDerived.rangeResolution.toFixed(1)} cm</span>
											</div>
											<div>
												<span className="text-text-tertiary">Max Range:</span>
												<span className="ml-2 font-mono text-accent-teal">{selectedDerived.maxRange.toFixed(1)} m</span>
											</div>
											<div>
												<span className="text-text-tertiary">Range Bins:</span>
												<span className="ml-2 font-mono text-accent-teal">{selectedDerived.rangeBins}</span>
											</div>
											<div>
												<span className="text-text-tertiary">Max Velocity:</span>
												<span className="ml-2 font-mono text-accent-blue">{selectedDerived.maxVelocity.toFixed(2)} m/s</span>
											</div>
											<div>
												<span className="text-text-tertiary">Vel Res:</span>
												<span className="ml-2 font-mono text-accent-blue">{(selectedDerived.velocityResolution * 100).toFixed(1)} cm/s</span>
											</div>
											<div>
												<span className="text-text-tertiary">Frame Rate:</span>
												<span className="ml-2 font-mono text-accent-green">{selectedDerived.frameRate.toFixed(0)} Hz</span>
											</div>
										</div>
									</div>
								)}

								<div className="grid grid-cols-2 gap-6">
									<div>
										<h4 className="font-medium text-text-secondary mb-2">Chirp</h4>
										<dl className="space-y-1.5 text-sm">
											{CHIRP_PARAMS.map(param => (
												<div key={param.key} className="flex justify-between" title={param.description}>
													<dt className="text-text-tertiary">{param.label}</dt>
													<dd className="font-mono text-text-primary">
														{selected.chirp[param.key]} {param.unit}
													</dd>
												</div>
											))}
										</dl>
									</div>
									<div>
										<h4 className="font-medium text-text-secondary mb-2">Frame</h4>
										<dl className="space-y-1.5 text-sm">
											{FRAME_PARAMS.map(param => (
												<div key={param.key} className="flex justify-between" title={param.description}>
													<dt className="text-text-tertiary">{param.label}</dt>
													<dd className="font-mono text-text-primary">
														{selected.frame[param.key]} {param.unit}
													</dd>
												</div>
											))}
										</dl>
									</div>
								</div>
							</div>
						</>
					) : (
						<div className="p-4">
							<p className="text-text-tertiary">Select a profile to view details.</p>
						</div>
					)}
				</div>
			</div>
		</div>
	)
}
