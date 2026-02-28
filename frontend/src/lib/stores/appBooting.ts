import { writable } from 'svelte/store';

export const appBooting = writable<boolean>(false);
