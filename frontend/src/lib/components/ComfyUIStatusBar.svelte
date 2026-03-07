<script lang="ts">
	import { getApiBase, appConfig } from '$lib/config';
	import { onMount, onDestroy } from 'svelte';
	import DbSizeBar from '$lib/components/DbSizeBar.svelte';

	interface Status {
		queue: { running: number; pending: number };
		system_stats: {
			vram_used_gb?: number;
			vram_total_gb?: number;
			ram_used_gb?: number;
			cpu_percent?: number;
			gpu_percent?: number;
		} | null;
	}

	let status = $state<Status | null>(null);
	let error = $state<string | null>(null);
	let workflowuiPluginAvailable = $state<boolean | null>(null);
	let workflowuiPluginIncompatible = $state(false);
	let dbSizeBytes = $state<number | null>(null);
	let dbBreakdown = $state<Record<string, number> | null>(null);
	let workflowuiPluginMinVersion = $state<string | null>(null);

	const POLL_INTERVAL_MS = 4000;
	const POLL_INTERVAL_HIDDEN_MS = 12000;
	const CONFIG_POLL_INTERVAL_MS = 60000;
	let intervalId: ReturnType<typeof setInterval> | null = null;
	let configIntervalId: ReturnType<typeof setInterval> | null = null;

	async function fetchConfig() {
		const base = getApiBase() || '';
		try {
			const res = await fetch(`${base}/config`, { signal: AbortSignal.timeout(5000) });
			if (!res.ok) return;
			const data = await res.json();
			workflowuiPluginAvailable = data.workflowuiPluginAvailable === true;
			workflowuiPluginIncompatible = data.workflowuiPluginIncompatible === true;
			dbSizeBytes = typeof data.dbSizeBytes === 'number' ? data.dbSizeBytes : null;
			dbBreakdown = data.dbBreakdown && typeof data.dbBreakdown === 'object' ? data.dbBreakdown : null;
			workflowuiPluginMinVersion =
				typeof data.workflowuiPluginMinVersion === 'string' && data.workflowuiPluginMinVersion
					? data.workflowuiPluginMinVersion
					: null;
		} catch {
			workflowuiPluginAvailable = null;
			workflowuiPluginIncompatible = false;
			dbSizeBytes = null;
			dbBreakdown = null;
			workflowuiPluginMinVersion = null;
		}
	}

	async function fetchStatus() {
		const base = getApiBase() || '';
		try {
			const res = await fetch(`${base}/comfyui/status`, { signal: AbortSignal.timeout(8000) });
			if (!res.ok) throw new Error(`Status ${res.status}`);
			const data = await res.json();
			status = data;
			error = null;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Unavailable';
			status = null;
		}
	}

	function startPolling() {
		if (typeof document === 'undefined') return;
		const isHidden = () => document.visibilityState === 'hidden';
		const ms = () => (isHidden() ? POLL_INTERVAL_HIDDEN_MS : POLL_INTERVAL_MS);
		fetchConfig();
		fetchStatus();
		intervalId = setInterval(fetchStatus, ms());
		configIntervalId = setInterval(fetchConfig, CONFIG_POLL_INTERVAL_MS);
		document.addEventListener('visibilitychange', onVisibilityChange);
	}

	function onVisibilityChange() {
		if (typeof document === 'undefined' || !intervalId) return;
		clearInterval(intervalId);
		intervalId = setInterval(fetchStatus, document.visibilityState === 'hidden' ? POLL_INTERVAL_HIDDEN_MS : POLL_INTERVAL_MS);
	}

	function stopPolling() {
		if (intervalId) {
			clearInterval(intervalId);
			intervalId = null;
		}
		if (configIntervalId) {
			clearInterval(configIntervalId);
			configIntervalId = null;
		}
		if (typeof document !== 'undefined') {
			document.removeEventListener('visibilitychange', onVisibilityChange);
		}
	}

	onMount(() => {
		startPolling();
	});

	onDestroy(() => {
		stopPolling();
	});
</script>

