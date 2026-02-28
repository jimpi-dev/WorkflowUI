import { getApiBase } from '$lib/config';

export const load = async ({ url, fetch }) => {
	const match = url.pathname.match(/^\/app\/([^/]+)/);
	const workflowId = match ? match[1] : null;
	let projectIdFromUrl: string | null = null;
	try {
		projectIdFromUrl = url.searchParams.get('project') ?? null;
	} catch {
	}
	const base = getApiBase();

	let workflows: { id: string; label: string; output_count?: number }[] = [];
	try {
		const workflowsUrl = base ? `${base}/workflows` : '/workflows';
		workflows = await fetch(workflowsUrl).then((r) => r.json());
	} catch {
	}

	let publicApps: { id: string; slug: string; title: string; description?: string | null }[] = [];
	try {
		const appsUrl = base ? `${base}/apps/public` : '/apps/public';
		publicApps = await fetch(appsUrl).then((r) => r.json());
	} catch {
	}

	let appTitle: string | null = null;
	let appHeaderColor: string | null = null;
	let appId: string | null = null;
	if (workflowId) {
		try {
			const appUrl = base ? `${base}/app/${workflowId}` : `/app/${workflowId}`;
			const appRes = await fetch(appUrl);
			if (appRes.ok) {
				const data = await appRes.json();
				appTitle = data?.app?.title ?? null;
				appHeaderColor = data?.app?.header_color ?? null;
				appId = data?.app?.id ?? null;
			}
		} catch {
		}
	}

	let projectFromUrl: { id: string; name: string } | null = null;
	let projectHeaderColor: string | null = null;
	if (projectIdFromUrl) {
		try {
			const projUrl = base ? `${base}/projects/${projectIdFromUrl}` : `/projects/${projectIdFromUrl}`;
			const projRes = await fetch(projUrl);
			if (projRes.ok) {
				const proj = await projRes.json();
				projectFromUrl = { id: proj.id, name: proj.name };
				projectHeaderColor = proj?.header_color ?? null;
			}
		} catch {
		}
	}

	return { workflows, publicApps, workflowId, appId, appTitle, appHeaderColor, projectFromUrl, projectHeaderColor };
};
