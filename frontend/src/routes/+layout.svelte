<script lang="ts">
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';
	import { page } from '$app/stores';
	import { appBooting } from '$lib/stores/appBooting';
	import { clearHeaderAppContext } from '$lib/stores/headerAppContext';
	import AppHeader from '$lib/components/AppHeader.svelte';
	import ComfyUIStatusBar from '$lib/components/ComfyUIStatusBar.svelte';
	import ComfyUIConsole from '$lib/components/ComfyUIConsole.svelte';
	import QueueBadge from '$lib/components/QueueBadge.svelte';
	import QueuePanel from '$lib/components/QueuePanel.svelte';
	import PluginWelcomeModal from '$lib/components/PluginWelcomeModal.svelte';
	import { consolePanelOpen } from '$lib/stores/consolePanelOpen';
	import { queuePanelOpen } from '$lib/stores/queuePanelOpen';
	import { queuePanelWidth } from '$lib/stores/queuePanelWidth';
	import { tick, onMount } from 'svelte';
	let { children } = $props();

	let layoutEl: HTMLDivElement | null = $state(null);
	let footerEl: HTMLElement | null = $state(null);
	let isMobile = $state(false);
	let mobileQueueMounted = $state(false);
	let mobileQueueOpen = $state(false);
	let mobileConsoleMounted = $state(false);
	let mobileConsoleOpen = $state(false);
	let mobileQueueTimeout: ReturnType<typeof setTimeout> | null = null;
	let mobileConsoleTimeout: ReturnType<typeof setTimeout> | null = null;

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

	onMount(() => {
		if (typeof window === 'undefined') return;
		const mql = window.matchMedia('(max-width: 639px)');
		const update = () => {
			isMobile = mql.matches;
			if (!isMobile) {
				mobileQueueMounted = false;
				mobileQueueOpen = false;
				mobileConsoleMounted = false;
				mobileConsoleOpen = false;
			}
		};
		update();
		if ('addEventListener' in mql) mql.addEventListener('change', update);
		else mql.addListener(update);
		return () => {
			if ('removeEventListener' in mql) mql.removeEventListener('change', update);
			else mql.removeListener(update);
		};
	});

	$effect(() => {
		if (!isMobile) return;
		if ($queuePanelOpen) {
			if (mobileQueueTimeout) clearTimeout(mobileQueueTimeout);
			mobileQueueMounted = true;
			mobileQueueOpen = false;
			// Trigger the transition to open state.
			mobileQueueTimeout = setTimeout(async () => {
				await tick();
				mobileQueueOpen = true;
				mobileQueueTimeout = null;
			}, 0);
		} else if (mobileQueueMounted) {
			if (mobileQueueTimeout) clearTimeout(mobileQueueTimeout);
			mobileQueueOpen = false;
			mobileQueueTimeout = setTimeout(() => {
				mobileQueueMounted = false;
				mobileQueueOpen = false;
				mobileQueueTimeout = null;
			}, 220);
		}
	});

	$effect(() => {
		if (!isMobile) return;
		if ($consolePanelOpen) {
			if (mobileConsoleTimeout) clearTimeout(mobileConsoleTimeout);
			mobileConsoleMounted = true;
			mobileConsoleOpen = false;
			mobileConsoleTimeout = setTimeout(async () => {
				await tick();
				mobileConsoleOpen = true;
				mobileConsoleTimeout = null;
			}, 0);
		} else if (mobileConsoleMounted) {
			if (mobileConsoleTimeout) clearTimeout(mobileConsoleTimeout);
			mobileConsoleOpen = false;
			mobileConsoleTimeout = setTimeout(() => {
				mobileConsoleMounted = false;
				mobileConsoleOpen = false;
				mobileConsoleTimeout = null;
			}, 220);
		}
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="app-layout has-status-bar" bind:this={layoutEl}>
	<PluginWelcomeModal />
	<AppHeader />

	<div class="app-content-row">
		<div class="app-content-main">
			<main class="app-viewport">
				{@render children()}
			</main>
			{#if isMobile}
				{#if mobileConsoleMounted}
					<div
						class="console-mobile-backdrop"
						class:console-mobile-backdrop--open={mobileConsoleOpen}
						role="presentation"
						onclick={() => consolePanelOpen.set(false)}
					/>
					<div class="console-mobile-sheet" class:console-mobile-sheet--open={mobileConsoleOpen}>
						<ComfyUIConsole open={$consolePanelOpen} onclose={() => consolePanelOpen.set(false)} mobileFullscreen />
					</div>
				{/if}
			{:else}
				{#if $consolePanelOpen}
					<ComfyUIConsole open={$consolePanelOpen} onclose={() => consolePanelOpen.set(false)} />
				{/if}
			{/if}
		</div>
		{#if isMobile}
			{#if mobileQueueMounted}
				<div
					class="queue-mobile-backdrop"
					class:queue-mobile-backdrop--open={mobileQueueOpen}
					role="presentation"
					onclick={() => queuePanelOpen.set(false)}
				/>
				<aside class="queue-column queue-mobile-sheet" class:queue-mobile-sheet--open={mobileQueueOpen}>
					<QueuePanel />
				</aside>
			{/if}
		{:else}
			{#if $queuePanelOpen}
				<aside class="queue-column" style="width: {$queuePanelWidth}px;">
					<QueuePanel />
				</aside>
			{/if}
		{/if}
	</div>

	<div class="app-footer-area">
		<div class="app-footer-row">
			<div class="app-footer-main">
				<footer class="app-footer" bind:this={footerEl}>
					<ComfyUIStatusBar />
				</footer>
				<QueueBadge />
			</div>
			{#if $queuePanelOpen}
				<div class="app-footer-spacer" style="width: {$queuePanelWidth}px;"></div>
			{/if}
		</div>
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

	.app-content-row {
		display: flex;
		flex-direction: row;
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}

	.app-content-main {
		flex: 1;
		min-width: 0;
		min-height: 0;
		display: flex;
		flex-direction: column;
		overflow: hidden;
	}

	.app-viewport {
		flex: 1;
		min-width: 0;
		min-height: 0;
		overflow: auto;
		display: flex;
		flex-direction: column;
	}

	.queue-column {
		flex-shrink: 0;
		min-height: 0;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.queue-mobile-backdrop {
		position: fixed;
		inset: 0;
		z-index: 10000;
		background: rgba(0, 0, 0, 0.55);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		opacity: 0;
		transition: opacity 220ms ease;
	}
	.queue-mobile-backdrop--open {
		opacity: 1;
	}

	.queue-mobile-sheet {
		position: fixed;
		inset: 0;
		z-index: 10001;
		display: flex;
		flex-direction: column;
		width: 100vw;
		transform: translateX(100%);
		transition: transform 220ms ease;
	}
	.queue-mobile-sheet--open {
		transform: translateX(0%);
	}

	.console-mobile-backdrop {
		position: fixed;
		inset: 0;
		z-index: 10020;
		background: rgba(0, 0, 0, 0.55);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		opacity: 0;
		transition: opacity 220ms ease;
	}
	.console-mobile-backdrop--open {
		opacity: 1;
	}
	.console-mobile-sheet {
		position: fixed;
		inset: 0;
		z-index: 10021;
		display: flex;
		flex-direction: column;
		transform: translateX(100%);
		transition: transform 220ms ease;
	}
	.console-mobile-sheet--open {
		transform: translateX(0%);
	}

	.app-footer-area {
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
	}

	.app-footer-row {
		display: flex;
		flex-direction: row;
		width: 100%;
		min-width: 0;
	}

	.app-footer-main {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}

	.app-footer-spacer {
		flex-shrink: 0;
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
