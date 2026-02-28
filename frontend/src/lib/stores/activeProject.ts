import { writable } from 'svelte/store';

const STORAGE_KEY = 'workflow-ui-active-project';

export type ActiveProject = { id: string; name: string } | null;

function loadFromStorage(): ActiveProject {
	if (typeof window === 'undefined') return null;
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (!raw) return null;
		const parsed = JSON.parse(raw) as { id: string; name: string };
		if (parsed?.id && parsed?.name) return parsed;
	} catch {
	}
	return null;
}

function persist(value: ActiveProject) {
	if (typeof window === 'undefined') return;
	try {
		if (value) localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
		else localStorage.removeItem(STORAGE_KEY);
	} catch {
	}
}

function createActiveProjectStore() {
	const { subscribe, set, update } = writable<ActiveProject>(loadFromStorage());
	return {
		subscribe,
		set(value: ActiveProject) {
			persist(value);
			set(value);
		},
		update,
		select(id: string, name: string) {
			this.set({ id, name });
		},
		clear() {
			this.set(null);
		},
	};
}

export const activeProject = createActiveProjectStore();
