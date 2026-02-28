import { getApiBase } from '$lib/config';

export type AppSummary = {
	id: string;
	slug: string;
	title: string;
	description?: string | null;
	is_public: boolean;
	created_at: number;
	last_used?: number | null;
	workflow_version_id: string;
	supported_input_kinds?: string[] | null;
	header_color?: string | null;
	created_from_image_import?: boolean;
};

export type ProjectOption = {
	id: string;
	name: string;
	slug?: string | null;
	run_count: number;
};

export const load = async ({ fetch, url, depends }) => {
	depends(url);
	const base = getApiBase() || '';
	let apps: AppSummary[] = [];
	let projects: ProjectOption[] = [];
	try {
		const res = await fetch(`${base}/apps`);
		if (res.ok) apps = await res.json();
	} catch {
	}
	try {
		const res = await fetch(`${base}/projects`);
		if (res.ok) projects = await res.json();
	} catch {
	}
	return { apps, projects };
};
