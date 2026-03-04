<script lang="ts">
    import { onDestroy } from 'svelte';
    import { getApiBase } from '$lib/config';

    type MediaType = 'image' | 'video' | 'audio';

    const MEDIA_CONFIG: Record<MediaType, { accept: string; extensions: string[]; mimePrefixes: string[]; errorHint: string }> = {
        image: { accept: '.png,.jpg,.jpeg,.webp,.gif', extensions: ['.png', '.jpg', '.jpeg', '.webp', '.gif'], mimePrefixes: ['image/'], errorHint: 'Use PNG, JPEG, WebP or GIF.' },
        video: { accept: '.mp4,.webm,.mkv,.mov', extensions: ['.mp4', '.webm', '.mkv', '.mov'], mimePrefixes: ['video/'], errorHint: 'Use MP4, WebM, MKV or MOV.' },
        audio: { accept: '.mp3,.wav,.ogg,.flac,.m4a', extensions: ['.mp3', '.wav', '.ogg', '.flac', '.m4a'], mimePrefixes: ['audio/'], errorHint: 'Use MP3, WAV, OGG, FLAC or M4A.' },
    };

    onDestroy(() => {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
    });

    $effect(() => {
        if (overrideDisplayValue && overrideDisplayValue !== '' && (value == null || value === '')) {
            value = overrideDisplayValue;
        }
    });

    let {
        input,
        value = $bindable(''),
        mediaType = 'image',
        appId = null,
        prefillRunId = null,
        prefillSubfolder = '',
        prefillType = 'image',
        overrideDisplayValue = undefined
    }: {
        input: unknown;
        value?: string;
        mediaType?: MediaType;
        appId?: string | null;
        prefillRunId?: string | null;
        prefillSubfolder?: string;
        prefillType?: string;
        overrideDisplayValue?: string;
    } = $props();

    const config = $derived(MEDIA_CONFIG[mediaType]);

    function hasAllowedExtension(name: string): boolean {
        const ext = name.slice(name.lastIndexOf('.')).toLowerCase();
        return config.extensions.includes(ext);
    }

    function isValidMime(type: string): boolean {
        return config.mimePrefixes.some((p) => type.startsWith(p)) || type.startsWith('application/');
    }

    function mediaValueToString(v: unknown): string {
        if (v == null) return '';
        if (typeof v === 'string') return v;
        if (typeof v === 'object' && v !== null && 'filename' in v) {
            const f = (v as { filename?: unknown }).filename;
            return typeof f === 'string' ? f : '';
        }
        return '';
    }
    const displayValue = $derived((overrideDisplayValue != null && overrideDisplayValue !== '') ? overrideDisplayValue : mediaValueToString(value));

    let uploading = $state(false);
    let error = $state<string | null>(null);
    let fileInput: HTMLInputElement;
    let previewUrl = $state('');
    const prefilledMediaUrl = $derived.by(() => {
        const filename = displayValue;
        if (!filename || previewUrl) return '';
        const base = getApiBase() || '';
        const params = new URLSearchParams();
        params.set('filename', filename);
        if (prefillRunId) {
            params.set('subfolder', prefillSubfolder);
            params.set('type', prefillType || mediaType);
            params.set('run_id', prefillRunId);
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
            error = `${config.errorHint} Got: ${file.name}`;
            return;
        }
        if (!isValidMime(file.type)) {
            error = `File must be a ${mediaType}. ${config.errorHint}`;
            return;
        }
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        if (mediaType === 'image') {
            previewUrl = URL.createObjectURL(file);
        }
        error = null;
        uploading = true;
        try {
            const apiBase = getApiBase() || '';
            let url: string;
            const form = new FormData();
            if (mediaType === 'image') {
                form.append('image', file);
                url = appId ? `${apiBase}/upload_image?app_id=${encodeURIComponent(appId)}` : `${apiBase}/upload_image`;
            } else {
                form.append('file', file);
                url = appId
                    ? `${apiBase}/upload_media?type=${mediaType}&app_id=${encodeURIComponent(appId)}`
                    : `${apiBase}/upload_media?type=${mediaType}`;
            }
            const res = await fetch(url, { method: 'POST', body: form });
            if (!res.ok) {
                const text = await res.text();
                throw new Error(text || `Upload failed (${res.status})`);
            }
            const data = await res.json();
            value = data.name ?? data.filename ?? file.name;
        } catch (err) {
            error = err instanceof Error ? err.message : 'Upload failed';
        } finally {
            uploading = false;
        }
    }

    function clearMedia() {
        if (previewUrl) {
            URL.revokeObjectURL(previewUrl);
            previewUrl = '';
        }
        value = '';
        error = null;
        if (fileInput) fileInput.value = '';
    }

    function chooseFile() {
        if (fileInput && !uploading) fileInput.click();
    }

    const chooseLabel = mediaType === 'image' ? 'Choose image file' : mediaType === 'video' ? 'Choose video file' : 'Choose audio file';
    const clearLabel = mediaType === 'image' ? 'Clear image' : mediaType === 'video' ? 'Clear video' : 'Clear audio';
</script>

<label class="media-field">
    <div class="label">{input.label}</div>
    <div class="media-row">
        <div class="file-row">
            <input
                type="file"
                accept={config.accept}
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
                aria-label={chooseLabel}
            >Choose file</button>
            {#if displayValue}
                <span class="filename" title={displayValue}>{displayValue}</span>
                <button type="button" class="clear-btn" onclick={clearMedia} title={clearLabel}>×</button>
            {:else}
                <span class="no-file">No file chosen</span>
            {/if}
        </div>
        <div class="preview-wrap" aria-hidden="true">
            {#if mediaType === 'image'}
                {#if previewUrl}
                    <img src={previewUrl} alt="" class="preview-img" />
                {:else if displayValue && prefilledMediaUrl}
                    <img src={prefilledMediaUrl} alt="" class="preview-img" referrerpolicy="no-referrer" />
                {:else}
                    <div class="preview-placeholder"></div>
                {/if}
            {:else}
                <div class="preview-placeholder preview-media">
                    <span class="media-icon">{mediaType === 'video' ? '▶' : '♪'}</span>
                </div>
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

<style>
    .media-field {
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
    .media-row {
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
    .preview-placeholder.preview-media {
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .preview-placeholder .media-icon {
        font-size: 2rem;
        color: var(--muted, #888);
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
</style>
