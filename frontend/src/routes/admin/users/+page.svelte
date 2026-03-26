<script lang="ts">
	import { getApiBase } from '$lib/config';
	import { authState } from '$lib/stores/auth';
	import { get } from 'svelte/store';

	type UserRow = {
		id: string;
		username: string;
		role: 'admin' | 'user';
		allow_all_apps: boolean;
		disabled_at: number | null;
		allowed_app_ids: string[];
	};
	type AppRow = { id: string; slug: string; title: string };

	let users = $state<UserRow[]>([]);
	let apps = $state<AppRow[]>([]);
	let loading = $state(true);
	let error = $state('');
	let newUsername = $state('');
	let newPassword = $state('');
	let newRole = $state<'admin' | 'user'>('user');
	let newAllowAll = $state(false);
	let newAllowedAppIds = $state<string[]>([]);

	async function loadAll() {
		loading = true;
		error = '';
		try {
			const base = getApiBase() || '';
			const [u, a] = await Promise.all([
				fetch(`${base}/admin/users`, { credentials: 'include' }),
				fetch(`${base}/admin/apps`, { credentials: 'include' })
			]);
			if (!u.ok) throw new Error('Failed to load users');
			users = await u.json();
			apps = a.ok ? await a.json() : [];
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load users';
		} finally {
			loading = false;
		}
	}

	async function createUser() {
		try {
			const base = getApiBase() || '';
			const res = await fetch(`${base}/admin/users`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify({
					username: newUsername,
					password: newPassword,
					role: newRole,
					allow_all_apps: newAllowAll
					,
					allowed_app_ids: newAllowedAppIds
				})
			});
			if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail || 'Failed to create user');
			newUsername = '';
			newPassword = '';
			newRole = 'user';
			newAllowAll = false;
			newAllowedAppIds = [];
			await loadAll();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to create user';
		}
	}

	async function saveUser(u: UserRow) {
		try {
			const base = getApiBase() || '';
			const res = await fetch(`${base}/admin/users/${u.id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify({
					role: u.role,
					allow_all_apps: u.allow_all_apps,
					disabled_at: u.disabled_at,
					allowed_app_ids: u.allowed_app_ids
				})
			});
			if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail || 'Failed to update user');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to update user';
		}
	}

	$effect(() => {
		const auth = get(authState);
		if (!auth.loaded) return;
		if (!auth.authenticated || auth.user?.role !== 'admin') {
			error = 'Admin access required';
			loading = false;
			return;
		}
		loadAll();
	});
</script>

<div class="page">
	<h1>User Management</h1>
	{#if error}<p class="error">{error}</p>{/if}
	{#if loading}
		<p>Loading...</p>
	{:else}
		<section>
			<h2>Create user</h2>
			<div class="row">
				<input placeholder="username" bind:value={newUsername} />
				<input placeholder="password" type="password" bind:value={newPassword} />
				<select bind:value={newRole}><option value="user">user</option><option value="admin">admin</option></select>
				<label><input type="checkbox" bind:checked={newAllowAll} />allow all apps</label>
				{#if !newAllowAll}
					{#each apps as app (app.id)}
						<label>
							<input
								type="checkbox"
								checked={newAllowedAppIds.includes(app.id)}
								onchange={(e) => {
									const checked = (e.currentTarget as HTMLInputElement).checked;
									newAllowedAppIds = checked
										? [...newAllowedAppIds, app.id]
										: newAllowedAppIds.filter((id) => id !== app.id);
								}}
							/>
							{app.title}
						</label>
					{/each}
				{/if}
				<button onclick={createUser}>Create</button>
			</div>
		</section>
		<section>
			<h2>Users</h2>
			{#each users as u (u.id)}
				<div class="user-card">
					<strong>{u.username}</strong>
					<select bind:value={u.role}><option value="user">user</option><option value="admin">admin</option></select>
					<label><input type="checkbox" bind:checked={u.allow_all_apps} />allow all apps</label>
					{#if !u.allow_all_apps}
						{#each apps as app (app.id)}
							<label>
								<input
									type="checkbox"
									checked={u.allowed_app_ids.includes(app.id)}
									onchange={(e) => {
										const checked = (e.currentTarget as HTMLInputElement).checked;
										u.allowed_app_ids = checked
											? [...u.allowed_app_ids, app.id]
											: u.allowed_app_ids.filter((id) => id !== app.id);
									}}
								/>
								{app.title}
							</label>
						{/each}
					{/if}
					<label><input type="checkbox" checked={u.disabled_at != null} onchange={(e) => (u.disabled_at = (e.currentTarget as HTMLInputElement).checked ? Date.now() : null)} />disabled</label>
					<button onclick={() => saveUser(u)}>Save</button>
				</div>
			{/each}
		</section>
	{/if}
</div>

<style>
	.row, .user-card { display:flex; gap:0.5rem; align-items:center; flex-wrap:wrap; margin-bottom:0.5rem; }
	.error { color: var(--warning, #d33); }
</style>
