import { getApiBase } from '$lib/config';

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
			if (Array.isArray(list)) {
				comfyuiWorkflows = list.map((w: { id?: string; label?: string }) => ({
					id: typeof w.id === 'string' ? w.id : String(w.id ?? ''),
					label: typeof w.label === 'string' ? w.label : (w.id != null ? String(w.id) : '')
				})).filter((w: { id: string }) => w.id);
			}
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
