import { useState, useEffect, useRef } from 'react'
import { testsApi } from '../api/client'
import { testsWs } from '../api/websocket'
import Button from '../components/common/Button'

interface TestModule {
	name: string
	path: string
	hardware_required: boolean
}

export default function TestRunner() {
	const [modules, setModules] = useState<TestModule[]>([])
	const [selected, setSelected] = useState<string[]>([])
	const [includeHardware, setIncludeHardware] = useState(false)
	const [running, setRunning] = useState(false)
	const [output, setOutput] = useState<string[]>([])
	const outputRef = useRef<HTMLDivElement>(null)

	useEffect(() => {
		testsApi.listModules().then(setModules).catch(() => {})
	}, [])

	useEffect(() => {
		testsWs.connect()

		const unsubs = [
			testsWs.on('test_start', () => {
				setOutput([])
				setRunning(true)
			}),
			testsWs.on('test_output', (msg) => {
				const payload = msg.payload as { line: string }
				setOutput(prev => [...prev, payload.line])
			}),
			testsWs.on('test_complete', (msg) => {
				const payload = msg.payload as { returncode: number }
				setOutput(prev => [...prev, '', `Exit code: ${payload.returncode}`])
				setRunning(false)
			}),
		]

		return () => {
			unsubs.forEach(unsub => unsub())
			testsWs.disconnect()
		}
	}, [])

	useEffect(() => {
		if (outputRef.current) {
			outputRef.current.scrollTop = outputRef.current.scrollHeight
		}
	}, [output])

	const handleRun = () => {
		testsWs.send({
			type: 'run',
			modules: selected,
			include_hardware: includeHardware,
		})
	}

	const toggleModule = (name: string) => {
		setSelected(prev =>
			prev.includes(name)
				? prev.filter(m => m !== name)
				: [...prev, name]
		)
	}

	return (
		<div className="space-y-6">
			<h2 className="text-xl font-semibold">Test Runner</h2>

			<div className="grid grid-cols-3 gap-6">
				{/* Module Selection */}
				<div className="bg-gray-800 rounded-lg p-4">
					<h3 className="text-lg font-medium mb-4">Test Modules</h3>
					<div className="space-y-2">
						{modules.map(mod => (
							<label
								key={mod.name}
								className="flex items-center gap-3 p-2 rounded hover:bg-gray-700 cursor-pointer"
							>
								<input
									type="checkbox"
									checked={selected.includes(mod.name)}
									onChange={() => toggleModule(mod.name)}
									className="w-4 h-4"
								/>
								<div>
									<span className="font-medium">{mod.name}</span>
									{mod.hardware_required && (
										<span className="ml-2 text-xs bg-yellow-600 text-yellow-100 px-1.5 py-0.5 rounded">
											hardware
										</span>
									)}
								</div>
							</label>
						))}
					</div>

					<div className="mt-4 pt-4 border-t border-gray-700">
						<label className="flex items-center gap-3 cursor-pointer">
							<input
								type="checkbox"
								checked={includeHardware}
								onChange={e => setIncludeHardware(e.target.checked)}
								className="w-4 h-4"
							/>
							<span>Include hardware tests</span>
						</label>
					</div>

					<div className="mt-4">
						<Button
							onClick={handleRun}
							disabled={running}
							className="w-full"
						>
							{running ? 'Running...' : 'Run Tests'}
						</Button>
					</div>
				</div>

				{/* Output */}
				<div className="col-span-2 bg-gray-800 rounded-lg p-4">
					<h3 className="text-lg font-medium mb-4">Output</h3>
					<div
						ref={outputRef}
						className="h-96 overflow-auto bg-gray-900 rounded p-3 font-mono text-sm"
					>
						{output.length === 0 ? (
							<p className="text-gray-500">Run tests to see output.</p>
						) : (
							output.map((line, i) => (
								<div
									key={i}
									className={
										line.includes('PASSED') ? 'text-green-400' :
										line.includes('FAILED') ? 'text-red-400' :
										line.includes('ERROR') ? 'text-red-400' :
										line.includes('SKIPPED') ? 'text-yellow-400' :
										'text-gray-300'
									}
								>
									{line || '\u00A0'}
								</div>
							))
						)}
					</div>
				</div>
			</div>
		</div>
	)
}
