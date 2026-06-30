<script lang="ts">
	import { onMount, onDestroy, tick } from 'svelte';
	import { get } from 'svelte/store';
	import { browser } from '$app/environment';
	import { getApiBase } from '$lib/config';
	import { authState } from '$lib/stores/auth';
	import {
		THUMB_SCALE_MAX,
		THUMB_SCALE_MIN,
		getThumbFitModeCookie,
		getThumbSizeCookie,
		setThumbFitModeCookie,
		setThumbSizeCookie,
		getThumbShowFilenameCookie,
		setThumbShowFilenameCookie,
		getVaultSortCookie,
		setVaultSortCookie,
		type ThumbFitMode,
		type VaultSortMode
	} from '$lib/cookie';
	import LightboxViewer, { type LightboxItem } from '$lib/components/LightboxViewer.svelte';
	import MediaBrowserDialog from '$lib/components/MediaBrowserDialog.svelte';
	import ThumbnailOverlay from '$lib/components/ThumbnailOverlay.svelte';
	import { genVaultExistsByInputFilenames, pushInputToGenVault } from '$lib/api/genvault';
	import { createGenVaultExistsPoller, type GenVaultExistsPoller } from '$lib/genvault/existsPoller';
	import { genvaultEnabled } from '$lib/stores/genvaultEnabled';
	import { toastError, toastSuccess } from '$lib/stores/toast';

	type VaultItem = {
		filename: string;
		size_bytes: number | null;
		mtime_ms: number | null;
		uploaded_at: number | null;
		owner_user_id: string | null;
		can_delete: boolean;
		usage_generation_count?: number;
	};

	const apiBase = getApiBase() || '';
	const VAULT_LIST_TIMEOUT_MS = 120_000;

	let items = $state<VaultItem[]>([]);
	let loading = $state(true);
	let loadError = $state<string | null>(null);
	let uploading = $state(false);
	let uploadMessage = $state<string | null>(null);
	let deleting = $state<Set<string>>(new Set());
	let fileInputEl = $state<HTMLInputElement | null>(null);
	let pushingVaultInputs = $state<Set<string>>(new Set());
	let inputInVault = $state<Record<string, boolean>>({});
	let genVaultExistsPoller = $state<GenVaultExistsPoller | null>(null);

	let thumbnailScale = $state<number>(browser ? getThumbSizeCookie() : 100);
	let thumbnailFitMode = $state<ThumbFitMode>(browser ? getThumbFitModeCookie() : 'cover');
	let showThumbFilename = $state<boolean>(browser ? getThumbShowFilenameCookie() : false);
	let vaultSortMode = $state<VaultSortMode>(browser ? getVaultSortCookie() : 'recent');

	const sortedVaultItems = $derived.by(() => {
		const copy = [...items];
		if (vaultSortMode === 'usage') {
			copy.sort((a, b) => {
				const u = (b.usage_generation_count ?? 0) - (a.usage_generation_count ?? 0);
				if (u !== 0) return u;
				return (b.mtime_ms ?? b.uploaded_at ?? 0) - (a.mtime_ms ?? a.uploaded_at ?? 0);
			});
		} else {
			copy.sort(
				(a, b) => (b.mtime_ms ?? b.uploaded_at ?? 0) - (a.mtime_ms ?? a.uploaded_at ?? 0)
			);
		}
		return copy;
	});

	function setVaultSortMode(mode: VaultSortMode) {
		vaultSortMode = mode;
		if (browser) setVaultSortCookie(mode);
	}

	let lightboxOpen = $state(false);
	let lightboxImages = $state<LightboxItem[]>([]);
	let lightboxIndex = $state(0);

	let mediaBrowserOpen = $state(false);
	let mediaBrowserVaultInput = $state<string | null>(null);

	/** Natural size labels `width×height` once each vault image has loaded */
	let imageDims = $state<Record<string, string>>({});

	function formatBytes(n: number | null): string {
		if (n == null || Number.isNaN(n)) return '—';
		if (n < 1024) return `${n} B`;
		if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
		return `${(n / (1024 * 1024)).toFixed(1)} MB`;
	}

	function previewUrl(filename: string): string {
		const q = new URLSearchParams({
			filename,
			subfolder: '',
			type: 'input'
		});
		return `${apiBase}/image?${q.toString()}`;
	}

	function setThumbnailScale(value: number) {
		const next = Math.min(THUMB_SCALE_MAX, Math.max(THUMB_SCALE_MIN, Math.round(value)));
		thumbnailScale = next;
		if (browser) setThumbSizeCookie(next);
	}

	function setThumbnailFitMode(mode: ThumbFitMode) {
		thumbnailFitMode = mode;
		if (browser) setThumbFitModeCookie(mode);
	}

	function setShowThumbFilename(value: boolean) {
		showThumbFilename = value;
		if (browser) setThumbShowFilenameCookie(value);
	}

	function buildLightboxList(list: VaultItem[]): LightboxItem[] {
		return list
			.filter((it) => it.size_bytes != null)
			.map((it) => ({
				id: it.filename,
				url: previewUrl(it.filename),
				filename: it.filename,
				mediaType: 'image' as const
			}));
	}

	function openLightboxFor(filename: string) {
		const list = buildLightboxList(items);
		const idx = list.findIndex((x) => x.id === filename);
		if (idx === -1) return;
		lightboxImages = list;
		lightboxIndex = idx;
		lightboxOpen = true;
	}

	function closeLightbox() {
		lightboxOpen = false;
	}

	function openOutputsBrowser(filename: string, e?: Event) {
		e?.stopPropagation?.();
		e?.preventDefault?.();
		mediaBrowserVaultInput = filename;
		mediaBrowserOpen = true;
	}

	function closeMediaBrowser() {
		mediaBrowserOpen = false;
		mediaBrowserVaultInput = null;
	}

	async function downloadLightboxItem(item: LightboxItem) {
		const res = await fetch(item.url);
		if (!res.ok) return;
		const blob = await res.blob();
		const blobUrl = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = blobUrl;
		a.download = item.filename ?? 'vault-image.png';
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(blobUrl);
	}

	function getScrollRestoreEl(): HTMLElement | null {
		if (!browser) return null;
		return document.querySelector('main.app-viewport');
	}

	function pruneImageDimsForFilenames(filenames: Set<string>) {
		const next: Record<string, string> = {};
		for (const [k, v] of Object.entries(imageDims)) {
			if (filenames.has(k)) next[k] = v;
		}
		imageDims = next;
	}

	async function loadList(opts?: { silent?: boolean }) {
		const silent = !!opts?.silent;
		const scrollEl = silent ? getScrollRestoreEl() : null;
		const prevScrollTop = scrollEl?.scrollTop ?? 0;

		if (!silent) {
			loading = true;
			loadError = null;
		}
		const controller = new AbortController();
		const timeoutId = silent
			? null
			: window.setTimeout(() => controller.abort(), VAULT_LIST_TIMEOUT_MS);
		try {
			const res = await fetch(`${apiBase}/vault/inputs`, { signal: controller.signal });
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				loadError = (d.detail as string) || res.statusText || 'Failed to load Vault';
				items = [];
				imageDims = {};
				return;
			}
			const data = await res.json();
			const nextItems: VaultItem[] = Array.isArray(data.items) ? data.items : [];
			items = nextItems;
			pruneImageDimsForFilenames(new Set(nextItems.map((i) => i.filename)));
			if (silent && scrollEl) {
				await tick();
				scrollEl.scrollTop = prevScrollTop;
			}
		} catch (e) {
			if (e instanceof DOMException && e.name === 'AbortError') {
				loadError = `Vault list timed out after ${VAULT_LIST_TIMEOUT_MS / 1000}s. Try again or reduce input files on disk.`;
			} else {
				loadError = e instanceof Error ? e.message : 'Failed to load Vault';
			}
			items = [];
			if (!silent) imageDims = {};
		} finally {
			if (timeoutId != null) window.clearTimeout(timeoutId);
			if (!silent) loading = false;
		}
	}

	async function uploadFiles(files: FileList | null) {
		const file = files?.[0];
		if (!file || !file.type.startsWith('image/')) {
			uploadMessage = 'Choose an image file (PNG, JPEG, WebP, GIF).';
			return;
		}
		uploading = true;
		uploadMessage = null;
		try {
			const form = new FormData();
			form.append('image', file);
			const res = await fetch(`${apiBase}/upload_image`, { method: 'POST', body: form });
			const data = await res.json().catch(() => ({}));
			if (!res.ok) {
				uploadMessage = (data.detail as string) || 'Upload failed';
				return;
			}
			uploadMessage = `Uploaded as ${data.name ?? 'new file'}.`;
			await loadList({ silent: true });
		} catch (e) {
			uploadMessage = e instanceof Error ? e.message : 'Upload failed';
		} finally {
			uploading = false;
			if (fileInputEl) fileInputEl.value = '';
		}
	}

	async function downloadFile(filename: string) {
		try {
			const url = previewUrl(filename);
			const res = await fetch(url);
			if (!res.ok) {
				toastError('Download failed.');
				return;
			}
			const blob = await res.blob();
			const a = document.createElement('a');
			a.href = URL.createObjectURL(blob);
			a.download = filename;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(a.href);
		} catch {
			toastError('Download failed.');
		}
	}

	async function deleteFile(filename: string) {
		if (!window.confirm(`Delete ${filename} from the Vault? This cannot be undone.`)) return;
		deleting = new Set([...deleting, filename]);
		try {
			const res = await fetch(`${apiBase}/vault/inputs/${encodeURIComponent(filename)}`, {
				method: 'DELETE'
			});
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				toastError((d.detail as string) || 'Delete failed');
				return;
			}
			if (lightboxOpen) {
				const nextList = buildLightboxList(items.filter((i) => i.filename !== filename));
				if (nextList.length === 0) {
					closeLightbox();
				} else {
					const curId = lightboxImages[lightboxIndex]?.id;
					let ni = curId ? nextList.findIndex((x) => x.id === curId) : -1;
					if (ni === -1) ni = Math.min(lightboxIndex, nextList.length - 1);
					lightboxImages = nextList;
					lightboxIndex = ni;
				}
			}
			await loadList({ silent: true });
		} catch {
			toastError('Delete failed');
		} finally {
			const next = new Set(deleting);
			next.delete(filename);
			deleting = next;
		}
	}

	async function sendInputToGenVault(filename: string) {
		if (pushingVaultInputs.has(filename)) return;
		pushingVaultInputs = new Set([...pushingVaultInputs, filename]);
		try {
			const res = await pushInputToGenVault(filename);
			toastSuccess(res?.uploaded?.duplicate ? 'Bild ist bereits in GenVault gespeichert.' : 'An GenVault gesendet.');
			inputInVault = { ...inputInVault, [filename]: true };
		} catch (e) {
			toastError(e instanceof Error ? e.message : 'Send to GenVault failed.');
		} finally {
			const next = new Set(pushingVaultInputs);
			next.delete(filename);
			pushingVaultInputs = next;
		}
	}

	async function refreshInputGenVaultStatus() {
		const filenames = Array.from(new Set(items.map((it) => it.filename).filter(Boolean)));
		if (!filenames.length) return;
		try {
			const rows = await genVaultExistsByInputFilenames(
				filenames.map((filename) => ({ clientKey: filename, filename }))
			);
			const next = { ...inputInVault };
			for (const row of rows) {
				if (row?.client_key) next[row.client_key] = !!row.in_vault;
			}
			inputInVault = next;
		} catch {
			// ignore: purely visual status hint
		}
	}

	$effect(() => {
		if (!$genvaultEnabled) {
			genVaultExistsPoller?.destroy();
			genVaultExistsPoller = null;
			return;
		}
		if (!genVaultExistsPoller) {
			genVaultExistsPoller = createGenVaultExistsPoller(
				refreshInputGenVaultStatus,
				() => get(genvaultEnabled)
			);
		}
		const keys = Array.from(new Set(items.map((it) => it.filename).filter(Boolean)));
		genVaultExistsPoller.notifyKeys(keys);
	});

	onDestroy(() => {
		genVaultExistsPoller?.destroy();
		genVaultExistsPoller = null;
	});

	onMount(() => {
		void loadList();
	});

	let authHint = $derived(
		$authState.enabled && $authState.user
			? 'Signed in — Vault lists images you uploaded while logged in. Use the thumbnail controls to download or remove files.'
			: $authState.enabled
				? 'Sign in to manage your uploaded input images.'
				: 'Authentication is off — Vault lists all input images on this server.'
	);
