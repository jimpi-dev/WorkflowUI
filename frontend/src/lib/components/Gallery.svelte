<script lang="ts">
    import { browser } from '$app/environment';
    import { tick } from 'svelte';
    import {
        getThumbFitModeCookie,
        getThumbSizeCookie,
        setThumbFitModeCookie,
        setThumbSizeCookie,
        type ThumbFitMode,
        type ThumbSize
    } from '$lib/cookie';
    import ThumbnailOverlay from '$lib/components/ThumbnailOverlay.svelte';
    import RunHeaderActions from '$lib/components/RunHeaderActions.svelte';
    import RunAppBadge from '$lib/components/RunAppBadge.svelte';
    import LightboxViewer, { type LightboxItem } from '$lib/components/LightboxViewer.svelte';

    export type GalleryImage = {
        id: string;
        url: string;
        previewUrl?: string;
        filename?: string;
        promptId: string;
        backendRunId: string;
        seed?: number;
        outputIndex?: number;
        executionTimeSec?: number;
        mediaType?: 'image' | 'video' | 'audio';
        remote_deleted?: boolean;
    };

    export type StorageState = {
        local_storage_status?: string;
        remote_status?: string;
        local_path?: string;
    };

    export type RunGroup = {
        id: string;
        createdAt: number;
        seed?: number;
        images: GalleryImage[];
        status: 'queued' | 'running' | 'done' | 'error' | 'cancelled';
        queue_position?: number;
        workflowName?: string;
        appTitle?: string | null;
        runCount?: number;
        totalRuntimeSec?: number;
        inputs?: Record<string, any>;
        error?: string;
        backendRunIds: string[];
        storageByBackend: Record<string, StorageState>;
    };

    let {
        runs = [],
        outputLabels = [],
        runningProgress = {},
        savingRunIds = new Set(),
        deletingRunIds = new Set(),
        deletingLocalRunIds = new Set(),
        deletingBothRunIds = new Set(),
        savingImageKeys = new Set(),
        deletingImageKeys = new Set(),
        deletingLocalImageKeys = new Set(),
        deletingBothImageKeys = new Set(),
        manualSaveDisabled = false,
        showPreviewActions = true,
        comfyuiDeleteSupported = true,
        favoriteRunIds = new Set() as Set<string>,
        onToggleFavorite = undefined as ((backendRunId: string) => void) | undefined,
        onSaveRun,
        onDeleteRemoteRun,
        onDeleteLocalRun,
        onDeleteBothRun,
        onCancelRunGroup,
        cancellingRunIds = new Set(),
        onSaveImage,
        onDeleteRemoteImage,
        onDeleteLocalImage,
        onDeleteBothImage,
        onSendToApp = undefined as ((backendRunId: string, outputIndex: number) => void) | undefined,
        appHeaderColor = undefined as string | null | undefined,
        onMetadataClick = undefined as ((run: RunGroup, image: GalleryImage) => void) | undefined,
        onDeleteRemoteSelected = undefined as ((runId: string, images: GalleryImage[]) => void) | undefined,
        onDeleteLocalSelected = undefined as ((runId: string, images: GalleryImage[]) => void) | undefined,
        onDeleteBothSelected = undefined as ((runId: string, images: GalleryImage[]) => void) | undefined,
        onDeleteRun = undefined as ((runId: string, backendRunIds: string[]) => void) | undefined,
        onReplicateRun = undefined as ((runId: string, appSlug: string) => void) | undefined,
        onShowRunMetadata = undefined as ((backendRunId: string) => void) | undefined,
        appSlugForReplicate = undefined as string | null | undefined,
        onLightboxOpenChange = undefined as ((open: boolean) => void) | undefined,
        onRunFocusChange = undefined as ((focused: boolean) => void) | undefined
    }: {
        runs?: RunGroup[];
        outputLabels?: (string | undefined)[];
        runningProgress?: Record<string, number>;
        savingRunIds?: Set<string>;
        deletingRunIds?: Set<string>;
        deletingLocalRunIds?: Set<string>;
        deletingBothRunIds?: Set<string>;
        savingImageKeys?: Set<string>;
        deletingImageKeys?: Set<string>;
        deletingLocalImageKeys?: Set<string>;
        deletingBothImageKeys?: Set<string>;
        manualSaveDisabled?: boolean;
        showPreviewActions?: boolean;
        comfyuiDeleteSupported?: boolean;
        favoriteRunIds?: Set<string>;
        onToggleFavorite?: (backendRunId: string) => void;
        onSaveRun?: (runId: string, backendRunIds: string[]) => void;
        onDeleteRemoteRun?: (runId: string, backendRunIds: string[]) => void;
        onDeleteLocalRun?: (runId: string, backendRunIds: string[]) => void;
        onDeleteBothRun?: (runId: string, backendRunIds: string[]) => void;
        onCancelRunGroup?: (runId: string, backendRunIds: string[]) => void;
        cancellingRunIds?: Set<string>;
        onSaveImage?: (runId: string, image: GalleryImage) => void;
        onDeleteRemoteImage?: (runId: string, image: GalleryImage) => void;
        onDeleteLocalImage?: (runId: string, image: GalleryImage) => void;
        onDeleteBothImage?: (runId: string, image: GalleryImage) => void;
        onSendToApp?: (backendRunId: string, outputIndex: number) => void;
        onMetadataClick?: (run: RunGroup, image: GalleryImage) => void;
        onDeleteRemoteSelected?: (runId: string, images: GalleryImage[]) => void;
        onDeleteLocalSelected?: (runId: string, images: GalleryImage[]) => void;
        onDeleteBothSelected?: (runId: string, images: GalleryImage[]) => void;
        onDeleteRun?: (runId: string, backendRunIds: string[]) => void;
        onReplicateRun?: (runId: string, appSlug: string) => void;
        onShowRunMetadata?: (backendRunId: string) => void;
        appSlugForReplicate?: string | null;
        appHeaderColor?: string | null;
        onLightboxOpenChange?: (open: boolean) => void;
        onRunFocusChange?: (focused: boolean) => void;
    } = $props();

    let flatImages = $derived(runs.flatMap(r => r.images));

    let lightboxRunId = $state<string | null>(null);
    let lightboxSeedFilter = $state<number[] | null>(null);

    let lightboxOpen = $state(false);
    let lightboxIndex = $state(0);

    let playingAudioThumbKey = $state<string | null>(null);

    let galleryEl: HTMLDivElement | null = null;

    $effect(() => {
        if (galleryEl && runs.length) {
            tick().then(() => {
                galleryEl?.scrollTo({ left: 0, behavior: 'smooth' });
            });
        }
    });

    $effect(() => {
        onLightboxOpenChange?.(lightboxOpen);
    });

    let lightboxImages = $derived.by(() => {
        if (lightboxRunId) {
            const run = runs.find((r) => r.id === lightboxRunId);
            if (run) {
                const selected = run.images.filter((img) => selectedImageKeys.has(`${run.id}-${img.id}`));
                if (selected.length > 0) {
                    return selected;
                }
                return getFilteredImagesForRun(run);
            }
        }
        return flatImages;
    });

    let lightboxRun = $derived(lightboxRunId ? runs.find((r) => r.id === lightboxRunId) ?? null : null);


    function groupByOutputIndex(images: GalleryImage[]): [string, GalleryImage[]][] {
        const groups: Record<string, GalleryImage[]> = {};
        for (const img of images) {
            const key = String(img.outputIndex ?? img.promptId ?? '0');
            groups[key] ??= [];
            groups[key].push(img);
        }
        const entries = Object.entries(groups);
        entries.sort(([a], [b]) => {
            const na = Number(a);
            const nb = Number(b);
            if (!Number.isNaN(na) && !Number.isNaN(nb)) return na - nb;
            return a.localeCompare(b);
        });
        return entries;
    }

    let seedFilterByRun = $state<Record<string, number[]>>({});
    function addSeedToFilter(runId: string, seed: number) {
        const n = Number(seed);
        const prev = seedFilterByRun[runId] ?? [];
        if (prev.includes(n)) return;
        seedFilterByRun = { ...seedFilterByRun, [runId]: [...prev, n] };
    }
    function removeSeedFromFilter(runId: string, seed: number) {
        const n = Number(seed);
        const prev = seedFilterByRun[runId] ?? [];
        const next = prev.filter((s) => s !== n);
        if (next.length === 0) {
            const { [runId]: _, ...rest } = seedFilterByRun;
            seedFilterByRun = rest;
        } else {
            seedFilterByRun = { ...seedFilterByRun, [runId]: next };
        }
    }
    function toggleSeedInFilter(runId: string, seed: number) {
        const prev = seedFilterByRun[runId] ?? [];
        if (prev.includes(seed)) removeSeedFromFilter(runId, seed);
        else addSeedToFilter(runId, seed);
    }
    function clearSeedFilter(runId: string) {
        const { [runId]: _, ...rest } = seedFilterByRun;
        seedFilterByRun = rest;
    }
    function hasActiveSeedFilter(runId: string): boolean {
        const seeds = seedFilterByRun[runId];
        return !!seeds?.length;
    }
    function getFilteredImagesForRun(run: RunGroup): GalleryImage[] {
        const seeds = seedFilterByRun[run.id];
        if (!seeds?.length) return run.images;
        return run.images.filter((img) => img.seed != null && seeds.includes(Number(img.seed)));
    }

    function getDisplayImagesForRun(run: RunGroup): GalleryImage[] {
        return run.images;
    }

    function getRunStorageSummary(run: RunGroup): { label: string; tone: string } | null {
        if (!run.backendRunIds?.length) return null;
        const states = run.backendRunIds.map((id) => run.storageByBackend[id]?.local_storage_status);
        const allSaved = states.length > 0 && states.every((s) => s === 'saved');
        const anySaved = states.some((s) => s === 'saved');
        const anyPartial = states.some((s) => s === 'partial');
        const anyFailed = states.some((s) => s === 'failed');
        if (allSaved) return { label: 'Fully Saved', tone: 'saved' };
        if (anySaved || anyPartial) return { label: 'Partially Saved', tone: 'partial' };
        if (anyFailed) return { label: 'Failed', tone: 'failed' };
        return { label: 'Remote Only', tone: 'remote' };
    }

    function getImageStatus(run: RunGroup, img: GalleryImage): { label: string; tone: string } | null {
        const key = `${img.backendRunId}:${img.outputIndex ?? -1}`;
        if (savingImageKeys.has(key)) return { label: 'Saving', tone: 'saving' };
        if (deletingImageKeys.has(key)) return { label: 'Deleting', tone: 'saving' };
        const st = run.storageByBackend?.[img.backendRunId];
        if (st?.local_storage_status === 'saved') return { label: 'Saved', tone: 'saved' };
        if (st?.local_storage_status === 'partial') return { label: 'Partial', tone: 'partial' };
        if (st?.local_storage_status === 'failed') return { label: 'Failed', tone: 'failed' };
        if (st?.remote_status === 'deleted') return { label: 'Deleted (remote)', tone: 'deleted' };
        return null;
    }

    function isImageInFilter(runId: string, seed: number | undefined): boolean {
        if (seed == null) return false;
        const seeds = seedFilterByRun[runId] ?? [];
        return seeds.includes(Number(seed));
    }

    function getResolutionFromInputs(inputs: Record<string, any> | undefined): { width: number; height: number } | null {
        if (!inputs || typeof inputs !== 'object') return null;
        let w: number | null = null;
        let h: number | null = null;
        for (const [key, value] of Object.entries(inputs)) {
            const n = Number(value);
            if (Number.isNaN(n)) continue;
            if (key.endsWith('.width') || key.endsWith('.width_override')) w = n;
            if (key.endsWith('.height') || key.endsWith('.height_override')) h = n;
        }
        if (w != null && h != null && w > 0 && h > 0) return { width: w, height: h };
        return null;
    }

    function getOrientationLabel(width: number, height: number): 'portrait' | 'landscape' | 'square' {
        if (width === height) return 'square';
        return height > width ? 'portrait' : 'landscape';
    }

    let collapsedOutputs = $state(new Set<string>());
    function toggleOutputSection(runId: string, outputKey: string) {
        const key = `${runId}_${outputKey}`;
        const next = new Set(collapsedOutputs);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        collapsedOutputs = next;
    }
    function isOutputCollapsed(runId: string, outputKey: string): boolean {
        return collapsedOutputs.has(`${runId}_${outputKey}`);
    }
    
    function openLightboxFromRun(run: RunGroup, image: GalleryImage) {
        const selected = run.images.filter((img) => selectedImageKeys.has(`${run.id}-${img.id}`));
        const list = selected.length > 0 ? selected : getFilteredImagesForRun(run);
        const idx = list.findIndex((img) => img.id === image.id);
        if (idx === -1) return;

        document.querySelectorAll('audio').forEach((a) => a.pause());
        document.querySelectorAll('video').forEach((v) => v.pause());
        playingAudioThumbKey = null;

        markThumbLoaded(run.id, image.id);

        lightboxRunId = run.id;
        lightboxSeedFilter = seedFilterByRun[run.id]?.length ? seedFilterByRun[run.id] : null;
        lightboxIndex = idx;
        lightboxOpen = true;
    }

    function closeLightbox() {
        lightboxOpen = false;
        lightboxRunId = null;
        lightboxSeedFilter = null;
    }
    
    function copySeed(seed: number) {
        navigator.clipboard.writeText(String(seed));
    }

    let collapsedRuns = $state(new Set<string>());

    function toggleRun(runId: string) {
        collapsedRuns.has(runId)
            ? collapsedRuns.delete(runId)
            : collapsedRuns.add(runId);

        collapsedRuns = new Set(collapsedRuns); // Svelte trigger
    }

    function expandAllRuns() {
        collapsedRuns = new Set();
    }

    function collapseAllRuns() {
        collapsedRuns = new Set(runs.map((r) => r.id));
    }

    let thumbnailSize = $state<ThumbSize>(browser ? getThumbSizeCookie() : 'medium');
    function setThumbnailSize(size: ThumbSize) {
        thumbnailSize = size;
        if (browser) setThumbSizeCookie(size);
    }
    let thumbnailFitMode = $state<ThumbFitMode>(browser ? getThumbFitModeCookie() : 'cover');
    function setThumbnailFitMode(mode: ThumbFitMode) {
        thumbnailFitMode = mode;
        if (browser) setThumbFitModeCookie(mode);
    }

    let visibleRunIds = $state<Set<string>>(new Set());
    function setRunVisible(runId: string) {
        visibleRunIds = new Set(visibleRunIds).add(runId);
    }
    function thumbSrc(_thumbKey: string, url: string): string {
        return url;
    }
    let loadedThumbIds = $state<Set<string>>(new Set());
    function markThumbLoaded(runId: string, imgId: string) {
        loadedThumbIds = new Set(loadedThumbIds).add(`${runId}-${imgId}`);
    }
    let selectedImageKeys = $state<Set<string>>(new Set());
    let focusedRunId = $state<string | null>(null);
    function toggleSelection(runId: string, imgId: string) {
        const key = `${runId}-${imgId}`;
        const next = new Set(selectedImageKeys);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        selectedImageKeys = next;
    }
    function isImageSelected(runId: string, imgId: string) {
        return selectedImageKeys.has(`${runId}-${imgId}`);
    }
    function clearSelectionForRun(runId: string) {
        const run = runs.find((r) => r.id === runId);
        if (!run) return;
        const next = new Set(selectedImageKeys);
        for (const img of run.images) {
            next.delete(`${runId}-${img.id}`);
        }
        selectedImageKeys = next;
    }
    function toggleRunFocus(runId: string) {
        focusedRunId = focusedRunId === runId ? null : runId;
    }

    $effect(() => {
        onRunFocusChange?.(!!focusedRunId);
    });

    $effect(() => {
        if (!browser || !focusedRunId) return;
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === 'Escape') focusedRunId = null;
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    });
    function observeRunSection(node: HTMLElement, runId: string) {
        if (!browser) return;
        const observer = new IntersectionObserver(
            (entries) => {
                for (const e of entries) {
                    if (e.isIntersecting) setRunVisible(runId);
                }
            },
            { rootMargin: '200px', threshold: 0 }
        );
        observer.observe(node);
        return {
            destroy() {
                observer.disconnect();
            },
        };
    }

    async function downloadImage(img: { url: string; filename?: string; mediaType?: string }) {
        const res = await fetch(img.url);
        const blob = await res.blob();
        const blobUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = blobUrl;
        a.download = img.filename ?? (img.mediaType === 'video' ? 'video.mp4' : img.mediaType === 'audio' ? 'audio.mp3' : 'image.png');
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(blobUrl);
    }
