<script lang="ts">
    import { onDestroy } from 'svelte';
    import { getApiBase } from '$lib/config';
    import MediaBrowserDialog from '$lib/components/MediaBrowserDialog.svelte';
    import type { MediaBrowserSelection } from '$lib/types/mediaBrowser';

    onDestroy(() => {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
    });

    $effect(() => {
        if (overrideDisplayValue && overrideDisplayValue !== '' && (value == null || value === '')) {
            value = overrideDisplayValue;
        }
    });

    const ACCEPT_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.gif'];
    const ACCEPT_ATTR = '.png,.jpg,.jpeg,.webp,.gif';
    const MIME_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'];

    function hasAllowedExtension(name: string): boolean {
        const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
        return ACCEPT_EXTENSIONS.includes(ext);
    }

    let {
        input,
        value = $bindable(''),
        appId = null,
        projectId = null,
        prefillRunId = null,
        prefillSubfolder = '',
        prefillType = 'image',
        overrideDisplayValue = undefined,
        onMediaSelection = undefined
    }: {
        input: unknown;
        value?: string;
        appId?: string | null;
        projectId?: string | null;
        prefillRunId?: string | null;
        prefillSubfolder?: string;
        prefillType?: string;
        overrideDisplayValue?: string;
        onMediaSelection?: ((selection: MediaBrowserSelection | null) => void) | undefined;
    } = $props();

    function imageValueToString(v: unknown): string {
        if (v == null) return '';
        if (typeof v === 'string') return v;
        if (typeof v === 'object' && v !== null && 'filename' in v) {
            const f = (v as { filename?: unknown }).filename;
            return typeof f === 'string' ? f : '';
        }
        return '';
    }
    const displayValue = $derived((overrideDisplayValue != null && overrideDisplayValue !== '') ? overrideDisplayValue : imageValueToString(value));

    let uploading = $state(false);
    let error = $state<string | null>(null);
    let fileInput: HTMLInputElement;
    let previewUrl = $state('');
    let browserOpen = $state(false);
    let browserSelection = $state<MediaBrowserSelection | null>(null);
    $effect(() => {
        if (!browserSelection) return;
        if (displayValue !== browserSelection.filename) {
            browserSelection = null;
        }
    });
    const prefilledImageUrl = $derived.by(() => {
        const filename = displayValue;
        if (!filename || previewUrl) return '';
        const base = getApiBase() || '';
        const params = new URLSearchParams();
        params.set('filename', filename);
        const fromBrowser = browserSelection;
        const effectiveRunId = fromBrowser?.source === 'generation'
            ? (fromBrowser.runId ?? null)
            : prefillRunId;
        const effectiveSubfolder = fromBrowser?.subfolder ?? prefillSubfolder;
        const effectiveType = fromBrowser?.type ?? prefillType ?? 'image';
        if (effectiveRunId) {
            params.set('subfolder', effectiveSubfolder || '');
            params.set('type', effectiveType || 'image');
            params.set('run_id', effectiveRunId);
        } else {
            params.set('subfolder', '');
            params.set('type', 'input');
        }
        return `${base}/image?${params.toString()}`;
    });

    async function onFileChange(e: Event) {
        const target = e.target as HTMLInputElement;
        const file = target?.files?.[0];
        if (!file) return;
        if (!hasAllowedExtension(file.name)) {
            error = `Use PNG, JPEG, WebP or GIF. Got: ${file.name}`;
            return;
        }
        if (!MIME_TYPES.includes(file.type) && !file.type.startsWith('image/')) {
            error = 'File must be an image (PNG, JPEG, WebP or GIF).';
            return;
        }
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = URL.createObjectURL(file);
        error = null;
        uploading = true;
        try {
            const apiBase = getApiBase() || '';
            const form = new FormData();
            form.append('image', file);
            const url = appId ? `${apiBase}/upload_image?app_id=${encodeURIComponent(appId)}` : `${apiBase}/upload_image`;
            const res = await fetch(url, {
                method: 'POST',
                body: form
            });
            if (!res.ok) {
                const text = await res.text();
                throw new Error(text || `Upload failed (${res.status})`);
            }
            const data = await res.json();
            value = data.name ?? data.filename ?? file.name;
            browserSelection = null;
            onMediaSelection?.(null);
        } catch (err) {
            error = err instanceof Error ? err.message : 'Upload failed';
        } finally {
            uploading = false;
        }
    }

    function clearImage() {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
            previewUrl = '';
        }
        value = '';
        browserSelection = null;
        onMediaSelection?.(null);
        error = null;
        if (fileInput) fileInput.value = '';
    }

    function chooseFile() {
        if (fileInput && !uploading) fileInput.click();
    }

    function chooseFromBrowser(selection: MediaBrowserSelection) {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
            previewUrl = '';
        }
        browserSelection = selection;
        value = selection.filename;
        error = null;
        if (fileInput) fileInput.value = '';
        onMediaSelection?.(selection);
        browserOpen = false;
    }
