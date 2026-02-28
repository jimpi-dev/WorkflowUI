import { getApiBase } from '$lib/config';

export const load = async ({ fetch }) => {
	const base = getApiBase() || '';
	let embedOnDownload = false;
	let embedOnSave = false;
	try {
		const res = await fetch(`${base}/config`);
		if (res.ok) {
			const cfg = await res.json();
			embedOnDownload = cfg.embedWorkflowuiMetadataOnDownload === true;
			embedOnSave = cfg.embedWorkflowuiMetadataOnSave === true;
		}
	} catch {
	}
	return { embedWorkflowuiMetadataOnDownload: embedOnDownload, embedWorkflowuiMetadataOnSave: embedOnSave };
};