<div class="status-bar" role="status" aria-label="ComfyUI queue and system status">
	<span class="status-item app-info">{appConfig.appName} v{appConfig.version}</span>
	{#if appConfig.githubRepoUrl}
		<span class="status-sep" aria-hidden="true">|</span>
		<a
			href={appConfig.githubRepoUrl}
			target="_blank"
			rel="noopener noreferrer"
			class="status-item github-link"
			aria-label="GitHub repository"
		>
			<svg class="github-icon" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
				<path
					d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"
				/>
			</svg>
			Repo
		</a>
	{/if}
	{#if workflowuiPluginAvailable === true}
		<span class="status-sep" aria-hidden="true">|</span>
		<span class="status-item status-ok plugin-state" role="status" title="ComfyUI addon is installed and compatible.">
			<span class="plugin-state-dot plugin-state-ok" aria-hidden="true"></span>
			<span class="plugin-state-text">WorkflowUI plugin connected</span>
		</span>
	{/if}
	{#if workflowuiPluginAvailable === false}
		<span class="status-sep" aria-hidden="true">|</span>
		{#if workflowuiPluginIncompatible}
			<span
				class="status-item status-warning plugin-state"
				role="status"
				title={workflowuiPluginMinVersion
					? `Update the WorkflowUI plugin on ComfyUI to at least version ${workflowuiPluginMinVersion} for full compatibility.`
					: 'Update the WorkflowUI plugin on ComfyUI to the required version for full compatibility.'}
			>
				<span class="plugin-state-dot plugin-state-incompatible" aria-hidden="true"></span>
				<span class="plugin-state-text">
					WorkflowUI plugin version incompatible — update the ComfyUI addon to ≥{workflowuiPluginMinVersion ?? 'required version'} for full compatibility.
				</span>
			</span>
		{:else}
			<span class="status-item status-warning plugin-state" role="status" title="Install or update the WorkflowUI plugin on ComfyUI for more features (e.g. delete on server, media browse).">
				<span class="plugin-state-dot plugin-state-missing" aria-hidden="true"></span>
				<span class="plugin-state-text">WorkflowUI plugin not found — install the ComfyUI addon for more features.</span>
			</span>
		{/if}
	{/if}
	<span class="status-sep" aria-hidden="true">|</span>
	{#if error && !status}
		<span class="status-item status-error">ComfyUI status unavailable</span>
	{:else if status}
		<span class="status-item queue" class:active={status.queue.running > 0 || status.queue.pending > 0}>
			Queue: {status.queue.running} running, {status.queue.pending} pending
		</span>
		{#if status.system_stats && (status.system_stats.vram_used_gb != null || status.system_stats.vram_total_gb != null)}
			<span class="status-sep" aria-hidden="true">|</span>
			<span class="status-item vram">
				VRAM {status.system_stats.vram_used_gb ?? '—'}/{status.system_stats.vram_total_gb ?? '—'} GB
			</span>
		{/if}
		{#if status.system_stats?.gpu_percent != null}
			<span class="status-sep" aria-hidden="true">|</span>
			<span class="status-item gpu">GPU {status.system_stats.gpu_percent}%</span>
		{/if}
		{#if status.system_stats?.cpu_percent != null}
			<span class="status-sep" aria-hidden="true">|</span>
			<span class="status-item cpu">CPU {status.system_stats.cpu_percent}%</span>
		{/if}
		{#if status.system_stats?.ram_used_gb != null}
			<span class="status-sep" aria-hidden="true">|</span>
			<span class="status-item ram">RAM {status.system_stats.ram_used_gb} GB</span>
		{/if}
	{:else}
		<span class="status-item status-loading">Queue: —</span>
	{/if}
	<span class="status-sep" aria-hidden="true">|</span>
	<span class="status-item db-size">
		<DbSizeBar
			sizeBytes={dbSizeBytes}
			breakdown={dbBreakdown}
			onVacuumComplete={(bytes) => { dbSizeBytes = bytes; fetchConfig(); }}
		/>
	</span>
</div>

<style>
	.status-bar {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		padding: 0.35rem 1rem;
		font-size: 0.8rem;
		color: var(--muted);
		background: var(--card);
		border-top: 1px solid var(--border);
		min-height: 28px;
	}
	.status-item {
		white-space: nowrap;
	}
	.status-item.queue.active {
		color: var(--accent);
	}
	.status-item.status-error {
		color: var(--warning);
	}
	.status-item.status-warning {
		color: var(--warning);
		font-weight: 500;
	}
	.status-item.status-ok {
		color: var(--accent);
		opacity: 0.9;
	}
	.status-item.status-loading {
		opacity: 0.7;
	}
	.status-sep {
		opacity: 0.5;
		user-select: none;
	}
	.github-link {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		color: inherit;
		text-decoration: none;
		opacity: 0.85;
	}
	.github-link:hover {
		opacity: 1;
		text-decoration: underline;
	}
	.github-icon {
		width: 12px;
		height: 12px;
		flex-shrink: 0;
	}

	.plugin-state {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.plugin-state-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
	}
	.plugin-state-ok {
		background: var(--accent);
		opacity: 0.95;
	}
	.plugin-state-incompatible {
		background: var(--warning);
	}
	.plugin-state-missing {
		background: var(--warning);
		opacity: 0.85;
	}

	@media (max-width: 639px) {
		.status-bar {
			flex-wrap: wrap;
			justify-content: flex-start;
			gap: 0.25rem 0.5rem;
			padding: 0.25rem 0.75rem;
			padding-bottom: calc(0.5rem + env(safe-area-inset-bottom, 0));
			min-height: 28px;
		}
		.status-item {
			white-space: normal;
		}
		.github-link {
			display: none;
		}
		.status-sep:has(+ .github-link) {
			display: none;
		}
		.plugin-state-text {
			display: none;
		}
		.plugin-state-dot {
			width: 10px;
			height: 10px;
		}
	}
</style>