</script>

<label class="image-field">
    <div class="label">{input.label}</div>
    <div class="image-row">
        <div class="file-row">
            <input
                type="file"
                accept={ACCEPT_ATTR}
                bind:this={fileInput}
                onchange={onFileChange}
                disabled={uploading}
                class="file-input"
                aria-label={input.label}
            />
            <button
                type="button"
                class="choose-file-btn"
                onclick={chooseFile}
                disabled={uploading}
                aria-label="Choose image file"
            >Choose file</button>
            <button
                type="button"
                class="choose-file-btn"
                onclick={() => (browserOpen = true)}
                disabled={uploading}
                aria-label="Browse generated media"
            >Browse media</button>
            {#if displayValue}
                <span class="filename" title={displayValue}>{displayValue}</span>
                <button type="button" class="clear-btn" onclick={clearImage} title="Clear image">×</button>
            {:else}
                <span class="no-file">No file chosen</span>
            {/if}
        </div>
        <div class="preview-wrap" aria-hidden="true">
            {#if previewUrl}
                <img src={previewUrl} alt="" class="preview-img" />
            {:else if displayValue && prefilledImageUrl}
                <img src={prefilledImageUrl} alt="" class="preview-img" referrerpolicy="no-referrer" />
            {:else}
                <div class="preview-placeholder"></div>
            {/if}
        </div>
    </div>
    {#if uploading}
        <div class="hint">Uploading…</div>
    {/if}
    {#if error}
        <div class="error" role="alert">{error}</div>
    {/if}
</label>

<MediaBrowserDialog
    open={browserOpen}
    initialProjectId={projectId}
    initialAppId={appId}
    onClose={() => (browserOpen = false)}
    onSelect={chooseFromBrowser}
/>

<style>
    .image-field {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        min-width: 0;
    }
    .label {
        font-size: 0.85rem;
        font-weight: 500;
        opacity: 0.9;
    }
    .image-row {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        flex-wrap: nowrap;
        min-width: 0;
    }
    .file-row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex: 1;
        min-width: 0;
    }
    .file-input {
        position: absolute;
        opacity: 0;
        width: 0;
        height: 0;
        pointer-events: none;
    }
    .choose-file-btn {
        flex-shrink: 0;
        padding: 0.35rem 0.6rem;
        border-radius: 6px;
        border: 1px solid var(--border);
        background: rgba(255, 255, 255, 0.06);
        color: inherit;
        cursor: pointer;
        font-size: 0.8rem;
    }
    .choose-file-btn:hover:not(:disabled) {
        background: rgba(255, 255, 255, 0.08);
    }
    .choose-file-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }
    .filename,
    .no-file {
        flex-shrink: 1;
        min-width: 0;
        font-size: 0.8rem;
        color: var(--muted, #888);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .preview-wrap {
        flex-shrink: 0;
        width: 140px;
        height: 140px;
        border-radius: 8px;
        overflow: hidden;
        background: #111;
        box-shadow: 0 0 0 1px var(--border);
    }
    .preview-placeholder {
        width: 100%;
        height: 100%;
        background: rgba(255, 255, 255, 0.04);
    }
    .preview-img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
    }
    .hint {
        font-size: 0.85rem;
        color: var(--muted);
    }
    .clear-btn {
        flex-shrink: 0;
        padding: 0.2rem 0.45rem;
        border-radius: 4px;
        border: 1px solid var(--border);
        background: rgba(255, 255, 255, 0.06);
        color: var(--muted);
        cursor: pointer;
        font-size: 1rem;
        line-height: 1;
    }
    .clear-btn:hover {
        color: var(--text);
        background: rgba(255, 255, 255, 0.08);
    }
    .error {
        font-size: 0.8rem;
        color: var(--error, #e57373);
    }
    @media (max-width: 639px) {
        .image-row {
            flex-direction: column;
            align-items: stretch;
            gap: 0.6rem;
        }
        .file-row {
            flex-wrap: wrap;
            align-items: stretch;
            gap: 0.45rem;
        }
        .choose-file-btn,
        .clear-btn {
            min-height: 44px;
        }
        .choose-file-btn {
            flex: 1 1 calc(50% - 0.25rem);
            min-width: 130px;
            font-size: 0.82rem;
        }
        .filename,
        .no-file {
            order: 3;
            width: 100%;
            white-space: nowrap;
            font-size: 0.78rem;
        }
        .clear-btn {
            order: 2;
            min-width: 44px;
        }
        .preview-wrap {
            width: 100%;
            max-width: 220px;
            height: auto;
            aspect-ratio: 1 / 1;
        }
    }
</style>
