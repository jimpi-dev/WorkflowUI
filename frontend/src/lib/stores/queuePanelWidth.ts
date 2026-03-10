import { writable } from 'svelte/store';
import { getQueuePanelWidthCookie } from '$lib/cookie';

function createQueuePanelWidthStore() {
	const initial = typeof document !== 'undefined' ? getQueuePanelWidthCookie() : 380;
	const { subscribe, set, update } = writable(initial);
	return {
		subscribe,
		set,
		update
	};
}

export const queuePanelWidth = createQueuePanelWidthStore();
