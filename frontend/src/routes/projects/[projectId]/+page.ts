import { getApiBase } from '$lib/config';

export type AppSummary = { id: string; slug: string | null; title: string | null };

export const load = async ({ params, fetch }) => {
	const base = getApiBase() || '';
	let project: {
		id: string;
		name: string;
		slug?: string | null;
		description?: string | null;
		created_at: number;
		updated_at: number;
		tags?: string[];
		metadata?: { notes?: { id: string; content: string; created_at: number }[]; favorites?: string[] } | null;
		run_count: number;
		apps_used: { id: string; slug: string | null; title: string | null; removed?: boolean; header_color?: string | null }[];
		storage_mode?: string | null;
		header_color?: string | null;
		has_local_data?: boolean;
		has_remote_data?: boolean;
	} | null = null;
	let mediaStorage: { enabled: boolean; rootPath: string; deleteRemoteAfterSave: boolean } | null = null;
	let comfyuiDeleteSupported = false;
	let embedWorkflowuiMetadataOnDownload = false;
	let appsForNew: AppSummary[] = [];
	try {
		const [res, cfgRes] = await Promise.all([
			fetch(`${base}/projects/${params.projectId}`),
			fetch(`${base}/config`)
		]);
		if (res.ok) project = await res.json();
		if (cfgRes.ok) {
			const cfg = await cfgRes.json();
			if (cfg && typeof cfg === 'object') {
				if (cfg.mediaStorage) mediaStorage = cfg.mediaStorage;
				comfyuiDeleteSupported = cfg.comfyuiDeleteSupported === true;
				embedWorkflowuiMetadataOnDownload = cfg.embedWorkflowuiMetadataOnDownload === true;
			}
		}
		
		if (project && project.run_count === 0) {
			const appsRes = await fetch(`${base}/apps`);
			if (appsRes.ok) {
				const list = await appsRes.json();
				appsForNew = Array.isArray(list) ? list.map((a: { id: string; slug?: string | null; title?: string | null }) => ({ id: a.id, slug: a.slug ?? null, title: a.title ?? null })) : [];
			}
		}
	} catch {
	}
	return { project, projectId: params.projectId, mediaStorage, comfyuiDeleteSupported, embedWorkflowuiMetadataOnDownload, appsForNew };
};
