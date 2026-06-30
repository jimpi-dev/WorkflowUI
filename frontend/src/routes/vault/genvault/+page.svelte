<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { getApiBase } from '$lib/config';
	import { genvaultEnabled } from '$lib/stores/genvaultEnabled';

	const apiBase = getApiBase();
	let loading = $state(true);
	let loadError = $state<string | null>(null);
	let genvaultUrl = $state('http://localhost:8090');

	async function loadUrl() {
		if (!$genvaultEnabled) {
			loading = false;
			return;
		}
		loading = true;
		loadError = null;
		try {
			const res = await fetch(`${apiBase}/genvault/url`);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			const data = await res.json();
			if (typeof data?.url === 'string' && data.url.trim()) {
				genvaultUrl = data.url.trim();
			}
		} catch (e) {
			loadError = e instanceof Error ? e.message : 'Failed to load GenVault URL';
		} finally {
			loading = false;
		}
	}

	onMount(() => {
		if (!$genvaultEnabled) {
			void goto('/vault');
			return;
		}
		void loadUrl();
	});
</script>

<svelte:head>
	<title>Vault / GenVault — WorkflowUI</title>
</svelte:head>

<section class="genvault-page">
	<header class="genvault-header">
		<h1>Vault / GenVault</h1>
		<div class="actions">
			<a href="/vault" class="link-btn">Input Images</a>
			<a href={genvaultUrl} target="_blank" rel="noreferrer" class="link-btn">Open standalone</a>
		</div>
	</header>

	{#if loading}
		<p class="muted">Loading GenVault…</p>
	{:else if loadError}
		<p class="error">GenVault konnte nicht geladen werden: {loadError}</p>
	{:else}
		<iframe title="GenVault" src={genvaultUrl} class="frame"></iframe>
	{/if}
</section>

<style>
	.genvault-page {
		padding: 0.75rem 1rem 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.genvault-header {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.genvault-header h1 {
		margin: 0;
		font-size: 1.3rem;
	}
	.actions {
		display: flex;
		gap: 0.5rem;
	}
	.link-btn {
		text-decoration: none;
		padding: 0.35rem 0.65rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text);
		background: var(--surface);
	}
	.frame {
		width: 100%;
		min-height: 78vh;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: #0b0e14;
	}
	.error {
		color: var(--warning);
	}
</style>

