import { writable } from 'svelte/store';
import { QUICK_RUNS_PROJECT_ID, QUICK_RUNS_PROJECT_NAME } from '$lib/constants';

export type QuickRunsProject = {
	id: string;
	name: string;
};

const _quickRunsProject = writable<QuickRunsProject>({
	id: QUICK_RUNS_PROJECT_ID,
	name: QUICK_RUNS_PROJECT_NAME
});

export const quickRunsProject = {
	subscribe: _quickRunsProject.subscribe,
	setFromConfig(config: unknown) {
		if (!config || typeof config !== 'object') return;
		const raw = (config as { quick_runs_project_id?: unknown }).quick_runs_project_id;
		if (typeof raw === 'string' && raw.trim()) {
			_quickRunsProject.set({ id: raw.trim(), name: QUICK_RUNS_PROJECT_NAME });
		}
	},
	resetToDefault() {
		_quickRunsProject.set({ id: QUICK_RUNS_PROJECT_ID, name: QUICK_RUNS_PROJECT_NAME });
	}
};
