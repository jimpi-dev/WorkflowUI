<script lang="ts">
	import { getApiBase } from '$lib/config';
	import { projectRunsInvalidate } from '$lib/stores/projectRunsInvalidate';

	let { projectId, projectName, returnPath = '' }: { projectId: string; projectName: string; returnPath?: string } = $props();

	const projectHref = $derived(
		'/projects/' + projectId + (returnPath ? '?from=' + encodeURIComponent(returnPath) : '')
	);

	const apiBase = getApiBase() || '';

	let detail = $state<{
		name: string;
		run_count: number;
		created_at: number;
		apps_used: { title: string }[];
	} | null>(null);
	let loading = $state(true);

	function refetch(id: string) {
		loading = true;
		fetch(`${apiBase}/projects/${id}`)
			.then((r) => (r.ok ? r.json() : null))
			.then((d) => {
				detail = d;
			})
			.catch(() => {
				detail = null;
			})
			.finally(() => {
				loading = false;
			});
	}

	$effect(() => {
		const id = projectId;
		if (!id) {
			detail = null;
			loading = false;
			return;
		}
		refetch(id);
	});

	$effect(() => {
		const id = projectId;
		if (!id) return;
		const unsub = projectRunsInvalidate.subscribe((inv) => {
			if (inv.projectId === id) refetch(id);
		});
		return unsub;
	});
</script>

<a href={projectHref} class="project-console" title="Open project">
	<div class="console-title">─ project ─</div>
	<div class="console-body">
		{#if loading}
			<div class="console-line"><span class="console-prompt">$</span><span class="console-muted"> loading...</span></div>
		{:else if detail}
			<div class="console-line"><span class="console-label">name</span><span class="console-sep">:</span> <span class="console-value">{detail.name}</span></div>
			<div class="console-line"><span class="console-label">runs</span><span class="console-sep">:</span> <span class="console-value">{detail.run_count}</span></div>
			<div class="console-line"><span class="console-label">created</span><span class="console-sep">:</span> <span class="console-value">{new Date(detail.created_at).toLocaleDateString()}</span></div>
			{#if detail.apps_used?.length > 0}
				<div class="console-line"><span class="console-label">apps</span><span class="console-sep">:</span> <span class="console-value">{detail.apps_used.length}</span></div>
			{/if}
			<div class="console-line console-prompt">$</div>
		{:else}
			<div class="console-line"><span class="console-value">{projectName}</span></div>
			<div class="console-line console-prompt">$</div>
		{/if}
	</div>
</a>

<style>
	.project-console {
		display: block;
		text-decoration: none;
		color: inherit;
		flex-shrink: 0;
		margin-left: 0.75rem;
		align-self: center;
		width: 220px;
	}
	.console-title {
		font-family: ui-monospace, 'Cascadia Code', 'Fira Code', 'SF Mono', Consolas, monospace;
		font-size: 0.7rem;
		letter-spacing: 0.05em;
		color: var(--accent);
		border: 1px solid var(--border);
		border-bottom: none;
		padding: 0.2rem 0.5rem;
		background: var(--accent-soft);
		border-radius: 6px 6px 0 0;
	}
	.console-body {
		font-family: ui-monospace, 'Cascadia Code', 'Fira Code', 'SF Mono', Consolas, monospace;
		font-size: 0.72rem;
		line-height: 1.45;
		padding: 0.5rem 0.75rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 0 0 6px 6px;
		box-shadow: var(--shadow-md);
		width: 100%;
		box-sizing: border-box;
	}
	.console-line {
		display: block;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.console-prompt {
		color: var(--accent);
	}
	.console-label {
		color: var(--accent);
	}
	.console-sep {
		color: var(--muted);
		margin-right: 0.25rem;
	}
	.console-value {
		color: var(--text);
	}
	.console-muted {
		color: var(--muted);
	}
	.project-console:hover .console-title {
		border-color: color-mix(in srgb, var(--accent) 50%, var(--border));
	}
	.project-console:hover .console-body {
		border-color: color-mix(in srgb, var(--accent) 40%, var(--border));
	}
</style>
