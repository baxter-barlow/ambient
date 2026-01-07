const API_BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
	const response = await fetch(`${API_BASE}${path}`, {
		...options,
		headers: {
			'Content-Type': 'application/json',
			...options?.headers,
		},
	})

	if (!response.ok) {
		const error = await response.json().catch(() => ({ detail: response.statusText }))
		throw new Error(error.detail || 'Request failed')
	}

	return response.json()
}

// Device endpoints
export const deviceApi = {
	getStatus: () => request<import('../types').DeviceStatus>('/device/status'),
	getPorts: () => request<import('../types').SerialPort[]>('/device/ports'),
	verifyPorts: (cliPort: string, dataPort: string) =>
		request<import('../types').PortVerifyResult>('/device/verify-ports', {
			method: 'POST',
			body: JSON.stringify({ cli_port: cliPort, data_port: dataPort }),
		}),
	connect: (cliPort: string, dataPort: string, config?: string) =>
		request<import('../types').DeviceStatus>('/device/connect', {
			method: 'POST',
			body: JSON.stringify({ cli_port: cliPort, data_port: dataPort, config }),
		}),
	disconnect: () =>
		request<import('../types').DeviceStatus>('/device/disconnect', { method: 'POST' }),
	stop: () =>
		request<import('../types').DeviceStatus>('/device/stop', { method: 'POST' }),
}

// Recording endpoints
export const recordingApi = {
	list: () => request<import('../types').RecordingInfo[]>('/recordings'),
	getStatus: () => request<import('../types').RecordingStatus>('/recordings/status'),
	start: (name: string, format: string = 'h5') =>
		request<import('../types').RecordingStatus>('/recordings/start', {
			method: 'POST',
			body: JSON.stringify({ name, format }),
		}),
	stop: () => request<import('../types').RecordingStatus>('/recordings/stop', { method: 'POST' }),
	delete: (id: string) => request('/recordings/' + id, { method: 'DELETE' }),
}

// Config endpoints
export const configApi = {
	listProfiles: () => request<import('../types').ConfigProfile[]>('/config/profiles'),
	getProfile: (name: string) => request<import('../types').ConfigProfile>(`/config/profiles/${name}`),
	saveProfile: (profile: import('../types').ConfigProfile) =>
		request<import('../types').ConfigProfile>('/config/profiles', {
			method: 'POST',
			body: JSON.stringify(profile),
		}),
	deleteProfile: (name: string) => request(`/config/profiles/${name}`, { method: 'DELETE' }),
	flash: (profileName: string) =>
		request('/config/flash?profile_name=' + profileName, { method: 'POST' }),
}

// Params endpoints
export const paramsApi = {
	getCurrent: () => request<import('../types').AlgorithmParams>('/params/current'),
	setCurrent: (params: import('../types').AlgorithmParams) =>
		request<import('../types').AlgorithmParams>('/params/current', {
			method: 'PUT',
			body: JSON.stringify(params),
		}),
	listPresets: () => request<{ name: string; description: string; params: import('../types').AlgorithmParams }[]>('/params/presets'),
}

// Tests endpoints
export const testsApi = {
	listModules: () => request<{ name: string; path: string; hardware_required: boolean }[]>('/tests/modules'),
	run: (modules: string[], includeHardware: boolean) =>
		request('/tests/run', {
			method: 'POST',
			body: JSON.stringify({ modules, include_hardware: includeHardware }),
		}),
}
