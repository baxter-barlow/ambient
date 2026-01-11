import { useState, useEffect, useRef } from 'react'
import { testsApi } from '../api/client'
import { testsWs } from '../api/websocket'
import Button from '../components/common/Button'
import clsx from 'clsx'

interface TestModule {
	name: string
	path: string
	hardware_required: boolean
}

/**
 * Test Runner following TE design principles:
 * - Borders as hierarchy
 * - Monospace for output
 * - Functional accent colors
 */
export default function TestRunner() {
	const [modules, setModules] = useState<TestModule[]>([])
	const [selected, setSelected] = useState<string[]>([])
	const [includeHardware, setIncludeHardware] = useState(false)
	const [running, setRunning] = useState(false)
	const [output, setOutput] = useState<string[]>([])
	const outputRef = useRef<HTMLDivElement>(null)

	useEffect(() => {
		testsApi.listModules().then(setModules).catch((e) => {
			console.warn('Failed to list test modules:', e)
		})
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
		<div className="space-y-6 max-w-6xl">
			<h2 className="text-h2 text-ink-primary">Test Runner</h2>

			<div className="grid grid-cols-3 gap-4">
				{/* Module Selection */}
				<div className="bg-bg-secondary border border-border">
					<div className="px-4 py-3 border-b border-border">
						<span className="text-small font-medium text-ink-primary">Test Modules</span>
					</div>
					<div className="p-3 space-y-1">
						{modules.map(mod => (
							<label
								key={mod.name}
								className="flex items-center gap-3 p-2 hover:bg-bg-tertiary cursor-pointer transition-all duration-fast"
							>
								<input
									type="checkbox"
									checked={selected.includes(mod.name)}
									onChange={() => toggleModule(mod.name)}
									className="w-4 h-4 accent-accent-yellow"
								/>
								<div>
									<span className="text-small font-medium text-ink-primary">{mod.name}</span>
									{mod.hardware_required && (
										<span className="ml-2 text-label border border-accent-orange text-accent-orange px-1 py-0.5 bg-bg-tertiary uppercase font-mono">
											HW
										</span>
									)}
								</div>
							</label>
						))}
					</div>

					<div className="mx-3 pt-3 pb-3 border-t border-border">
						<label className="flex items-center gap-3 cursor-pointer">
							<input
								type="checkbox"
								checked={includeHardware}
								onChange={e => setIncludeHardware(e.target.checked)}
								className="w-4 h-4 accent-accent-yellow"
							/>
							<span className="text-small text-ink-secondary">Include hardware tests</span>
						</label>
					</div>

					<div className="p-3 pt-0">
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
				<div className="col-span-2 bg-bg-secondary border border-border">
					<div className="px-4 py-3 border-b border-border">
						<span className="text-small font-medium text-ink-primary">Output</span>
					</div>
					<div className="p-4">
						<div
							ref={outputRef}
							className="h-96 overflow-auto bg-bg-primary border border-border p-3 font-mono text-small"
						>
							{output.length === 0 ? (
								<p className="text-ink-muted">Run tests to see output.</p>
							) : (
								output.map((line, i) => (
									<div
										key={i}
										className={clsx(
											line.includes('PASSED') ? 'text-accent-green' :
											line.includes('FAILED') ? 'text-accent-red' :
											line.includes('ERROR') ? 'text-accent-red' :
											line.includes('SKIPPED') ? 'text-accent-orange' :
											'text-ink-secondary'
										)}
									>
										{line || '\u00A0'}
									</div>
								))
							)}
						</div>
					</div>
				</div>
			</div>
		</div>
	)
}
