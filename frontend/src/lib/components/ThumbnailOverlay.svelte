<script lang="ts">
    import type { Snippet } from 'svelte';
    import FavoriteSash from '$lib/components/FavoriteSash.svelte';
    let {
        mediaType = 'image',
        resolution = undefined as string | undefined,
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
        showSendToVault = false,
        isInVault = false,
        sendingToVault = false,
        showDelete = false,
        deleteDisabled = false,
        fileName = undefined as string | undefined,
        showFilenameAlways = false,
        onMetadataClick = undefined as (() => void) | undefined,
        onToggleFavorite = undefined as (() => void) | undefined,
        onToggleSelection = undefined as (() => void) | undefined,
        onDownload = undefined as (() => void) | undefined,
        onSendToApp = undefined as (() => void) | undefined,
        onSendToVault = undefined as (() => void) | undefined,
        onDelete = undefined as (() => void) | undefined,
        children
    }: {
        mediaType?: 'image' | 'video' | 'audio';
        resolution?: string;
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
        showSendToVault?: boolean;
        isInVault?: boolean;
        sendingToVault?: boolean;
        showDelete?: boolean;
        deleteDisabled?: boolean;
        fileName?: string;
        showFilenameAlways?: boolean;
        onMetadataClick?: () => void;
        onToggleFavorite?: () => void;
        onToggleSelection?: () => void;
        onDownload?: () => void;
        onSendToApp?: () => void;
        onSendToVault?: () => void;
        onDelete?: () => void;
        children?: Snippet;
    } = $props();

    const showFilenameChip = $derived(!!(fileName != null && String(fileName).trim() !== ''));
    const showSeedChip = $derived(
        (!!(mediaType !== 'audio' && resolution)) ||
            (showSeed && seed !== undefined && seed !== null && String(seed).trim() !== '') ||
            executionTimeSec != null
    );

    function stop(e: Event) {
        e.preventDefault();
        e.stopPropagation();
    }
</script>

