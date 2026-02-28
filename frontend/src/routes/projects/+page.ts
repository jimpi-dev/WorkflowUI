import { getApiBase } from '$lib/config';

export type ProjectSummary = {
	id: string;
	name: string;
	description?: string | null;
	created_at: number;
	updated_at: number;
	run_count: number;
	tags?: string[];
	storage_mode?: string;
	header_color?: string | null;
	archived_at?: number | null;
};

export const load = async ({ fetch, url, depends }) => {
	depends(url);
	depends('app:projects');
	const base = getApiBase() || '';
	const showArchive = url.searchParams.get('tab') === 'archive';
	// Fetch both lists in parallel so we can show counts on both tabs
	let activeProjects: ProjectSummary[] = [];
	let archivedProjects: ProjectSummary[] = [];
	try {
		const [activeRes, archiveRes] = await Promise.all([
			fetch(`${base}/projects?archived=false`),
			fetch(`${base}/projects?archived=true`)
		]);
		if (activeRes.ok) activeProjects = await activeRes.json();
		if (archiveRes.ok) archivedProjects = await archiveRes.json();
	} catch {
	}
	const projects = showArchive ? archivedProjects : activeProjects;
	return {
		projects,
		showArchive,
		activeCount: activeProjects.length,
		archiveCount: archivedProjects.length
	};
};
