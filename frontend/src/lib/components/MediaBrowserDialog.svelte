<script lang="ts">
    import { getApiBase } from '$lib/config';
    import { getCookie, setCookie } from '$lib/cookie';
    import FavoriteSash from '$lib/components/FavoriteSash.svelte';
    import LightboxViewer, { type LightboxItem } from '$lib/components/LightboxViewer.svelte';
    import type { MediaBrowserItem, MediaBrowserSelection } from '$lib/types/mediaBrowser';

    type ProjectOption = { id: string; name: string; headerColor?: string | null; lastUsedAt?: number | null };
    type AppOption = { id: string; title: string };

    let {
        open = false,
        initialProjectId = null,
        initialAppId = null,
        onClose = undefined,
        onSelect = undefined
    }: {
        open?: boolean;
        initialProjectId?: string | null;
        initialAppId?: string | null;
        onClose?: (() => void) | undefined;
        onSelect?: ((selection: MediaBrowserSelection) => void) | undefined;
    } = $props();

    const apiBase = getApiBase() || '';
    const PAGE_SIZE = 60;
    const THUMB_SCALE_COOKIE = 'workflowui_media_browser_thumb_scale';
    const FAVORITES_ONLY_COOKIE = 'workflowui_media_browser_favorites_only';

    let projects = $state<ProjectOption[]>([]);
    let apps = $state<AppOption[]>([]);
    let items = $state<MediaBrowserItem[]>([]);
    let total = $state(0);
    let loading = $state(false);
    let loadingMore = $state(false);
    let loadError = $state<string | null>(null);
    let initialized = $state(false);

    let filterProjectId = $state('');
    let filterSource = $state<'all' | 'generation' | 'input'>('all');
    let filterAppId = $state('');
    let filterFromDate = $state('');
    let filterToDate = $state('');
    let filterQ = $state('');
    let filterFavoritesOnly = $state(false);

    let loadSeq = 0;
    let listAbortController: AbortController | null = null;
    let sentinelEl: HTMLDivElement | null = null;
    let dialogEl: HTMLDialogElement | null = null;
    let maximized = $state(false);
    let thumbScale = $state(100);
    let thumbScaleInitialized = $state(false);
    let favoritesOnlyInitialized = $state(false);
    let isMobile = $state(false);
    let moreFiltersOpen = $state(false);
    let projectPickerOpen = $state(false);
    let projectPickerSearch = $state('');
    let previewOpen = $state(false);
    let previewItem = $state<MediaBrowserItem | null>(null);
    let resolutionByKey = $state<Record<string, { width: number; height: number }>>({});
    let failedThumbUrls = $state<Record<string, true>>({});

    const hasMore = $derived(items.length < total);
    const displayedItems = $derived.by(() => {
        let next = items;
        if (filterFavoritesOnly) {
            next = next.filter((item) => item.source === 'generation' && item.is_favorite === true);
        }
        return next.filter((item) => !failedThumbUrls[imageUrlFor(item)]);
    });
    const querySignature = $derived(
        [
            filterProjectId.trim(),
            filterSource,
            filterAppId.trim(),
            filterFromDate.trim(),
            filterToDate.trim(),
            filterQ.trim().toLowerCase(),
            filterFavoritesOnly ? '1' : '0'
        ].join('|')
    );

    function resetFilters() {
        filterProjectId = (initialProjectId ?? '').trim();
        filterSource = 'all';
        filterAppId = '';
        filterFromDate = '';
        filterToDate = '';
        filterQ = '';
        projectPickerSearch = '';
    }

    function clampThumbScale(n: number): number {
        if (!Number.isFinite(n)) return 100;
        return Math.max(70, Math.min(300, Math.round(n)));
    }

    async function loadApps() {
        try {
            const appRes = await fetch(`${apiBase}/apps`);
            if (appRes.ok) {
                const raw = await appRes.json();
                apps = Array.isArray(raw)
                    ? raw
                          .filter((a) => a && typeof a.id === 'string' && typeof a.title === 'string')
                          .map((a) => ({ id: a.id, title: a.title }))
                    : [];
            } else {
                apps = [];
            }
        } catch {
            apps = [];
        }
    }

    async function loadProjects() {
        try {
            const q = new URLSearchParams();
            q.set('source', filterSource);
            if (filterAppId.trim()) q.set('app_id', filterAppId.trim());
            if (filterFromDate.trim()) q.set('since', String(new Date(filterFromDate.trim()).setHours(0, 0, 0, 0)));
            if (filterToDate.trim()) q.set('until', String(new Date(filterToDate.trim()).setHours(23, 59, 59, 999)));
            if (filterQ.trim()) q.set('q', filterQ.trim());
            if (filterFavoritesOnly) q.set('favorites_only', '1');
            const res = await fetch(`${apiBase}/media-browser/projects?${q.toString()}`);
            if (!res.ok) {
                projects = [];
                filterProjectId = '';
                return;
            }
            const payload = await res.json();
            const nextProjects: ProjectOption[] = Array.isArray(payload?.items)
                ? payload.items
                      .filter((p: any) => p && typeof p.id === 'string' && typeof p.name === 'string')
                      .map((p: any) => ({
                          id: p.id,
                          name: p.name,
                          headerColor: typeof p.header_color === 'string' ? p.header_color : null,
                          lastUsedAt: typeof p.last_used_at === 'number' ? p.last_used_at : null
                      }))
                : [];
            projects = nextProjects;
            if (filterProjectId && !nextProjects.some((p) => p.id === filterProjectId)) {
                filterProjectId = '';
            }
            if (initialProjectId && !filterProjectId && nextProjects.some((p) => p.id === initialProjectId)) {
                filterProjectId = initialProjectId;
            }
        } catch {
            projects = [];
            filterProjectId = '';
        }
    }

    async function loadItems(offset = 0) {
        const isInitial = offset === 0;
        const requestId = ++loadSeq;
        if (isInitial) {
            if (listAbortController) listAbortController.abort();
            listAbortController = new AbortController();
            loading = true;
            loadingMore = false;
            loadError = null;
            failedThumbUrls = {};
            resolutionByKey = {};
        } else {
            if (loading || loadingMore || !hasMore) return;
            loadingMore = true;
        }
        const controller = listAbortController ?? new AbortController();
        if (!listAbortController) listAbortController = controller;
        try {
            const q = new URLSearchParams();
            q.set('limit', String(PAGE_SIZE));
            q.set('offset', String(offset));
            q.set('source', filterSource);
            if (filterProjectId.trim()) q.set('project_id', filterProjectId.trim());
            if (filterAppId.trim()) q.set('app_id', filterAppId.trim());
            if (filterFromDate.trim()) {
                q.set('since', String(new Date(filterFromDate.trim()).setHours(0, 0, 0, 0)));
            }
            if (filterToDate.trim()) {
                q.set('until', String(new Date(filterToDate.trim()).setHours(23, 59, 59, 999)));
            }
            if (filterQ.trim()) q.set('q', filterQ.trim());
            if (filterFavoritesOnly) q.set('favorites_only', '1');
            const res = await fetch(`${apiBase}/media-browser/images?${q.toString()}`, { signal: controller.signal });
            if (requestId !== loadSeq) return;
            if (!res.ok) {
                if (isInitial) {
                    items = [];
                    total = 0;
                }
                loadError = `Failed to load media (${res.status})`;
                return;
            }
            const payload = await res.json();
            if (requestId !== loadSeq) return;
            const nextItems = Array.isArray(payload?.items) ? (payload.items as MediaBrowserItem[]) : [];
            total = typeof payload?.total === 'number' ? payload.total : nextItems.length;
            if (isInitial) items = nextItems;
            else items = [...items, ...nextItems];
        } catch (err) {
            if (err instanceof DOMException && err.name === 'AbortError') return;
            if (requestId !== loadSeq) return;
            loadError = 'Failed to load media.';
            if (isInitial) {
                items = [];
                total = 0;
            }
        } finally {
            if (requestId !== loadSeq) {
                if (!isInitial) loadingMore = false;
                return;
            }
            if (isInitial) loading = false;
            else loadingMore = false;
        }
    }

    function loadMore() {
        if (!hasMore || loading || loadingMore) return;
        loadItems(items.length);
    }

    function imageUrlFor(item: MediaBrowserItem): string {
        const params = new URLSearchParams();
        params.set('filename', item.filename);
        params.set('subfolder', item.subfolder || '');
        params.set('type', item.type || 'image');
        if (item.source === 'generation' && item.run_id) {
            params.set('run_id', item.run_id);
        }
        return `${apiBase}/image?${params.toString()}`;
    }

    function choose(item: MediaBrowserItem) {
        onSelect?.({
            source: item.source,
            filename: item.filename,
            runId: item.source === 'generation' ? item.run_id : undefined,
            outputIndex: item.source === 'generation' ? item.output_index : undefined,
            subfolder: item.subfolder || '',
            type: item.type || 'image',
            projectId: item.project_id,
            projectName: item.project_name,
            appId: item.app_id,
            appTitle: item.app_title,
            createdAt: item.created_at
        });
        onClose?.();
    }

    function itemKey(item: MediaBrowserItem, idx: number): string {
        return `${item.run_id}:${item.source}:${item.output_index}:${item.filename}:${idx}`;
    }

    function openPreview(item: MediaBrowserItem) {
        previewItem = item;
        previewOpen = true;
    }

    function closePreview() {
        previewOpen = false;
        previewItem = null;
    }

    function onThumbLoad(item: MediaBrowserItem, idx: number, event: Event) {
        const img = event.currentTarget as HTMLImageElement | null;
        if (!img || !img.naturalWidth || !img.naturalHeight) return;
        const key = itemKey(item, idx);
        const prev = resolutionByKey[key];
        if (prev && prev.width === img.naturalWidth && prev.height === img.naturalHeight) return;
        resolutionByKey = {
            ...resolutionByKey,
            [key]: { width: img.naturalWidth, height: img.naturalHeight }
        };
    }

    function onThumbError(item: MediaBrowserItem) {
        const url = imageUrlFor(item);
        if (failedThumbUrls[url]) return;
        failedThumbUrls = {
            ...failedThumbUrls,
            [url]: true
        };
    }

    const previewItems = $derived.by(() => {
        if (!previewItem) return [] as LightboxItem[];
        return [
            {
                id: `${previewItem.run_id}:${previewItem.output_index}:${previewItem.filename}`,
                url: imageUrlFor(previewItem),
                filename: previewItem.filename,
                mediaType: 'image',
                runId: previewItem.run_id,
                backendRunId: previewItem.run_id,
                outputIndex: previewItem.output_index
            }
        ] as LightboxItem[];
    });

    function handleBackdropClick(e: MouseEvent) {
        if ((e.target as HTMLElement).classList.contains('media-browser-backdrop')) onClose?.();
    }

    function handleKeydown(e: KeyboardEvent) {
        if (e.key === 'Escape') onClose?.();
    }

    function handleDialogClick(e: MouseEvent) {
        if (!dialogEl) return;
        if (e.target === dialogEl) onClose?.();
    }

    function toggleMaximized() {
        maximized = !maximized;
    }

    function selectProject(projectId: string) {
        filterProjectId = projectId;
        projectPickerOpen = false;
        projectPickerSearch = '';
    }

    const filteredProjectOptions = $derived.by(() => {
        const q = projectPickerSearch.trim().toLowerCase();
        if (!q) return projects;
        return projects.filter((p) => p.name.toLowerCase().includes(q));
    });
    const selectedProject = $derived.by(() => projects.find((p) => p.id === filterProjectId) ?? null);
    const activeFilterLabels = $derived.by(() => {
        const labels: string[] = [];
        if (selectedProject) labels.push(selectedProject.name);
        if (filterSource !== 'all') labels.push(filterSource === 'generation' ? 'Generated' : 'Input');
        if (filterFavoritesOnly) labels.push('Favorites');
        if (filterAppId) {
            const app = apps.find((candidate) => candidate.id === filterAppId);
            if (app) labels.push(app.title);
        }
        if (filterFromDate || filterToDate) {
            labels.push(filterFromDate && filterToDate ? `${filterFromDate} to ${filterToDate}` : (filterFromDate || filterToDate));
        }
        return labels;
    });

    function retryLoad() {
        loadError = null;
        loadItems(0);
    }

    function clearSearchFilter() {
        filterQ = '';
    }

    function observeSentinel(node: HTMLDivElement) {
        let observer: IntersectionObserver | null = null;
        if (typeof IntersectionObserver !== 'undefined') {
            observer = new IntersectionObserver((entries) => {
                if (entries.some((entry) => entry.isIntersecting)) loadMore();
            }, { rootMargin: isMobile ? '360px 0px' : '200px 0px' });
            observer.observe(node);
        }
        return {
            destroy() {
                observer?.disconnect();
            }
        };
    }

    let previousSig = $state<string | null>(null);
    let wasOpen = $state(false);
    $effect(() => {
        if (open && !wasOpen) {
            resetFilters();
            loading = true;
            loadError = null;
            items = [];
            total = 0;
            if (!initialized) {
                initialized = true;
                loadApps();
            }
            loadProjects();
        }
        wasOpen = open;
        if (!open) return;
        if (!initialized) {
            initialized = true;
            loadApps();
            loadProjects();
        }
    });
    $effect(() => {
        if (!open) return;
        const sig = querySignature;
        if (previousSig === sig) return;
        previousSig = sig;
        loadItems(0);
    });
    $effect(() => {
        if (typeof window === 'undefined') return;
        const media = window.matchMedia('(max-width: 639px)');
        const update = () => {
            isMobile = media.matches;
        };
        update();
        try {
            media.addEventListener('change', update);
            return () => media.removeEventListener('change', update);
        } catch {
            media.addListener(update);
            return () => media.removeListener(update);
        }
    });
    $effect(() => {
        if (!open) {
            previousSig = null;
            projectsFilterSigPrev = null;
            projectPickerOpen = false;
            moreFiltersOpen = false;
            maximized = false;
            if (listAbortController) {
                listAbortController.abort();
                listAbortController = null;
            }
        }
    });
    $effect(() => {
        if (isMobile) {
            maximized = false;
        }
    });
    $effect(() => {
        if (!dialogEl) return;
        if (open) {
            if (!dialogEl.open) {
                try {
                    dialogEl.showModal();
                } catch {
                    // Ignore if already open in race scenarios.
                }
            }
        } else if (dialogEl.open) {
            dialogEl.close();
        }
    });
    $effect(() => {
        if (thumbScaleInitialized) return;
        thumbScaleInitialized = true;
        const raw = getCookie(THUMB_SCALE_COOKIE);
        const parsed = raw != null ? Number(raw) : NaN;
        thumbScale = clampThumbScale(parsed);
    });
    $effect(() => {
        if (favoritesOnlyInitialized) return;
        favoritesOnlyInitialized = true;
        const raw = getCookie(FAVORITES_ONLY_COOKIE);
        filterFavoritesOnly = raw === '1' || raw === 'true';
    });
    $effect(() => {
        if (!thumbScaleInitialized) return;
        thumbScale = clampThumbScale(Number(thumbScale));
        setCookie(THUMB_SCALE_COOKIE, String(thumbScale));
    });
    $effect(() => {
        if (!favoritesOnlyInitialized) return;
        setCookie(FAVORITES_ONLY_COOKIE, filterFavoritesOnly ? '1' : '0');
    });
    let projectsFilterSigPrev = $state<string | null>(null);
    const projectsFilterSig = $derived(
        [
            filterSource,
            filterAppId.trim(),
            filterFromDate.trim(),
            filterToDate.trim(),
            filterQ.trim().toLowerCase(),
            filterFavoritesOnly ? '1' : '0'
        ].join('|')
    );
    $effect(() => {
        if (!open) return;
        const sig = projectsFilterSig;
        if (projectsFilterSigPrev === sig) return;
        projectsFilterSigPrev = sig;
        loadProjects();
    });
