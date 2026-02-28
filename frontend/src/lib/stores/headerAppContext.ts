import { writable } from 'svelte/store';

export type HeaderAppContext = {
	workflowId: string | null;
	displayName: string | null;
	headerColor: string | null;
	appId: string | null;
	projectId: string | null;
	projectName: string | null;
	projectHeaderColor: string | null;
	projectDetail: { name: string; run_count: number; created_at: number } | null;
};

const initial: HeaderAppContext = {
	workflowId: null,
	displayName: null,
	headerColor: null,
	appId: null,
	projectId: null,
	projectName: null,
	projectHeaderColor: null,
	projectDetail: null
};

export const headerAppContext = writable<HeaderAppContext>({ ...initial });

export function setHeaderAppContext(ctx: Partial<HeaderAppContext>) {
	headerAppContext.update((prev) => ({ ...prev, ...ctx }));
}

export function clearHeaderAppContext() {
	headerAppContext.set({ ...initial });
}
