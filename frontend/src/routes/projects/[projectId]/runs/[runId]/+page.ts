import { getApiBase } from '$lib/config';

export const load = async ({ params, fetch }) => {
	const base = getApiBase() || '';
	let run: {
		id: string;
		project_id: string;
		workflow_version_id: string;
		app_id: string | null;
		status: string;
		created_at: number;
		prompt_id: string | null;
		seed: number | null;
		images: { filename: string; subfolder: string; type: string; remote_deleted?: boolean }[];
		execution_time: number | null;
		error: string | null;
		input_snapshot: { values?: Record<string, unknown>; bindings?: unknown[] } | null;
		metadata_snapshot: Record<string, unknown> | null;
		deleted_outputs?: { output_index: number; seed?: number; master_seed?: number; filename?: string; subfolder?: string; type?: string; deleted_at_ts?: number }[];
		parent_run_id?: string | null;
		parent_media_id?: string | null;
		parent_app_title?: string | null;
		root_run_id?: string | null;
		deleted_at?: number | null;
		child_run_ids?: string[];
	} | null = null;
	try {
		const res = await fetch(`${base}/runs/${params.runId}`);
		if (res.ok) run = await res.json();
	} catch {
	}
	return { run, projectId: params.projectId, runId: params.runId };
};
