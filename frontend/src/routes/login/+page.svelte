<script lang="ts">
	import { goto } from '$app/navigation';
	import { getApiBase } from '$lib/config';
	import { authState } from '$lib/stores/auth';

	let username = $state('');
	let password = $state('');
	let loading = $state(false);
	let error = $state('');

	async function submit() {
		loading = true;
		error = '';
		try {
			const base = getApiBase() || '';
			const res = await fetch(`${base}/auth/login`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username, password }),
				credentials: 'include'
			});
			const data = await res.json().catch(() => ({}));
			if (!res.ok) throw new Error(data?.detail || 'Login failed');
			authState.set({
				enabled: true,
				authenticated: true,
				user: data?.user ?? null,
				loaded: true
			});
			goto('/');
		} catch (e) {
			error = e instanceof Error ? e.message : 'Login failed';
		} finally {
			loading = false;
		}
	}
</script>

<div class="login-page">
	<form class="card" onsubmit={(e) => { e.preventDefault(); submit(); }}>
		<h1>Sign in</h1>
		<label>
			Username
			<input bind:value={username} autocomplete="username" />
		</label>
		<label>
			Password
			<input type="password" bind:value={password} autocomplete="current-password" />
		</label>
		{#if error}<p class="error">{error}</p>{/if}
		<button type="submit" disabled={loading}>{loading ? 'Signing in...' : 'Sign in'}</button>
	</form>
</div>

<style>
	.login-page { display:flex; justify-content:center; padding:3rem 1rem; }
	.card { width:min(420px, 100%); display:flex; flex-direction:column; gap:0.75rem; }
	.error { color: var(--warning, #d33); margin:0; }
</style>
