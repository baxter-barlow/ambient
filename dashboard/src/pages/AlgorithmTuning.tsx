import { useState, useEffect } from 'react'
import { paramsApi } from '../api/client'
import Button from '../components/common/Button'
import { showToast } from '../components/common/Toast'
import type { AlgorithmParams } from '../types'

/**
 * Algorithm Tuning following TE design principles:
 * - Borders as hierarchy
 * - Monospace for data values
 * - Functional accent colors for visualization
 */
export default function AlgorithmTuning() {
	const [params, setParams] = useState<AlgorithmParams | null>(null)
	const [presets, setPresets] = useState<{ name: string; description: string }[]>([])
	const [modified, setModified] = useState(false)

	useEffect(() => {
		loadData()
	}, [])

	const loadData = async () => {
		try {
			const [current, presetList] = await Promise.all([
				paramsApi.getCurrent(),
				paramsApi.listPresets() as Promise<{ name: string; description: string; params: AlgorithmParams }[]>,
			])
			setParams(current)
			setPresets(presetList.map(p => ({ name: p.name, description: p.description })))
		} catch (e) {
			console.warn('Failed to load algorithm parameters:', e)
		}
	}

	const handleChange = (key: keyof AlgorithmParams, value: number | string) => {
		if (!params) return
		setParams({ ...params, [key]: value })
		setModified(true)
	}

	const handleApply = async () => {
		if (!params) return
		try {
			await paramsApi.setCurrent(params)
			setModified(false)
			showToast('Parameters applied', 'success')
		} catch (e) {
			showToast(`Failed to apply parameters: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
		}
	}

	const handleReset = () => {
		loadData()
		setModified(false)
	}

	const handleApplyPreset = async (name: string) => {
		try {
			const preset = await paramsApi.listPresets() as { name: string; params: AlgorithmParams }[]
			const found = preset.find(p => p.name === name)
			if (found) {
				setParams(found.params)
				setModified(true)
			}
		} catch (e) {
			showToast(`Failed to load preset: ${e instanceof Error ? e.message : 'Unknown error'}`, 'error')
		}
	}

	if (!params) return <div className="text-ink-muted">Loading...</div>

	const sliderParams = [
		{ key: 'hr_low_hz', label: 'HR Low (Hz)', min: 0.5, max: 1.5, step: 0.05 },
		{ key: 'hr_high_hz', label: 'HR High (Hz)', min: 2.0, max: 4.0, step: 0.1 },
		{ key: 'rr_low_hz', label: 'RR Low (Hz)', min: 0.05, max: 0.2, step: 0.01 },
		{ key: 'rr_high_hz', label: 'RR High (Hz)', min: 0.4, max: 1.0, step: 0.05 },
		{ key: 'window_seconds', label: 'Window (s)', min: 5, max: 30, step: 1 },
	] as const

	return (
		<div className="space-y-6 max-w-6xl">
			<div className="flex items-center justify-between">
				<h2 className="text-h2 text-ink-primary">Algorithm Tuning</h2>
				<div className="flex gap-3">
					<Button onClick={handleApply} disabled={!modified}>Apply Changes</Button>
					<Button variant="secondary" onClick={handleReset} disabled={!modified}>Reset</Button>
				</div>
			</div>

			<div className="grid grid-cols-3 gap-4">
				{/* Presets */}
				<div className="bg-bg-secondary border border-border">
					<div className="px-4 py-3 border-b border-border">
						<span className="text-small font-medium text-ink-primary">Presets</span>
					</div>
					<div className="p-3 space-y-1">
						{presets.map(preset => (
							<button
								key={preset.name}
								onClick={() => handleApplyPreset(preset.name)}
								className="w-full text-left p-3 bg-bg-tertiary hover:bg-border transition-all duration-fast"
							>
								<p className="text-small font-medium text-ink-primary">{preset.name}</p>
								{preset.description && (
									<p className="text-label text-ink-muted">{preset.description}</p>
								)}
							</button>
						))}
					</div>
				</div>

				{/* Parameters */}
				<div className="col-span-2 bg-bg-secondary border border-border">
					<div className="px-4 py-3 border-b border-border">
						<span className="text-small font-medium text-ink-primary">Parameters</span>
					</div>
					<div className="p-4 space-y-6">
						{sliderParams.map(({ key, label, min, max, step }) => (
							<div key={key}>
								<div className="flex justify-between mb-2">
									<label className="text-small text-ink-secondary uppercase">{label}</label>
									<span className="font-mono text-accent-blue">
										{params[key as keyof AlgorithmParams]}
									</span>
								</div>
								<input
									type="range"
									min={min}
									max={max}
									step={step}
									value={params[key as keyof AlgorithmParams] as number}
									onChange={e => handleChange(key as keyof AlgorithmParams, parseFloat(e.target.value))}
									className="w-full accent-accent-yellow"
								/>
								<div className="flex justify-between text-label text-ink-muted font-mono">
									<span>{min}</span>
									<span>{max}</span>
								</div>
							</div>
						))}

						{/* Clutter method */}
						<div>
							<label className="block text-small text-ink-secondary mb-2 uppercase">Clutter Removal</label>
							<select
								value={params.clutter_method}
								onChange={e => handleChange('clutter_method', e.target.value)}
								className="w-full bg-bg-tertiary border border-border px-3 py-2 text-small text-ink-primary focus:outline-none focus:border-accent-yellow"
							>
								<option value="mti">MTI (Moving Target Indicator)</option>
								<option value="moving_avg">Moving Average</option>
								<option value="none">None</option>
							</select>
						</div>
					</div>

					{/* Frequency ranges visualization */}
					<div className="mx-4 mb-4 pt-4 border-t border-border">
						<h4 className="text-small font-medium text-ink-secondary mb-4">Frequency Ranges</h4>
						<div className="space-y-4">
							<div>
								<div className="flex justify-between text-small mb-1">
									<span className="text-accent-red">Heart Rate Band</span>
									<span className="text-ink-muted font-mono">
										{(params.hr_low_hz * 60).toFixed(0)} - {(params.hr_high_hz * 60).toFixed(0)} BPM
									</span>
								</div>
								<div className="h-2 bg-bg-tertiary relative">
									<div
										className="absolute h-full bg-accent-red"
										style={{
											left: `${(params.hr_low_hz / 4) * 100}%`,
											width: `${((params.hr_high_hz - params.hr_low_hz) / 4) * 100}%`,
										}}
									/>
								</div>
							</div>
							<div>
								<div className="flex justify-between text-small mb-1">
									<span className="text-accent-blue">Respiratory Rate Band</span>
									<span className="text-ink-muted font-mono">
										{(params.rr_low_hz * 60).toFixed(0)} - {(params.rr_high_hz * 60).toFixed(0)} BPM
									</span>
								</div>
								<div className="h-2 bg-bg-tertiary relative">
									<div
										className="absolute h-full bg-accent-blue"
										style={{
											left: `${(params.rr_low_hz / 4) * 100}%`,
											width: `${((params.rr_high_hz - params.rr_low_hz) / 4) * 100}%`,
										}}
									/>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</div>
	)
}
