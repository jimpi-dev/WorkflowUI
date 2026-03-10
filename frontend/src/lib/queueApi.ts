import { api } from '$lib/api';

export type QueueSummary = {
	seed?: number;
	latent_resolution?: string;
	runs?: number;
	key_inputs?: { label: string; value: unknown }[];
};

export type QueueItem = {
	run_id: string;
	run_group_id?: string | null;
	status: string;
	queue_position?: number;
	app_title?: string | null;
	app_slug?: string | null;
	app_header_color?: string | null;
	project_id?: string | null;
	project_title?: string | null;
	created_at?: number | null;
	comfyui_unreachable_warning?: string | null;
	summary?: QueueSummary;
};

export type QueueResponse = {
	running: QueueItem | null;
	queued: QueueItem[];
	processing_halted: boolean;
};

export async function getQueue(): Promise<QueueResponse> {
	const res = await api.get('queue');
	if (!res.ok) throw new Error(res.statusText || 'Failed to fetch queue');
	return res.json();
}

export async function pauseQueue(): Promise<{ ok: boolean; processing_halted: boolean }> {
	const res = await api.post('queue/pause', {});
	if (!res.ok) throw new Error(res.statusText || 'Failed to pause queue');
	return res.json();
}

export async function startQueue(): Promise<{ ok: boolean; processing_halted: boolean }> {
	const res = await api.post('queue/start', {});
	if (!res.ok) throw new Error(res.statusText || 'Failed to start queue');
	return res.json();
}

export async function cancelRun(runId: string): Promise<void> {
	const res = await api.post(`runs/${runId}/cancel`, {});
	if (!res.ok) throw new Error(res.statusText || 'Failed to cancel run');
}

export async function retryRun(runId: string): Promise<{ ok: boolean; queue_position: number }> {
	const res = await api.post(`runs/${runId}/retry`, {});
	if (!res.ok) throw new Error(res.statusText || 'Failed to retry run');
	return res.json();
}

export async function reorderRun(
	runId: string,
	direction: 'up' | 'down'
): Promise<{ ok: boolean; queue_position: number }> {
	const res = await api.post(`runs/${runId}/reorder`, { direction });
	if (!res.ok) throw new Error(res.statusText || 'Failed to reorder run');
	return res.json();
}

export async function moveRun(
	runId: string,
	position: number
): Promise<{ ok: boolean; queue_position: number }> {
	const res = await api.post(`runs/${runId}/move`, { position });
	if (!res.ok) throw new Error(res.statusText || 'Failed to move run');
	return res.json();
}
