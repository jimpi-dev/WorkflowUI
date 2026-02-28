<script lang="ts">
	import '../../app.css';
	import { getApiBase } from '$lib/config';
	import { activeProject } from '$lib/stores/activeProject';
	import { projectRunsInvalidate } from '$lib/stores/projectRunsInvalidate';
	import { headerAppContext } from '$lib/stores/headerAppContext';
	import { QUICK_RUNS_PROJECT_ID, QUICK_RUNS_PROJECT_NAME } from '$lib/constants';
	import ProjectSelector from '$lib/components/ProjectSelector.svelte';
	import { appBooting } from '$lib/stores/appBooting';
	import { projectSelectorOpen } from '$lib/stores/projectSelectorOpen';
	let { data, children } = $props();

	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	let currentProject = $state<{ id: string; name: string } | null>(null);
	let projectDetail = $state<{ name: string; run_count: number; created_at: number } | null>(null);
	$effect(() => {
		const unsub = activeProject.subscribe((v) => (currentProject = v));
		return unsub;
	});
	$effect(() => {
		if (!browser || !data.workflowId) return;
		const id = requestAnimationFrame(() => {
			appBooting.set(false);
		});
		return () => cancelAnimationFrame(id);
	});

	// URL drives project context: ?project=id → that project. Do not auto-select Quick runs so the project selector can show when no choice exists.
	$effect(() => {
		const fromUrl = data.projectFromUrl;
		if (fromUrl?.id && fromUrl?.name) {
			activeProject.select(fromUrl.id, fromUrl.name);
		}
	});
	// Sync active project to URL so /app/[id] shows ?project=id (skip for Legacy and Quick runs—no project in URL)
	$effect(() => {
		if (!browser || !data.workflowId || !currentProject || currentProject.id === QUICK_RUNS_PROJECT_ID) return;
		const projectInUrl = $page.url.searchParams.get('project');
		if (projectInUrl === currentProject.id) return;
		const params = new URLSearchParams($page.url.searchParams);
		params.set('project', currentProject.id);
		const newUrl = $page.url.pathname + '?' + params.toString();
		goto(newUrl, { replaceState: true, noScroll: true });
	});
	// Show selector when user has not chosen a project yet, or when "Switch project" was clicked in header
	let projectSelectorOpenValue = $state(false);
	$effect(() => {
		const unsub = projectSelectorOpen.subscribe((v) => (projectSelectorOpenValue = v));
		return unsub;
	});
	let showProjectSelector = $derived(browser && (currentProject === null || projectSelectorOpenValue));

	// Sync shared header with app context (app name + project + header color) for the single AppHeader in root layout
	$effect(() => {
		const workflowId = data.workflowId ?? null;
		const current = workflowId ? data.workflows?.find((w) => w.id === workflowId) : null;
		const displayName = workflowId
			? (data.appTitle ?? current?.label ?? workflowId)
			: null;
		headerAppContext.update((prev) => ({
			...prev,
			workflowId,
			displayName,
			headerColor: data.appHeaderColor ?? null,
			appId: data.appId ?? null,
			projectId: currentProject?.id ?? null,
			projectName: currentProject?.name ?? null,
			projectHeaderColor: data.projectHeaderColor ?? null,
			projectDetail: projectDetail ?? null
		}));
	});

	function refetchProjectDetail(id: string) {
		const apiBase = getApiBase() || '';
		fetch(`${apiBase}/projects/${id}`)
			.then((r) => (r.ok ? r.json() : null))
			.then((d) => {
				projectDetail = d ? { name: d.name, run_count: d.run_count ?? 0, created_at: d.created_at } : null;
			})
			.catch(() => {
				projectDetail = null;
			});
	}

	// Fetch project detail for metadata in bracket when project is selected (skip for Quick runs)
	$effect(() => {
		const id = currentProject?.id;
		if (!id || id === QUICK_RUNS_PROJECT_ID) {
			projectDetail = null;
			return;
		}
		refetchProjectDetail(id);
	});

	// Refetch when a run completes so run_count in bracket stays in sync
	$effect(() => {
		const id = currentProject?.id;
		if (!id) return;
		const unsub = projectRunsInvalidate.subscribe((inv) => {
			if (inv.projectId === id) refetchProjectDetail(id);
		});
		return unsub;
	});
</script>

<div class="app-route-wrapper">
	<main class="app-main-inner">
		{#if showProjectSelector}
			<div class="project-selector-overlay">
				<ProjectSelector onSelect={() => projectSelectorOpen.set(false)} />
			</div>
		{:else}
			{@render children()}
		{/if}
	</main>
</div>

<style>
	.app-route-wrapper {
		display: flex;
		flex-direction: column;
		flex: 1;
		min-height: 0;
	}

	.app-main-inner {
		flex: 1;
		min-height: 0;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}

	.app-main-inner > :global(.page) {
		flex: 1;
		min-height: 0;
		overflow: hidden;
	}

	.project-selector-overlay {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 40vh;
		padding: 2rem;
		background: color-mix(in srgb, var(--bg, #0d0d0d) 85%, transparent);
	}
</style>
