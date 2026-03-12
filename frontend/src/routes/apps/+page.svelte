<script lang="ts">
	import { onMount } from 'svelte';
	import { get } from 'svelte/store';
	import { goto, invalidate } from '$app/navigation';
	import { page } from '$app/stores';
	import type { AppSummary, ProjectOption } from './+page';
	import { QUICK_RUNS_PROJECT_ID } from '$lib/constants';
	import { appBooting } from '$lib/stores/appBooting';
	import { getApiBase } from '$lib/config';
	import { getContrastForeground } from '$lib/utils/color';

	const sendFromRun = $derived.by(() => {
		try {
			return $page.url?.searchParams?.get('send_from_run') ?? null;
		} catch {
			return null;
		}
	});
	const sendFromOutput = $derived.by(() => {
		try {
			return $page.url?.searchParams?.get('send_from_output') ?? null;
		} catch {
			return null;
		}
	});
	const sendFromProject = $derived.by(() => {
		try {
			return $page.url?.searchParams?.get('project') ?? null;
		} catch {
			return null;
		}
	});
	const sendToAppParams = $derived.by(() => {
		const run = sendFromRun != null ? String(sendFromRun).trim() : '';
		const out = sendFromOutput != null ? String(sendFromOutput).trim() : '';
		if (!run || !out || run === 'null' || out === 'null') return null;
		const params: Record<string, string> = {
			send_from_run: run,
			send_from_output: out
		};
		if (sendFromProject) params.project = sendFromProject;
		return new URLSearchParams(params);
	});

	let sendFromMediaKind = $state<string | null>(null);
	$effect(() => {
		const runId = sendFromRun;
		const outputParam = sendFromOutput;
		if (!runId || outputParam == null) {
			sendFromMediaKind = null;
			return;
		}
		const outputIndex = parseInt(outputParam, 10);
		if (Number.isNaN(outputIndex) || outputIndex < 0) {
			sendFromMediaKind = null;
			return;
		}
		const apiBase = getApiBase() || '';
		fetch(`${apiBase}/runs/${runId}`)
			.then((res) => (res.ok ? res.json() : null))
			.then((run: { media?: { kind?: string; type?: string }[]; images?: { type?: string }[] } | null) => {
				const list = run?.media ?? run?.images;
				if (!Array.isArray(list) || outputIndex >= list.length) {
					sendFromMediaKind = null;
					return;
				}
				const ent = list[outputIndex];
				if (!ent || typeof ent !== 'object') {
					sendFromMediaKind = null;
					return;
				}
				const kind = (ent as { kind?: string }).kind ?? (ent as { type?: string }).type ?? 'image';
				sendFromMediaKind = typeof kind === 'string' ? kind : 'image';
			})
			.catch(() => {
				sendFromMediaKind = null;
			});
	});

	function usePortal(node: HTMLElement) {
		document.body.appendChild(node);
		return {
			destroy() {
				if (node.parentNode) node.parentNode.removeChild(node);
			}
		};
	}

	let { data } = $props();

	onMount(() => {
		invalidate(get(page).url);
	});

	type SortKey = 'created' | 'name' | 'slug' | 'used';
	const sortOptions: { value: SortKey; label: string }[] = [
		{ value: 'used', label: 'Recently used' },
		{ value: 'created', label: 'Newest first' },
		{ value: 'name', label: 'Name A–Z' },
		{ value: 'slug', label: 'Slug A–Z' },
	];

	let search = $state('');
	let sortBy = $state<SortKey>('used');
	let tagFilters = $state<string[]>([]); // [] = all tags
	let viewMode = $state<'grid' | 'list'>('grid');
	let activeTab = $state<'my-apps' | 'browse'>('my-apps');
	let openDropdownFor = $state<string | null>(null);
	let projectFilter = $state('');
	let dropdownTriggerEl = $state<HTMLButtonElement | null>(null);
	let dropdownPosition = $state<{ top: number; left: number } | null>(null);

	let appToDelete = $state<{ slug: string; title: string } | null>(null);
	let deleteError = $state<string | null>(null);
	let deleteLoading = $state(false);
	let copyingSlug = $state<string | null>(null);
	let copyError = $state<string | null>(null);

	function requestDeleteApp(app: AppSummary) {
		appToDelete = { slug: app.slug, title: app.title ?? app.slug };
		deleteError = null;
	}

	function closeDeleteDialog() {
		if (!deleteLoading) {
			appToDelete = null;
			deleteError = null;
		}
	}

	async function confirmDeleteApp() {
		if (!appToDelete || deleteLoading) return;
		deleteError = null;
		deleteLoading = true;
		try {
			const base = getApiBase() || '';
			const res = await fetch(`${base}/apps/${appToDelete.slug}`, { method: 'DELETE' });
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				throw new Error(
					typeof d?.detail === 'string' ? d.detail : res.status === 404 ? 'App not found' : 'Failed to delete app'
				);
			}
			appToDelete = null;
			invalidate(get(page).url);
		} catch (e) {
			deleteError = e instanceof Error ? e.message : 'Failed to delete app';
		} finally {
			deleteLoading = false;
		}
	}

	async function copyApp(app: AppSummary) {
		copyError = null;
		copyingSlug = app.slug;
		const apiBase = getApiBase() || '';
		try {
			const res = await fetch(`${apiBase}/apps/${app.slug}/copy`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ new_title: `Copy of ${app.title || app.slug}` })
			});
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				throw new Error(
					typeof d?.detail === 'string' ? d.detail : res.status === 404 ? 'App not found' : 'Failed to copy app'
				);
			}
			const created = await res.json();
			invalidate(get(page).url);
			goto(`/apps/${created.slug}/edit`);
		} catch (e) {
			copyError = e instanceof Error ? e.message : 'Failed to copy app';
		} finally {
			copyingSlug = null;
		}
	}

	const projectsExcludingQuickRuns = $derived(
		(data.projects ?? []).filter((p) => p.id !== QUICK_RUNS_PROJECT_ID)
	);

	const filteredProjectsForDropdown = $derived.by(() => {
		const q = projectFilter.trim().toLowerCase();
		if (!q) return projectsExcludingQuickRuns;
		return projectsExcludingQuickRuns.filter((p) => {
			const name = (p.name ?? '').toLowerCase();
			const slug = (p.slug ?? '').toLowerCase();
			return name.includes(q) || slug.includes(q);
		});
	});

	function matchesSearch(a: AppSummary): boolean {
		if (!search.trim()) return true;
		const q = search.trim().toLowerCase();
		const title = (a.title ?? '').toLowerCase();
		const slug = (a.slug ?? '').toLowerCase();
		const desc = (a.description ?? '').toLowerCase();
		return title.includes(q) || slug.includes(q) || desc.includes(q);
	}

	function isCompatibleWithSendFrom(a: AppSummary): boolean {
		if (!sendFromRun || !sendFromOutput) return true;
		const kinds = a.supported_input_kinds;
		if (!kinds || kinds.length === 0) return true;
		const kind = sendFromMediaKind ?? 'image';
		return kinds.some((k) => (k ?? '').toLowerCase() === kind.toLowerCase());
	}

	const allTags = $derived(
		Array.from(
			new Set(
				(data.apps ?? [])
					.flatMap((a) => a.tags ?? [])
					.map((t) => (t ?? '').trim().toLowerCase())
					.filter(Boolean)
			)
		).sort()
	);

	function matchesTagFilter(a: AppSummary): boolean {
		if (!tagFilters.length) return true;
		const appTags = (a.tags ?? []).map((t) => (t ?? '').trim().toLowerCase());
		if (!appTags.length) return false;
		// ANY-of-selected semantics
		return tagFilters.some((t) => appTags.includes(t));
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
		data.apps.filter(
			(a) => matchesSearch(a) && isCompatibleWithSendFrom(a) && matchesTagFilter(a)
		)
	);

	const sorted = $derived.by(() => {
		const list = [...filtered];
		switch (sortBy) {
			case 'name':
				list.sort((a, b) => (a.title ?? '').localeCompare(b.title ?? ''));
				break;
			case 'slug':
				list.sort((a, b) => (a.slug ?? '').localeCompare(b.slug ?? ''));
				break;
			case 'used':
				list.sort((a, b) => {
					const au = a.last_used ?? 0;
					const bu = b.last_used ?? 0;
					return bu - au;
				});
				break;
			default:
				list.sort((a, b) => (b.created_at ?? 0) - (a.created_at ?? 0));
				break;
		}
		return list;
	});

	function formatDate(ms: number): string {
		return new Date(ms).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
	}

	function formatRelative(ms: number): string {
		const d = new Date(ms);
		const now = Date.now();
		const diff = now - d.getTime();
		const sec = Math.floor(diff / 1000);
		const min = Math.floor(sec / 60);
		const hr = Math.floor(min / 60);
		const day = Math.floor(hr / 24);
		if (day >= 14) return d.toLocaleDateString(undefined, { dateStyle: 'medium' });
		if (day >= 1) return `${day}d ago`;
		if (hr >= 1) return `${hr}h ago`;
		if (min >= 1) return `${min}m ago`;
		if (sec >= 10) return `${sec}s ago`;
		return 'Just now';
	}

	function appUrl(slug: string, projectId: string | null): string {
		const params = new URLSearchParams();
		if (projectId && projectId !== QUICK_RUNS_PROJECT_ID) params.set('project', projectId);
		if (sendToAppParams) {
			sendToAppParams.forEach((v, k) => params.set(k, v));
		}
		const q = params.toString();
		return q ? `/app/${slug}?${q}` : `/app/${slug}`;
	}

	function openWithProject(slug: string, projectId: string) {
		openDropdownFor = null;
		projectFilter = '';
		dropdownTriggerEl = null;
		dropdownPosition = null;
		appBooting.set(true);
		goto(appUrl(slug, projectId));
	}

	function openAppQuickRuns(slug: string) {
		appBooting.set(true);
		goto(appUrl(slug, null));
	}

	function onCardClick(e: MouseEvent, appSlug: string) {
		const target = e.target as Element;
		if (target.closest('a, button, input, .open-with-wrap, .app-card-delete-btn')) return;
		e.preventDefault();
		openAppQuickRuns(appSlug);
	}

	function onCardKeydown(e: KeyboardEvent, appSlug: string) {
		if (e.key !== 'Enter' && e.key !== ' ') return;
		const target = e.target as Element;
		if (target.closest('a, button, input, .open-with-wrap, .app-card-delete-btn')) return;
		e.preventDefault();
		openAppQuickRuns(appSlug);
	}

	function toggleDropdown(slug: string, trigger?: HTMLButtonElement) {
		if (openDropdownFor === slug) {
			openDropdownFor = null;
			projectFilter = '';
			dropdownTriggerEl = null;
			dropdownPosition = null;
		} else {
			openDropdownFor = slug;
			projectFilter = '';
			dropdownTriggerEl = trigger ?? null;
			if (trigger) {
				const rect = trigger.getBoundingClientRect();
				dropdownPosition = { top: rect.bottom + 4, left: rect.left };
			}
		}
	}

	function updateDropdownPosition() {
		if (!dropdownTriggerEl) {
			dropdownPosition = null;
			return;
		}
		const rect = dropdownTriggerEl.getBoundingClientRect();
		dropdownPosition = { top: rect.bottom + 4, left: rect.left };
	}

	$effect(() => {
		if (openDropdownFor && dropdownTriggerEl) {
			updateDropdownPosition();
			const onScrollOrResize = () => updateDropdownPosition();
			window.addEventListener('scroll', onScrollOrResize, true);
			window.addEventListener('resize', onScrollOrResize);
			return () => {
				window.removeEventListener('scroll', onScrollOrResize, true);
				window.removeEventListener('resize', onScrollOrResize);
			};
		} else {
			dropdownPosition = null;
		}
	});

	$effect(() => {
		if (!openDropdownFor) return;
		const onClick = (e: MouseEvent) => {
			if (!(e.target as Element).closest('.open-with-wrap') && !(e.target as Element).closest('.open-with-menu')) {
				openDropdownFor = null;
				projectFilter = '';
				dropdownTriggerEl = null;
				dropdownPosition = null;
			}
		};
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				openDropdownFor = null;
				projectFilter = '';
				dropdownTriggerEl = null;
				dropdownPosition = null;
			}
		};
		document.addEventListener('keydown', onKey);
		const t = setTimeout(() => {
			document.addEventListener('click', onClick);
			const input = document.querySelector('.open-with-filter-input') as HTMLInputElement | null;
			input?.focus();
		}, 50);
		return () => {
			clearTimeout(t);
			document.removeEventListener('click', onClick);
			document.removeEventListener('keydown', onKey);
		};
	});
