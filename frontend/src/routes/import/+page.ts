import { getApiBase } from '$lib/config';

function normalizeComfyuiWorkflows(list: unknown): { id: string; label: string }[] {
	if (!Array.isArray(list)) return [];
	return list.flatMap((item) => {
		if (typeof item === 'string' && item.trim()) {
			return [{ id: item, label: item }];
		}
		if (!item || typeof item !== 'object') return [];
		const rec = item as Record<string, unknown>;
		if (typeof rec.id !== 'string' || !rec.id.trim()) return [];
		const id = rec.id;
		const label = typeof rec.label === 'string' && rec.label.trim() ? rec.label : id;
		return [{ id, label }];
	});
}

export const load = async ({ fetch }) => {
	const base = getApiBase() || '';
	let embedOnDownload = false;
	let embedOnSave = false;
	let comfyuiWorkflows: { id: string; label: string }[] = [];
	try {
		const res = await fetch(`${base}/config`);
		if (res.ok) {
			const cfg = await res.json();
			embedOnDownload = cfg.embedWorkflowuiMetadataOnDownload === true;
			embedOnSave = cfg.embedWorkflowuiMetadataOnSave === true;
		}
	} catch {
	}
	let comfyuiWorkflowsError: string | null = null;
	try {
		const wfRes = await fetch(`${base}/comfyui/workflows`);
		if (wfRes.ok) {
			const data = await wfRes.json();
			const list = Array.isArray(data) ? data : data?.workflows;
			comfyuiWorkflows = normalizeComfyuiWorkflows(list);
			if (comfyuiWorkflows.length === 0 && typeof data?.error === 'string' && data.error) {
				comfyuiWorkflowsError = data.error;
			}
		}
	} catch (e) {
		comfyuiWorkflowsError = e instanceof Error ? e.message : 'Failed to load workflow list';
	}
	return {
		embedWorkflowuiMetadataOnDownload: embedOnDownload,
		embedWorkflowuiMetadataOnSave: embedOnSave,
		comfyuiWorkflows,
		comfyuiWorkflowsError
	};
};
