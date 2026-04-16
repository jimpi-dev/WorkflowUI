<script lang="ts">
	import { getApiBase } from '$lib/config';
	import { invalidate } from '$app/navigation';
	import type { AdminApp, AdminUser } from './+page';

	let { data } = $props<{
		data: {
			users: AdminUser[];
			apps: AdminApp[];
			usersError: string | null;
			appsError: string | null;
		};
	}>();

	const apiBase = getApiBase() || '';
	let createBusy = $state(false);
	let saveBusyUserId = $state<string | null>(null);
	let statusMessage = $state<string | null>(null);
	let statusError = $state<string | null>(null);

	type CreateForm = {
		username: string;
		password: string;
		role: 'admin' | 'user';
		allow_all_apps: boolean;
		allowed_app_ids: string[];
	};

	let createForm = $state<CreateForm>({
		username: '',
		password: '',
		role: 'user',
		allow_all_apps: false,
		allowed_app_ids: []
	});

	type EditState = {
		role: 'admin' | 'user';
		allow_all_apps: boolean;
		allowed_app_ids: string[];
		password: string;
		disabled: boolean;
	};
	let editById = $state<Record<string, EditState>>({});

	$effect(() => {
		const next: Record<string, EditState> = {};
		for (const u of data.users ?? []) {
			next[u.id] = {
				role: u.role,
				allow_all_apps: !!u.allow_all_apps,
				allowed_app_ids: [...(u.allowed_app_ids ?? [])],
				password: '',
				disabled: !!u.disabled_at
			};
		}
		editById = next;
	});

	function toggleAllowedApp(list: string[], appId: string): string[] {
		const s = new Set(list);
		if (s.has(appId)) s.delete(appId);
		else s.add(appId);
		return Array.from(s);
	}

	async function refresh() {
		await invalidate('app:projects');
		await invalidate((url) => url.pathname === '/admin/users');
	}

	async function createUser() {
		statusMessage = null;
		statusError = null;
		const username = createForm.username.trim();
		const password = createForm.password;
		if (!username || !password) {
			statusError = 'Username and password are required.';
			return;
		}
		createBusy = true;
		try {
			const res = await fetch(`${apiBase}/admin/users`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					username,
					password,
					role: createForm.role,
					allow_all_apps: createForm.allow_all_apps,
					allowed_app_ids: createForm.allow_all_apps ? [] : createForm.allowed_app_ids
				})
			});
			if (!res.ok) {
				const body = await res.json().catch(() => ({}));
				throw new Error(body?.detail || `Create failed (${res.status})`);
			}
			createForm = {
				username: '',
				password: '',
				role: 'user',
				allow_all_apps: false,
				allowed_app_ids: []
			};
			statusMessage = 'User created.';
			await refresh();
		} catch (e) {
			statusError = e instanceof Error ? e.message : 'Create failed';
		} finally {
			createBusy = false;
		}
	}

	async function saveUser(user: AdminUser) {
		statusMessage = null;
		statusError = null;
		const edit = editById[user.id];
		if (!edit) return;
		saveBusyUserId = user.id;
		try {
			const payload: Record<string, unknown> = {
				allow_all_apps: edit.allow_all_apps,
				allowed_app_ids: edit.allow_all_apps ? [] : edit.allowed_app_ids,
				disabled_at: edit.disabled ? Date.now() : null
			};
			if (!user.is_protected_admin) {
				payload.role = edit.role;
			}
			if (edit.password.trim()) payload.password = edit.password;
			const res = await fetch(`${apiBase}/admin/users/${user.id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(payload)
			});
			if (!res.ok) {
				const body = await res.json().catch(() => ({}));
				throw new Error(body?.detail || `Update failed (${res.status})`);
			}
			edit.password = '';
			statusMessage = `Saved ${user.username}.`;
			await refresh();
		} catch (e) {
			statusError = e instanceof Error ? e.message : 'Update failed';
		} finally {
			saveBusyUserId = null;
		}
	}
</script>

<div class="admin-users-page">
	<header class="page-header">
		<h1>Users</h1>
		<p>Manage accounts, roles, and app access.</p>
	</header>

	{#if data.usersError}
		<p class="error">{data.usersError}</p>
	{/if}
	{#if data.appsError}
		<p class="error">{data.appsError}</p>
	{/if}
	{#if statusError}
		<p class="error">{statusError}</p>
	{/if}
	{#if statusMessage}
		<p class="ok">{statusMessage}</p>
	{/if}

	<section class="card create-card">
		<h2>Create user</h2>
		<div class="grid">
			<input placeholder="Username" bind:value={createForm.username} />
			<input placeholder="Password" type="password" bind:value={createForm.password} />
			<select bind:value={createForm.role}>
				<option value="user">user</option>
				<option value="admin">admin</option>
			</select>
			<label><input type="checkbox" bind:checked={createForm.allow_all_apps} /> Allow all apps</label>
		</div>
		{#if !createForm.allow_all_apps}
			<div class="apps-picker">
				{#each data.apps as app (app.id)}
					<label>
						<input
							type="checkbox"
							checked={createForm.allowed_app_ids.includes(app.id)}
							onchange={() => (createForm.allowed_app_ids = toggleAllowedApp(createForm.allowed_app_ids, app.id))}
						/>
						{app.title} ({app.slug})
					</label>
				{/each}
			</div>
		{/if}
		<button disabled={createBusy} onclick={createUser}>
			{createBusy ? 'Creating...' : 'Create user'}
		</button>
	</section>

	<section class="card list-card">
		<h2>Existing users</h2>
		{#if data.users.length === 0}
			<p>No users.</p>
		{:else}
			{#each data.users as user (user.id)}
				{@const edit = editById[user.id]}
				<div class="user-row">
					<div class="user-head">
						<div class="user-title">
							<strong>{user.username}</strong>
							{#if user.is_protected_admin}
								<span class="badge">Protected admin</span>
							{/if}
						</div>
						<span class="subtle-id">{user.id}</span>
					</div>
					{#if edit}
						<div class="grid">
							<select bind:value={edit.role} disabled={!!user.is_protected_admin} title={user.is_protected_admin ? 'Protected admin role cannot be changed' : ''}>
								<option value="user">user</option>
								<option value="admin">admin</option>
							</select>
							<input placeholder="New password (optional)" type="password" bind:value={edit.password} />
							<label><input type="checkbox" bind:checked={edit.allow_all_apps} /> Allow all apps</label>
							<label>
								<input
									type="checkbox"
									bind:checked={edit.disabled}
									disabled={!!user.is_protected_admin}
								/>
								Disabled
							</label>
						</div>
						{#if user.is_protected_admin}
							<p class="hint">This protected admin account cannot be disabled and its role cannot be changed.</p>
						{/if}
						{#if !edit.allow_all_apps}
							<div class="apps-picker">
								{#each data.apps as app (app.id)}
									<label>
										<input
											type="checkbox"
											checked={edit.allowed_app_ids.includes(app.id)}
											onchange={() => (edit.allowed_app_ids = toggleAllowedApp(edit.allowed_app_ids, app.id))}
										/>
										{app.title} ({app.slug})
									</label>
								{/each}
							</div>
						{/if}
						<button disabled={saveBusyUserId === user.id} onclick={() => saveUser(user)}>
							{saveBusyUserId === user.id ? 'Saving...' : 'Save'}
						</button>
					{/if}
				</div>
			{/each}
		{/if}
	</section>
</div>

<style>
	.admin-users-page {
		padding: 1rem;
		display: grid;
		gap: 1rem;
		max-width: 1100px;
		margin: 0 auto;
	}
	.page-header p {
		margin-top: 0.25rem;
		color: var(--muted);
	}
	.card {
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 1rem;
		background: var(--card);
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(260px, 380px));
		gap: 0.6rem;
		margin-bottom: 0.6rem;
		align-items: center;
	}
	input,
	select,
	button {
		max-width: 100%;
	}
	.apps-picker {
		max-height: 180px;
		overflow: auto;
		border: 1px solid var(--border);
		padding: 0.6rem;
		border-radius: 6px;
		display: grid;
		gap: 0.25rem;
		margin-bottom: 0.6rem;
		max-width: 780px;
	}
	.user-row {
		border-top: 1px solid var(--border);
		padding-top: 0.85rem;
		margin-top: 0.85rem;
	}
	.user-head { display: flex; flex-direction: column; margin-bottom: 0.45rem; }
	.user-title { display: flex; gap: 0.5rem; align-items: center; }
	.badge {
		font-size: 0.75rem;
		padding: 0.15rem 0.45rem;
		border-radius: 999px;
		border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
		background: color-mix(in srgb, var(--accent) 14%, transparent);
		color: var(--text);
	}
	.subtle-id { color: var(--muted); font-size: 0.85rem; }
	.hint { color: var(--muted); margin-top: -0.15rem; margin-bottom: 0.5rem; }
	.error { color: #ff7373; }
	.ok { color: #7cd992; }
</style>
