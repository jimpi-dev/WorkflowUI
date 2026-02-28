import { getApiBase } from '$lib/config';

export async function load({ params, fetch, depends }) {
	depends('app:workflow');
	const apiBase = getApiBase() || '';
	let workflow: {
		id: string;
		name: string;
		created_at: number;
		versions: { id: string; workflow_id: string; version: number; graph_hash: string; created_at: number; apps: { id: string; slug: string; title: string; is_public: boolean }[] }[];
	} | null = null;
	try {
		const res = await fetch(`${apiBase}/workflow-definitions/${params.workflowId}`);
		if (res.ok) workflow = await res.json();
	} catch {
	}
	return { workflow };
}
