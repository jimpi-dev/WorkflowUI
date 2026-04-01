import { getApiBase } from '$lib/config';

export type AdminUser = {
	id: string;
	username: string;
	role: 'admin' | 'user';
	allow_all_apps: boolean;
	disabled_at: number | null;
	quick_runs_project_id?: string | null;
	created_at: number;
	allowed_app_ids: string[];
};

export type AdminApp = {
	id: string;
	slug: string;
	title: string;
};

export const load = async ({ fetch }) => {
	const base = getApiBase() || '';
	let users: AdminUser[] = [];
	let apps: AdminApp[] = [];
	let usersError: string | null = null;
	let appsError: string | null = null;

	try {
		const r = await fetch(`${base}/admin/users`, { cache: 'no-store' });
		if (r.ok) users = await r.json();
		else usersError = `Failed to load users (${r.status})`;
	} catch {
		usersError = 'Failed to load users';
	}

	try {
		const r = await fetch(`${base}/admin/apps`, { cache: 'no-store' });
		if (r.ok) apps = await r.json();
		else appsError = `Failed to load apps (${r.status})`;
	} catch {
		appsError = 'Failed to load apps';
	}

	return { users, apps, usersError, appsError };
};