<div class="thumb-overlay-root">
    <FavoriteSash visible={isFavorite} />
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

    {#if showFilenameChip || showSeedChip}
        <div class="thumb-overlay-bl-stack">
            {#if showSeedChip}
                <span
                    class="thumb-overlay-seed"
                    title={[
                        mediaType !== 'audio' && resolution ? 'Media resolution' : '',
                        showSeed && seed != null ? 'Seed value' : '',
                        executionTimeSec != null ? 'Generation time' : ''
                    ]
                        .filter(Boolean)
                        .join(' · ') || undefined}
                >
                    {#if mediaType !== 'audio' && resolution}
                        <span class="thumb-overlay-resolution">{resolution}</span>
                    {/if}
                    {#if showSeed && seed !== undefined && seed !== null && String(seed).trim() !== ''}
                        {#if mediaType !== 'audio' && resolution}
                            <span class="thumb-overlay-sep" aria-hidden="true"> · </span>
                        {/if}
                        <span class="seed-value">{seed}</span>
                    {/if}
                    {#if executionTimeSec != null}
                        {#if (showSeed && seed !== undefined && seed !== null && String(seed).trim() !== '') || (mediaType !== 'audio' && resolution)}
                            <span class="thumb-overlay-sep" aria-hidden="true"> · </span>
                        {/if}
                        <span class="thumb-overlay-time">{Math.round(Number(executionTimeSec))} sec</span>
                    {/if}
                </span>
            {/if}
            {#if showFilenameChip}
                <span
                    class="thumb-overlay-filename"
                    class:thumb-overlay-filename--always={showFilenameAlways}
                    title={fileName}
                >{fileName}</span>
            {/if}
        </div>
    {/if}

    {#if showDownload || showSendToApp || showSendToVault || (showDelete && onDelete)}
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
            {#if showSendToVault && onSendToVault}
                <button
                    type="button"
                    class="thumb-overlay-btn"
                    class:thumb-overlay-btn-active={isInVault}
                    title="Save to GenVault"
                    aria-label="Save to GenVault"
                    onclick={(e) => { stop(e); onSendToVault(); }}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M8 12h8" />
                        <path d="M12 8v8" />
                    </svg>
                </button>
            {/if}
            {#if showDelete && onDelete}
                <button
                    type="button"
                    class="thumb-overlay-btn thumb-overlay-delete"
                    disabled={deleteDisabled}
                    title="Remove from Vault"
                    aria-label="Remove from Vault"
                    onclick={(e) => { stop(e); if (!deleteDisabled) onDelete(); }}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <path d="M3 6h18" />
                        <path d="M8 6V4h8v2" />
                        <path d="M10 11v6" />
                        <path d="M14 11v6" />
                        <path d="M6 6l1 14h10l1-14" />
                    </svg>
                </button>
            {/if}
        </div>
    {/if}

    {#if sendingToVault}
        <div class="thumb-transfer-overlay" aria-hidden="true">
            <span class="thumb-transfer-label">Sending to GenVault…</span>
            <span class="thumb-transfer-bar">
                <span class="thumb-transfer-bar-fill"></span>
            </span>
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
    /* FavoriteSash is full-bleed decorative; parent rule would re-enable hits and block checkbox */
    .thumb-overlay-root > :global(.favorite-sash),
    .thumb-overlay-root > :global(.favorite-sash *) {
        pointer-events: none;
    }
    .thumb-overlay-media {
        position: absolute;
        inset: 0;
        z-index: 0;
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
    .thumb-overlay-delete:hover:not(:disabled) {
        border-color: rgba(248, 113, 113, 0.85);
        color: #fecaca;
    }
    .thumb-overlay-delete:disabled {
        opacity: 0.35;
        cursor: not-allowed;
    }
    .thumb-overlay-btn svg {
        width: 14px;
        height: 14px;
    }
    .thumb-overlay-btn-active {
        border-color: color-mix(in srgb, var(--accent) 70%, var(--border));
        background: color-mix(in srgb, var(--accent) 28%, rgba(0, 0, 0, 0.55));
        color: var(--accent);
        opacity: 1;
    }

    .thumb-overlay-ul {
        position: absolute;
        top: 6px;
        left: 6px;
        z-index: 2;
    }

    .thumb-overlay-ur {
        position: absolute;
        top: 6px;
        right: 6px;
        z-index: 2;
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

    .thumb-overlay-bl-stack {
        position: absolute;
        bottom: 6px;
        left: 6px;
        z-index: 2;
        display: flex;
        flex-direction: column-reverse;
        align-items: flex-start;
        gap: 4px;
        max-width: calc(100% - 80px);
        pointer-events: none;
    }
    .thumb-overlay-bl-stack .thumb-overlay-seed,
    .thumb-overlay-bl-stack .thumb-overlay-filename {
        pointer-events: auto;
    }
    .thumb-overlay-seed {
        padding: 2px 6px;
        border-radius: 4px;
        background: rgba(0, 0, 0, 0.6);
        color: rgba(255, 255, 255, 0.9);
        font-size: 0.7rem;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        opacity: 0;
    }
    .thumb-overlay-filename {
        padding: 2px 6px;
        border-radius: 4px;
        background: rgba(0, 0, 0, 0.6);
        color: rgba(255, 255, 255, 0.9);
        font-size: 0.7rem;
        white-space: nowrap;
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        opacity: 0;
    }
    .thumb-overlay-filename.thumb-overlay-filename--always {
        opacity: 1;
    }
    :global(.output-thumb:hover) .thumb-overlay-seed,
    :global(.output-thumb:focus-within) .thumb-overlay-seed {
        opacity: 1;
    }
    :global(.output-thumb:hover) .thumb-overlay-filename,
    :global(.output-thumb:focus-within) .thumb-overlay-filename {
        opacity: 1;
    }
    .thumb-overlay-seed .seed-value {
        font-weight: 500;
    }
    .thumb-overlay-seed .thumb-overlay-resolution {
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
        z-index: 2;
        display: flex;
        gap: 6px;
        align-items: center;
    }
    .thumb-transfer-overlay {
        position: absolute;
        inset: 0;
        z-index: 4;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        background: color-mix(in srgb, rgba(10, 12, 20, 0.72) 85%, transparent);
        backdrop-filter: blur(1.5px);
        pointer-events: none;
    }
    .thumb-transfer-label {
        font-size: 0.74rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        color: rgba(255, 255, 255, 0.96);
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.7);
    }
    .thumb-transfer-bar {
        width: min(84%, 170px);
        height: 5px;
        border-radius: 999px;
        overflow: hidden;
        background: rgba(255, 255, 255, 0.22);
        border: 1px solid rgba(255, 255, 255, 0.25);
    }
    .thumb-transfer-bar-fill {
        display: block;
        height: 100%;
        width: 42%;
        border-radius: 999px;
        background: linear-gradient(
            90deg,
            rgba(255, 255, 255, 0.25) 0%,
            color-mix(in srgb, var(--accent) 80%, #9fb4ff) 38%,
            color-mix(in srgb, var(--accent) 65%, #dbe5ff) 62%,
            rgba(255, 255, 255, 0.2) 100%
        );
        animation: thumb-transfer-slide 1.15s ease-in-out infinite;
        will-change: transform;
    }
    @keyframes thumb-transfer-slide {
        0% { transform: translateX(-110%); }
        100% { transform: translateX(250%); }
    }

    :global(.output-thumb.output-thumb-audio) .thumb-overlay-ul,
    :global(.output-thumb.output-thumb-video) .thumb-overlay-ul {
        top: 6px;
        left: 6px;
    }
    :global(.output-thumb.output-thumb-audio) {
        --thumb-audio-bar-offset: 52px;
    }
    :global(.output-thumb.output-thumb-audio) .thumb-overlay-br {
        bottom: var(--thumb-audio-bar-offset, 48px);
    }
    :global(.output-thumb.output-thumb-audio) .thumb-overlay-bl-stack {
        bottom: var(--thumb-audio-bar-offset, 48px);
        left: 6px;
    }
</style>