</script>

{#if runs.length}
<div class="gallery-expand-collapse" class:hidden-when-lightbox={lightboxOpen}>
    <button type="button" class="expand-collapse-btn" onclick={expandAllRuns}>Expand all</button>
    <button type="button" class="expand-collapse-btn" onclick={collapseAllRuns}>Collapse all</button>
    <span class="gallery-size-divider" aria-hidden="true"></span>
    <div class="gallery-thumb-size" role="group" aria-label="Thumbnail size">
        <button
            type="button"
            class="expand-collapse-btn thumb-size-btn"
            class:active={thumbnailSize === 'small'}
            onclick={() => setThumbnailSize('small')}
            title="Small thumbnails"
            aria-label="Small thumbnails"
            aria-pressed={thumbnailSize === 'small'}
        >
            <svg class="thumb-size-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="2" y="2" width="8" height="8" rx="1"/>
                <rect x="14" y="2" width="8" height="8" rx="1"/>
                <rect x="2" y="14" width="8" height="8" rx="1"/>
                <rect x="14" y="14" width="8" height="8" rx="1"/>
            </svg>
        </button>
        <button
            type="button"
            class="expand-collapse-btn thumb-size-btn"
            class:active={thumbnailSize === 'medium'}
            onclick={() => setThumbnailSize('medium')}
            title="Medium thumbnails"
            aria-label="Medium thumbnails"
            aria-pressed={thumbnailSize === 'medium'}
        >
            <svg class="thumb-size-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="2" y="4" width="9" height="9" rx="1"/>
                <rect x="13" y="4" width="9" height="9" rx="1"/>
                <rect x="2" y="15" width="9" height="7" rx="1"/>
                <rect x="13" y="15" width="9" height="7" rx="1"/>
            </svg>
        </button>
        <button
            type="button"
            class="expand-collapse-btn thumb-size-btn"
            class:active={thumbnailSize === 'large'}
            onclick={() => setThumbnailSize('large')}
            title="Large thumbnails"
            aria-label="Large thumbnails"
            aria-pressed={thumbnailSize === 'large'}
        >
            <svg class="thumb-size-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <rect x="3" y="3" width="18" height="18" rx="2"/>
            </svg>
        </button>
    </div>
    <span class="gallery-size-divider" aria-hidden="true"></span>
    <div class="gallery-thumb-fit" role="group" aria-label="Thumbnail render mode">
        <button
            type="button"
            class="expand-collapse-btn thumb-fit-btn"
            class:active={thumbnailFitMode === 'cover'}
            onclick={() => setThumbnailFitMode('cover')}
            title="Default thumbnail"
            aria-label="Default thumbnail"
            aria-pressed={thumbnailFitMode === 'cover'}
        >
            Default thumbnail
        </button>
        <button
            type="button"
            class="expand-collapse-btn thumb-fit-btn"
            class:active={thumbnailFitMode === 'contain'}
            onclick={() => setThumbnailFitMode('contain')}
            title="Fit into thumbnail"
            aria-label="Fit into thumbnail"
            aria-pressed={thumbnailFitMode === 'contain'}
        >
            Fit into thumbnail
        </button>
    </div>
</div>
{#each runs as run (run.id)}
    {#if !focusedRunId || focusedRunId === run.id}
    {@const filteredImages = getFilteredImagesForRun(run)}
    {@const displayImages = getDisplayImagesForRun(run)}
    {@const outputGroups = groupByOutputIndex(displayImages)}
    {@const runCount = run.runCount ?? 1}
    {@const runResolution = getResolutionFromInputs(run.inputs)}
    {@const storageSummary = getRunStorageSummary(run)}
    {@const runSelected = run.images.some((img) => selectedImageKeys.has(`${run.id}-${img.id}`))}
    {@const selectedCount = run.images.filter((img) => selectedImageKeys.has(`${run.id}-${img.id}`)).length}
    {@const selectedImages = runSelected ? run.images.filter((img) => selectedImageKeys.has(`${run.id}-${img.id}`)) : []}
    {@const selectedHasRemote = runSelected ? selectedImages.some((img) => !img.remote_deleted) : true}
    {@const selectedHasLocal = runSelected ? selectedImages.some((img) => { const st = run.storageByBackend?.[img.backendRunId]; return st?.local_storage_status === 'saved' || st?.local_storage_status === 'partial'; }) : true}
    {@const savingRun = run.backendRunIds?.some((id) => savingRunIds.has(id))}
    {@const deletingRun = run.backendRunIds?.some((id) => deletingRunIds.has(id))}
    {@const deletingLocalRun = run.backendRunIds?.some((id) => deletingLocalRunIds.has(id))}
    {@const deletingBothRun = run.backendRunIds?.some((id) => deletingBothRunIds.has(id))}
    {@const hasVisibleContent = displayImages.length > 0 || run.status === 'queued' || run.status === 'running'}
    {#if hasVisibleContent}
    <section class="run-section" use:observeRunSection={run.id}>
        <header
            class="run-header"
            role="button"
            tabindex="0"
            onclick={() => toggleRun(run.id)}
            onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleRun(run.id); } }}
        >
            <div class="run-title">
                <span class="run-dot"></span>
                <RunAppBadge
                    appHeaderColor={appHeaderColor ?? undefined}
                    label={run.appTitle ?? run.workflowName ?? 'App'}
                    title={run.appTitle ?? run.workflowName ?? ''}
                />
                {#if run.status === 'queued'}
                    <span class="muted">Queue #{run.queue_position ?? '?'}</span>
                    {#if onCancelRunGroup}
                        {@const cancelling = run.backendRunIds?.some((id) => cancellingRunIds.has(id))}
                        <button
                            type="button"
                            class="run-header-cancel-btn"
                            disabled={cancelling}
                            onclick={(e) => { e.stopPropagation(); onCancelRunGroup(run.id, run.backendRunIds ?? []); }}
                            title="Cancel this run"
                            aria-label="Cancel"
                        >{cancelling ? '…' : 'Cancel'}</button>
                    {/if}
                {:else if run.status === 'running'}
                    {@const completed = runningProgress[run.id] ?? 0}
                    {@const pct = runCount > 0 ? Math.min(99, Math.round((completed / runCount) * 100)) : 0}
                    <span class="muted">⌛ Generating… {pct}%</span>
                    {#if onCancelRunGroup}
                        {@const cancelling = run.backendRunIds?.some((id) => cancellingRunIds.has(id))}
                        <button
                            type="button"
                            class="run-header-cancel-btn"
                            disabled={cancelling}
                            onclick={(e) => { e.stopPropagation(); onCancelRunGroup(run.id, run.backendRunIds ?? []); }}
                            title="Cancel this run"
                            aria-label="Cancel"
                        >{cancelling ? '…' : 'Cancel'}</button>
                    {/if}
                {:else if run.status === 'error'}
                    <span class="error">✗ Error</span>
                {:else if run.status === 'cancelled'}
                    <span class="muted">Cancelled</span>
                {:else}
                    <span class="done">✓ Done</span>
                {/if}
                <span class="run-count" title="{runCount} run{runCount === 1 ? '' : 's'}, {outputGroups.length} output{outputGroups.length === 1 ? '' : 's'}, {filteredImages.length} image{filteredImages.length === 1 ? '' : 's'} total">
                    {runCount} run{runCount === 1 ? '' : 's'} · {outputGroups.length} output{outputGroups.length === 1 ? '' : 's'} · {#if hasActiveSeedFilter(run.id)}{filteredImages.length} of {run.images.length} imgs{:else}{filteredImages.length} imgs{/if}
                    {#if runSelected}
                        <span class="run-count-filter"> · {selectedCount} selected for lightbox</span>
                    {/if}
                    {#if runResolution}
                        <span class="run-resolution" title="Resolution and orientation for this run"> · @ {runResolution.height}×{runResolution.width} – {getOrientationLabel(runResolution.width, runResolution.height)}</span>
                    {/if}
                </span>
            </div>

            <RunHeaderActions
                storageSummary={storageSummary}
                status={run.status}
                createdAt={run.createdAt}
                timeExtra={run.status === 'done' && run.totalRuntimeSec != null ? ` · ${run.totalRuntimeSec} sec.` : ''}
                saveDisabled={manualSaveDisabled || !run.backendRunIds?.length || savingRun}
                saveLoading={savingRun}
                onSave={() => onSaveRun?.(run.id, run.backendRunIds ?? [])}
                saveTitle={manualSaveDisabled ? 'Manual save disabled for remote-only projects' : undefined}
                remoteDisabled={!run.backendRunIds?.length || deletingRun || !comfyuiDeleteSupported || (runSelected && !selectedHasRemote)}
                remoteLoading={deletingRun}
                onDeleteRemote={() => { if (runSelected && onDeleteRemoteSelected) { onDeleteRemoteSelected(run.id, selectedImages); clearSelectionForRun(run.id); } else onDeleteRemoteRun?.(run.id, run.backendRunIds ?? []); }}
                remoteTitle={!comfyuiDeleteSupported ? 'Install WorkflowUIPlugin on ComfyUI to delete on server' : runSelected && !selectedHasRemote ? 'No remote files in selection to delete' : undefined}
                localDisabled={!run.backendRunIds?.length || deletingLocalRun || (runSelected && !selectedHasLocal)}
                localLoading={deletingLocalRun}
                onDeleteLocal={() => { if (runSelected && onDeleteLocalSelected) { onDeleteLocalSelected(run.id, selectedImages); clearSelectionForRun(run.id); } else onDeleteLocalRun?.(run.id, run.backendRunIds ?? []); }}
                localTitle={runSelected && !selectedHasLocal ? 'No local files in selection to delete' : undefined}
                allDisabled={!run.backendRunIds?.length || deletingBothRun || !comfyuiDeleteSupported || (runSelected && (!selectedHasRemote || !selectedHasLocal))}
                allLoading={deletingBothRun}
                onDeleteAll={() => { if (runSelected && onDeleteBothSelected) { onDeleteBothSelected(run.id, selectedImages); clearSelectionForRun(run.id); } else onDeleteBothRun?.(run.id, run.backendRunIds ?? []); }}
                allTitle={!comfyuiDeleteSupported ? 'Install WorkflowUIPlugin on ComfyUI to delete on server' : runSelected && (!selectedHasRemote || !selectedHasLocal) ? 'Selection has no local and/or remote files to delete' : undefined}
                deleteRunDisabled={run.backendRunIds?.some((id) => deletingRunIds.has(id) || deletingLocalRunIds.has(id) || deletingBothRunIds.has(id)) ?? false}
                deleteRunLoading={deletingRun || deletingLocalRun || deletingBothRun}
                onDeleteRun={onDeleteRun ? () => onDeleteRun(run.id, run.backendRunIds ?? []) : undefined}
                showReplicate={!!appSlugForReplicate && !!onReplicateRun}
                replicateDisabled={false}
                onReplicate={appSlugForReplicate && onReplicateRun ? () => onReplicateRun(run.backendRunIds?.[0] ?? run.id, appSlugForReplicate) : undefined}
                replicateTitle="Open this app with the same parameters to replicate the run"
                showShowMetadata={!!onShowRunMetadata}
                onShowMetadata={onShowRunMetadata ? () => onShowRunMetadata(run.backendRunIds?.[0] ?? run.id) : undefined}
                showFullscreenToggle={true}
                fullscreenActive={focusedRunId === run.id}
                onToggleFullscreen={() => toggleRunFocus(run.id)}
                collapseIcon={collapsedRuns.has(run.id) ? '▸' : '▾'}
                hasSelection={runSelected}
            />
        </header>
        {#if run.status === 'running'}
            <div class="progress">
                <div class="bar"></div>
            </div>
        {/if}
        {#if !collapsedRuns.has(run.id)}
            <div class="run-body" data-lightbox-open={lightboxOpen}>
                {#key `${run.id}-${(seedFilterByRun[run.id] ?? []).length}`}
                {#if run.status === 'error'}
                    <div class="error-placeholder">
                        {run.error ?? 'Run failed'}
                    </div>
                {:else if run.status === 'queued' && run.images.length === 0}
                    <div class="queued-placeholder">
                        Waiting in queue #{run.queue_position ?? '?'}…
                    </div>
                {:else}
                    {#if runSelected}
                        <div class="run-filter-bar" role="group" aria-label="Lightbox filter by selection">
                            <span class="run-filter-label">Lightbox filter: {selectedCount} selected</span>
                            <button type="button" class="run-filter-clear" onclick={(e) => { e.preventDefault(); clearSelectionForRun(run.id); }}>Clear selection</button>
                        </div>
                    {/if}
                    {#if hasActiveSeedFilter(run.id)}
                        <div
                            class="run-filter-bar"
                            role="group"
                            aria-label="Filter by seed"
                        >
                            <span class="run-filter-label">Filter by seed:</span>
                            <div class="run-filter-seeds">
                                {#each (seedFilterByRun[run.id] ?? []) as seed (seed)}
                                    <button
                                        type="button"
                                        class="run-filter-chip"
                                        title="Remove seed from filter"
                                        onclick={(e) => { e.preventDefault(); removeSeedFromFilter(run.id, seed); }}
                                    >
                                        <span class="chip-seed">{seed}</span>
                                        <span class="chip-remove-label">× Remove</span>
                                        <svg class="chip-remove-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M18 6L6 18M6 6l12 12"/></svg>
                                    </button>
                                {/each}
                            </div>
                            <span class="run-filter-hint">Click a seed on any image to add; click chip or highlighted seed to remove.</span>
                            <button
                                type="button"
                                class="run-filter-clear"
                                title="Show all outputs"
                                onclick={(e) => { e.preventDefault(); clearSeedFilter(run.id); }}
                            >
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M18 6L6 18M6 6l12 12"/></svg>
                                Clear filter
                            </button>
                        </div>
                    {/if}
                    <div class="output-sections">
                        {#each groupByOutputIndex(displayImages) as [outputKey, images]}
                            {@const sectionKey = `${run.id}_${outputKey}`}
                            {@const collapsed = collapsedOutputs.has(sectionKey)}
                            <div class="output-section" data-output-key={outputKey}>
                                <button
                                    type="button"
                                    class="output-section-header"
                                    onclick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        toggleOutputSection(run.id, outputKey);
                                    }}
                                >
                                    <span class="output-section-title">{outputLabels[Number(outputKey)] ?? `Output ${Number(outputKey) + 1}`}</span>
                                    <span class="output-section-count">
                                        {#if hasActiveSeedFilter(run.id)}
                                            {images.filter((img) => isImageInFilter(run.id, img.seed)).length} of {images.length}
                                        {:else}
                                            {images.length}
                                        {/if}
                                    </span>
                                    <svg class="output-section-chevron" class:collapsed aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                        <path d="M6 9l6 6 6-6"/>
                                    </svg>
                                </button>
                                {#if !collapsed}
                                    <div
                                        class="output-section-body"
                                        class:thumb-size-small={thumbnailSize === 'small'}
                                        class:thumb-size-medium={thumbnailSize === 'medium'}
                                        class:thumb-size-large={thumbnailSize === 'large'}
                                        class:thumb-fit-contain={thumbnailFitMode === 'contain'}
                                    >
                                        {#each images as img (img.id)}
                                            {@const inFilter = isImageInFilter(run.id, img.seed)}
                                            {@const imageStatus = getImageStatus(run, img)}
                                            {@const thumbKey = `${run.id}-${img.id}`}
                                            {@const isRemoteDeleted = !!img.remote_deleted}
                                            {@const isLoaded = loadedThumbIds.has(thumbKey) || isRemoteDeleted}
                                            {@const isDeleting = imageStatus?.label === 'Deleting'}
                                            {@const hasLocalStorage = imageStatus?.tone === 'saved' || imageStatus?.tone === 'partial'}
                                            <div
                                                class="output-thumb thumb-media"
                                                class:thumb-loaded={isLoaded}
                                                class:output-thumb-video={img.mediaType === 'video'}
                                                class:output-thumb-audio={img.mediaType === 'audio'}
                                                class:output-thumb-deleted={isRemoteDeleted}
                                                class:output-thumb-deleting={isDeleting}
                                                class:audio-playing={img.mediaType === 'audio' && playingAudioThumbKey === thumbKey}
                                                class:thumb-filtered-out={hasActiveSeedFilter(run.id) && !inFilter}
                                                class:output-thumb-local-storage={hasLocalStorage}
                                                role="button"
                                                tabindex="0"
                                                onclick={(e) => {
                                                const target = e.target as HTMLElement;
                                                const thumb = target.closest('.output-thumb');
                                                const audio = thumb?.querySelector<HTMLAudioElement>('audio');
                                                if (target.closest('.output-thumb-audio-play-btn') || target.closest('.output-thumb-audio-controls-wrap')) {
                                                    if (audio) {
                                                        if (audio.paused) {
                                                            document.querySelectorAll('audio').forEach((el) => { if (el !== audio) el.pause(); });
                                                            audio.play();
                                                        } else {
                                                            audio.pause();
                                                        }
                                                    }
                                                    return;
                                                }
                                                if (!isRemoteDeleted && !isDeleting && (!hasActiveSeedFilter(run.id) || inFilter)) openLightboxFromRun(run, img);
                                            }}
                                                onkeydown={(e) => {
                                                if (e.key !== 'Enter') return;
                                                if ((e.target as HTMLElement).closest('.output-thumb-audio-play-btn, .output-thumb-audio-controls-wrap')) return;
                                                if (!isRemoteDeleted && !isDeleting && (!hasActiveSeedFilter(run.id) || inFilter)) openLightboxFromRun(run, img);
                                            }}
                                                onmouseenter={(e) => { if (img.mediaType === 'video') (e.currentTarget as HTMLElement).querySelector('video')?.play(); }}
                                                onmouseleave={(e) => { if (img.mediaType === 'video') (e.currentTarget as HTMLElement).querySelector('video')?.pause(); }}
                                            >
                                                <span class="thumb-loading" class:hide={isLoaded} aria-hidden="true">
                                                    <span class="thumb-loading-spinner" aria-hidden="true"></span>
                                                </span>
                                                {#if isDeleting}
                                                    <div class="output-thumb-deleting-overlay" aria-hidden="true" aria-live="polite">
                                                        <span class="output-thumb-deleting-spinner" aria-hidden="true"></span>
                                                        <span class="output-thumb-deleting-label">Deleting…</span>
                                                    </div>
                                                {/if}
                                                <ThumbnailOverlay
                                                    mediaType={img.mediaType ?? 'image'}
                                                    seed={img.seed}
                                                    executionTimeSec={img.executionTimeSec}
                                                    isFavorite={favoriteRunIds.has(img.backendRunId)}
                                                    isSelected={isImageSelected(run.id, img.id)}
                                                    showMetadata={true}
                                                    showFavorite={!!onToggleFavorite}
                                                    showSelection={true}
                                                    showSeed={true}
                                                    showDownload={!isRemoteDeleted}
                                                    showSendToApp={!!onSendToApp && !isRemoteDeleted}
                                                    onMetadataClick={() => !isRemoteDeleted && (onMetadataClick ? onMetadataClick(run, img) : openLightboxFromRun(run, img))}
                                                    onToggleFavorite={() => onToggleFavorite?.(img.backendRunId)}
                                                    onToggleSelection={() => toggleSelection(run.id, img.id)}
                                                    onDownload={() => downloadImage(img)}
                                                    onSendToApp={() => onSendToApp?.(img.backendRunId, img.outputIndex ?? 0)}
                                                >
                                                    {#if isRemoteDeleted}
                                                        <div class="output-thumb-deleted-placeholder" aria-hidden="true">
                                                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M8 6l1 14h6l1-14"/></svg>
                                                            <span>Deleted</span>
                                                        </div>
                                                    {:else if img.mediaType === 'video'}
                                                        <video
                                                            src={thumbSrc(thumbKey, img.url)}
                                                            preload="auto"
                                                            muted
                                                            playsinline
                                                            loop
                                                            aria-hidden="true"
                                                            onloadeddata={(e) => {
                                                                const v = e.currentTarget;
                                                                if (v) { v.currentTime = 0; v.pause(); }
                                                                markThumbLoaded(run.id, img.id);
                                                            }}
                                                            onloadedmetadata={(e) => {
                                                                const v = e.currentTarget;
                                                                if (v) { v.currentTime = 0; v.pause(); }
                                                                markThumbLoaded(run.id, img.id);
                                                            }}
                                                            onerror={() => markThumbLoaded(run.id, img.id)}
                                                        ></video>
                                                        <span class="output-thumb-play" aria-hidden="true" title="Play video">
                                                            <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
                                                        </span>
                                                    {:else if img.mediaType === 'audio'}
                                                        <div class="output-thumb-audio-preview">
                                                            <div class="output-thumb-audio-center" aria-hidden="true">
                                                                <div class="output-thumb-audio-visual">
                                                                    <svg class="output-thumb-audio-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                                                                        <path d="M12 3v9.28c-.47-.17-.97-.28-1.5-.28C8.01 12 6 14.01 6 16.5S8.01 21 10.5 21c2.31 0 4.2-1.75 4.45-4H15V6h4V3h-7z"/>
                                                                    </svg>
                                                                    <span class="output-thumb-audio-label">AUDIO</span>
                                                                    <button
                                                                        type="button"
                                                                        class="output-thumb-audio-play-btn"
                                                                        title="Play audio"
                                                                        aria-label="Play audio"
                                                                    >
                                                                        <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
                                                                    </button>
                                                                </div>
                                                            </div>
                                                            <div class="output-thumb-audio-controls-wrap">
                                                                <audio
                                                                    src={thumbSrc(thumbKey, img.url)}
                                                                    preload="metadata"
                                                                    controls
                                                                    playsinline
                                                                    onloadeddata={() => markThumbLoaded(run.id, img.id)}
                                                                    onplay={(e) => {
                                                                        const el = e.currentTarget as HTMLAudioElement;
                                                                        document.querySelectorAll('audio').forEach((a) => { if (a !== el) a.pause(); });
                                                                        playingAudioThumbKey = thumbKey;
                                                                    }}
                                                                    onpause={() => {
                                                                        playingAudioThumbKey = null;
                                                                    }}
                                                                ></audio>
                                                            </div>
                                                        </div>
                                                    {:else}
                                                        <img
                                                            src={thumbSrc(thumbKey, img.previewUrl ?? img.url)}
                                                            alt=""
                                                            onload={() => markThumbLoaded(run.id, img.id)}
                                                            onerror={() => markThumbLoaded(run.id, img.id)}
                                                        />
                                                    {/if}
                                                </ThumbnailOverlay>
                                                {#if imageStatus}
                                                    <span class={`image-status ${imageStatus.tone}`}>{imageStatus.label}</span>
                                                {/if}
                                            </div>
                                        {/each}
                                    </div>
                                {/if}
                            </div>
                        {/each}
                    </div>
                {/if}
                {/key}
            </div>
        {/if}
    </section>
    {/if}
    {/if}
{/each}
{/if}

<LightboxViewer
    open={lightboxOpen}
    items={lightboxImages as LightboxItem[]}
    index={lightboxIndex}
    onIndexChange={(i) => { lightboxIndex = i; }}
    onClose={closeLightbox}
    onDownload={downloadImage}
    onMetadata={lightboxRun ? (item) => { const run = lightboxRun; closeLightbox(); onMetadataClick(run, item as GalleryImage); } : undefined}
    onToggleFavorite={onToggleFavorite ? (item) => onToggleFavorite(item.backendRunId!) : undefined}
    isFavorite={onToggleFavorite ? (item) => favoriteRunIds.has(item.backendRunId!) : undefined}
    onToggleSelection={lightboxRunId ? (item) => toggleSelection(lightboxRunId, item.id) : undefined}
    isSelected={lightboxRunId ? (item) => isImageSelected(lightboxRunId, item.id) : undefined}
    onSendToApp={onSendToApp ? (item) => { const backendRunId = item.backendRunId!; const outputIndex = item.outputIndex ?? 0; closeLightbox(); onSendToApp(backendRunId, outputIndex); } : undefined}
    showCloseLabel={true}
    ariaTitle="Media viewer"
/>

<style>
    .progress {
        height: 6px;
        border-radius: 999px;
        background: color-mix(in srgb, var(--text) 14%, transparent);
        overflow: hidden;
    }

    .progress .bar {
        height: 100%;
        width: 40%;
        background: linear-gradient(
                90deg,
                transparent,
                var(--accent),
                transparent
        );
        animation: slide 1.2s linear infinite;
    }

    @keyframes slide {
        from {
            transform: translateX(-100%);
        }
        to {
            transform: translateX(250%);
        }
    }

    .run-header {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        align-items: center;
        gap: 0.5rem 1rem;
        padding: 0.5rem 0.75rem 0.5rem 0.75rem;
        margin: 0 -0.25rem 0 0;
        background: color-mix(in srgb, var(--surface) 50%, transparent);
        border-bottom: 1px solid var(--border);
        border-left: 3px solid var(--accent);
        border-radius: 6px 6px 0 0;
        cursor: pointer;
        transition: background 0.15s ease;
    }
    .run-header:hover {
        background: color-mix(in srgb, var(--surface) 70%, transparent);
    }

    .run-title {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-weight: 500;
    }

    .run-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: var(--accent);
    }

    .run-count {
        font-size: 0.7rem;
        color: var(--muted);
        margin-left: 0.25rem;
    }
    .run-count-filter {
        color: var(--accent);
        font-style: italic;
    }

    .run-header-cancel-btn {
        flex-shrink: 0;
        margin-left: 0.25rem;
        padding: 0.2rem 0.5rem;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        color: var(--error, #e57373);
        background: color-mix(in srgb, var(--error, #e57373) 18%, transparent);
        border: 1px solid var(--error, #e57373);
        border-radius: 6px;
        cursor: pointer;
        transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
    }
    .run-header-cancel-btn:hover:not(:disabled) {
        background: color-mix(in srgb, var(--error, #e57373) 28%, transparent);
        border-color: #ef5350;
        color: #ff8a80;
    }
    .run-header-cancel-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .run-meta {
        display: flex;
        align-items: center;
        gap: 0.75rem;

        font-size: 0.7rem;
        color: var(--muted);
    }

    .run-actions {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
    }
    .run-action-btn {
        min-width: 26px;
        height: 26px;
        border-radius: 6px;
        border: 1px solid var(--border);
        background: rgba(0, 0, 0, 0.25);
        color: var(--text);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.25rem;
        padding: 0 0.35rem;
        cursor: pointer;
        transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease, opacity 0.15s ease;
    }
    .run-action-btn:hover:not(:disabled) {
        border-color: var(--accent);
        background: color-mix(in srgb, var(--accent) 18%, transparent);
        color: var(--accent);
    }
    .run-action-btn.context-aware {
        border-color: #e6a23c;
        color: #e6a23c;
        background: color-mix(in srgb, #e6a23c 14%, transparent);
    }
    .run-action-btn.context-aware:hover:not(:disabled) {
        border-color: #f0c674;
        color: #f0c674;
        background: color-mix(in srgb, #e6a23c 22%, transparent);
    }
    .run-action-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
    }
    .run-action-btn.delete-run-btn {
        border-color: var(--error, #c55);
        color: var(--error, #c55);
        background: color-mix(in srgb, var(--error, #c55) 12%, transparent);
    }
    .run-action-btn.delete-run-btn:hover:not(:disabled) {
        border-color: var(--error, #e55);
        color: var(--error, #e55);
        background: color-mix(in srgb, var(--error, #e55) 20%, transparent);
    }

    .run-storage-badge {
        font-size: 0.65rem;
        padding: 0.15rem 0.35rem;
        border-radius: 6px;
        border: 1px solid var(--border);
        background: rgba(0, 0, 0, 0.2);
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }

    .run-storage-badge.saved {
        color: var(--accent);
        border-color: var(--accent);
    }

    .run-storage-badge.partial {
        color: var(--partial-badge);
        border-color: var(--partial-badge);
    }

    .run-storage-badge.failed {
        color: #e57373;
        border-color: #e57373;
    }

    .run-storage-badge.remote {
        color: var(--muted);
    }

    .collapse-icon {
        font-size: 0.9rem;
        opacity: 0.7;
    }

    .run-body {
        margin-top: 0.25rem;
    }

    .queued-placeholder {
        padding: 1.5rem;
        border: 1px dashed var(--border);
        border-radius: 8px;
        color: var(--muted);
        font-size: 0.85rem;
        text-align: center;
    }

    .error-placeholder {
        padding: 1.5rem;
        border: 1px solid var(--border);
        border-radius: 8px;
        color: #e57373;
        font-size: 0.9rem;
        text-align: center;
    }

    .error {
        color: #e57373;
    }

    .gallery-expand-collapse {
        position: sticky;
        top: 0;
        z-index: 10;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.75rem;
        padding: 0.25rem 0 0.5rem 0;
        flex-wrap: wrap;
        background: var(--bg);
        border-bottom: 1px solid var(--border);
    }
    .gallery-expand-collapse.hidden-when-lightbox {
        visibility: hidden;
    }
    .gallery-size-divider {
        width: 1px;
        height: 1.25rem;
        background: var(--border);
        margin: 0 0.15rem;
    }
    .gallery-thumb-size {
        display: flex;
        align-items: center;
        gap: 0.2rem;
    }
    .gallery-thumb-fit {
        display: flex;
        align-items: center;
        gap: 0.2rem;
    }
    .thumb-size-btn {
        padding: 0.35rem 0.45rem;
    }
    .thumb-size-btn .thumb-size-icon {
        width: 18px;
        height: 18px;
        display: block;
    }
    .thumb-size-btn.active {
        background: color-mix(in srgb, var(--accent) 22%, var(--surface));
        border-color: var(--accent);
        color: var(--accent);
    }
    .thumb-fit-btn.active {
        background: color-mix(in srgb, var(--accent) 22%, var(--surface));
        border-color: var(--accent);
        color: var(--accent);
    }
    .expand-collapse-btn {
        font-size: 0.8rem;
        padding: 0.35rem 0.6rem;
        background: var(--surface);
        color: var(--text);
        border: 1px solid var(--border);
        border-radius: 6px;
        cursor: pointer;
    }
    .expand-collapse-btn:hover {
        background: color-mix(in srgb, var(--accent) 15%, var(--surface));
        border-color: var(--accent);
    }

    .run-section {
        background: var(--bg);
        border: 2px solid #1f1f1f;
        border-radius: 8px;
        padding: 0.75rem 1rem 1rem;
        margin-bottom: 1.5rem;
    }
    
    .output-sections {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        margin-top: 0.5rem;
    }

    .output-section {
        border: 1px solid var(--border);
        border-radius: 8px;
        overflow: hidden;
        background: rgba(0, 0, 0, 0.15);
    }

    .output-section-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        width: 100%;
        padding: 0.5rem 0.75rem;
        border: none;
        background: transparent;
        color: var(--text);
        font-size: 0.8rem;
        cursor: pointer;
        text-align: left;
    }

    .output-section-header:hover {
        background: rgba(255, 255, 255, 0.05);
    }

    .output-section-title {
        font-weight: 500;
    }

    .output-section-count {
        font-size: 0.7rem;
        color: var(--muted);
    }

    .output-section-chevron {
        width: 18px;
        height: 18px;
        margin-left: auto;
        flex-shrink: 0;
        transition: transform 0.2s ease;
    }

    .output-section-chevron.collapsed {
        transform: rotate(-90deg);
    }

    .output-section-body {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 0.75rem;
        padding: 0.75rem;
        border-top: 1px solid var(--border);
    }
    .output-section-body.thumb-size-small {
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    }
    .output-section-body.thumb-size-medium {
        grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    }
    .output-section-body.thumb-size-large {
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    }
    @media (max-width: 639px) {
        .output-section-body {
            gap: 0.5rem;
            padding: 0.5rem;
        }
        .output-section-body.thumb-size-small {
            grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
        }
        .output-section-body.thumb-size-medium {
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
        }
        .output-section-body.thumb-size-large {
            grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
        }
        .run-section {
            min-width: 0;
            max-width: 100%;
            box-sizing: border-box;
            overflow-x: hidden;
        }
        .run-header {
            min-width: 0;
            width: 100%;
            overflow-wrap: break-word;
        }
        .run-title {
            flex-wrap: wrap;
            min-width: 0;
            overflow-wrap: break-word;
        }
        .run-count,
        .run-resolution {
            overflow-wrap: break-word;
        }
    }

    .output-thumb.output-thumb-local-storage {
        box-shadow: 0 0 0 2px #d4af37;
    }
    .output-thumb {
        position: relative;
        aspect-ratio: 1;
        border-radius: 8px;
        overflow: hidden;
        cursor: pointer;
        background: #111;
        box-shadow: 0 0 0 1px #222;
    }

    .output-thumb img,
    .output-thumb video {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }
    .output-section-body.thumb-fit-contain .output-thumb img,
    .output-section-body.thumb-fit-contain .output-thumb video {
        object-fit: contain;
        background: #0b0b0b;
    }

    .thumb-placeholder {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #1a1a1a;
    }
    .thumb-placeholder-spinner {
        width: 24px;
        height: 24px;
        border: 2px solid var(--border);
        border-top-color: var(--accent);
        border-radius: 50%;
        animation: thumb-spin 0.7s linear infinite;
    }
    .thumb-loading {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #111;
        z-index: 1;
        transition: opacity 0.15s ease;
    }
    .thumb-loading.hide {
        opacity: 0;
        pointer-events: none;
    }
    .thumb-media.thumb-loaded .thumb-loading {
        display: none;
    }
    .thumb-loading-spinner {
        width: 22px;
        height: 22px;
        border: 2px solid var(--border);
        border-top-color: var(--accent);
        border-radius: 50%;
        animation: thumb-spin 0.7s linear infinite;
    }
    @keyframes thumb-spin {
        to { transform: rotate(360deg); }
    }
    .output-thumb-deleted .thumb-loading {
        display: none;
    }
    .output-thumb-deleting {
        box-shadow: 0 0 0 2px var(--accent), 0 0 0 4px rgba(0, 0, 0, 0.3);
    }
    .output-thumb-deleting-overlay {
        position: absolute;
        inset: 0;
        z-index: 2;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.4rem;
        background: rgba(0, 0, 0, 0.75);
        color: var(--text);
        animation: output-thumb-deleting-pulse 1.2s ease-in-out infinite;
    }
    .output-thumb-deleting-spinner {
        width: 24px;
        height: 24px;
        border: 2px solid rgba(255, 255, 255, 0.3);
        border-top-color: #fff;
        border-radius: 50%;
        animation: spin 0.8s linear infinite;
    }
    .output-thumb-deleting-label {
        font-size: 0.75rem;
        font-weight: 500;
    }
    @keyframes output-thumb-deleting-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.85; }
    }
    .output-thumb-deleted-placeholder {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        background: var(--surface);
        color: var(--muted);
        font-size: 0.75rem;
    }
    .output-thumb-deleted-placeholder svg {
        width: 28px;
        height: 28px;
        opacity: 0.7;
    }

    .output-thumb-play {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        pointer-events: none;
        color: rgba(255, 255, 255, 0.9);
        background: rgba(0, 0, 0, 0.2);
        transition: background 0.15s ease;
    }
    .output-thumb:hover .output-thumb-play {
        background: rgba(0, 0, 0, 0.4);
    }

    .output-thumb-play svg {
        width: 48px;
        height: 48px;
    }

    .output-thumb-audio-preview {
        position: absolute;
        inset: 0;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        align-items: center;
        padding: 0.5rem;
        background: rgba(0, 0, 0, 0.4);
    }
    .output-thumb-audio-center {
        position: absolute;
        inset: 0;
        z-index: 3;
        display: flex;
        align-items: center;
        justify-content: center;
        padding-bottom: 2.5rem;
        pointer-events: none;
    }
    .output-thumb-audio-visual {
        pointer-events: auto;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.35rem;
        color: rgba(255, 255, 255, 0.9);
    }
    .output-thumb-audio-icon {
        width: 40px;
        height: 40px;
    }
    .output-thumb-audio-label {
        font-size: 0.65rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .output-thumb-audio-preview audio {
        width: 100%;
        min-width: 0;
        flex-shrink: 0;
    }

    .output-thumb-audio-play-btn {
        position: relative;
        z-index: 4;
        margin-top: 0.35rem;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        border: none;
        background: rgba(255, 255, 255, 0.9);
        color: #111;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        flex-shrink: 0;
        transition: background 0.15s ease, transform 0.1s ease;
    }
    .output-thumb-audio-play-btn:hover {
        background: #fff;
        transform: scale(1.05);
    }
    .output-thumb-audio-play-btn svg {
        width: 22px;
        height: 22px;
        margin-left: 2px;
    }
    .output-thumb-audio-controls-wrap {
        position: relative;
        z-index: 10;
        width: 100%;
    }

    .output-thumb:hover {
        box-shadow: 0 0 0 2px var(--accent);
    }

    .output-thumb.output-thumb-audio.audio-playing {
        box-shadow: 0 0 0 2px var(--accent), 0 0 12px color-mix(in srgb, var(--accent) 70%, transparent);
        animation: audio-pulse-glow 1.5s ease-in-out infinite;
    }
    @keyframes audio-pulse-glow {
        0%, 100% {
            box-shadow: 0 0 0 2px var(--accent), 0 0 8px color-mix(in srgb, var(--accent) 50%, transparent);
        }
        50% {
            box-shadow: 0 0 0 2px var(--accent), 0 0 20px color-mix(in srgb, var(--accent) 85%, transparent);
        }
    }

    .output-thumb.thumb-filtered-out {
        opacity: 0.4;
        pointer-events: none;
    }

    .output-thumb.thumb-filtered-out .thumb-overlay-root {
        pointer-events: auto;
    }

    .image-status {
        position: absolute;
        left: 6px;
        bottom: 6px;
        padding: 2px 6px;
        border-radius: 6px;
        font-size: 0.6rem;
        letter-spacing: 0.02em;
        background: rgba(0, 0, 0, 0.6);
        color: var(--text);
        border: 1px solid rgba(255, 255, 255, 0.12);
        text-transform: uppercase;
    }

    .image-status.saved {
        color: var(--accent);
        border-color: var(--accent);
    }

    .image-status.partial {
        color: #f0c674;
        border-color: #f0c674;
    }

    .image-status.failed {
        color: #e57373;
        border-color: #e57373;
    }

    .image-status.deleted {
        color: #8abeb7;
        border-color: #8abeb7;
    }

    .image-status.saving {
        color: var(--text);
        border-color: var(--accent);
    }

    .icon {
        width: 16px;
        height: 16px;
    }

    .icon.spinner {
        animation: spin 0.9s linear infinite;
    }

    @keyframes spin {
        from {
            transform: rotate(0deg);
        }
        to {
            transform: rotate(360deg);
        }
    }

    .run-filter-bar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.5rem;
        padding: 0.35rem 0.5rem;
        background: var(--accent-soft);
        border-radius: 6px;
        font-size: 0.75rem;
    }

    .run-filter-label {
        color: var(--muted);
        flex-shrink: 0;
    }

    .run-filter-seeds {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
    }

    .run-filter-chip {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.5rem;
        border: 1px solid var(--accent);
        border-radius: 6px;
        background: var(--accent-soft);
        color: var(--text);
        font-size: 0.75rem;
        cursor: pointer;
    }

    .run-filter-chip .chip-seed {
        font-weight: 600;
    }

    .run-filter-chip .chip-remove-label {
        color: var(--muted);
        font-size: 0.7rem;
    }

    .run-filter-chip:hover {
        background: rgba(255, 255, 255, 0.12);
        border-color: var(--accent-hover);
    }

    .run-filter-chip:hover .chip-remove-label {
        color: var(--text);
    }

    .run-filter-chip .chip-remove-icon {
        width: 12px;
        height: 12px;
        opacity: 0.9;
    }

    .run-filter-hint {
        color: var(--muted);
        font-size: 0.7rem;
        flex-basis: 100%;
        margin-top: 0.15rem;
    }

    .run-filter-clear {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.2rem 0.4rem;
        border: none;
        background: transparent;
        color: var(--accent);
        font-size: 0.75rem;
        cursor: pointer;
        border-radius: 4px;
    }

    .run-filter-clear:hover {
        background: rgba(255, 255, 255, 0.08);
    }

    .run-filter-clear svg {
        width: 12px;
        height: 12px;
    }

</style>
