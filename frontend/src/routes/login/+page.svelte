<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { getApiBase } from '$lib/config';
	import { authState } from '$lib/stores/auth';

	let username = $state('');
	let password = $state('');
	let loading = $state(false);
	let errorMessage = $state('');

	onMount(async () => {
		const base = getApiBase() || '';
		try {
			const res = await fetch(`${base}/auth/me`, { credentials: 'include' });
			if (!res.ok) return;
			const data = await res.json();
			const enabled = !!data?.enabled;
			const authenticated = !!data?.authenticated;
			authState.set({
				enabled,
				authenticated,
				user: data?.user ?? null,
				loaded: true
			});
			if (!enabled) {
				goto('/');
				return;
			}
			if (authenticated) {
				goto('/');
			}
		} catch {
			// keep page usable; submit will show a concrete error if login fails
		}
	});

	async function submit() {
		errorMessage = '';
		const user = username.trim();
		if (!user || !password) {
			errorMessage = 'Please enter both username and password.';
			return;
		}
		loading = true;
		try {
			const base = getApiBase() || '';
			const res = await fetch(`${base}/auth/login`, {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ username: user, password })
			});
			const data = await res.json().catch(() => ({}));
			if (!res.ok || !data?.ok) {
				errorMessage =
					typeof data?.detail === 'string' && data.detail
						? data.detail
						: 'Login failed. Please check your credentials.';
				return;
			}
			authState.set({
				enabled: true,
				authenticated: true,
				user: data?.user ?? null,
				loaded: true
			});
			goto('/');
		} catch {
			errorMessage = 'Unable to reach the server. Please try again.';
		} finally {
			loading = false;
		}
	}
</script>

<main class="login-page">
	<section class="login-card">
		<h1>Sign in</h1>
		<p class="subtitle">Authentication is enabled. Sign in to continue.</p>
		<form
			onsubmit={(e) => {
				e.preventDefault();
				void submit();
			}}
		>
			<div class="field">
				<label for="username">Username</label>
				<input id="username" type="text" autocomplete="username" bind:value={username} />
			</div>
			<div class="field">
				<label for="password">Password</label>
				<input id="password" type="password" autocomplete="current-password" bind:value={password} />
			</div>
			{#if errorMessage}
				<p class="error" role="alert">{errorMessage}</p>
			{/if}
			<button type="submit" disabled={loading}>
				{#if loading}Signing in...{:else}Sign in{/if}
			</button>
		</form>
	</section>
</main>

<style>
	.login-page {
		min-height: calc(100vh - 180px);
		display: grid;
		place-items: center;
		padding: 1rem;
	}

	.login-card {
		width: min(420px, 100%);
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 1.25rem;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
	}

	.subtitle {
		margin: 0.25rem 0 1rem;
		color: var(--muted);
	}

	.error {
		color: #f87171;
		margin: 0.25rem 0 0.75rem;
	}

	button {
		width: 100%;
	}
</style>
