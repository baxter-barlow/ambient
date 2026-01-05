import { useState, useEffect } from 'react'
import { paramsApi } from '../api/client'
import Button from '../components/common/Button'
import type { AlgorithmParams } from '../types'

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
		} catch {
			// ignore
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
		} catch {
			// ignore
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
		} catch {
			// ignore
		}
	}

	if (!params) return <div>Loading...</div>

	const sliderParams = [
		{ key: 'hr_low_hz', label: 'HR Low (Hz)', min: 0.5, max: 1.5, step: 0.05 },
		{ key: 'hr_high_hz', label: 'HR High (Hz)', min: 2.0, max: 4.0, step: 0.1 },
		{ key: 'rr_low_hz', label: 'RR Low (Hz)', min: 0.05, max: 0.2, step: 0.01 },
		{ key: 'rr_high_hz', label: 'RR High (Hz)', min: 0.4, max: 1.0, step: 0.05 },
		{ key: 'window_seconds', label: 'Window (s)', min: 5, max: 30, step: 1 },
	] as const

	return (
		<div className="space-y-6">
			<div className="flex items-center justify-between">
				<h2 className="text-xl font-semibold">Algorithm Tuning</h2>
				<div className="flex gap-2">
					<Button onClick={handleApply} disabled={!modified}>
						Apply Changes
					</Button>
					<Button variant="secondary" onClick={handleReset} disabled={!modified}>
						Reset
					</Button>
				</div>
			</div>

			<div className="grid grid-cols-3 gap-6">
				{/* Presets */}
				<div className="bg-gray-800 rounded-lg p-4">
					<h3 className="text-lg font-medium mb-4">Presets</h3>
					<div className="space-y-2">
						{presets.map(preset => (
							<button
								key={preset.name}
								onClick={() => handleApplyPreset(preset.name)}
								className="w-full text-left p-3 rounded bg-gray-700 hover:bg-gray-600"
							>
								<p className="font-medium">{preset.name}</p>
								{preset.description && (
									<p className="text-sm text-gray-400">{preset.description}</p>
								)}
							</button>
						))}
					</div>
				</div>

				{/* Parameters */}
				<div className="col-span-2 bg-gray-800 rounded-lg p-4">
					<h3 className="text-lg font-medium mb-4">Parameters</h3>

					<div className="space-y-6">
						{sliderParams.map(({ key, label, min, max, step }) => (
							<div key={key}>
								<div className="flex justify-between mb-2">
									<label className="text-gray-300">{label}</label>
									<span className="font-mono text-radar-400">
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
									className="w-full"
								/>
								<div className="flex justify-between text-xs text-gray-500">
									<span>{min}</span>
									<span>{max}</span>
								</div>
							</div>
						))}

						{/* Clutter method */}
						<div>
							<label className="block text-gray-300 mb-2">Clutter Removal</label>
							<select
								value={params.clutter_method}
								onChange={e => handleChange('clutter_method', e.target.value)}
								className="w-full bg-gray-700 border border-gray-600 rounded px-3 py-2"
							>
								<option value="mti">MTI (Moving Target Indicator)</option>
								<option value="moving_avg">Moving Average</option>
								<option value="none">None</option>
							</select>
						</div>
					</div>

					{/* Frequency ranges visualization */}
					<div className="mt-6 pt-6 border-t border-gray-700">
						<h4 className="font-medium text-gray-300 mb-4">Frequency Ranges</h4>
						<div className="space-y-4">
							<div>
								<div className="flex justify-between text-sm mb-1">
									<span className="text-red-400">Heart Rate Band</span>
									<span className="text-gray-400">
										{(params.hr_low_hz * 60).toFixed(0)} - {(params.hr_high_hz * 60).toFixed(0)} BPM
									</span>
								</div>
								<div className="h-2 bg-gray-700 rounded relative">
									<div
										className="absolute h-full bg-red-500 rounded"
										style={{
											left: `${(params.hr_low_hz / 4) * 100}%`,
											width: `${((params.hr_high_hz - params.hr_low_hz) / 4) * 100}%`,
										}}
									/>
								</div>
							</div>
							<div>
								<div className="flex justify-between text-sm mb-1">
									<span className="text-blue-400">Respiratory Rate Band</span>
									<span className="text-gray-400">
										{(params.rr_low_hz * 60).toFixed(0)} - {(params.rr_high_hz * 60).toFixed(0)} BPM
									</span>
								</div>
								<div className="h-2 bg-gray-700 rounded relative">
									<div
										className="absolute h-full bg-blue-500 rounded"
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
