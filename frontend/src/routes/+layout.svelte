<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';
	import { page } from '$app/stores';
	import { appBooting } from '$lib/stores/appBooting';
	import { clearHeaderAppContext } from '$lib/stores/headerAppContext';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import ComfyUIStatusBar from '$lib/components/ComfyUIStatusBar.svelte';
	import ComfyUIConsole from '$lib/components/ComfyUIConsole.svelte';
	import ComfyUIQueueWidget from '$lib/components/QueueWidget.svelte';
	import PluginWelcomeModal from '$lib/components/PluginWelcomeModal.svelte';
	import { consolePanelOpen } from '$lib/stores/consolePanelOpen';
	import { onMount } from 'svelte';
	let { children } = $props();

	let layoutEl: HTMLDivElement | null = $state(null);
	let footerEl: HTMLElement | null = $state(null);

	let isAppRoute = $derived(
		$page.url.pathname === '/app' || $page.url.pathname.startsWith('/app/')
	);
	$effect(() => {
		if (!isAppRoute) {
			clearHeaderAppContext();
		}
	});

	function setFooterHeightVar() {
		if (layoutEl && footerEl && typeof footerEl.offsetHeight === 'number') {
			layoutEl.style.setProperty('--app-footer-height', `${footerEl.offsetHeight}px`);
		}
	}

	onMount(() => {
		if (!footerEl || !layoutEl) return;
		setFooterHeightVar();
		const ro = new ResizeObserver(setFooterHeightVar);
		ro.observe(footerEl);
		return () => ro.disconnect();
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="app-layout has-status-bar" bind:this={layoutEl}>
	<PluginWelcomeModal />
	<AppHeader />

	<main class="app-viewport">
		{@render children()}
	</main>

	<div class="app-footer-area">
		{#if $consolePanelOpen}
			<ComfyUIConsole open={$consolePanelOpen} onclose={() => consolePanelOpen.set(false)} />
		{/if}
		<footer class="app-footer" bind:this={footerEl}>
			<ComfyUIStatusBar />
		</footer>
		<ComfyUIQueueWidget />
	</div>

	{#if $appBooting}
		<div class="app-booting-mask" role="status" aria-live="polite" aria-label="Loading app">
			<div class="app-booting-content">
				<div class="app-booting-spinner" aria-hidden="true"></div>
				<p class="app-booting-text">Booting app…</p>
				<p class="app-booting-sub">Taking you to the workflow</p>
			</div>
		</div>
	{/if}
</div>

<style>
	.app-layout {
		display: flex;
		flex-direction: column;
		height: 100vh;
		min-height: 100vh;
		overflow: hidden;
	}
	@media (max-width: 639px) {
		.app-layout {
			height: 100dvh;
			min-height: 100dvh;
		}
	}

	.app-viewport {
		flex: 1;
		min-height: 0;
		overflow: auto;
		display: flex;
		flex-direction: column;
	}

	.app-footer-area {
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
	}
	
    .app-footer {
		flex-shrink: 0;
	}

	.app-booting-mask {
		position: fixed;
		inset: 0;
		z-index: 100000;
		display: flex;
		align-items: center;
		justify-content: center;
		background: color-mix(in srgb, var(--bg, #0d0d0d) 75%, transparent);
		backdrop-filter: blur(8px);
		-webkit-backdrop-filter: blur(8px);
		animation: app-booting-fade-in 0.25s ease-out;
	}

	.app-booting-content {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1.25rem;
		padding: 2.5rem 3rem;
		background: color-mix(in srgb, var(--card, #1a1a1a) 95%, transparent);
		border: 1px solid color-mix(in srgb, var(--accent) 25%, var(--border));
		border-radius: 16px;
		box-shadow: 0 24px 48px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(255, 255, 255, 0.04) inset;
	}

	.app-booting-spinner {
		width: 40px;
		height: 40px;
		border: 3px solid color-mix(in srgb, var(--accent) 30%, transparent);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: app-booting-spin 0.9s linear infinite;
	}

	.app-booting-text {
		margin: 0;
		font-size: 1.15rem;
		font-weight: 600;
		color: var(--text);
		letter-spacing: -0.02em;
	}

	.app-booting-sub {
		margin: 0;
		font-size: 0.9rem;
		color: var(--muted);
	}

	@keyframes app-booting-fade-in {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}

	@keyframes app-booting-spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
