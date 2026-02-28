import { writable } from 'svelte/store';

type State = { projectId: string | null; tick: number };

const { subscribe, set, update } = writable<State>({ projectId: null, tick: 0 });

export const projectRunsInvalidate = {
	subscribe,
	invalidate(projectId: string | null) {
		if (!projectId) return;
		update((s) => ({ projectId, tick: s.tick + 1 }));
	},
};
