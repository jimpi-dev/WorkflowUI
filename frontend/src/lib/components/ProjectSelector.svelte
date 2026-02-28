<script lang="ts">
	import { tick } from 'svelte';
	import { getApiBase } from '$lib/config';
	import { activeProject } from '$lib/stores/activeProject';
	import { QUICK_RUNS_PROJECT_ID, QUICK_RUNS_PROJECT_NAME } from '$lib/constants';

	type ProjectItem = { id: string; name: string; slug?: string | null; run_count: number; header_color?: string | null };

	let { onSelect, onCreate }: {
		onSelect?: () => void;
		onCreate?: (id: string, name: string) => void;
	} = $props();

	let projects = $state<ProjectItem[]>([]);
	let loading = $state(true);
	let searchQuery = $state('');
	let createName = $state('');
	let createSlug = $state('');
	let creating = $state(false);
	let error = $state('');
	let justGenerateButton: HTMLButtonElement | undefined = $state();

	const apiBase = getApiBase() || '';

	const filteredProjects = $derived.by(() => {
		const q = searchQuery.trim().toLowerCase();
		if (!q) return projects;
		return projects.filter(
			(p) =>
				p.name.toLowerCase().includes(q) ||
				(p.slug && p.slug.toLowerCase().includes(q))
		);
	});

	async function loadProjects() {
		loading = true;
		error = '';
		try {
			const res = await fetch(`${apiBase}/projects`);
			if (!res.ok) throw new Error(res.statusText);
			projects = await res.json();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load projects';
			projects = [];
		} finally {
			loading = false;
		}
	}

	async function createProject() {
		const name = createName.trim();
		if (!name) {
			error = 'Enter a project name';
			return;
		}
		creating = true;
		error = '';
		try {
			const res = await fetch(`${apiBase}/projects`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name,
					slug: createSlug.trim() || undefined,
					description: null
				})
			});
			const data = await res.json().catch(() => ({}));
			if (!res.ok) {
				error = (data.detail ?? data.message ?? res.statusText) || 'Create failed';
				return;
			}
			activeProject.select(data.id, data.name);
			onCreate?.(data.id, data.name);
			onSelect?.();
			createName = '';
			createSlug = '';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Create failed';
		} finally {
			creating = false;
		}
	}

	function selectExisting(id: string, name: string) {
		activeProject.select(id, name);
		onSelect?.();
	}

	function selectJustGenerate() {
		activeProject.select(QUICK_RUNS_PROJECT_ID, QUICK_RUNS_PROJECT_NAME);
		onSelect?.();
	}

	$effect(() => {
		loadProjects();
	});

	$effect(() => {
		if (!loading && justGenerateButton) {
			tick().then(() => justGenerateButton?.focus());
		}
	});
</script>

<div
	class="project-selector"
	role="dialog"
	aria-modal="true"
	aria-labelledby="project-selector-title"
	aria-describedby="project-selector-desc"
