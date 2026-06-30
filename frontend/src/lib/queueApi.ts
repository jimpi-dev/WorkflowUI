import { api } from '$lib/api';
import { notifyQueueChanged } from '$lib/queueNotify';

export type QueueSummary = {
	seed?: number;
	latent_resolution?: string;
	key_inputs?: { label: string; value: unknown }[];
};

export type QueueDetailInput = {
	key: string;
	label: string;
	value: unknown;
	display_value: string;
	value_kind: 'scalar' | 'list' | 'object' | 'empty';
	group: 'core' | 'text' | 'numeric' | 'boolean' | 'media' | 'other';
	media_type?: 'image' | 'video' | 'audio';
	preview_url?: string;
};

export type QueueDetails = {
	total_inputs: number;
	media_count: number;
	groups: {
		core: QueueDetailInput[];
		text: QueueDetailInput[];
		numeric: QueueDetailInput[];
		boolean: QueueDetailInput[];
		media: QueueDetailInput[];
		other: QueueDetailInput[];
	};
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
	details?: QueueDetails;
};

export type QueueResponse = {
	running: QueueItem | null;
	queued: QueueItem[];
	processing_halted: boolean;
};

export type RecentRunItem = {
	id: string;
	run_group_id: string | null;
	project_id: string;
	project_title: string | null;
	workflow_version_id: string;
	app_id: string | null;
	app_slug: string | null;
	app_title: string | null;
	app_header_color?: string | null;
	status: string;
	queue_position?: number | null;
	created_at: number;
	seed: number | null;
	images: { filename: string; subfolder: string; type: string; remote_deleted?: boolean }[];
	execution_time: number | null;
	error: string | null;
	local_storage_status?: string | null;
	remote_status?: string | null;
	local_path?: string | null;
	local_storage_bytes?: number | null;
	remote_storage_bytes?: number | null;
	comfyui_unreachable_warning?: string | null;
	parent_run_id?: string | null;
	parent_media_id?: string | null;
	root_run_id?: string | null;
	summary?: QueueSummary;
};

export type RecentRunsResponse = {
	runs: RecentRunItem[];
	total: number;
};

export async function getQueue(): Promise<QueueResponse> {
	const res = await api.get('queue');
	if (!res.ok) throw new Error(res.statusText || 'Failed to fetch queue');
	return res.json();
}

export async function getRecentRuns(params?: {
	projectId?: string;
	appId?: string;
	status?: string[];
	q?: string;
	limit?: number;
	offset?: number;
	signal?: AbortSignal;
}): Promise<RecentRunsResponse> {
	const qs = new URLSearchParams();
	if (params?.projectId) qs.set('project_id', params.projectId);
	if (params?.appId) qs.set('app_id', params.appId);
	if (params?.status?.length) qs.set('status', params.status.join(','));
	if (params?.q?.trim()) qs.set('q', params.q.trim());
	if (typeof params?.limit === 'number') qs.set('limit', String(params.limit));
	if (typeof params?.offset === 'number') qs.set('offset', String(params.offset));
	const path = qs.size ? `runs/recent?${qs.toString()}` : 'runs/recent';
	const res = await api.get(path, params?.signal ? { signal: params.signal } : undefined);
	if (!res.ok) throw new Error(res.statusText || 'Failed to fetch recent runs');
	return res.json();
}

export async function pauseQueue(): Promise<{ ok: boolean; processing_halted: boolean }> {
	const res = await api.post('queue/pause', {});
	if (!res.ok) throw new Error(res.statusText || 'Failed to pause queue');
	const data = await res.json();
	notifyQueueChanged();
	return data;
}

export async function startQueue(): Promise<{ ok: boolean; processing_halted: boolean }> {
	const res = await api.post('queue/start', {});
	if (!res.ok) throw new Error(res.statusText || 'Failed to start queue');
	const data = await res.json();
	notifyQueueChanged();
	return data;
}

export async function cancelRun(runId: string): Promise<void> {
	const res = await api.post(`runs/${runId}/cancel`, {});
	if (!res.ok) throw new Error(res.statusText || 'Failed to cancel run');
	notifyQueueChanged();
}

export async function retryRun(runId: string): Promise<{ ok: boolean; queue_position: number }> {
	const res = await api.post(`runs/${runId}/retry`, {});
	if (!res.ok) throw new Error(res.statusText || 'Failed to retry run');
	const data = await res.json();
	notifyQueueChanged();
	return data;
}

export async function reorderRun(
	runId: string,
	direction: 'up' | 'down'
): Promise<{ ok: boolean; queue_position: number }> {
	const res = await api.post(`runs/${runId}/reorder`, { direction });
	if (!res.ok) throw new Error(res.statusText || 'Failed to reorder run');
	const data = await res.json();
	notifyQueueChanged();
	return data;
}

export async function moveRun(
	runId: string,
	position: number
): Promise<{ ok: boolean; queue_position: number }> {
	const res = await api.post(`runs/${runId}/move`, { position });
	if (!res.ok) throw new Error(res.statusText || 'Failed to move run');
	const data = await res.json();
	notifyQueueChanged();
	return data;
}
