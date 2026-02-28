<script lang="ts">
    import type { Snippet } from 'svelte';
    let {
        mediaType = 'image',
        seed = undefined as number | string | undefined,
        executionTimeSec = undefined as number | null | undefined,
        isFavorite = false,
        isSelected = false,
        showMetadata = true,
        showFavorite = true,
        showSelection = true,
        showSeed = true,
        showDownload = true,
        showSendToApp = true,
        onMetadataClick = undefined as (() => void) | undefined,
        onToggleFavorite = undefined as (() => void) | undefined,
        onToggleSelection = undefined as (() => void) | undefined,
        onDownload = undefined as (() => void) | undefined,
        onSendToApp = undefined as (() => void) | undefined,
        children
    }: {
        mediaType?: 'image' | 'video' | 'audio';
        seed?: number | string;
        executionTimeSec?: number | null;
        isFavorite?: boolean;
        isSelected?: boolean;
        showMetadata?: boolean;
        showFavorite?: boolean;
        showSelection?: boolean;
        showSeed?: boolean;
        showDownload?: boolean;
        showSendToApp?: boolean;
        onMetadataClick?: () => void;
        onToggleFavorite?: () => void;
        onToggleSelection?: () => void;
        onDownload?: () => void;
        onSendToApp?: () => void;
        children?: Snippet;
    } = $props();

    function stop(e: Event) {
        e.preventDefault();
        e.stopPropagation();
    }
</script>

