import { writable } from 'svelte/store';

export type PresetHeaderState = {
	creationOn: boolean;
	openListDialogRequest: boolean;
};

const initial: PresetHeaderState = {
	creationOn: false,
	openListDialogRequest: false
};

export const presetHeaderStore = writable<PresetHeaderState>({ ...initial });

export function setPresetHeaderCreation(on: boolean) {
	presetHeaderStore.update((s) => ({ ...s, creationOn: on }));
}

export function togglePresetHeaderCreation() {
	presetHeaderStore.update((s) => ({ ...s, creationOn: !s.creationOn }));
}

export function requestOpenPresetList() {
	presetHeaderStore.update((s) => ({ ...s, openListDialogRequest: true }));
}

export function clearPresetListRequest() {
	presetHeaderStore.update((s) => ({ ...s, openListDialogRequest: false }));
}
