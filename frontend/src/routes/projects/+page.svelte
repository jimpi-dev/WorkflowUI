<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { get } from 'svelte/store';
	import { goto, invalidate } from '$app/navigation';
	import { page } from '$app/stores';
	import { browser } from '$app/environment';
	import { getApiBase } from '$lib/config';
	import { quickRunsProject } from '$lib/stores/quickRunsProject';
	import { getContrastForeground } from '$lib/utils/color';
	import DeleteProjectDialog from '$lib/components/DeleteProjectDialog.svelte';
	import type { ProjectSummary } from './+page';

	const DEFAULT_PROJECT_NAME = 'Untitled project';

	let { data } = $props();
	let creating = $state(false);
	const showArchive = $derived(data.showArchive ?? false);

	onMount(() => {
		invalidate(get(page).url);
	});
	let dialogOpen = $state(false);
	let newProjectName = $state('');
	let newProjectHeaderColor = $state<string | null>(null);

	let projectsTabEl = $state<HTMLButtonElement | null>(null);
	let archiveTabEl = $state<HTMLButtonElement | null>(null);
	let prevShowArchive = $state<boolean | undefined>(undefined);
	$effect(() => {
		if (!browser) return;
		const cur = showArchive;
		if (prevShowArchive !== undefined && prevShowArchive !== cur) {
			tick().then(() => {
				if (cur && archiveTabEl) archiveTabEl.focus();
				else if (!cur && projectsTabEl) projectsTabEl.focus();
			});
		}
		prevShowArchive = cur;
	});

	let deleteDialogOpen = $state(false);
	let deleteDialogProject = $state<ProjectSummary | null>(null);
	let unarchivingId = $state<string | null>(null);

	function openDeleteDialog(p: ProjectSummary, e: MouseEvent) {
		e.preventDefault();
		e.stopPropagation();
		deleteDialogProject = p;
		deleteDialogOpen = true;
	}

	function closeDeleteDialog() {
		deleteDialogOpen = false;
		deleteDialogProject = null;
	}

	function onDeleteSuccess() {
		invalidate('app:projects');
		goto('/projects');
	}

	async function unarchiveProject(p: ProjectSummary, e: MouseEvent) {
		e.preventDefault();
		e.stopPropagation();
		if (unarchivingId) return;
		unarchivingId = p.id;
		const base = getApiBase() || '';
		try {
			const res = await fetch(`${base}/projects/${p.id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ archived_at: null }),
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				alert(err?.detail ?? 'Failed to unarchive');
				return;
			}
			invalidate('app:projects');
			goto('/projects');
		} finally {
			unarchivingId = null;
		}
	}

	function openNewProjectDialog() {
		newProjectName = '';
		dialogOpen = true;
	}

	function closeNewProjectDialog() {
		dialogOpen = false;
		newProjectName = '';
		newProjectHeaderColor = null;
	}

	async function createProject(name: string) {
		if (creating) return;
		
		const headerColor = newProjectHeaderColor;
		creating = true;
		closeNewProjectDialog();
		try {
			const base = getApiBase() || '';
			const res = await fetch(`${base}/projects`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: name.trim() || DEFAULT_PROJECT_NAME,
					description: '',
					header_color: headerColor ?? undefined
				})
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				alert(err?.detail ?? 'Failed to create project');
				return;
			}
			const project = await res.json();
			goto(`/projects/${project.id}`);
		} finally {
			creating = false;
		}
	}

	function handleCreateWithName() {
		createProject(newProjectName.trim() || DEFAULT_PROJECT_NAME);
	}

	function handleSkipName() {
		createProject(DEFAULT_PROJECT_NAME);
	}

	type SortKey = 'updated' | 'name' | 'created' | 'runs';
	const sortOptions: { value: SortKey; label: string }[] = [
		{ value: 'updated', label: 'Last used' },
		{ value: 'name', label: 'Name A–Z' },
		{ value: 'created', label: 'Newest first' },
		{ value: 'runs', label: 'Most runs' },
	];

	let search = $state('');
	let sortBy = $state<SortKey>('updated');
	let tagFilters = $state<string[]>([]);
	let viewMode = $state<'grid' | 'list'>('grid');
	let isMobile = $state(browser && typeof window !== 'undefined' ? window.matchMedia('(max-width: 639px)').matches : false);

	function setViewMode(mode: 'grid' | 'list') {
		viewMode = mode;
	}

	function setColorFilter(value: string) {
		colorFilter = value;
	}

	function formatRelativeTime(ms: number): string {
		const d = new Date(ms);
		const now = Date.now();
		const diff = now - d.getTime();
		const sec = Math.floor(diff / 1000);
		const min = Math.floor(sec / 60);
		const hr = Math.floor(min / 60);
		const day = Math.floor(hr / 24);
		if (day >= 7) return d.toLocaleDateString();
		if (day >= 1) return `${day}d ago`;
		if (hr >= 1) return `${hr}h ago`;
		if (min >= 1) return `${min}m ago`;
		if (sec >= 10) return `${sec}s ago`;
		return 'Just now';
	}

	function matchesSearch(p: ProjectSummary): boolean {
		if (!search.trim()) return true;
		const q = search.trim().toLowerCase();
		const name = (p.name ?? '').toLowerCase();
		const desc = (p.description ?? '').toLowerCase();
		const tags = (p.tags ?? []).join(' ').toLowerCase();
		return name.includes(q) || desc.includes(q) || tags.includes(q);
	}

	const allTags = $derived(
		Array.from(
			new Set(
				(data.projects ?? [])
					.flatMap((p) => p.tags ?? [])
					.map((t) => (t ?? '').trim().toLowerCase())
					.filter(Boolean)
			)
		).sort()
	);

	function matchesTagFilter(p: ProjectSummary): boolean {
		if (!tagFilters.length) return true;
		const projTags = (p.tags ?? []).map((t) => (t ?? '').trim().toLowerCase());
		if (!projTags.length) return false;
		return tagFilters.some((t) => projTags.includes(t));
	}

	let tagFilterOpen = $state(false);

	$effect(() => {
		if (!tagFilterOpen) return;
		const onClick = (e: MouseEvent) => {
			if (!(e.target as Element).closest('.tag-filter')) {
				tagFilterOpen = false;
			}
		};
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				tagFilterOpen = false;
			}
		};
		document.addEventListener('click', onClick);
		document.addEventListener('keydown', onKey);
		return () => {
			document.removeEventListener('click', onClick);
			document.removeEventListener('keydown', onKey);
		};
	});

	const filtered = $derived(
		data.projects.filter((p) => matchesSearch(p) && matchesTagFilter(p))
	);

	const sorted = $derived.by(() => {
		const list = [...filtered];
		switch (sortBy) {
			case 'name':
				list.sort((a, b) => (a.name ?? '').localeCompare(b.name ?? ''));
				break;
			case 'created':
				list.sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0));
				break;
			case 'runs':
				list.sort((a, b) => (b.run_count ?? 0) - (a.run_count ?? 0));
				break;
			default:
				list.sort((a, b) => (b.updated_at ?? b.created_at ?? 0) - (a.updated_at ?? a.created_at ?? 0));
				break;
		}
		const quickIdx = list.findIndex((p) => p.id === $quickRunsProject.id);
		if (quickIdx > 0) {
			const [quick] = list.splice(quickIdx, 1);
			list.unshift(quick);
		}
		return list;
	});
</script>

<div class="projects-page">
	<header class="page-header">
		<div class="header-top">
			<h1>Projects</h1>
			<p class="subtitle">Browse and open your run collections. Sorted by last used.</p>
		</div>
		<div class="tabs" role="tablist" aria-label="Projects or Archive">
			<button
				type="button"
				role="tab"
				class="tab-btn"
				class:active={!showArchive}
				aria-selected={!showArchive}
				bind:this={projectsTabEl}
				onclick={() => goto('/projects')}
			>
				<svg class="tab-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
					<path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
				</svg>
				<span class="tab-label">Projects</span>
				<span class="tab-count" aria-label="{data.activeCount} active projects">{data.activeCount}</span>
			</button>
			<button
				type="button"
				role="tab"
				class="tab-btn"
				class:active={showArchive}
				aria-selected={showArchive}
				bind:this={archiveTabEl}
				onclick={() => goto('/projects?tab=archive')}
			>
				<svg class="tab-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
					<path d="M21 8v13H3V8"/><path d="M1 3h22v5H1z"/><path d="M10 12h4"/>
				</svg>
				<span class="tab-label">Archive</span>
				<span class="tab-count" aria-label="{data.archiveCount} archived projects">{data.archiveCount}</span>
			</button>
		</div>
		<div class="toolbar">
			<button type="button" class="create-project-btn" disabled={creating} onclick={openNewProjectDialog}>
				Start a new project
			</button>
			<div class="search-wrap">
				<svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
					<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
				</svg>
				<input
					type="search"
					placeholder="Search projects…"
					bind:value={search}
					class="search-input"
					aria-label="Search projects"
				/>
			</div>
			<details class="filters-more" open={!isMobile}>
				<summary>
					<span>Filters / More</span>
					<svg class="filters-more-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
						<path d="M6 9l6 6 6-6" />
					</svg>
				</summary>
				<div class="filters-more-content">
					<select class="sort-select" bind:value={sortBy} aria-label="Sort by">
						{#each sortOptions as opt}
							<option value={opt.value}>{opt.label}</option>
						{/each}
					</select>
					<div class="tag-filter">
						<button
							type="button"
							class="tag-filter-trigger"
							onclick={() => (tagFilterOpen = !tagFilterOpen)}
							aria-haspopup="listbox"
							aria-expanded={tagFilterOpen}
							id="tag-filter-trigger"
						>
							<span class="tag-filter-trigger-main">
								{#if !tagFilters.length}
									<span class="tag-filter-summary-text">All tags</span>
								{:else}
									<span class="tag-filter-summary-text">
										{tagFilters.length === 1 ? '1 tag' : `${tagFilters.length} tags`}
									</span>
									<span class="tag-filter-summary-chips" aria-hidden="true">
										{#each tagFilters.slice(0, 3) as tag (tag)}
											<span class="tag-chip tag-chip-small">{tag}</span>
										{/each}
										{#if tagFilters.length > 3}
											<span class="tag-chip tag-chip-more">+{tagFilters.length - 3}</span>
										{/if}
									</span>
								{/if}
							</span>
							<svg class="tag-filter-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
								<path d="M6 9l6 6 6-6"/>
							</svg>
						</button>
						{#if tagFilterOpen}
							<div
								class="tag-filter-menu"
								role="listbox"
								aria-multiselectable="true"
								aria-label="Filter projects by tag"
							>
								<button
									type="button"
									class="tag-filter-option"
									role="option"
									aria-selected={!tagFilters.length}
									onclick={() => (tagFilters = [])}
								>
									<span class="tag-filter-checkbox" aria-hidden="true">
										{#if !tagFilters.length}
											<span class="tag-filter-checkbox-inner"></span>
										{/if}
									</span>
									<span class="tag-filter-option-text">
										<span class="tag-filter-option-label">All tags</span>
									</span>
								</button>
								{#each allTags as tag (tag)}
									<button
										type="button"
										class="tag-filter-option"
										role="option"
										aria-selected={tagFilters.includes(tag)}
										onclick={() => {
											const set = new Set(tagFilters);
											if (set.has(tag)) set.delete(tag); else set.add(tag);
											tagFilters = Array.from(set);
										}}
									>
										<span class="tag-filter-checkbox" aria-hidden="true">
											{#if tagFilters.includes(tag)}
												<span class="tag-filter-checkbox-inner"></span>
											{/if}
										</span>
										<span class="tag-filter-option-text">
											<span class="tag-filter-option-label">{tag}</span>
										</span>
									</button>
								{/each}
							</div>
						{/if}
					</div>
				</div>
			</details>
			<div class="view-toggle" role="tablist" aria-label="View">
				<button
					type="button"
					class="view-btn"
					class:active={viewMode === 'grid'}
					onclick={(e) => { e.preventDefault(); e.stopPropagation(); setViewMode('grid'); }}
					aria-pressed={viewMode === 'grid'}
					aria-label="Grid view"
				>
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
				</button>
				<button
					type="button"
					class="view-btn"
					class:active={viewMode === 'list'}
					onclick={(e) => { e.preventDefault(); e.stopPropagation(); setViewMode('list'); }}
					aria-pressed={viewMode === 'list'}
					aria-label="List view"
				>
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
				</button>
			</div>
		</div>
	</header>

	{#if sorted.length === 0}
		<div class="empty-state">
			<div class="empty-icon" aria-hidden="true">
				<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
					<path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
				</svg>
			</div>
			<h2>{data.projects.length === 0 ? (showArchive ? 'No archived projects' : 'No projects yet') : 'No matching projects'}</h2>
			<p class="empty-desc">
				{#if data.projects.length === 0}
					{showArchive ? 'Archive a project from the Projects tab to see it here.' : 'Create a project from an app when you run a workflow. Open the app and choose or create a project there.'}
				{:else}
					Try a different search or sort.
				{/if}
			</p>
			{#if data.projects.length === 0 && !showArchive}
				<button type="button" onclick={() => goto('/app')}>Open App</button>
			{/if}
		</div>
	{:else}
		<div class="projects-scroll-wrap">
			<div class="projects-container" class:list-view={viewMode === 'list'}>
			{#each sorted as p (p.id)}
				<a href="/projects/{p.id}" class="project-card" class:quick-runs-card={p.id === $quickRunsProject.id}>
					<div
						class="card-visual"
						class:header-contrast-light={p.header_color && getContrastForeground(p.header_color) === 'light'}
						class:header-contrast-dark={p.header_color && getContrastForeground(p.header_color) === 'dark'}
						style={p.header_color
							? `--header-color: ${p.header_color}; background: linear-gradient(135deg, ${p.header_color} 0%, color-mix(in srgb, ${p.header_color} 75%, black) 100%);`
							: ''}
					>
						<span class="card-run-badge">{p.run_count} run{p.run_count === 1 ? '' : 's'}</span>
						{#if p.id === $quickRunsProject.id}
							<span class="card-quick-badge" aria-label="Default for Just generate">Just generate</span>
						{/if}
						<div class="card-actions-visual" role="presentation" tabindex="-1" onclick={(e) => (e.preventDefault(), e.stopPropagation())} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); } }}>
							{#if showArchive}
								<button
									type="button"
									class="card-action-btn unarchive-btn"
									title="Restore to Projects"
									disabled={unarchivingId === p.id}
									onclick={(ev) => unarchiveProject(p, ev)}
								>
									{unarchivingId === p.id ? '…' : 'Unarchive'}
								</button>
							{:else if p.id !== $quickRunsProject.id}
								<button
									type="button"
									class="card-action-btn delete-btn"
									title="Delete or archive project"
									onclick={(ev) => openDeleteDialog(p, ev)}
								>
									Delete / Archive
								</button>
							{/if}
						</div>
					</div>
					<div class="card-body" class:list-body={viewMode === 'list'}>
						{#if viewMode === 'list'}
							<div class="list-row">
								<span class="list-run-badge">{p.run_count ?? 0} run{(p.run_count ?? 0) === 1 ? '' : 's'}</span>
								{#if p.id === $quickRunsProject.id}
									<span class="card-quick-badge list-quick-badge" aria-label="Default for Just generate">Just generate</span>
								{/if}
								<h3 class="project-name list-name">{p.name ?? ''}</h3>
								<span class="list-slug-desc">{#if p.description}{p.description}{:else}—{/if}</span>
								{#if p.tags?.length}
									<div class="project-tags list-tags">
										{#each p.tags.slice(0, 4) as tag (tag)}
											<span class="tag-chip tag-chip-small">{tag}</span>
										{/each}
										{#if (p.tags?.length ?? 0) > 4}
											<span class="tag-chip tag-chip-more">+{(p.tags?.length ?? 0) - 4}</span>
										{/if}
									</div>
								{/if}
								<div class="list-right-group">
									{#if showArchive}
										<button
											type="button"
											class="list-action-btn unarchive-btn"
											title="Restore to Projects"
											disabled={unarchivingId === p.id}
											onclick={(ev) => unarchiveProject(p, ev)}
										>
											{unarchivingId === p.id ? '…' : 'Unarchive'}
										</button>
									{:else if p.id !== $quickRunsProject.id}
										<button
											type="button"
											class="list-action-btn delete-btn"
											title="Delete or archive project"
											onclick={(ev) => openDeleteDialog(p, ev)}
										>
											Delete / Archive
										</button>
									{/if}
									<div class="date-infobox date-infobox-list" role="group" aria-label="Dates">
										<span class="date-infobox-inline">
											<span class="date-infobox-label">Last used</span>
											<span class="date-infobox-value">{formatRelativeTime(p.updated_at ?? p.created_at ?? 0)}</span>
										</span>
										<span class="date-infobox-sep" aria-hidden="true">·</span>
										<span class="date-infobox-inline">
											<span class="date-infobox-label">Created</span>
											<span class="date-infobox-value">{p.created_at != null ? new Date(p.created_at).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '—'}</span>
										</span>
									</div>
								</div>
							</div>
						{:else}
							<h3 class="project-name">{p.name}</h3>
							{#if p.description}
								<p class="project-desc">{p.description}</p>
							{/if}
							<div class="project-meta">
								<span class="meta-item" title="Last used">
									<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
									{formatRelativeTime(p.updated_at ?? p.created_at ?? 0)}
								</span>
								<span class="meta-item">Created {p.created_at != null ? new Date(p.created_at).toLocaleDateString() : '—'}</span>
							</div>
							{#if p.tags?.length}
								<div class="project-tags">
									{#each p.tags.slice(0, 4) as tag (tag)}
										<span class="tag-chip tag-chip-small">{tag}</span>
									{/each}
									{#if (p.tags?.length ?? 0) > 4}
										<span class="tag-chip tag-chip-more">+{(p.tags?.length ?? 0) - 4}</span>
									{/if}
								</div>
							{/if}
						{/if}
					</div>
				</a>
			{/each}
			</div>
		</div>
	{/if}

	{#if dialogOpen}
		<div class="dialog-backdrop" role="dialog" aria-modal="true" aria-labelledby="new-project-dialog-title" tabindex="-1" onclick={closeNewProjectDialog} onkeydown={(e) => { if (e.key === 'Escape') closeNewProjectDialog(); }}>
			<div class="dialog-box" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
				<h2 id="new-project-dialog-title" class="dialog-title">New project</h2>
				<p class="dialog-desc">Give your project a name, or skip to name it later.</p>
				<label class="dialog-label">
					<span class="dialog-label-text">Project name</span>
					<input
						type="text"
						class="dialog-input"
						placeholder="Project name (optional)"
						bind:value={newProjectName}
						onkeydown={(e) => {
							if (e.key === 'Enter') handleCreateWithName();
							if (e.key === 'Escape') closeNewProjectDialog();
						}}
					/>
				</label>
				<label class="dialog-label">
					<span class="dialog-label-text">Header color</span>
					<div class="header-color-wrap">
						<input
							type="color"
							class="header-color-input"
							value={newProjectHeaderColor ?? '#6d5dfc'}
							oninput={(e) => (newProjectHeaderColor = (e.currentTarget as HTMLInputElement).value)}
							aria-label="Header color"
						/>
						{#if newProjectHeaderColor}
							<button type="button" class="header-color-clear" onclick={() => (newProjectHeaderColor = null)}>Clear</button>
						{/if}
					</div>
				</label>
				<div class="dialog-actions">
					<button type="button" class="dialog-btn secondary" onclick={closeNewProjectDialog}>Cancel</button>
					<button type="button" class="dialog-btn secondary" onclick={handleSkipName}>Skip</button>
					<button type="button" class="dialog-btn primary" onclick={handleCreateWithName}>Create</button>
				</div>
			</div>
		</div>
	{/if}

	{#if deleteDialogProject}
		<DeleteProjectDialog
			open={deleteDialogOpen}
			projectId={deleteDialogProject.id}
			projectName={deleteDialogProject.name ?? ''}
			onClose={closeDeleteDialog}
			onSuccess={onDeleteSuccess}
		/>
	{/if}
</div>

<style>
	.projects-page {
		display: flex;
		flex-direction: column;
		padding: 1.25rem 1.5rem;
		max-width: 1400px;
		margin: 0 auto;
		width: 100%;
		min-height: min-content;
	}

	.page-header {
		flex-shrink: 0;
		margin-bottom: 1.25rem;
		background: var(--bg);
		padding-bottom: 0.25rem;
	}

	.header-top h1 {
		margin: 0 0 0.25rem 0;
		font-size: 1.6rem;
		font-weight: 600;
		letter-spacing: -0.02em;
		color: var(--text);
	}

	.subtitle {
		margin: 0;
		font-size: 0.9rem;
		color: var(--muted);
	}

	.tabs {
		display: inline-flex;
		gap: 0;
		margin-top: 1.25rem;
		margin-bottom: 0.75rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 10px;
		overflow: hidden;
		box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
	}
	.tab-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 1rem;
		font-size: 0.9rem;
		font-weight: 500;
		background: transparent;
		border: none;
		border-radius: 0;
		color: var(--muted);
		cursor: pointer;
		transition: background 0.2s ease, color 0.2s ease;
		border-right: 1px solid var(--border);
	}
	.tab-btn:last-child {
		border-right: none;
	}
	.tab-btn:hover {
		color: var(--text);
		background: color-mix(in srgb, var(--accent) 8%, transparent);
	}
	.tab-btn.active {
		color: var(--accent);
		background: var(--accent-soft);
		font-weight: 600;
		box-shadow: inset 0 -2px 0 0 var(--accent);
	}
	.tab-btn .tab-icon {
		flex-shrink: 0;
		opacity: 0.9;
	}
	.tab-btn .tab-label {
		letter-spacing: -0.01em;
	}
	.tab-btn .tab-count {
		font-variant-numeric: tabular-nums;
		font-size: 0.8rem;
		font-weight: 600;
		min-width: 1.5em;
		text-align: center;
		padding: 0.15rem 0.45rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--muted) 25%, transparent);
		color: var(--muted);
	}
	.tab-btn.active .tab-count {
		background: color-mix(in srgb, var(--accent) 22%, var(--card));
		color: var(--accent);
	}
	.tab-btn:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.toolbar {
		flex-shrink: 0;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem;
		margin-top: 1rem;
	}

	.filters-more {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.filters-more > summary {
		list-style: none;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		width: 100%;
		min-height: 44px;
		padding: 0.45rem 0.6rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text);
		font-size: 0.85rem;
		font-weight: 600;
	}
	.filters-more > summary::-webkit-details-marker {
		display: none;
	}
	.filters-more[open] > summary {
		display: none;
	}
	.filters-more-content {
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: nowrap;
	}
	.filters-more[open] .sort-select,
	.filters-more[open] .tag-filter {
		flex: 1 1 0;
		min-width: 0;
	}
	.filters-more-chevron {
		opacity: 0.75;
	}

	.create-project-btn {
		padding: 0.5rem 1rem;
		background: var(--accent);
		color: var(--accent-fg, #fff);
		border: 1px solid var(--accent);
		border-radius: 8px;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
		transition: opacity 0.2s, filter 0.2s;
	}
	.create-project-btn:hover:not(:disabled) {
		filter: brightness(1.1);
	}
	.create-project-btn:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.search-wrap {
		position: relative;
		flex: 1;
		min-width: 200px;
		max-width: 320px;
	}

	.search-icon {
		position: absolute;
		left: 0.75rem;
		top: 50%;
		transform: translateY(-50%);
		color: var(--muted);
		pointer-events: none;
	}

	.search-input {
		width: 100%;
		padding: 0.5rem 0.75rem 0.5rem 2.25rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text);
		font-size: 0.9rem;
		transition: border-color 0.2s, box-shadow 0.2s;
	}

	.search-input::placeholder {
		color: var(--muted);
	}

	.search-input:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 2px var(--accent-soft);
	}

	.sort-select {
		padding: 0.5rem 2rem 0.5rem 0.75rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text);
		font-size: 0.875rem;
		cursor: pointer;
		appearance: none;
		background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%238f98a8' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
		background-repeat: no-repeat;
		background-position: right 0.6rem center;
	}

	.sort-select:focus {
		outline: none;
		border-color: var(--accent);
	}

	/* Tag filter (projects) */
	.tag-filter {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 180px;
	}

	.tag-filter-trigger {
		display: inline-flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		width: 100%;
		padding: 0.5rem 0.75rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text);
		font-size: 0.875rem;
		cursor: pointer;
		transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
		text-align: left;
	}

	.tag-filter-trigger:hover {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 6%, var(--surface));
	}

	.tag-filter-trigger:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.tag-filter-trigger-main {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		min-width: 0;
	}

	.tag-filter-summary-text {
		white-space: nowrap;
		font-size: inherit;
	}

	.tag-filter-summary-chips {
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
	}

	.tag-filter-chevron {
		flex-shrink: 0;
		opacity: 0.7;
	}

	.tag-filter-menu {
		position: absolute;
		margin-top: 0.25rem;
		min-width: 220px;
		max-height: 320px;
		overflow: auto;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 8px;
		box-shadow: 0 10px 26px rgba(0, 0, 0, 0.35);
		padding: 0.25rem 0;
		z-index: 40;
	}

	.tag-filter-option {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		width: 100%;
		padding: 0.4rem 0.6rem;
		background: transparent;
		border: none;
		color: var(--text);
		font-size: 0.8rem;
		cursor: pointer;
		text-align: left;
	}

	.tag-filter-option:hover {
		background: var(--accent-soft);
	}

	.tag-filter-checkbox {
		width: 0.9rem;
		height: 0.9rem;
		border-radius: 3px;
		border: 1px solid var(--border);
		display: inline-flex;
		align-items: center;
		justify-content: center;
		background: var(--surface);
		flex-shrink: 0;
	}

	.tag-filter-checkbox-inner {
		width: 0.55rem;
		height: 0.55rem;
		border-radius: 2px;
		background: var(--accent);
	}

	.tag-filter-option-text {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.05rem;
		min-width: 0;
	}

	.tag-filter-option-label {
		font-size: 0.8rem;
		font-weight: 500;
	}

	/* Shared tag chips (copy of /apps) */
	.app-tags-row,
	.project-tags,
	.tag-filter-summary-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin-top: 0.2rem;
	}

	.tag-chip {
		display: inline-flex;
		align-items: center;
		padding: 0.05rem 0.4rem;
		border-radius: 999px;
		font-size: 0.68rem;
		font-weight: 500;
		color: var(--muted);
		background: color-mix(in srgb, var(--accent) 8%, var(--surface));
		border: 1px solid color-mix(in srgb, var(--accent) 20%, var(--border));
		max-width: 110px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.tag-chip-small {
		font-size: 0.62rem;
		max-width: 80px;
	}

	.tag-chip-more {
		color: var(--accent);
		border-color: color-mix(in srgb, var(--accent) 40%, var(--border));
		background: color-mix(in srgb, var(--accent) 12%, transparent);
	}

	.view-toggle {
		display: flex;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		overflow: hidden;
		pointer-events: auto;
	}

	.view-btn {
		position: relative;
		padding: 0.5rem 0.65rem;
		background: transparent;
		border: none;
		color: var(--muted);
		cursor: pointer;
		transition: color 0.2s, background 0.2s;
		box-shadow: none;
		transform: none;
		pointer-events: auto;
	}

	.view-btn:hover {
		color: var(--text);
		background: rgba(255, 255, 255, 0.04);
	}

	.view-btn.active {
		color: var(--accent);
		background: var(--accent-soft);
	}

	.view-btn svg {
		pointer-events: none;
	}

	.empty-state {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		padding: 3rem 2rem;
		min-height: 280px;
	}

	.empty-icon {
		color: var(--muted);
		opacity: 0.6;
		margin-bottom: 1rem;
	}

	.empty-state h2 {
		margin: 0 0 0.5rem 0;
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--text);
	}

	.empty-desc {
		margin: 0 0 1.5rem 0;
		max-width: 360px;
		font-size: 0.9rem;
		color: var(--muted);
		line-height: 1.5;
	}

	.projects-scroll-wrap {
		position: relative;
		z-index: 0;
		flex: none;
		padding-right: 0.25rem;
	}

	.projects-container {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
		gap: 1rem;
		align-content: start;
		min-height: min-content;
	}

	.projects-container.list-view {
		grid-template-columns: 1fr;
	}

	.project-card {
		display: flex;
		align-items: stretch;
		gap: 0;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		text-decoration: none;
		color: inherit;
		transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
		overflow: hidden;
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
	}

	.projects-container:not(.list-view) .project-card {
		flex-direction: column;
		min-height: 260px;
	}

	.list-view .project-card {
		flex-direction: column;
		align-items: stretch;
	}

	.project-card:hover {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 10%, var(--card));
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
	}

	.list-view .project-card:hover {
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}

	.card-visual {
		flex-shrink: 0;
		height: 88px;
		background: linear-gradient(135deg, var(--surface) 0%, color-mix(in srgb, var(--accent) 15%, var(--surface)) 100%);
		display: flex;
		flex-wrap: wrap;
		align-items: flex-start;
		align-content: flex-start;
		justify-content: flex-end;
		gap: 0.35rem;
		padding: 0.5rem 0.6rem;
	}

	.quick-runs-card .card-visual {
		background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 18%, var(--surface)) 0%, color-mix(in srgb, var(--accent) 8%, var(--surface)) 100%);
	}

	.card-visual.header-contrast-light .card-run-badge,
	.card-visual.header-contrast-light .card-quick-badge {
		color: rgba(255, 255, 255, 0.95);
		background: rgba(0, 0, 0, 0.28);
	}
	.card-visual.header-contrast-dark .card-run-badge,
	.card-visual.header-contrast-dark .card-quick-badge {
		color: rgba(0, 0, 0, 0.9);
		background: rgba(255, 255, 255, 0.4);
	}

	.list-view .card-visual {
		width: 100%;
		height: 8px;
		min-height: 8px;
		padding: 0;
		justify-content: flex-end;
		align-items: stretch;
		border-radius: 0;
	}

	.list-view .card-visual .card-run-badge,
	.list-view .card-visual .card-quick-badge,
	.list-view .card-visual .card-actions-visual {
		display: none;
	}

	.card-run-badge {
		font-size: 0.7rem;
		font-weight: 600;
		color: var(--muted);
		background: rgba(0, 0, 0, 0.2);
		padding: 0.2rem 0.45rem;
		border-radius: 6px;
		letter-spacing: 0.02em;
	}

	.card-quick-badge {
		font-size: 0.65rem;
		font-weight: 600;
		color: var(--accent-contrast, #fff);
		background: var(--accent);
		padding: 0.2rem 0.5rem;
		border-radius: 6px;
		letter-spacing: 0.02em;
	}

	.card-actions-visual {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: 0.35rem;
		margin-left: auto;
	}
	.card-action-btn {
		padding: 0.25rem 0.5rem;
		font-size: 0.7rem;
		font-weight: 600;
		border: none;
		border-radius: 6px;
		cursor: pointer;
		background: rgba(0, 0, 0, 0.35);
		color: rgba(255, 255, 255, 0.95);
		transition: background 0.2s;
	}
	.card-action-btn:hover:not(:disabled) {
		background: rgba(0, 0, 0, 0.5);
	}
	.card-action-btn:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}
	.card-visual.header-contrast-dark .card-action-btn {
		background: rgba(255, 255, 255, 0.35);
		color: rgba(0, 0, 0, 0.9);
	}
	.card-visual.header-contrast-dark .card-action-btn:hover:not(:disabled) {
		background: rgba(255, 255, 255, 0.5);
	}

	.list-action-btn {
		padding: 0.3rem 0.6rem;
		font-size: 0.75rem;
		font-weight: 500;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--surface);
		color: var(--text);
		cursor: pointer;
		transition: border-color 0.2s, background 0.2s;
	}
	.list-action-btn:hover:not(:disabled) {
		border-color: var(--accent);
		background: var(--accent-soft);
	}
	.list-action-btn:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.card-body {
		flex: 1;
		min-width: 0;
		padding: 1rem 1rem 1rem 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.list-view .card-body {
		padding: 1rem 1.25rem;
	}

	.card-body.list-body {
		padding: 0.5rem 1rem;
		gap: 0;
	}

	.list-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem 1rem;
		row-gap: 0.35rem;
		min-height: 0;
	}

	.list-run-badge {
		flex-shrink: 0;
		font-size: 0.65rem;
		font-weight: 600;
		color: var(--muted);
		background: rgba(0, 0, 0, 0.2);
		padding: 0.15rem 0.4rem;
		border-radius: 6px;
		letter-spacing: 0.02em;
	}

	.list-quick-badge {
		flex-shrink: 0;
		font-size: 0.65rem;
		padding: 0.15rem 0.4rem;
	}

	.list-name,
	.card-body.list-body .project-name {
		flex-shrink: 0;
		font-size: 0.95rem;
		-webkit-line-clamp: 1;
		line-clamp: 1;
		margin: 0;
		max-width: 220px;
	}

	.list-slug-desc {
		flex: 1;
		min-width: 0;
		font-size: 0.8rem;
		color: var(--muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		max-width: 280px;
	}

	.list-right-group {
		display: flex;
		align-items: flex-end;
		gap: 0.75rem;
		margin-left: auto;
		flex-shrink: 0;
	}

	.date-infobox {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		margin-top: 0.5rem;
		padding: 0.5rem 0.65rem;
		background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 6%, var(--surface)) 0%, color-mix(in srgb, var(--accent) 3%, var(--surface)) 100%);
		border: 1px solid color-mix(in srgb, var(--accent) 18%, var(--border));
		border-radius: 8px;
		border-left: 3px solid var(--accent);
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
	}

	.date-infobox-list {
		flex-direction: row;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem 0.75rem;
		margin-top: 0;
		margin-bottom: 0;
		padding: 0.4rem 0.6rem;
		box-sizing: border-box;
		display: inline-flex;
		align-items: center;
	}

	.date-infobox-inline {
		display: inline-flex;
		align-items: baseline;
		gap: 0.35rem;
		font-size: 0.75rem;
	}

	.date-infobox-list .date-infobox-inline {
		align-items: center;
	}

	.date-infobox-label {
		color: var(--muted);
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		font-size: 0.7rem;
	}

	.date-infobox-list .date-infobox-label {
		font-size: 0.65rem;
	}

	.date-infobox-value {
		color: var(--text);
		font-variant-numeric: tabular-nums;
	}

	.date-infobox-list .date-infobox-value {
		font-size: 0.8rem;
	}

	.date-infobox-sep {
		color: var(--border);
		font-weight: 300;
		user-select: none;
	}

	.project-name {
		margin: 0;
		font-size: 1rem;
		font-weight: 600;
		color: var(--text);
		line-height: 1.3;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.project-desc {
		margin: 0;
		font-size: 0.8rem;
		color: var(--muted);
		line-height: 1.35;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.project-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem;
		margin-top: 0.25rem;
		font-size: 0.75rem;
		color: var(--muted);
	}

	.meta-item {
		display: inline-flex;
		align-items: center;
		gap: 0.3rem;
	}

	.meta-item svg {
		flex-shrink: 0;
		opacity: 0.8;
	}

	.project-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.25rem;
		margin-top: auto;
		padding-top: 0.25rem;
	}

	.projects-scroll-wrap::-webkit-scrollbar {
		width: 8px;
	}

	.projects-scroll-wrap::-webkit-scrollbar-track {
		background: transparent;
	}

	.projects-scroll-wrap::-webkit-scrollbar-thumb {
		background: rgba(109, 93, 252, 0.25);
		border-radius: 4px;
	}

	.projects-scroll-wrap::-webkit-scrollbar-thumb:hover {
		background: rgba(109, 93, 252, 0.4);
	}

	.header-color-wrap {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.35rem;
	}
	.header-color-input {
		width: 2.5rem;
		height: 2.25rem;
		padding: 2px;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--surface);
		cursor: pointer;
	}
	.header-color-clear {
		padding: 0.35rem 0.6rem;
		font-size: 0.85rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		color: var(--muted);
		cursor: pointer;
	}
	.header-color-clear:hover {
		color: var(--text);
		border-color: var(--accent);
	}

	.dialog-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}
	.dialog-box {
		background: var(--card-bg, var(--card));
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 1.5rem;
		min-width: 320px;
		max-width: 420px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
	}
	.dialog-title {
		margin: 0 0 0.5rem 0;
		font-size: 1.2rem;
		color: var(--text);
	}
	.dialog-desc {
		margin: 0 0 1rem 0;
		font-size: 0.9rem;
		color: var(--muted);
	}
	.dialog-label {
		display: block;
		margin-bottom: 1.25rem;
	}
	.dialog-label-text {
		display: block;
		font-size: 0.85rem;
		font-weight: 500;
		color: var(--text);
		margin-bottom: 0.35rem;
	}
	.dialog-input {
		width: 100%;
		padding: 0.5rem 0.75rem;
		font-size: 0.95rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--input-bg);
		color: var(--text);
	}
	.dialog-input:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 2px var(--accent-soft);
	}
	.dialog-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.dialog-btn {
		padding: 0.5rem 1rem;
		font-size: 0.9rem;
		border-radius: 8px;
		cursor: pointer;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
	}
	.dialog-btn.secondary:hover {
		background: color-mix(in srgb, var(--accent) 15%, var(--surface));
		border-color: var(--accent);
	}
	.dialog-btn.primary {
		background: var(--accent);
		color: var(--accent-fg, #fff);
		border-color: var(--accent);
	}
	.dialog-btn.primary:hover {
		filter: brightness(1.1);
	}

	@media (max-width: 639px) {
		.projects-page {
			padding: 0.75rem 1rem;
		}
		.page-header {
			margin-bottom: 0.75rem;
		}
		.header-top h1 {
			font-size: 1.35rem;
		}
		.toolbar {
			flex-direction: column;
			align-items: stretch;
			gap: 0.5rem;
		}
		.filters-more {
			width: 100%;
		}
		.create-project-btn {
			width: 100%;
			min-height: 44px;
		}
		.search-wrap {
			max-width: none;
			min-width: 0;
		}
		.projects-container {
			grid-template-columns: 1fr;
			gap: 0.5rem;
		}
		.projects-container:not(.list-view) .project-card {
			min-height: 160px;
		}
		.project-card .card-visual {
			height: 52px;
			padding: 0.35rem 0.5rem;
		}
		.project-card .card-body {
			padding: 0.6rem 0.75rem;
			gap: 0.25rem;
		}
		.project-card .project-name {
			font-size: 0.9rem;
		}
		.project-card .project-desc,
		.project-card .project-meta {
			font-size: 0.75rem;
		}
		.project-card .meta-item {
			font-size: 0.7rem;
		}
		.list-view .card-body.list-body {
			padding: 0.4rem 0.75rem;
		}
		.dialog-backdrop {
			padding: 0.5rem;
			align-items: flex-start;
			padding-top: 2rem;
		}
		.dialog-box {
			width: 100%;
			min-width: 0;
			max-width: none;
		}
	}
</style>