<div class="thumb-overlay-root">
    <div class="thumb-overlay-media">
        {#if children}
            {@render children()}
        {/if}
    </div>

    {#if showMetadata && onMetadataClick}
        <button
            type="button"
            class="thumb-overlay-btn thumb-overlay-ul"
            title="View generation metadata"
            aria-label="View generation metadata"
            onclick={(e) => { stop(e); onMetadataClick(); }}
        >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 16v-4"/>
                <path d="M12 8h.01"/>
            </svg>
        </button>
    {/if}

    {#if showFavorite || showSelection}
        <div class="thumb-overlay-ur">
            {#if showFavorite && onToggleFavorite}
                <button
                    type="button"
                    class="thumb-overlay-btn thumb-favorite"
                    class:is-favorite={isFavorite}
                    title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
                    aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
                    onclick={(e) => { stop(e); onToggleFavorite(); }}
                >
                    <span class="thumb-favorite-outline" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round">
                            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                        </svg>
                    </span>
                    <span class="thumb-favorite-fill" aria-hidden="true">
                        <svg viewBox="0 0 24 24" fill="currentColor">
                            <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                        </svg>
                    </span>
                </button>
            {/if}
            {#if showSelection && onToggleSelection}
                <button
                    type="button"
                    class="thumb-overlay-btn thumb-select"
                    class:active={isSelected}
                    title={isSelected ? 'Remove from selection' : 'Add to selection'}
                    aria-label={isSelected ? 'Remove from selection' : 'Add to selection'}
                    onclick={(e) => { stop(e); onToggleSelection(); }}
                >
                    {#if isSelected}
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>
                    {:else}
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/></svg>
                    {/if}
                </button>
            {/if}
        </div>
    {/if}

    {#if (showSeed && seed !== undefined && seed !== null && String(seed).trim() !== '') || executionTimeSec != null}
        <span class="thumb-overlay-seed" title={[showSeed && seed != null ? 'Seed value' : '', executionTimeSec != null ? 'Generation time' : ''].filter(Boolean).join(' · ') || undefined}>
            {#if showSeed && seed !== undefined && seed !== null && String(seed).trim() !== ''}
                <span class="seed-value">{seed}</span>
            {/if}
            {#if executionTimeSec != null}
                {#if showSeed && seed !== undefined && seed !== null && String(seed).trim() !== ''}
                    <span class="thumb-overlay-sep" aria-hidden="true"> · </span>
                {/if}
                <span class="thumb-overlay-time">{Math.round(Number(executionTimeSec))} sec</span>
            {/if}
        </span>
    {/if}

    {#if showDownload || showSendToApp}
        <div class="thumb-overlay-br">
            {#if showDownload && onDownload}
                <button
                    type="button"
                    class="thumb-overlay-btn"
                    title="Download file"
                    aria-label="Download file"
                    onclick={(e) => { stop(e); onDownload(); }}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                        <path d="M7 10l5 5 5-5"/>
                        <path d="M12 15V3"/>
                    </svg>
                </button>
            {/if}
            {#if showSendToApp && onSendToApp}
                <button
                    type="button"
                    class="thumb-overlay-btn"
                    title="Send this output to app"
                    aria-label="Send this output to app"
                    onclick={(e) => { stop(e); onSendToApp(); }}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <path d="M5 12h14M12 5l7 7-7 7"/>
                    </svg>
                </button>
            {/if}
        </div>
    {/if}
</div>

<style>
    .thumb-overlay-root {
        position: absolute;
        inset: 0;
        pointer-events: none;
        z-index: 2;
    }
    .thumb-overlay-root > :global(*) {
        pointer-events: auto;
    }
    .thumb-overlay-media {
        position: absolute;
        inset: 0;
        pointer-events: auto;
    }
    .thumb-overlay-media :global(img),
    .thumb-overlay-media :global(video) {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }
    .thumb-overlay-media :global(.output-thumb-deleted-placeholder),
    .thumb-overlay-media :global(.output-thumb-audio-preview) {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
    }

    .thumb-overlay-btn {
        width: 26px;
        height: 26px;
        padding: 0;
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 0.35);
        background: rgba(0, 0, 0, 0.55);
        color: rgba(255, 255, 255, 0.9);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease;
        opacity: 0;
        overflow: hidden;
    }
    .thumb-overlay-root:has(.thumb-overlay-btn:hover) .thumb-overlay-btn,
    .thumb-overlay-root:has(.thumb-overlay-seed:hover) .thumb-overlay-btn,
    :global(.output-thumb:hover) .thumb-overlay-btn,
    :global(.output-thumb:focus-within) .thumb-overlay-btn {
        opacity: 1;
    }
    .thumb-overlay-btn:hover {
        border-color: var(--accent, rgba(99, 102, 241, 0.8));
        background: rgba(0, 0, 0, 0.7);
        color: #fff;
    }
    .thumb-overlay-btn svg {
        width: 14px;
        height: 14px;
    }

    .thumb-overlay-ul {
        position: absolute;
        top: 6px;
        left: 6px;
    }

    .thumb-overlay-ur {
        position: absolute;
        top: 6px;
        right: 6px;
        display: flex;
        gap: 6px;
        align-items: center;
    }

    .thumb-favorite {
        position: relative;
    }
    .thumb-favorite .thumb-favorite-outline,
    .thumb-favorite .thumb-favorite-fill {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .thumb-favorite .thumb-favorite-outline svg,
    .thumb-favorite .thumb-favorite-fill svg {
        width: 12px;
        height: 12px;
        flex-shrink: 0;
    }
    .thumb-favorite .thumb-favorite-fill {
        opacity: 0;
    }
    .thumb-favorite.is-favorite .thumb-favorite-outline {
        opacity: 0;
    }
    .thumb-favorite.is-favorite .thumb-favorite-fill {
        opacity: 1;
        color: #ffdc78;
    }
    .thumb-favorite:hover .thumb-favorite-fill {
        opacity: 1;
        color: #ffdc78;
    }
    .thumb-favorite.is-favorite {
        border-color: rgba(255, 220, 120, 0.5);
        opacity: 1;
    }

    .thumb-select.active {
        background: var(--accent, rgba(99, 102, 241, 0.9));
        border-color: var(--accent);
        color: #fff;
        opacity: 1;
    }

    .thumb-overlay-seed {
        position: absolute;
        bottom: 6px;
        left: 6px;
        padding: 2px 6px;
        border-radius: 4px;
        background: rgba(0, 0, 0, 0.6);
        color: rgba(255, 255, 255, 0.9);
        font-size: 0.7rem;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
        max-width: calc(100% - 80px);
        overflow: hidden;
        text-overflow: ellipsis;
        opacity: 0;
    }
    :global(.output-thumb:hover) .thumb-overlay-seed,
    :global(.output-thumb:focus-within) .thumb-overlay-seed {
        opacity: 1;
    }
    .thumb-overlay-seed .seed-value {
        font-weight: 500;
    }
    .thumb-overlay-seed .thumb-overlay-sep {
        opacity: 0.85;
        margin: 0 2px;
    }
    .thumb-overlay-seed .thumb-overlay-time {
        font-variant-numeric: tabular-nums;
    }

    .thumb-overlay-br {
        position: absolute;
        bottom: 6px;
        right: 6px;
        display: flex;
        gap: 6px;
        align-items: center;
    }

    :global(.output-thumb.output-thumb-audio) .thumb-overlay-ul,
    :global(.output-thumb.output-thumb-video) .thumb-overlay-ul {
        top: 6px;
        left: 6px;
    }
    :global(.output-thumb.output-thumb-audio) .thumb-overlay-seed,
    :global(.output-thumb.output-thumb-video) .thumb-overlay-seed {
        bottom: 6px;
        left: 6px;
    }
</style>
