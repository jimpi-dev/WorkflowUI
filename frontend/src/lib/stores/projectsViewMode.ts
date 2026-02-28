import { writable } from 'svelte/store';

export type ProjectsViewMode = 'grid' | 'list';

export const projectsViewMode = writable<ProjectsViewMode>('grid');