</script>

<div class="apps-page">
	<header class="page-header">
		{#if sendToAppParams}
			<p class="send-to-app-banner">Choose an app to send your output to. Opening an app will prefill the selected output.</p>
			{#if sendFromMediaKind}
				<p class="send-to-app-banner send-to-app-compat">Showing only apps that accept <strong>{sendFromMediaKind}</strong> as input.</p>
			{/if}
		{/if}
		<div class="header-top">
			<h1>Apps</h1>
			<p class="subtitle">All configured workflow apps. Edit settings or open an app to run.</p>
		</div>
		<div class="apps-tabs" role="tablist" aria-label="Apps view">
			<button
				type="button"
				role="tab"
				class="apps-tab"
				class:active={activeTab === 'my-apps'}
				aria-selected={activeTab === 'my-apps'}
				aria-controls="panel-my-apps"
				id="tab-my-apps"
				onclick={() => (activeTab = 'my-apps')}
			>
				<svg class="tab-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
					<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>
				</svg>
				My apps
			</button>
			<button
				type="button"
				role="tab"
				class="apps-tab"
				class:active={activeTab === 'browse'}
				aria-selected={activeTab === 'browse'}
				aria-controls="panel-browse"
				id="tab-browse"
				onclick={() => (activeTab = 'browse')}
			>
				<svg class="tab-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
					<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
				</svg>
				Explore apps from apps repository
				<span class="tab-badge">Soon</span>
			</button>
		</div>
	</header>

	<div id="panel-my-apps" role="tabpanel" aria-labelledby="tab-my-apps" class="tab-panel" hidden={activeTab !== 'my-apps'}>
		<div class="toolbar">
			<div class="search-wrap">
				<svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
					<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
				</svg>
				<input
					type="search"
					placeholder="Search apps…"
					bind:value={search}
					class="search-input"
					aria-label="Search apps"
				/>
			</div>
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
						aria-label="Filter apps by tag"
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
			<div class="view-toggle" role="tablist" aria-label="View">
				<button
					type="button"
					class="view-btn"
					class:active={viewMode === 'grid'}
					onclick={() => (viewMode = 'grid')}
					aria-pressed={viewMode === 'grid'}
					aria-label="Grid view"
				>
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
				</button>
				<button
					type="button"
					class="view-btn"
					class:active={viewMode === 'list'}
					onclick={() => (viewMode = 'list')}
					aria-pressed={viewMode === 'list'}
					aria-label="List view"
				>
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
				</button>
			</div>
			<a href="/apps/create" class="create-btn">Create app</a>
		</div>

	{#if sorted.length === 0}
		<div class="empty-state">
			<div class="empty-icon" aria-hidden="true">
				<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
					<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>
				</svg>
			</div>
			<h2>{data.apps.length === 0 ? 'No apps yet' : 'No matching apps'}</h2>
			<p class="empty-desc">
				{#if data.apps.length === 0}
					Create an app from a workflow version to expose it as a runnable web app.
				{:else}
					Try a different search or sort.
				{/if}
			</p>
			{#if data.apps.length === 0}
				<a href="/apps/create" class="create-btn">Create app</a>
			{/if}
		</div>
	{:else}
		<div class="apps-scroll-wrap">
			{#if copyError}
				<p class="copy-error-text">{copyError}</p>
			{/if}
			<div class="apps-container" class:list-view={viewMode === 'list'}>
			{#each sorted as app (app.id)}
				<div
					class="app-card"
					role="button"
					tabindex="0"
					aria-label="Open {app.title} in Quick runs"
					onclick={(e) => onCardClick(e, app.slug)}
					onkeydown={(e) => onCardKeydown(e, app.slug)}
				>
					<div
						class="card-visual"
						class:header-contrast-light={app.header_color && getContrastForeground(app.header_color) === 'light'}
						class:header-contrast-dark={app.header_color && getContrastForeground(app.header_color) === 'dark'}
						style={app.header_color
							? `--header-color: ${app.header_color}; background: linear-gradient(135deg, ${app.header_color} 0%, color-mix(in srgb, ${app.header_color} 75%, black) 100%);`
							: ''}
					>
						<span class="card-badge" class:public={app.is_public}>
							{app.is_public ? 'Public' : 'Private'}
						</span>
						<div class="card-visual-dates" role="group" aria-label="Dates">
							<span class="card-visual-date">
								<span class="card-visual-date-label">Last used</span>
								<span class="card-visual-date-value">{app.last_used ? formatRelative(app.last_used) : 'Never'}</span>
							</span>
							<span class="card-visual-date">
								<span class="card-visual-date-label">Created</span>
								<span class="card-visual-date-value">{formatDate(app.created_at)}</span>
							</span>
						</div>
					</div>
					<div class="card-body" class:list-body={viewMode === 'list'}>
						{#if viewMode === 'list'}
							<div class="list-row">
								<span class="card-badge list-badge" class:public={app.is_public}>{app.is_public ? 'Public' : 'Private'}</span>
								{#if app.created_from_image_import}
									<span class="badge-from-image" title="Created from workflow image import">From image</span>
								{/if}
								<h3 class="app-name list-name">{app.title}</h3>
								<span class="list-slug-desc">{#if app.description}{app.description}{:else}/{app.slug}{/if}</span>
								{#if app.tags && app.tags.length}
									<div class="app-tags-row list-tags">
										{#each app.tags.slice(0, 4) as tag (tag)}
											<span class="tag-chip tag-chip-small">{tag}</span>
										{/each}
										{#if app.tags.length > 4}
											<span class="tag-chip tag-chip-more">+{app.tags.length - 4}</span>
										{/if}
									</div>
								{/if}
								<div class="list-right-group">
									<div class="date-infobox date-infobox-list" role="group" aria-label="Dates">
										<span class="date-infobox-inline">
											<span class="date-infobox-label">Last used</span>
											<span class="date-infobox-value">{app.last_used ? formatRelative(app.last_used) : 'Never'}</span>
										</span>
										<span class="date-infobox-sep" aria-hidden="true">·</span>
										<span class="date-infobox-inline">
											<span class="date-infobox-label">Created</span>
											<span class="date-infobox-value">{formatDate(app.created_at)}</span>
										</span>
									</div>
									<div class="card-actions list-actions">
										<a
											href={appUrl(app.slug, sendFromProject)}
											class="action-btn primary"
											onclick={(e) => {
												if (e.ctrlKey || e.metaKey || e.button !== 0) return;
												e.preventDefault();
												appBooting.set(true);
												goto(appUrl(app.slug, sendFromProject));
											}}
										>Go to app</a>
										{#if projectsExcludingQuickRuns.length > 0}
											<div class="open-with-wrap">
												<button
													type="button"
													class="action-btn secondary open-with-trigger"
													title="Open app in selected project"
													aria-label="Open app in selected project"
													onclick={(e) => { e.preventDefault(); e.stopPropagation(); toggleDropdown(app.slug, e.currentTarget as HTMLButtonElement); }}
													aria-expanded={openDropdownFor === app.slug}
													aria-haspopup="true"
													aria-controls="open-with-menu-{app.slug}"
													id="open-with-btn-list-{app.slug}"
												>
													Open with…
													<svg class="chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
												</button>
												{#if openDropdownFor === app.slug}
													<div
														use:usePortal
														id="open-with-menu-{app.slug}"
														class="open-with-menu open-with-menu-fixed"
														role="listbox"
														aria-labelledby="open-with-btn-list-{app.slug}"
														aria-label="Choose project to open app with"
														style={dropdownPosition ? `position: fixed; top: ${dropdownPosition.top}px; left: ${dropdownPosition.left}px; z-index: 99999` : ''}
													>
														<div class="open-with-filter-wrap">
															<svg class="open-with-filter-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
															<input type="text" class="open-with-filter-input" placeholder="Filter projects…" bind:value={projectFilter} onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()} aria-label="Filter projects" />
														</div>
														<div class="open-with-list" role="group">
															{#each filteredProjectsForDropdown as proj (proj.id)}
																<button type="button" role="option" class="open-with-item" aria-selected="false" onclick={(e) => { e.stopPropagation(); openWithProject(app.slug, proj.id); }}>
																	<span class="open-with-name">{proj.name}</span>
																	<span class="open-with-meta">{proj.run_count} runs</span>
																</button>
															{/each}
															{#if filteredProjectsForDropdown.length === 0}
																<p class="open-with-empty">No matching projects</p>
															{/if}
														</div>
													</div>
												{/if}
											</div>
										{/if}
										<button
											type="button"
											class="action-btn secondary icon-only"
											aria-label="Copy app"
											title="Copy app"
											disabled={copyingSlug === app.slug}
											onclick={(e) => {
												e.preventDefault();
												e.stopPropagation();
												copyApp(app);
											}}
											onkeydown={(e) => e.stopPropagation()}
										>
											{#if copyingSlug === app.slug}
												<svg class="action-icon spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12a9 9 0 11-9-9"/></svg>
											{:else}
												<svg class="action-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
											{/if}
										</button>
										<a href="/apps/{app.slug}/edit" class="action-btn secondary icon-only" aria-label="Edit app" title="Edit app">
											<svg class="action-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
										</a>
										<button
											type="button"
											class="app-card-delete-btn action-btn icon-only"
											aria-label="Delete app"
											title="Delete app"
											onclick={(e) => {
												e.preventDefault();
												e.stopPropagation();
												requestDeleteApp(app);
											}}
											onkeydown={(e) => e.stopPropagation()}
										>
											<svg class="action-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
										</button>
									</div>
								</div>
							</div>
						{:else}
						<div class="app-name-row">
							<h3 class="app-name">{app.title}</h3>
							{#if app.created_from_image_import}
								<span class="badge-from-image" title="Created from workflow image import">From image</span>
							{/if}
						</div>
						{#if app.description}
							<p class="app-desc">{app.description}</p>
						{:else}
							<p class="app-slug">/{app.slug}</p>
						{/if}
						{#if app.tags && app.tags.length}
							<div class="app-tags-row">
								{#each app.tags.slice(0, 3) as tag (tag)}
									<span class="tag-chip">{tag}</span>
								{/each}
								{#if app.tags.length > 3}
									<span class="tag-chip tag-chip-more">+{app.tags.length - 3}</span>
								{/if}
							</div>
						{/if}
						<div class="card-actions">
							<a
								href={appUrl(app.slug, sendFromProject)}
								class="action-btn primary"
								onclick={(e) => {
									if (e.ctrlKey || e.metaKey || e.button !== 0) return;
									e.preventDefault();
									appBooting.set(true);
									goto(appUrl(app.slug, sendFromProject));
								}}
							>Go to app</a>
							{#if projectsExcludingQuickRuns.length > 0}
								<div class="open-with-wrap">
									<button
										type="button"
										class="action-btn secondary open-with-trigger"
										title="Open app in selected project"
										aria-label="Open app in selected project"
										onclick={(e) => {
											e.preventDefault();
											e.stopPropagation();
											toggleDropdown(app.slug, e.currentTarget as HTMLButtonElement);
										}}
										aria-expanded={openDropdownFor === app.slug}
										aria-haspopup="true"
										aria-controls="open-with-menu-{app.slug}"
										id="open-with-btn-{app.slug}"
									>
										Open with…
										<svg class="chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>
									</button>
									{#if openDropdownFor === app.slug}
										<div
											use:usePortal
											id="open-with-menu-{app.slug}"
											class="open-with-menu open-with-menu-fixed"
											role="listbox"
											aria-labelledby="open-with-btn-{app.slug}"
											aria-label="Choose project to open app with"
											style={dropdownPosition ? `position: fixed; top: ${dropdownPosition.top}px; left: ${dropdownPosition.left}px; z-index: 99999` : ''}
										>
											<div class="open-with-filter-wrap">
												<svg class="open-with-filter-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
												<input
													type="text"
													class="open-with-filter-input"
													placeholder="Filter projects…"
													bind:value={projectFilter}
													onclick={(e) => e.stopPropagation()}
													onkeydown={(e) => e.stopPropagation()}
													aria-label="Filter projects"
												/>
											</div>
											<div class="open-with-list" role="group">
												{#each filteredProjectsForDropdown as proj (proj.id)}
													<button
														type="button"
														role="option"
														class="open-with-item"
														aria-selected="false"
														onclick={(e) => {
															e.stopPropagation();
															openWithProject(app.slug, proj.id);
														}}
													>
														<span class="open-with-name">{proj.name}</span>
														<span class="open-with-meta">{proj.run_count} runs</span>
													</button>
												{/each}
												{#if filteredProjectsForDropdown.length === 0}
													<p class="open-with-empty">No matching projects</p>
												{/if}
											</div>
										</div>
									{/if}
								</div>
							{/if}
							<button
								type="button"
								class="action-btn secondary icon-only"
								aria-label="Copy app"
								title="Copy app"
								disabled={copyingSlug === app.slug}
								onclick={(e) => {
									e.preventDefault();
									e.stopPropagation();
									copyApp(app);
								}}
								onkeydown={(e) => e.stopPropagation()}
							>
								{#if copyingSlug === app.slug}
									<svg class="action-icon spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M21 12a9 9 0 11-9-9"/></svg>
								{:else}
									<svg class="action-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
								{/if}
							</button>
							<a href="/apps/{app.slug}/edit" class="action-btn secondary icon-only" aria-label="Edit app" title="Edit app">
								<svg class="action-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
							</a>
							<button
								type="button"
								class="app-card-delete-btn action-btn icon-only"
								aria-label="Delete app"
								title="Delete app"
								onclick={(e) => {
									e.preventDefault();
									e.stopPropagation();
									requestDeleteApp(app);
								}}
								onkeydown={(e) => e.stopPropagation()}
							>
								<svg class="action-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
							</button>
						</div>
						{/if}
					</div>
					</div>
			{/each}
			</div>
		</div>
	{/if}
</div>

		<div id="panel-browse" role="tabpanel" aria-labelledby="tab-browse" class="tab-panel tab-panel-browse" hidden={activeTab !== 'browse'}>
			<div class="coming-soon">
				<div class="coming-soon-visual" aria-hidden="true">
					<svg class="coming-soon-icon" width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
						<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
						<path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
						<path d="M8 7h8"/>
						<path d="M8 11h6"/>
					</svg>
					<div class="coming-soon-glow"></div>
				</div>
				<span class="coming-soon-label">Coming soon</span>
				<h2 class="coming-soon-title">Apps repository</h2>
				<p class="coming-soon-desc">
					We’re taking media creation to the next level. Soon you’ll browse a shared repository of workflow apps—discover, one-click install, and remix what others have built. Share your own processes and let the community run and extend them. Same workflows, better together.
				</p>
				<p class="coming-soon-cta">Stay tuned. This is where sharing gets real.</p>
			</div>
		</div>
	{#if appToDelete}
		<div
			class="delete-app-backdrop"
			role="dialog"
			aria-modal="true"
			aria-labelledby="delete-app-dialog-title"
			tabindex="-1"
			onclick={closeDeleteDialog}
			onkeydown={(e) => { if (e.key === 'Escape') closeDeleteDialog(); }}
		>
			<div class="delete-app-dialog" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
				<h2 id="delete-app-dialog-title" class="delete-app-title">Delete app?</h2>
				<p class="delete-app-desc">
					<strong>{appToDelete.title}</strong> will be removed. No generated data (runs, outputs, or media) is deleted. You can still view run history in projects.
				</p>
				{#if deleteError}
					<p class="delete-app-error">{deleteError}</p>
				{/if}
				<div class="delete-app-actions">
					<button type="button" class="delete-app-btn secondary" onclick={closeDeleteDialog} disabled={deleteLoading}>
						Cancel
					</button>
					<button
						type="button"
						class="delete-app-btn primary"
						disabled={deleteLoading}
						onclick={confirmDeleteApp}
					>
						{deleteLoading ? '…' : 'Delete'}
					</button>
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.apps-page {
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

	.apps-tabs {
		display: flex;
		gap: 0.25rem;
		margin-top: 1rem;
		border-bottom: 1px solid var(--border);
		padding-bottom: 0;
	}

	.apps-tab {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.6rem 1rem;
		background: transparent;
		border: none;
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
		color: var(--muted);
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
		transition: color 0.2s, border-color 0.2s;
		border-radius: 6px 6px 0 0;
	}

	.apps-tab:hover {
		color: var(--text);
	}

	.apps-tab.active {
		color: var(--accent);
		border-bottom-color: var(--accent);
	}

	.apps-tab .tab-icon {
		flex-shrink: 0;
		opacity: 0.85;
	}

	.tab-badge {
		font-size: 0.65rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		padding: 0.15rem 0.45rem;
		background: linear-gradient(135deg, color-mix(in srgb, var(--accent) 25%, var(--surface)) 0%, color-mix(in srgb, var(--accent) 15%, var(--surface)) 100%);
		border: 1px solid color-mix(in srgb, var(--accent) 40%, var(--border));
		border-radius: 999px;
		color: var(--accent);
		margin-left: 0.25rem;
	}

	.tab-panel {
		flex: none;
		display: flex;
		flex-direction: column;
	}

	.tab-panel[hidden] {
		display: none !important;
	}

	.tab-panel-browse {
		padding-top: 0.5rem;
	}

	.coming-soon {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		padding: 3rem 2rem;
		min-height: 320px;
		max-width: 520px;
		margin: 0 auto;
	}

	.coming-soon-visual {
		position: relative;
		margin-bottom: 1.25rem;
	}

	.coming-soon-icon {
		color: var(--accent);
		opacity: 0.9;
		filter: drop-shadow(0 0 20px color-mix(in srgb, var(--accent) 35%, transparent));
	}

	.coming-soon-glow {
		position: absolute;
		inset: -20px;
		background: radial-gradient(circle, color-mix(in srgb, var(--accent) 18%, transparent) 0%, transparent 70%);
		pointer-events: none;
	}

	.coming-soon-label {
		display: inline-block;
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.12em;
		color: var(--accent);
		margin-bottom: 0.5rem;
		padding: 0.2rem 0.6rem;
		background: var(--accent-soft);
		border-radius: 999px;
	}

	.coming-soon-title {
		margin: 0 0 0.75rem 0;
		font-size: 1.5rem;
		font-weight: 700;
		letter-spacing: -0.02em;
		color: var(--text);
	}

	.coming-soon-desc {
		margin: 0 0 1rem 0;
		font-size: 1rem;
		line-height: 1.6;
		color: var(--muted);
	}

	.coming-soon-cta {
		margin: 0;
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--accent);
	}

	.toolbar {
		flex-shrink: 0;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem;
		margin-top: 1rem;
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

	.color-filter {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 160px;
	}

	.color-filter-label {
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--muted);
	}
	/* Tag filter */
	.tag-filter {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 180px;
	}

	.tag-filter-label {
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--muted);
	}

	.tag-filter-trigger {
		display: inline-flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		width: 100%;
		padding: 0.45rem 0.6rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text);
		font-size: 0.85rem;
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
		font-size: 0.8rem;
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

	/* Shared tag chips (used in cards and tag filter summary) */
	.app-tags-row {
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
	}

	.view-btn {
		padding: 0.5rem 0.65rem;
		background: transparent;
		border: none;
		color: var(--muted);
		cursor: pointer;
		transition: color 0.2s, background 0.2s;
		box-shadow: none;
		transform: none;
	}

	.view-btn:hover {
		color: var(--text);
		background: rgba(255, 255, 255, 0.04);
	}

	.view-btn.active {
		color: var(--accent);
		background: var(--accent-soft);
	}

	.create-btn {
		padding: 0.5rem 1rem;
		background: var(--accent);
		color: var(--accent-contrast, #fff);
		border: none;
		border-radius: 8px;
		font-size: 0.875rem;
		font-weight: 500;
		text-decoration: none;
		cursor: pointer;
		transition: filter 0.2s, box-shadow 0.2s;
		white-space: nowrap;
	}

	.create-btn:hover {
		filter: brightness(1.08);
		box-shadow: 0 2px 8px var(--accent-soft);
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

	.apps-scroll-wrap {
		flex: none;
		padding: 6px 0.25rem 0 0;
	}

	.apps-container {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
		gap: 1rem;
		align-content: start;
		min-height: min-content;
	}

	.apps-container.list-view {
		grid-template-columns: 1fr;
	}

	.app-card {
		position: relative;
		display: flex;
		align-items: stretch;
		gap: 0;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		transition: border-color 0.2s, background 0.2s, box-shadow 0.2s, transform 0.2s ease;
		overflow: hidden;
		box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
		cursor: pointer;
	}

	.app-card-delete-btn {
		border-color: var(--error, #c55);
		color: var(--error, #c55);
		background: color-mix(in srgb, var(--error, #c55) 12%, transparent);
		flex-shrink: 0;
	}
	.app-card-delete-btn:hover {
		border-color: var(--error, #e55);
		color: var(--error, #e55);
		background: color-mix(in srgb, var(--error, #e55) 20%, transparent);
	}

	.app-card:hover {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 10%, var(--card));
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
		transform: translateY(-2px);
	}

	.list-view .app-card:hover {
		transform: none;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
	}

	.app-card:hover .action-btn.primary {
		box-shadow: 0 2px 8px var(--accent-soft);
	}

	.app-card:hover .action-btn.secondary {
		border-color: var(--accent);
		color: var(--accent);
		background: var(--accent-soft);
	}

	.apps-container:not(.list-view) .app-card {
		flex-direction: column;
		min-height: 260px;
	}

	.list-view .app-card {
		flex-direction: column;
		align-items: stretch;
	}

	.card-visual {
		flex-shrink: 0;
		height: 88px;
		background: linear-gradient(135deg, var(--surface) 0%, color-mix(in srgb, var(--accent) 15%, var(--surface)) 100%);
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.5rem 0.6rem;
	}

	.card-visual-dates {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		min-width: 0;
		align-items: flex-end;
		text-align: right;
	}

	.card-visual-date {
		display: flex;
		align-items: baseline;
		gap: 0.4rem;
		font-size: 0.7rem;
		justify-content: flex-end;
	}

	.card-visual-date-label {
		color: rgba(255, 255, 255, 0.5);
		text-transform: uppercase;
		letter-spacing: 0.04em;
		font-weight: 500;
		flex-shrink: 0;
	}

	:global([data-theme="light"]) .card-visual-date-label {
		color: rgba(0, 0, 0, 0.45);
	}

	.card-visual-date-value {
		color: rgba(255, 255, 255, 0.9);
		font-variant-numeric: tabular-nums;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	:global([data-theme="light"]) .card-visual-date-value {
		color: rgba(0, 0, 0, 0.75);
	}

	.card-visual.header-contrast-light .card-visual-date-label {
		color: rgba(255, 255, 255, 0.6);
	}
	.card-visual.header-contrast-light .card-visual-date-value {
		color: rgba(255, 255, 255, 0.95);
	}
	.card-visual.header-contrast-light .card-badge {
		color: rgba(255, 255, 255, 0.95);
		background: rgba(0, 0, 0, 0.28);
	}
	.card-visual.header-contrast-light .card-badge.public {
		color: rgba(255, 255, 255, 0.95);
		background: rgba(255, 255, 255, 0.22);
	}
	.card-visual.header-contrast-dark .card-visual-date-label {
		color: rgba(0, 0, 0, 0.55);
	}
	.card-visual.header-contrast-dark .card-visual-date-value {
		color: rgba(0, 0, 0, 0.9);
	}
	.card-visual.header-contrast-dark .card-badge {
		color: rgba(0, 0, 0, 0.85);
		background: rgba(255, 255, 255, 0.4);
	}
	.card-visual.header-contrast-dark .card-badge.public {
		color: rgba(0, 0, 0, 0.85);
		background: rgba(255, 255, 255, 0.55);
	}

	.list-view .card-visual {
		width: 100%;
		height: 8px;
		min-height: 8px;
		padding: 0;
		justify-content: flex-end;
		align-items: stretch;
	}

	.list-view .card-visual .card-visual-dates {
		display: none;
	}

	.list-view .card-visual .card-badge {
		display: none;
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

	.list-badge {
		flex-shrink: 0;
		font-size: 0.65rem;
		padding: 0.15rem 0.4rem;
	}

	.list-name {
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

	.list-actions {
		flex-shrink: 0;
		margin-top: 0;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.4rem;
	}

	.card-badge {
		font-size: 0.7rem;
		font-weight: 600;
		color: var(--muted);
		background: rgba(0, 0, 0, 0.2);
		padding: 0.2rem 0.45rem;
		border-radius: 6px;
		letter-spacing: 0.02em;
	}

	.card-badge.public {
		color: var(--accent);
		background: var(--accent-soft);
	}

	.card-body {
		flex: 1;
		min-width: 0;
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}

	.apps-container:not(.list-view) .card-body {
		padding-left: 0.65rem;
		padding-right: 0.65rem;
	}

	.list-view .card-body {
		padding: 1rem 1.25rem;
	}

	.app-name-row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.badge-from-image {
		--badge-color: var(--accent);
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.15rem 0.5rem;
		font-size: 0.65rem;
		font-weight: 600;
		letter-spacing: 0.04em;
		text-transform: uppercase;
		border-radius: 999px;
		background: color-mix(in srgb, var(--badge-color) 12%, transparent);
		border: 1px solid color-mix(in srgb, var(--badge-color) 35%, transparent);
		color: color-mix(in srgb, var(--badge-color) 90%, var(--text));
	}
	.app-name {
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

	.app-desc,
	.app-slug {
		margin: 0;
		font-size: 0.8rem;
		color: var(--muted);
		line-height: 1.35;
		display: -webkit-box;
		-webkit-line-clamp: 4;
		-webkit-box-orient: vertical;
		overflow: hidden;
		min-height: 3.6em;
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

	.date-infobox-label {
		color: var(--muted);
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		font-size: 0.7rem;
	}

	.date-infobox-value {
		color: var(--text);
		font-variant-numeric: tabular-nums;
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

	.date-infobox-list .date-infobox-label {
		font-size: 0.65rem;
	}

	.date-infobox-list .date-infobox-value {
		font-size: 0.8rem;
	}

	.date-infobox-sep {
		color: var(--border);
		font-weight: 300;
		user-select: none;
	}

	.card-actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.75rem;
		min-width: 0;
	}
	.card-actions .action-btn {
		min-width: 0;
		flex-shrink: 1;
		white-space: nowrap;
	}
	.card-actions .action-btn.icon-only {
		padding: 0.5rem;
		flex-shrink: 0;
	}
	.card-actions .action-btn.icon-only .action-icon {
		display: block;
	}
	.card-actions .app-card-delete-btn {
		flex-shrink: 0;
	}
	@keyframes spin {
		to { transform: rotate(360deg); }
	}
	.action-icon.spin {
		animation: spin 0.8s linear infinite;
	}

	.apps-container:not(.list-view) .card-actions {
		margin-top: auto;
	}

	.open-with-wrap {
		position: relative;
	}

	.open-with-trigger {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}

	.open-with-trigger .chevron {
		opacity: 0.8;
		transition: transform 0.2s;
	}

	.open-with-wrap:has([aria-expanded="true"]) .chevron {
		transform: rotate(180deg);
	}

	.open-with-menu {
		position: absolute;
		top: 100%;
		left: 0;
		margin-top: 0.25rem;
		min-width: 220px;
		max-width: 300px;
		max-height: 320px;
		display: flex;
		flex-direction: column;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 8px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
		z-index: 20;
		overflow: hidden;
	}

	.open-with-menu-fixed {
		z-index: 99999;
		pointer-events: auto;
	}

	.open-with-filter-wrap {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.6rem;
		border-bottom: 1px solid var(--border);
		background: var(--surface);
	}

	.open-with-filter-icon {
		flex-shrink: 0;
		color: var(--muted);
	}

	.open-with-filter-input {
		flex: 1;
		min-width: 0;
		padding: 0.35rem 0;
		background: transparent;
		border: none;
		color: var(--text);
		font-size: 0.875rem;
		outline: none;
	}

	.open-with-filter-input::placeholder {
		color: var(--muted);
	}

	.open-with-list {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		padding: 0.35rem 0;
	}

	.open-with-empty {
		margin: 0.75rem 0.75rem 0.5rem;
		font-size: 0.8rem;
		color: var(--muted);
	}

	.open-with-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		width: 100%;
		padding: 0.5rem 0.75rem;
		background: transparent;
		border: none;
		border-radius: 0;
		color: var(--text);
		font-size: 0.85rem;
		text-align: left;
		cursor: pointer;
		transition: background 0.15s;
	}

	.open-with-item:hover {
		background: var(--accent-soft);
	}

	.open-with-item:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: -2px;
	}

	.open-with-name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.open-with-meta {
		flex-shrink: 0;
		font-size: 0.75rem;
		color: var(--muted);
	}

	.action-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.4rem 0.75rem;
		border-radius: 6px;
		font-size: 0.8rem;
		font-weight: 500;
		text-decoration: none;
		transition: background 0.2s, color 0.2s, border-color 0.2s;
		cursor: pointer;
		border: 1px solid transparent;
	}

	.action-btn.primary {
		background: var(--accent);
		color: var(--accent-contrast, #fff);
		border-color: var(--accent);
	}

	.action-btn.primary:hover {
		filter: brightness(1.08);
		box-shadow: 0 2px 6px var(--accent-soft);
	}

	.action-btn.secondary {
		background: var(--surface);
		color: var(--text);
		border-color: var(--border);
	}

	.action-btn.secondary:hover,
	a.action-btn.secondary:hover,
	a.action-btn.secondary:focus-visible {
		border-color: var(--accent);
		color: var(--accent);
		background: var(--accent-soft);
	}

	.apps-scroll-wrap::-webkit-scrollbar {
		width: 8px;
	}

	.apps-scroll-wrap::-webkit-scrollbar-track {
		background: transparent;
	}

	.apps-scroll-wrap::-webkit-scrollbar-thumb {
		background: rgba(109, 93, 252, 0.25);
		border-radius: 4px;
	}

	.apps-scroll-wrap::-webkit-scrollbar-thumb:hover {
		background: rgba(109, 93, 252, 0.4);
	}

	.delete-app-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}
	.delete-app-dialog {
		background: var(--card-bg, var(--card));
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 1.5rem;
		min-width: 320px;
		max-width: 440px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
	}
	.delete-app-title {
		margin: 0 0 0.5rem 0;
		font-size: 1.2rem;
		color: var(--text);
	}
	.delete-app-desc {
		margin: 0 0 1rem 0;
		font-size: 0.9rem;
		color: var(--muted);
	}
	.delete-app-error {
		margin: 0 0 1rem 0;
		font-size: 0.9rem;
		color: var(--error, #dc2626);
	}
	.copy-error-text {
		margin: 0 0 0.5rem 0;
		font-size: 0.9rem;
		color: var(--error, #dc2626);
	}
	.delete-app-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.delete-app-btn {
		padding: 0.5rem 1rem;
		font-size: 0.9rem;
		border-radius: 8px;
		cursor: pointer;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
	}
	.delete-app-btn:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}
	.delete-app-btn.secondary:hover:not(:disabled) {
		background: color-mix(in srgb, var(--accent) 15%, var(--surface));
		border-color: var(--accent);
	}
	.delete-app-btn.primary {
		background: var(--accent);
		color: var(--accent-fg, #fff);
		border-color: var(--accent);
	}
	.delete-app-btn.primary:hover:not(:disabled) {
		filter: brightness(1.1);
	}

	@media (max-width: 639px) {
		.apps-page {
			padding: 0.75rem 1rem;
		}
		.apps-page .page-header {
			margin-bottom: 0.75rem;
		}
		.apps-page .header-top h1 {
			font-size: 1.35rem;
		}
		.apps-page .toolbar {
			flex-direction: column;
			align-items: stretch;
			gap: 0.5rem;
		}
		.apps-page .search-wrap {
			max-width: none;
			min-width: 0;
		}
		.apps-page .create-btn {
			width: 100%;
			min-height: 44px;
			justify-content: center;
		}
		.apps-page .apps-container {
			grid-template-columns: 1fr;
			gap: 0.5rem;
		}
		.apps-container:not(.list-view) .app-card {
			min-height: 160px;
		}
		.app-card .card-visual {
			height: 52px;
			padding: 0.35rem 0.5rem;
		}
		.app-card .card-body {
			padding: 0.6rem 0.6rem;
			gap: 0.25rem;
		}
		.app-card .app-name {
			font-size: 0.9rem;
		}
		.app-card .app-desc,
		.app-card .app-slug {
			font-size: 0.75rem;
		}
		.app-card .card-actions .action-btn {
			font-size: 0.8rem;
			padding: 0.4rem 0.65rem;
		}
		.app-card .card-actions .action-btn.icon-only {
			padding: 0.45rem;
		}
		.list-view .card-body.list-body {
			padding: 0.4rem 0.75rem;
		}
	}
</style>
