import { writable } from 'svelte/store';

export const consolePanelOpen = writable<boolean>(false);