</script>

<svelte:head>
	<title>Vault — WorkflowUI</title>
</svelte:head>

<section class="vault-page">
	<header class="vault-page-header">
		<div class="vault-title-block">
			<h1>Vault</h1>
			<div class="vault-subnav">
				<a href="/vault" class="vault-subnav-link active">Input Images</a>
				{#if $genvaultEnabled}
					<a href="/vault/genvault" class="vault-subnav-link">GenVault</a>
				{/if}
			</div>
			<p class="vault-lead">
				Input images for workflow runs: hover a thumbnail for download and delete, or click the image to open the
				viewer. Resolution appears on each thumbnail once the image has loaded.
			</p>
			{#if !loading}
				<p class="vault-total muted" role="status">
					{items.length} input image{items.length === 1 ? '' : 's'}
				</p>
			{/if}
			<p class="vault-hint muted">{authHint}</p>
		</div>
		<div class="gallery-controls-right">
			<div class="gallery-thumb-size">
				<label for="vault-thumb-size">Thumbnail size</label>
				<input
					id="vault-thumb-size"
					type="range"
					min={THUMB_SCALE_MIN}
					max={THUMB_SCALE_MAX}
					step="1"
					value={thumbnailScale}
					oninput={(e) => setThumbnailScale((e.currentTarget as HTMLInputElement).valueAsNumber)}
					aria-label="Thumbnail size percentage"
				/>
				<span class="thumb-size-value">{thumbnailScale}%</span>
			</div>
			<div class="gallery-thumb-fit" role="group" aria-label="Thumbnail render mode">
				<button
					type="button"
					class="thumb-fit-btn"
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
					class="thumb-fit-btn"
					class:active={thumbnailFitMode === 'contain'}
					onclick={() => setThumbnailFitMode('contain')}
					title="Fit into thumbnail"
					aria-label="Fit into thumbnail"
					aria-pressed={thumbnailFitMode === 'contain'}
				>
					Fit into thumbnail
				</button>
			</div>
			<label class="thumb-filename-option" title="When off, filenames appear on thumbnail hover only">
				<span class="thumb-filename-label">Filenames</span>
				<button
					type="button"
					role="switch"
					aria-checked={showThumbFilename}
					class="thumb-filename-toggle"
					class:on={showThumbFilename}
					aria-label="Always show filenames on thumbnails"
					onclick={() => setShowThumbFilename(!showThumbFilename)}
				>
					<span class="thumb-filename-toggle-track">
						<span class="thumb-filename-toggle-thumb"></span>
					</span>
				</button>
			</label>
			<div class="vault-sort" role="group" aria-label="Sort vault list">
				<span class="vault-sort-label muted">Sort</span>
				<button
					type="button"
					class="thumb-fit-btn"
					class:active={vaultSortMode === 'recent'}
					onclick={() => setVaultSortMode('recent')}
					aria-pressed={vaultSortMode === 'recent'}
				>
					Recent
				</button>
				<button
					type="button"
					class="thumb-fit-btn"
					class:active={vaultSortMode === 'usage'}
					onclick={() => setVaultSortMode('usage')}
					aria-pressed={vaultSortMode === 'usage'}
				>
					Most generated
				</button>
			</div>
		</div>
	</header>

	<section class="vault-toolbar card">
		<div class="vault-upload" aria-label="Upload input image">
			<input
				bind:this={fileInputEl}
				type="file"
				accept="image/png,image/jpeg,image/webp,image/gif,.png,.jpg,.jpeg,.webp,.gif"
				class="vault-file-input"
				disabled={uploading}
				onchange={(e) => void uploadFiles((e.currentTarget as HTMLInputElement).files)}
			/>
			<button
				type="button"
				class="vault-upload-btn"
				disabled={uploading}
				onclick={() => fileInputEl?.click()}
			>
				{uploading ? 'Uploading…' : 'Upload image'}
			</button>
			{#if uploadMessage}
				<p class="vault-upload-msg muted" role="status">{uploadMessage}</p>
			{/if}
		</div>
	</section>

	{#if loadError}
		<p class="vault-error" role="alert">{loadError}</p>
	{/if}

	{#if loading}
		<p class="vault-status muted">Loading…</p>
	{:else if items.length === 0}
		<p class="vault-status muted">No input images in the Vault yet. Upload an image to get started.</p>
	{:else}
		<div
			class="vault-grid-wrap output-section-body"
			class:thumb-fit-contain={thumbnailFitMode === 'contain'}
			style={`--thumb-size-scale:${thumbnailScale / 100};`}
		>
			{#each sortedVaultItems as it (it.filename)}
				<div class="vault-tile-wrap">
					<button
						type="button"
						class="vault-usage-badge"
						class:vault-usage-badge--zero={(it.usage_generation_count ?? 0) === 0}
						title="Open media browser: generations that used this input file"
						aria-label={`Generations using this input: ${it.usage_generation_count ?? 0}. Open browser.`}
						onclick={(e) => openOutputsBrowser(it.filename, e)}
					>
						{it.usage_generation_count ?? 0}×
					</button>
					{#if it.size_bytes != null}
						<div
							class="vault-thumb output-thumb"
							role="button"
							tabindex="0"
							aria-label={`Open ${it.filename} in viewer`}
							onclick={() => openLightboxFor(it.filename)}
							onkeydown={(e) => {
								if (e.key === 'Enter' || e.key === ' ') {
									e.preventDefault();
									openLightboxFor(it.filename);
								}
							}}
						>
							<ThumbnailOverlay
								mediaType="image"
								resolution={imageDims[it.filename]}
								fileName={it.filename}
								showFilenameAlways={showThumbFilename}
								showMetadata={false}
								showFavorite={false}
								showSelection={false}
								showSeed={false}
								showDownload={true}
								showSendToApp={false}
								showSendToVault={$genvaultEnabled}
								isInVault={!!inputInVault[it.filename]}
								showDelete={it.can_delete}
								deleteDisabled={deleting.has(it.filename)}
								onDownload={() => void downloadFile(it.filename)}
								onSendToVault={() => void sendInputToGenVault(it.filename)}
								onDelete={() => void deleteFile(it.filename)}
							>
								<img
									class="vault-thumb-img"
									src={previewUrl(it.filename)}
									alt=""
									loading="lazy"
									onload={(e) => {
										const el = e.currentTarget as HTMLImageElement;
										if (el.naturalWidth > 0 && el.naturalHeight > 0) {
											imageDims = {
												...imageDims,
												[it.filename]: `${el.naturalWidth}×${el.naturalHeight}`
											};
										}
									}}
								/>
							</ThumbnailOverlay>
						</div>
					{:else}
						<div class="vault-thumb vault-thumb-missing output-thumb muted" role="img" aria-label="Missing file">
							File missing on disk
						</div>
					{/if}
					<div class="vault-tile-footer">
						<span class="vault-size muted">{formatBytes(it.size_bytes)}</span>
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>

<LightboxViewer
	open={lightboxOpen}
	items={lightboxImages}
	index={lightboxIndex}
	onIndexChange={(i) => {
		lightboxIndex = i;
	}}
	onClose={closeLightbox}
	onDownload={(item) => void downloadLightboxItem(item)}
	onSendToVault={$genvaultEnabled
		? (item) => {
				const name = item.filename || item.id;
				if (name) void sendInputToGenVault(name);
			}
		: undefined}
	isInVault={$genvaultEnabled
		? (item) => {
				const name = item.filename || item.id;
				return !!(name && inputInVault[name]);
			}
		: undefined}
	isSendingToVault={$genvaultEnabled
		? (item) => {
				const name = item.filename || item.id;
				return !!(name && pushingVaultInputs.has(name));
			}
		: undefined}
	ariaTitle="Vault image viewer"
/>

<MediaBrowserDialog
	open={mediaBrowserOpen}
	filterByVaultInputFilename={mediaBrowserVaultInput}
	onClose={closeMediaBrowser}
/>

<style>
	.vault-page {
		width: 100%;
		max-width: none;
		margin: 0;
		padding: 0.75rem 1rem 1.5rem;
		box-sizing: border-box;
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-height: min-content;
	}

	.vault-page-header {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		flex-wrap: wrap;
		position: sticky;
		top: 0;
		z-index: 5;
		background: var(--bg);
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--border);
	}

	.vault-title-block {
		flex: 1 1 280px;
		min-width: 0;
	}

	.vault-page-header h1 {
		margin: 0 0 0.35rem 0;
		font-size: 1.5rem;
	}

	.vault-lead {
		margin: 0 0 0.35rem 0;
		color: var(--text);
		line-height: 1.45;
		max-width: 72ch;
	}
	.vault-subnav {
		display: inline-flex;
		gap: 0.5rem;
		margin: 0 0 0.45rem 0;
	}
	.vault-subnav-link {
		text-decoration: none;
		padding: 0.3rem 0.6rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text);
		background: var(--surface);
		font-size: 0.82rem;
	}
	.vault-subnav-link.active {
		border-color: var(--accent);
		color: var(--accent);
		background: var(--accent-soft);
	}

	.vault-hint {
		margin: 0;
		font-size: 0.9rem;
		line-height: 1.4;
	}

	.gallery-controls-right {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
		justify-content: flex-end;
		flex: 0 1 auto;
	}

	.gallery-thumb-size {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
	}
	.gallery-thumb-size label {
		font-size: 0.8rem;
		color: var(--muted);
	}
	.gallery-thumb-size input[type='range'] {
		width: min(280px, 52vw);
	}
	.thumb-size-value {
		min-width: 3.5rem;
		font-size: 0.8rem;
		color: var(--muted);
		text-align: right;
	}
	.gallery-thumb-fit {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.thumb-fit-btn {
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--muted);
		border-radius: 6px;
		padding: 0.3rem 0.55rem;
		font-size: 0.78rem;
		cursor: pointer;
	}
	.thumb-fit-btn.active {
		border-color: var(--accent);
		color: var(--accent);
		background: var(--accent-soft);
	}
	.thumb-filename-option {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
	}
	.thumb-filename-label {
		font-size: 0.8rem;
		color: var(--muted);
	}
	.thumb-filename-toggle {
		border: none;
		background: transparent;
		padding: 0;
		cursor: pointer;
	}
	.thumb-filename-toggle-track {
		display: block;
		width: 2.5rem;
		height: 1.35rem;
		border-radius: 999px;
		background: var(--border);
		position: relative;
		transition: background 0.15s ease;
	}
	.thumb-filename-toggle.on .thumb-filename-toggle-track {
		background: color-mix(in srgb, var(--accent) 55%, var(--border));
	}
	.thumb-filename-toggle-thumb {
		position: absolute;
		top: 2px;
		left: 2px;
		width: calc(1.35rem - 4px);
		height: calc(1.35rem - 4px);
		border-radius: 50%;
		background: var(--text);
		transition: transform 0.15s ease;
	}
	.thumb-filename-toggle.on .thumb-filename-toggle-thumb {
		transform: translateX(1.15rem);
	}

	.vault-toolbar.card {
		padding: 0.75rem 1rem;
		border-radius: var(--radius-lg);
		border: 1px solid var(--border);
		background: var(--card);
	}

	.vault-upload {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem;
	}

	.vault-file-input {
		position: absolute;
		width: 1px;
		height: 1px;
		opacity: 0;
		pointer-events: none;
	}

	.vault-upload-btn {
		padding: 0.5rem 1rem;
		border-radius: 8px;
		border: none;
		cursor: pointer;
		font-weight: 600;
		background: var(--accent);
		color: var(--accent-contrast);
	}

	.vault-upload-btn:disabled {
		opacity: 0.7;
		cursor: wait;
	}

	.vault-upload-msg {
		margin: 0;
		font-size: 0.9rem;
		flex-basis: 100%;
	}

	.vault-error {
		margin: 0;
		color: var(--warning);
	}

	.vault-status {
		margin: 0;
	}

	/* Match Activity gallery: scale min column by cookie-driven --thumb-size-scale */
	.output-section-body {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(calc(260px * var(--thumb-size-scale, 1)), 1fr));
		gap: 0.75rem;
		width: 100%;
	}

	.output-section-body.thumb-fit-contain .vault-thumb-img,
	.output-section-body.thumb-fit-contain :global(.thumb-overlay-media img) {
		object-fit: contain;
		background: #0b0b0b;
	}

	.vault-tile-wrap {
		display: flex;
		flex-direction: column;
		gap: 0.45rem;
		min-width: 0;
		position: relative;
	}

	.vault-usage-badge {
		position: absolute;
		top: 0.35rem;
		right: 0.35rem;
		/* Below .vault-page-header (z-index: 5) so badges don’t float over the sticky top bar when scrolling */
		z-index: 3;
		min-width: 1.65rem;
		padding: 0.15rem 0.4rem;
		border-radius: 999px;
		border: 1px solid color-mix(in srgb, var(--accent) 45%, var(--border));
		background: color-mix(in srgb, var(--accent) 22%, var(--card));
		color: var(--text);
		font-size: 0.72rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		line-height: 1.2;
		cursor: pointer;
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);
	}
	.vault-usage-badge:hover {
		border-color: var(--accent);
		color: var(--accent);
	}
	.vault-usage-badge--zero {
		opacity: 0.65;
		font-weight: 600;
	}

	.output-thumb {
		position: relative;
		border: 1px solid var(--border);
		border-radius: 8px;
		overflow: hidden;
		background: var(--surface);
		aspect-ratio: 1;
		display: block;
	}

	.output-thumb[role='button'] {
		cursor: pointer;
	}

	.vault-thumb-img {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}

	.vault-thumb-missing {
		display: flex;
		align-items: center;
		justify-content: center;
		text-align: center;
		font-size: 0.82rem;
		padding: 0.5rem;
	}

	.vault-tile-footer {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		min-width: 0;
	}

	.vault-size {
		font-size: 0.75rem;
	}

	@media (max-width: 900px) {
		.vault-page-header {
			flex-direction: column;
			align-items: flex-start;
		}
		.gallery-controls-right {
			width: 100%;
			justify-content: flex-start;
		}
		.output-section-body {
			grid-template-columns: repeat(auto-fill, minmax(calc(120px * var(--thumb-size-scale, 1)), 1fr));
		}
	}
</style>
