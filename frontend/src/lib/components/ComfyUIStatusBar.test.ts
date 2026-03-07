import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, waitFor } from '@testing-library/svelte';
import ComfyUIStatusBar from './ComfyUIStatusBar.svelte';

describe('ComfyUIStatusBar', () => {
	beforeEach(() => {
		vi.stubGlobal(
			'fetch',
			vi.fn((url: string) => {
				if (typeof url === 'string' && url.endsWith('/config')) {
					return Promise.resolve({
						ok: true,
						json: () =>
							Promise.resolve({
								workflowuiPluginAvailable: false,
								workflowuiPluginIncompatible: true,
								workflowuiPluginMinVersion: '1.0.10'
							})
					} as Response);
				}
				if (typeof url === 'string' && url.includes('/comfyui/status')) {
					return Promise.resolve({
						ok: true,
						json: () =>
							Promise.resolve({
								queue: { running: 0, pending: 0 },
								system_stats: null
							})
					} as Response);
				}
				return Promise.reject(new Error('Unexpected fetch URL'));
			})
		);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	it('shows version-incompatible warning when config has workflowuiPluginAvailable false and workflowuiPluginIncompatible true', async () => {
		const { getByText } = render(ComfyUIStatusBar);

		await waitFor(() => {
			expect(getByText(/WorkflowUI plugin version incompatible/i)).toBeInTheDocument();
		});

		expect(getByText(/update the ComfyUI addon.*for full compatibility/i)).toBeInTheDocument();
	});

	it('shows minimum version in message when workflowuiPluginMinVersion is returned', async () => {
		const { getByText } = render(ComfyUIStatusBar);

		await waitFor(() => {
			expect(getByText(/≥1\.0\.10/)).toBeInTheDocument();
		});
	});
});