>
	<h2 id="project-selector-title">Select or create a project</h2>
	<p id="project-selector-desc" class="hint">Run without naming a project, or choose one to organize your runs.</p>

	{#if loading}
		<p class="loading" aria-live="polite">Loading projects…</p>
	{:else}
		<div class="just-generate-section">
			<button
				type="button"
				class="just-generate-btn"
				bind:this={justGenerateButton}
				onclick={selectJustGenerate}
				onkeydown={(e) => e.key === 'Enter' && selectJustGenerate()}
				aria-describedby="just-generate-desc"
			>
				<span class="just-generate-label">Just generate</span>
				<span id="just-generate-desc" class="just-generate-desc">No project needed—your runs will appear in Quick runs</span>
			</button>
		</div>

		<div class="divider" aria-hidden="true">
			<span>or pick a project</span>
		</div>

		<div class="project-search-wrap">
			<label for="project-selector-search" class="sr-only">Search projects</label>
			<span class="project-search-icon" aria-hidden="true">
				<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
			</span>
			<input
				id="project-selector-search"
				type="search"
				class="project-search-input"
				placeholder="Search by name or slug…"
				bind:value={searchQuery}
				aria-label="Search projects"
				autocomplete="off"
			/>
		</div>

		<ul class="project-list" role="list">
			{#each filteredProjects as p (p.id)}
				<li class="project-item-wrapper">
					<button
						type="button"
						class="project-item"
						class:quick-runs={p.id === QUICK_RUNS_PROJECT_ID}
						class:has-color={!!p.header_color}
						onclick={() => selectExisting(p.id, p.name)}
						aria-label="{p.name}, {p.run_count ?? 0} runs"
						style={p.header_color ? `--project-color: ${p.header_color}` : ''}
					>
						{#if p.header_color}
							<span class="project-color-bar" aria-hidden="true"></span>
						{:else}
							<span class="project-color-bar project-color-bar-neutral" aria-hidden="true"></span>
						{/if}
						<span class="project-item-content">
							<span class="project-name">{p.name}</span>
							<span class="project-meta">{p.run_count ?? 0} runs</span>
						</span>
					</button>
				</li>
			{/each}
		</ul>
		{#if searchQuery.trim() && filteredProjects.length === 0}
			<p class="project-search-empty" role="status">No projects match "{searchQuery.trim()}"</p>
		{/if}

		<div class="create-section">
			<h3>Create new project</h3>
			<div class="create-form">
				<input
					type="text"
					placeholder="Project name"
					bind:value={createName}
					disabled={creating}
					aria-label="Project name"
				/>
				<input
					type="text"
					placeholder="Slug (optional)"
					bind:value={createSlug}
					disabled={creating}
					aria-label="Slug"
				/>
				<button type="button" onclick={createProject} disabled={creating}>
					{creating ? 'Creating…' : 'Create'}
				</button>
			</div>
		</div>
	{/if}

	{#if error}
		<p class="error">{error}</p>
	{/if}
</div>

<style>
	.project-selector {
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg, 12px);
		padding: 1.5rem;
		max-width: 480px;
		width: 100%;
		box-shadow: var(--shadow-md, 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1));
	}
	@media (max-width: 639px) {
		.project-selector {
			width: calc(100vw - 2rem);
			max-width: none;
			max-height: 85vh;
			overflow-y: auto;
		}
	}
	.project-selector h2 {
		margin: 0 0 0.25rem 0;
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--text);
	}
	.hint {
		margin: 0 0 1rem 0;
		color: var(--muted);
		font-size: 0.9rem;
	}
	.loading {
		margin: 1rem 0;
		color: var(--muted);
	}
	.just-generate-section {
		margin-bottom: 1.25rem;
	}
	.just-generate-btn {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.25rem;
		width: 100%;
		padding: 1rem 1.25rem;
		background: var(--accent);
		color: var(--accent-contrast, #fff);
		border: none;
		border-radius: 8px;
		cursor: pointer;
		font: inherit;
		font-weight: 600;
		text-align: left;
		transition: filter 0.15s ease, transform 0.1s ease;
	}
	.just-generate-btn:hover {
		filter: brightness(1.08);
	}
	.just-generate-btn:focus-visible {
		outline: 2px solid var(--accent-contrast, #fff);
		outline-offset: 2px;
	}
	.just-generate-btn:active {
		transform: scale(0.99);
	}
	.just-generate-label {
		font-size: 1.05rem;
	}
	.just-generate-desc {
		font-size: 0.85rem;
		font-weight: 400;
		opacity: 0.92;
	}
	.divider {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.divider::before,
	.divider::after {
		content: '';
		flex: 1;
		height: 1px;
		background: var(--border);
	}
	.project-search-wrap {
		position: relative;
		margin-bottom: 0.75rem;
	}
	.project-search-icon {
		position: absolute;
		left: 0.75rem;
		top: 50%;
		transform: translateY(-50%);
		width: 1.1rem;
		height: 1.1rem;
		color: var(--muted);
		pointer-events: none;
	}
	.project-search-icon svg {
		width: 100%;
		height: 100%;
		display: block;
	}
	.project-search-input {
		width: 100%;
		padding: 0.6rem 0.75rem 0.6rem 2.5rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text);
		font: inherit;
		font-size: 0.95rem;
		transition: border-color 0.2s ease, box-shadow 0.2s ease;
	}
	.project-search-input::placeholder {
		color: var(--muted);
	}
	.project-search-input:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 2px var(--accent-soft);
	}
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}
	.project-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 1.25rem;
		max-height: 340px;
		min-height: 200px;
		overflow-y: auto;
		list-style: none;
		padding: 0;
		margin: 0;
		scrollbar-gutter: stable;
	}
	.project-item-wrapper {
		display: block;
	}
	.project-item {
		display: flex;
		align-items: stretch;
		width: 100%;
		min-height: 52px;
		padding: 0;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		cursor: pointer;
		text-align: left;
		color: inherit;
		font: inherit;
		transition: background 0.2s ease, border-color 0.2s ease;
	}
	.project-item:hover {
		background: color-mix(in srgb, var(--accent) 8%, var(--surface));
		border-color: var(--accent);
	}
	.project-item.quick-runs {
		border-color: var(--accent);
		background: var(--accent-soft);
	}
	.project-item.has-color .project-color-bar {
		background: var(--project-color);
	}
	.project-color-bar {
		width: 4px;
		flex-shrink: 0;
		border-radius: 8px 0 0 8px;
		background: var(--project-color, transparent);
	}
	.project-color-bar-neutral {
		background: var(--muted);
		opacity: 0.4;
	}
	.project-item-content {
		display: flex;
		justify-content: space-between;
		align-items: center;
		flex: 1;
		padding: 0.75rem 1rem;
		gap: 0.75rem;
		min-width: 0;
	}
	.project-name {
		font-weight: 500;
		color: var(--text);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.project-meta {
		font-size: 0.85rem;
		color: var(--muted);
		flex-shrink: 0;
	}
	.project-search-empty {
		margin: -0.5rem 0 1rem 0;
		padding: 0.5rem 0;
		font-size: 0.9rem;
		color: var(--muted);
	}
	.create-section {
		margin-top: 10px;
	}
	.create-section h3 {
		margin: 0 0 0.5rem 0;
		font-size: 0.95rem;
		color: var(--muted);
	}
	.create-form {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.create-form input {
		padding: 0.5rem 0.75rem;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--surface);
		color: var(--text);
		font: inherit;
	}
	.create-form button {
		padding: 0.5rem 1rem;
		background: var(--accent);
		color: var(--accent-contrast, #fff);
		border: none;
		border-radius: 6px;
		cursor: pointer;
		font-weight: 500;
		font: inherit;
	}
	.create-form button:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}
	.error {
		margin: 0.75rem 0 0 0;
		color: var(--warning, #e55);
		font-size: 0.9rem;
	}
</style>
