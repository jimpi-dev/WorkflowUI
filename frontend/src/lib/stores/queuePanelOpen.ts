import { writable } from 'svelte/store';

const STORAGE_KEY = 'workflowui_queue_panel_open';

function getStored(): boolean {
	if (typeof sessionStorage === 'undefined') return false;
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		return raw === '1' || raw === 'true';
	} catch {
		return false;
	}
}

function persist(value: boolean) {
	try {
		if (typeof sessionStorage !== 'undefined') {
			sessionStorage.setItem(STORAGE_KEY, value ? '1' : '0');
		}
	} catch {
		// ignore
	}
}

function createQueuePanelOpenStore() {
	const initial = getStored();
	const { subscribe, set, update } = writable(initial);
	return {
		subscribe,
		set: (value: boolean) => {
			set(value);
			persist(value);
		},
		update: (fn: (value: boolean) => boolean) => {
			update((v) => {
				const next = fn(v);
				persist(next);
				return next;
			});
		}
	};
}

export const queuePanelOpen = createQueuePanelOpenStore();