</script>

<dialog
    class="media-browser-dialog"
    bind:this={dialogEl}
    aria-label="Media browser"
    onclick={handleDialogClick}
    onkeydown={handleKeydown}
    onclose={() => {
        if (open) onClose?.();
    }}
>
    <div
        class="media-browser-panel"
        class:maximized={maximized && !isMobile}
        class:mobile={isMobile}
        role="presentation"
        onclick={(e) => e.stopPropagation()}
        onkeydown={(e) => e.stopPropagation()}
        style={`--thumb-scale:${thumbScale};`}
    >
            <div class="media-browser-header">
                <div class="title-wrap">
                    <h2>Browse media</h2>
                    <div class="subtitle">Search by filename, project, app, or metadata phrases</div>
                </div>
                <div class="header-actions">
                    {#if !isMobile}
                        <button
                            type="button"
                            class="icon-btn"
                            onclick={toggleMaximized}
                            aria-label={maximized ? 'Restore dialog size' : 'Maximize dialog'}
                            title={maximized ? 'Restore' : 'Maximize'}
                        >
                            {#if maximized}
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                    <rect x="7" y="7" width="10" height="10" rx="1"></rect>
                                </svg>
                            {:else}
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                    <path d="M8 3H5a2 2 0 0 0-2 2v3"></path>
                                    <path d="M16 3h3a2 2 0 0 1 2 2v3"></path>
                                    <path d="M8 21H5a2 2 0 0 1-2-2v-3"></path>
                                    <path d="M16 21h3a2 2 0 0 0 2-2v-3"></path>
                                </svg>
                            {/if}
                        </button>
                    {/if}
                    <button type="button" class="icon-btn close-btn" onclick={onClose} aria-label="Close media browser" title="Close">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                            <path d="M18 6L6 18M6 6l12 12"/>
                        </svg>
                    </button>
                </div>
            </div>
            <div class="search-row">
                <div class="search-left">
                    <div class="primary-search-wrap">
                        <input
                            type="search"
                            class="primary-search"
                            placeholder="Search filename, project, app, or metadata…"
                            bind:value={filterQ}
                            aria-label="Search media"
                        />
                        {#if filterQ}
                            <button
                                type="button"
                                class="search-clear-btn"
                                onclick={clearSearchFilter}
                                aria-label="Clear search"
                                title="Clear search"
                            >
                                Clear
                            </button>
                        {/if}
                    </div>
                    <div class="search-helpers">
                        <div class="search-tip">
                            Tip: search phrases from metadata (prompt text, model names, sampler, LoRA, seed).
                        </div>
                    </div>
                </div>
                <div class="search-right">
                    <label class="favorites-filter-option" title="Show only favorited generations">
                        <span class="favorites-filter-label">Favorites only</span>
                        <button
                            type="button"
                            class="favorites-filter-toggle"
                            class:on={filterFavoritesOnly}
                            aria-pressed={filterFavoritesOnly}
                            aria-label="Toggle favorites only"
                            onclick={() => (filterFavoritesOnly = !filterFavoritesOnly)}
                        >
                            <span class="favorites-filter-toggle-track">
                                <span class="favorites-filter-toggle-thumb"></span>
                            </span>
                        </button>
                    </label>
                    {#if isMobile}
                        <select bind:value={filterSource} aria-label="Filter by source" class="mobile-source">
                            <option value="all">All</option>
                            <option value="generation">Generated</option>
                            <option value="input">Input</option>
                        </select>
                        <button
                            type="button"
                            class="mobile-filters-toggle"
                            onclick={() => (moreFiltersOpen = !moreFiltersOpen)}
                            aria-expanded={moreFiltersOpen}
                            aria-controls="mobile-more-filters"
                        >
                            {moreFiltersOpen ? 'Hide filters' : 'More filters'}
                        </button>
                    {:else}
                        <label class="thumb-size-control" for="thumb-size-slider">
                            <span>Thumbs</span>
                            <input
                                id="thumb-size-slider"
                                type="range"
                                min="70"
                                max="300"
                                step="5"
                                bind:value={thumbScale}
                                aria-label="Thumbnail size percent"
                            />
                            <span class="thumb-size-value">{thumbScale}%</span>
                        </label>
                    {/if}
                </div>
            </div>
            {#if isMobile && activeFilterLabels.length > 0}
                <div class="active-filters" aria-label="Active filters">
                    {#each activeFilterLabels as label}
                        <span class="filter-chip">{label}</span>
                    {/each}
                </div>
            {/if}
            <div class="filters" class:mobile-hidden={isMobile && !moreFiltersOpen} id="mobile-more-filters">
                <div class="project-picker-wrap">
                    <button
                        type="button"
                        class="project-picker-toggle"
                        onclick={() => (projectPickerOpen = !projectPickerOpen)}
                        aria-label="Filter by project"
                        aria-expanded={projectPickerOpen}
                    >
                        <span class="project-picker-label">
                            {#if selectedProject}
                                <span class="project-color-dot" style={selectedProject.headerColor ? `background:${selectedProject.headerColor}` : ''}></span>
                                <span class="project-picker-name">{selectedProject.name}</span>
                            {:else}
                                <span class="project-color-dot neutral"></span>
                                <span class="project-picker-name">All projects</span>
                            {/if}
                        </span>
                        <span class="project-picker-chevron">▾</span>
                    </button>
                    {#if projectPickerOpen}
                        <div class="project-picker-popover">
                            <input
                                type="search"
                                class="project-picker-search"
                                placeholder="Filter projects…"
                                bind:value={projectPickerSearch}
                                aria-label="Filter projects list"
                            />
                            <div class="project-picker-list">
                                <button type="button" class="project-option" onclick={() => selectProject('')}>
                                    <span class="project-color-dot neutral"></span>
                                    <span class="project-option-name">All projects</span>
                                </button>
                                {#each filteredProjectOptions as p (p.id)}
                                    <button type="button" class="project-option" onclick={() => selectProject(p.id)}>
                                        <span class="project-color-dot" style={p.headerColor ? `background:${p.headerColor}` : ''}></span>
                                        <span class="project-option-name">{p.name}</span>
                                    </button>
                                {/each}
                            </div>
                        </div>
                    {/if}
                </div>
                {#if !isMobile}
                    <select bind:value={filterSource} aria-label="Filter by source">
                        <option value="all">All sources</option>
                        <option value="generation">Generated outputs</option>
                        <option value="input">Uploaded inputs</option>
                    </select>
                {/if}
                <select bind:value={filterAppId} aria-label="Filter by app">
                    <option value="">All apps</option>
                    {#each apps as app (app.id)}
                        <option value={app.id}>{app.title}</option>
                    {/each}
                </select>
                <input type="date" bind:value={filterFromDate} aria-label="From date" />
                <input type="date" bind:value={filterToDate} aria-label="To date" />
                {#if isMobile}
                    <label class="thumb-size-control mobile-thumb-size" for="thumb-size-slider-mobile">
                        <span>Thumbnail size</span>
                        <input
                            id="thumb-size-slider-mobile"
                            type="range"
                            min="70"
                            max="300"
                            step="5"
                            bind:value={thumbScale}
                            aria-label="Thumbnail size percent"
                        />
                        <span class="thumb-size-value">{thumbScale}%</span>
                    </label>
                {/if}
            </div>
            <div class="results">
                {#if loading}
                    <div class="state loading-state">
                        <span class="loading-spinner" aria-hidden="true"></span>
                        <span>Preparing media browser…</span>
                    </div>
                {:else if loadError}
                    <div class="state error with-action">
                        <span>{loadError}</span>
                        <button type="button" class="retry-btn" onclick={retryLoad}>Retry</button>
                    </div>
                {:else if displayedItems.length === 0}
                    <div class="state">No media matches the current filters.</div>
                {:else}
                    <div class="media-grid">
                        {#each displayedItems as item, idx (itemKey(item, idx))}
                            <div
                                class="media-card"
                                role="button"
                                tabindex="0"
                                onclick={() => choose(item)}
                                onkeydown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                        e.preventDefault();
                                        choose(item);
                                    }
                                }}
                                title={item.filename}
                            >
                                <FavoriteSash visible={item.is_favorite === true} />
                                <button
                                    type="button"
                                    class="thumb-preview-btn"
                                    aria-label="Preview full image"
                                    title="Preview full image"
                                    onclick={(e) => {
                                        e.stopPropagation();
                                        openPreview(item);
                                    }}
                                >
                                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8S1 12 1 12z"></path>
                                        <circle cx="12" cy="12" r="3"></circle>
                                    </svg>
                                </button>
                                {#if resolutionByKey[itemKey(item, idx)]}
                                    {@const dim = resolutionByKey[itemKey(item, idx)]}
                                    <div class="thumb-resolution-badge">{dim.width}×{dim.height}</div>
                                {/if}
                                <img
                                    src={imageUrlFor(item)}
                                    alt=""
                                    loading="lazy"
                                    referrerpolicy="no-referrer"
                                    onload={(e) => onThumbLoad(item, idx, e)}
                                    onerror={() => onThumbError(item)}
                                />
                                <div class="meta">
                                    <div class="name">{item.filename}</div>
                                    <div class="sub">
                                        {item.project_name} · {item.source === 'input' ? 'Input' : 'Output'}
                                    </div>
                                </div>
                            </div>
                        {/each}
                    </div>
                    <div bind:this={sentinelEl} use:observeSentinel class="sentinel"></div>
                    {#if loadingMore}
                        <div class="state loading-state">
                            <span class="loading-spinner" aria-hidden="true"></span>
                            <span>Loading more…</span>
                        </div>
                    {/if}
                {/if}
            </div>
    </div>
    <LightboxViewer
        open={previewOpen}
        items={previewItems}
        index={0}
        onClose={closePreview}
        onIndexChange={() => {}}
        ariaTitle="Media preview"
    />
</dialog>

<style>
    .media-browser-dialog {
        margin: auto;
        padding: 0;
        border: none;
        background: transparent;
        width: 100%;
        max-width: none;
        max-height: none;
        overflow: visible;
    }
    .media-browser-dialog::backdrop {
        background: rgba(0, 0, 0, 0.55);
    }
    .media-browser-panel {
        width: min(1100px, 95vw);
        max-height: 90vh;
        margin: 1rem auto;
        display: flex;
        flex-direction: column;
        background: var(--card-bg, var(--card));
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
    }
    .media-browser-panel.mobile {
        width: 100vw;
        max-width: 100vw;
        height: 100dvh;
        max-height: 100dvh;
        margin: 0;
        border-radius: 0;
        border-left: none;
        border-right: none;
    }
    .media-browser-panel.maximized {
        width: calc(100vw - 2rem);
        max-height: calc(100vh - 2rem);
        height: calc(100vh - 2rem);
    }
    .media-browser-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.8rem 1rem;
        border-bottom: 1px solid var(--border);
        gap: 0.75rem;
        position: sticky;
        top: 0;
        z-index: 5;
        background: var(--card-bg, var(--card));
    }
    .title-wrap {
        display: flex;
        flex-direction: column;
        min-width: 0;
    }
    .media-browser-header h2 {
        margin: 0;
        font-size: 1rem;
    }
    .subtitle {
        margin-top: 0.2rem;
        font-size: 0.78rem;
        color: var(--muted);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .header-actions {
        display: inline-flex;
        align-items: center;
        gap: 0.45rem;
        flex-shrink: 0;
    }
    .icon-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        min-width: 32px;
        min-height: 32px;
        padding: 0;
        border-radius: 8px;
        border: 1px solid color-mix(in srgb, var(--border) 80%, transparent);
        background: color-mix(in srgb, var(--surface, #111827) 75%, transparent);
        color: var(--text);
        cursor: pointer;
        line-height: 1;
        box-shadow: none;
        transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    }
    .icon-btn svg {
        width: 16px;
        height: 16px;
        display: block;
    }
    .icon-btn:hover {
        color: var(--accent);
        border-color: var(--accent);
        background: color-mix(in srgb, var(--accent) 14%, transparent);
    }
    .icon-btn:focus-visible {
        outline: 2px solid var(--accent);
        outline-offset: 2px;
    }
    .search-row {
        padding: 0.75rem 1rem 0.55rem;
        border-bottom: 1px solid var(--border);
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 0.75rem;
        align-items: start;
    }
    .search-left {
        min-width: 0;
    }
    .search-right {
        display: inline-flex;
        align-items: center;
        justify-content: flex-end;
        flex-wrap: wrap;
        gap: 0.65rem;
    }
    .primary-search {
        width: 100%;
        min-width: 0;
        padding: 0.62rem 0.75rem;
        border-radius: 8px;
        border: 1px solid var(--border);
        background: var(--surface, #111827);
        color: var(--text);
        font-size: 0.95rem;
    }
    .primary-search-wrap {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        align-items: center;
        gap: 0.5rem;
    }
    .search-clear-btn {
        min-height: 36px;
        padding: 0.35rem 0.6rem;
        border-radius: 8px;
        border: 1px solid var(--border);
        background: color-mix(in srgb, var(--surface, #111827) 75%, transparent);
        color: var(--text);
        box-shadow: none;
        font-size: 0.78rem;
    }
    .primary-search:focus {
        outline: none;
        border-color: var(--accent);
        box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 20%, transparent);
    }
    .search-helpers {
        margin-top: 0.5rem;
        display: block;
    }
    .search-tip {
        font-size: 0.75rem;
        color: var(--muted);
    }
    .filters {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 0.5rem;
        padding: 0.75rem 1rem;
        border-bottom: 1px solid var(--border);
    }
    .filters.mobile-hidden {
        display: none;
    }
    .filters input,
    .filters select {
        min-width: 0;
        padding: 0.45rem 0.55rem;
        border-radius: 6px;
        border: 1px solid var(--border);
        background: var(--surface, #111827);
        color: var(--text);
    }
    .favorites-filter-option {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
    }
    .favorites-filter-label {
        font-size: 0.82rem;
        color: var(--muted);
    }
    .favorites-filter-toggle {
        border: none;
        background: transparent;
        padding: 0;
        cursor: pointer;
    }
    .favorites-filter-toggle-track {
        width: 2.2rem;
        height: 1.2rem;
        border-radius: 999px;
        background: color-mix(in srgb, var(--border) 75%, transparent);
        display: inline-flex;
        align-items: center;
        padding: 0 0.15rem;
        transition: background 0.2s ease;
    }
    .favorites-filter-toggle-thumb {
        width: 0.85rem;
        height: 0.85rem;
        border-radius: 999px;
        background: var(--muted);
        transition: transform 0.2s ease, background 0.2s ease;
    }
    .favorites-filter-toggle.on .favorites-filter-toggle-track {
        background: color-mix(in srgb, var(--accent) 30%, transparent);
    }
    .favorites-filter-toggle.on .favorites-filter-toggle-thumb {
        transform: translateX(0.95rem);
        background: var(--accent);
    }
    .thumb-size-control {
        display: inline-flex;
        align-items: center;
        gap: 0.6rem;
        font-size: 0.82rem;
        color: var(--muted);
    }
    .thumb-size-control input[type="range"] {
        width: 150px;
    }
    .mobile-thumb-size {
        grid-column: 1 / -1;
        justify-content: space-between;
        padding: 0.2rem 0;
    }
    .thumb-size-value {
        font-variant-numeric: tabular-nums;
        color: var(--text);
        min-width: 3.3rem;
        text-align: right;
    }
    .project-picker-wrap {
        position: relative;
    }
    .project-picker-toggle {
        width: 100%;
        min-width: 0;
        padding: 0.45rem 0.55rem;
        border-radius: 6px;
        border: 1px solid var(--border);
        background: var(--surface, #111827);
        color: var(--text);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        cursor: pointer;
    }
    .project-picker-label {
        min-width: 0;
        display: flex;
        align-items: center;
        gap: 0.45rem;
    }
    .project-picker-name {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        text-align: left;
    }
    .project-picker-chevron {
        color: var(--muted);
        flex-shrink: 0;
    }
    .project-picker-popover {
        position: absolute;
        top: calc(100% + 0.35rem);
        left: 0;
        width: min(360px, 70vw);
        border: 1px solid var(--border);
        border-radius: 8px;
        background: var(--card-bg, var(--card));
        z-index: 200;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        padding: 0.45rem;
    }
    .project-picker-search {
        width: 100%;
        margin-bottom: 0.4rem;
        padding: 0.45rem 0.55rem;
        border: 1px solid var(--border);
        border-radius: 6px;
        background: var(--surface, #111827);
        color: var(--text);
    }
    .project-picker-list {
        max-height: 260px;
        overflow: auto;
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
    }
    .project-option {
        width: 100%;
        border: 1px solid transparent;
        border-radius: 6px;
        background: rgba(255, 255, 255, 0.02);
        color: inherit;
        cursor: pointer;
        text-align: left;
        padding: 0.35rem 0.45rem;
        display: flex;
        align-items: center;
        gap: 0.45rem;
    }
    .project-option:hover {
        border-color: var(--accent);
        background: rgba(255, 255, 255, 0.05);
    }
    .project-option-name {
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .project-color-dot {
        width: 0.62rem;
        height: 0.62rem;
        border-radius: 999px;
        background: var(--muted);
        flex-shrink: 0;
    }
    .project-color-dot.neutral {
        opacity: 0.6;
    }
    .results {
        overflow: auto;
        padding: 0.75rem 1rem 1rem;
    }
    .media-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(clamp(140px, calc(180px * var(--thumb-scale) / 100), 540px), clamp(140px, calc(180px * var(--thumb-scale) / 100), 540px)));
        justify-content: start;
        gap: 0.75rem;
    }
    .media-card {
        position: relative;
        border: 1px solid var(--border);
        background: rgba(255, 255, 255, 0.03);
        border-radius: 8px;
        padding: 0.4rem;
        color: inherit;
        text-align: left;
        cursor: pointer;
        overflow: hidden;
    }
    .media-card:hover {
        border-color: var(--accent);
        background: rgba(255, 255, 255, 0.06);
    }
    .media-card img {
        width: 100%;
        aspect-ratio: 1/1;
        object-fit: cover;
        display: block;
        border-radius: 6px;
        background: #111;
    }
    .thumb-preview-btn {
        position: absolute;
        top: 0.65rem;
        right: 0.65rem;
        width: 26px;
        height: 26px;
        border-radius: 999px;
        border: 1px solid color-mix(in srgb, var(--border) 80%, transparent);
        background: rgba(0, 0, 0, 0.58);
        color: #f6f8ff;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        z-index: 2;
        cursor: pointer;
        padding: 0;
        opacity: 0.9;
    }
    .thumb-preview-btn svg {
        width: 14px;
        height: 14px;
        display: block;
    }
    .thumb-preview-btn:hover {
        border-color: var(--accent);
        color: white;
        background: color-mix(in srgb, var(--accent) 42%, rgba(0, 0, 0, 0.5));
        opacity: 1;
    }
    .thumb-resolution-badge {
        position: absolute;
        top: 0.65rem;
        left: 0.65rem;
        z-index: 2;
        font-size: 0.68rem;
        line-height: 1;
        padding: 0.22rem 0.38rem;
        border-radius: 999px;
        border: 1px solid color-mix(in srgb, var(--border) 75%, transparent);
        background: rgba(0, 0, 0, 0.62);
        color: #f2f5ff;
        font-variant-numeric: tabular-nums;
        pointer-events: none;
    }
    .meta {
        margin-top: 0.4rem;
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
        min-width: 0;
    }
    .name,
    .sub {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .name {
        font-size: 0.78rem;
    }
    .sub {
        font-size: 0.72rem;
        color: var(--muted);
    }
    .state {
        font-size: 0.85rem;
        color: var(--muted);
        padding: 0.5rem 0.25rem;
    }
    .state.with-action {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.6rem;
    }
    .state.loading-state {
        display: inline-flex;
        align-items: center;
        gap: 0.55rem;
    }
    .loading-spinner {
        width: 16px;
        height: 16px;
        border-radius: 999px;
        border: 2px solid color-mix(in srgb, var(--border) 75%, transparent);
        border-top-color: var(--accent);
        animation: media-browser-spin 0.8s linear infinite;
        flex-shrink: 0;
    }
    @keyframes media-browser-spin {
        to {
            transform: rotate(360deg);
        }
    }
    .state.error {
        color: var(--error, #e57373);
    }
    .retry-btn {
        padding: 0.4rem 0.65rem;
        min-height: 36px;
        border-radius: 8px;
        border: 1px solid var(--border);
        background: color-mix(in srgb, var(--surface, #111827) 75%, transparent);
        color: var(--text);
        box-shadow: none;
    }
    .active-filters {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        padding: 0.55rem 1rem 0;
    }
    .filter-chip {
        display: inline-flex;
        align-items: center;
        height: 1.5rem;
        padding: 0 0.55rem;
        border-radius: 999px;
        border: 1px solid color-mix(in srgb, var(--accent) 35%, var(--border));
        background: color-mix(in srgb, var(--accent) 14%, transparent);
        color: var(--text);
        font-size: 0.72rem;
    }
    .mobile-source {
        min-height: 38px;
        min-width: 104px;
    }
    .mobile-filters-toggle {
        min-height: 38px;
        padding: 0.35rem 0.65rem;
        font-size: 0.82rem;
        border-radius: 8px;
        border: 1px solid var(--border);
        background: color-mix(in srgb, var(--surface, #111827) 75%, transparent);
        color: var(--text);
        box-shadow: none;
    }
    .sentinel {
        width: 100%;
        height: 1px;
    }
    @media (max-width: 639px) {
        .media-browser-dialog {
            width: 100vw;
            height: 100dvh;
            max-width: 100vw;
            max-height: 100dvh;
            margin: 0;
            overflow: hidden;
        }
        .media-browser-header {
            padding-top: calc(0.75rem + env(safe-area-inset-top));
            padding-inline: 0.75rem;
        }
        .subtitle {
            display: none;
        }
        .search-row {
            grid-template-columns: 1fr;
            gap: 0.55rem;
            padding: 0.65rem 0.75rem;
        }
        .search-clear-btn {
            min-height: 44px;
        }
        .search-helpers {
            display: none;
        }
        .search-right {
            justify-content: flex-start;
        }
        .filters {
            grid-template-columns: 1fr;
            gap: 0.55rem;
            padding: 0.6rem 0.75rem 0.7rem;
        }
        .filters input,
        .filters select,
        .project-picker-toggle,
        .project-picker-search,
        .project-option {
            min-height: 44px;
        }
        .project-picker-popover {
            position: relative;
            top: 0.5rem;
            width: 100%;
            max-width: 100%;
        }
        .results {
            padding: 0.65rem 0.75rem calc(0.85rem + env(safe-area-inset-bottom));
        }
        .media-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.55rem;
        }
        .media-card {
            padding: 0.32rem;
        }
        .thumb-preview-btn {
            width: 34px;
            height: 34px;
            top: 0.45rem;
            right: 0.45rem;
        }
        .thumb-preview-btn svg {
            width: 17px;
            height: 17px;
        }
        .thumb-resolution-badge {
            top: 0.45rem;
            left: 0.45rem;
            font-size: 0.64rem;
        }
        .name {
            font-size: 0.74rem;
        }
        .sub {
            font-size: 0.68rem;
        }
        .icon-btn {
            width: 40px;
            height: 40px;
            min-width: 40px;
            min-height: 40px;
        }
        .favorites-filter-toggle-track {
            width: 2.45rem;
            height: 1.35rem;
        }
        .favorites-filter-toggle-thumb {
            width: 0.95rem;
            height: 0.95rem;
        }
        .favorites-filter-toggle.on .favorites-filter-toggle-thumb {
            transform: translateX(1.08rem);
        }
    }
</style>
