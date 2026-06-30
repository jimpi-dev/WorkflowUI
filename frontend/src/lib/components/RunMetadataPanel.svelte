<script lang="ts">
	import { getApiBase } from '$lib/config';
	import { formatBytes } from '$lib/utils/format';
	import SendToAppDialog from '$lib/components/SendToAppDialog.svelte';
	import LightboxViewer, { type LightboxItem } from '$lib/components/LightboxViewer.svelte';
	import MediaBrowserDialog from '$lib/components/MediaBrowserDialog.svelte';

	const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp']);
	const VIDEO_EXTS = new Set(['.mp4', '.mov', '.webm', '.mkv', '.avi']);
	const AUDIO_EXTS = new Set(['.mp3', '.wav', '.ogg', '.flac', '.m4a']);

	type InputMediaEntry = {
		key: string;
		label: string;
		filename: string;
		mediaType: 'image' | 'video' | 'audio';
		url: string;
	};

	function bindingBaseKey(key: string): string {
		const m = key.match(/^(.*)\[\d+]$/);
		return m?.[1] ?? key;
	}

	function friendlyInputLabel(field: string | undefined, key: string): string {
		const source = (field || key).split('.').pop() ?? key;
		const s = source.replace(/_/g, ' ').trim();
		if (!s) return key;
		return s.charAt(0).toUpperCase() + s.slice(1);
	}

	function guessInputMediaType(field: string, key: string, value: string): 'image' | 'video' | 'audio' | null {
		const hay = `${field} ${key}`.toLowerCase();
		if (['image', 'img', 'photo'].some((t) => hay.includes(t))) return 'image';
		if (['video', 'movie', 'clip'].some((t) => hay.includes(t))) return 'video';
		if (['audio', 'sound', 'music'].some((t) => hay.includes(t))) return 'audio';
		const lower = value.toLowerCase();
		for (const ext of IMAGE_EXTS) {
			if (lower.endsWith(ext)) return 'image';
		}
		for (const ext of VIDEO_EXTS) {
			if (lower.endsWith(ext)) return 'video';
		}
		for (const ext of AUDIO_EXTS) {
			if (lower.endsWith(ext)) return 'audio';
		}
		return null;
	}

	function flattenSnapshotStringValues(values: Record<string, unknown>): { key: string; value: string }[] {
		const out: { key: string; value: string }[] = [];
		for (const [key, value] of Object.entries(values)) {
			if (typeof value === 'string' && value.trim()) {
				out.push({ key, value: value.trim() });
			} else if (Array.isArray(value)) {
				value.forEach((item, i) => {
					if (typeof item === 'string' && item.trim()) {
						out.push({ key: `${key}[${i}]`, value: item.trim() });
					}
				});
			}
		}
		return out;
	}

	function inputMediaEntriesFromSnapshot(
		snap: Record<string, unknown> | null | undefined,
		runId: string,
		api: string
	): InputMediaEntry[] {
		if (!snap || typeof snap !== 'object') return [];
		const valuesRaw = snap.values;
		const bindingsRaw = snap.bindings;
		if (!valuesRaw || typeof valuesRaw !== 'object' || Array.isArray(valuesRaw)) return [];
		const values = valuesRaw as Record<string, unknown>;
		const bindByKey: Record<string, { field?: string }> = {};
		if (Array.isArray(bindingsRaw)) {
			for (const b of bindingsRaw) {
				if (b && typeof b === 'object' && typeof (b as { key?: unknown }).key === 'string') {
					const k = (b as { key: string }).key;
					bindByKey[k] = b as { field?: string };
				}
			}
		}
		const flat = flattenSnapshotStringValues(values);
		const out: InputMediaEntry[] = [];
		let n = 0;
		for (const { key, value: filename } of flat) {
			if (n >= 48) break;
			const b = bindByKey[bindingBaseKey(key)] ?? {};
			const field = String(b.field ?? key);
			const mediaType = guessInputMediaType(field, key, filename);
			if (!mediaType) continue;
			const label = friendlyInputLabel(typeof b.field === 'string' ? b.field : undefined, key);
			const url = `${api}/runs/${encodeURIComponent(runId)}/input-media?filename=${encodeURIComponent(filename)}`;
			out.push({ key, label, filename, mediaType, url });
			n++;
		}
		return out;
	}

	let {
		runId,
		projectId = null,
		onClose,
		mode = 'output',
		embedWorkflowuiMetadataOnDownload = false
	}: {
		runId: string;
		projectId?: string | null;
		onClose: () => void;
		mode?: 'output' | 'run';
		/** Match project grid URLs when metadata-on-download is enabled. */
		embedWorkflowuiMetadataOnDownload?: boolean;
	} = $props();

	const apiBase = getApiBase() || '';

	type RunDetail = {
		id: string;
		project_id?: string;
		workflow_version_id?: string;
		app_id?: string | null;
		status: string;
		created_at: number;
		prompt_id?: string | null;
		seed?: number | null;
		images?: { filename: string; subfolder?: string; type?: string; remote_deleted?: boolean }[];
		media?: { filename: string; subfolder?: string; type?: string; remote_deleted?: boolean }[];
		execution_time?: number | null;
		error?: string | null;
		input_snapshot?: Record<string, unknown> | null;
		metadata_snapshot?: Record<string, unknown> | null;
		deleted_outputs?: { output_index: number; seed?: number; master_seed?: number; filename?: string; subfolder?: string; type?: string; deleted_at_ts?: number }[];
		parent_run_id?: string | null;
		parent_media_id?: string | null;
		parent_app_title?: string | null;
		root_run_id?: string | null;
		deleted_at?: number | null;
		child_run_ids?: string[];
		local_storage_status?: string | null;
		local_path?: string | null;
		local_storage_bytes?: number | null;
		remote_storage_bytes?: number | null;
	};

	let run = $state<RunDetail | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let sendToAppOutputIndex = $state<number | null>(null);
	let inputLightboxOpen = $state(false);
	let inputLightboxItems = $state<LightboxItem[]>([]);
	let inputLightboxIndex = $state(0);
	let mediaBrowserOpen = $state(false);
	let mediaBrowserVaultFilename = $state<string | null>(null);
	let inputThumbFailed = $state<Set<string>>(new Set());
	let imageLoadFailed = $state<Set<string>>(new Set());
	let copiedId = $state<'run' | 'snapshot' | 'input' | null>(null);
	/** ComfyUI metadata embedded in the output file (PNG / MP4). */
	let fileEmbedComfyui = $state<'loading' | 'yes' | 'no' | 'na' | 'unavailable' | null>(null);

	async function copyToClipboard(text: string, id: 'run' | 'snapshot' | 'input') {
		try {
			await navigator.clipboard.writeText(text);
			copiedId = id;
			setTimeout(() => { copiedId = null; }, 2000);
		} catch (_) {}
	}

	$effect(() => {
		const id = runId;
		if (!id) {
			run = null;
			loading = false;
			return;
		}
		loading = true;
		error = null;
		fetch(`${apiBase}/runs/${id}`)
			.then((res) => {
				if (!res.ok) throw new Error(res.status === 404 ? 'Run not found' : `Failed to load run`);
				return res.json();
			})
			.then((data: RunDetail) => {
				run = data;
				loading = false;
			})
			.catch((e: Error) => {
				error = e.message;
				run = null;
				loading = false;
			});
	});

	const outputList = $derived(run?.media?.length ? run.media : run?.images ?? []);

	const inputMediaEntries = $derived.by((): InputMediaEntry[] => {
		const r = run;
		if (!r) return [];
		return inputMediaEntriesFromSnapshot(
			r.input_snapshot as Record<string, unknown> | null | undefined,
			r.id,
			apiBase
		);
	});

	$effect(() => {
		void run?.id;
		inputThumbFailed = new Set();
	});

	$effect(() => {
		const id = runId;
		const outs = outputList;
		if (!id || !outs.length) {
			fileEmbedComfyui = null;
			return;
		}
		fileEmbedComfyui = 'loading';
		let cancelled = false;
		fetch(`${apiBase}/runs/${encodeURIComponent(id)}/output-workflowui-embedded?output_index=0`)
			.then((res) => (res.ok ? res.json() : null))
			.then(
				(
					j: {
						hasWorkflowuiEmbeddedMetadata?: boolean | null;
						hasEmbeddedWorkflowuiMetadata?: boolean | null;
						hasComfyuiEmbeddedMetadata?: boolean | null;
						comfyuiEmbeddedCheckApplicable?: boolean;
						unavailable?: boolean;
					} | null
				) => {
					if (cancelled || !j) {
						if (!cancelled) fileEmbedComfyui = 'unavailable';
						return;
					}
					if (j.unavailable) {
						fileEmbedComfyui = 'unavailable';
						return;
					}
					if (!j.comfyuiEmbeddedCheckApplicable) fileEmbedComfyui = 'na';
					else if (j.hasComfyuiEmbeddedMetadata === true) fileEmbedComfyui = 'yes';
					else fileEmbedComfyui = 'no';
				}
			)
			.catch(() => {
				if (!cancelled) fileEmbedComfyui = 'unavailable';
			});
		return () => {
			cancelled = true;
		};
	});

	function primaryMediaKind(o: { type?: string; filename?: string } | undefined): 'video' | 'audio' | 'image' {
		if (!o) return 'image';
		const t = (o.type ?? '').toLowerCase();
		if (t === 'video') return 'video';
		if (t === 'audio') return 'audio';
		const fn = (o.filename ?? '').toLowerCase();
		if (fn.endsWith('.mp4') || fn.endsWith('.webm') || fn.endsWith('.mkv') || fn.endsWith('.mov')) return 'video';
		if (fn.endsWith('.mp3') || fn.endsWith('.wav') || fn.endsWith('.flac')) return 'audio';
		return 'image';
	}

	function imageUrl(img: { filename: string; subfolder?: string; type?: string }, rid?: string) {
		const subfolder = img.subfolder ?? '';
		const type = img.type ?? 'output';
		let url = `${apiBase}/image?filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(subfolder)}&type=${encodeURIComponent(type)}`;
		if (rid) url += `&run_id=${encodeURIComponent(rid)}`;
		if (rid && embedWorkflowuiMetadataOnDownload) url += '&embed_workflowui_metadata=1';
		return url;
	}

	function imageKey(index: number) {
		return `${run?.id ?? ''}_${index}`;
	}

	function markImageLoadFailed(index: number) {
		imageLoadFailed = new Set([...imageLoadFailed, imageKey(index)]);
	}

	async function downloadPrimaryOutput() {
		if (!run || !outputList.length) return;
		const img = outputList[0];
		if (img.remote_deleted) return;
		const url = imageUrl(img, run.id);
		const res = await fetch(url);
		if (!res.ok) return;
		const blob = await res.blob();
		const blobUrl = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = blobUrl;
		a.download = img.filename || 'output';
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(blobUrl);
	}

	function runMetaAsText(r: RunDetail): string {
		const lines: string[] = [];
		lines.push(`Run ID: ${r.id}`);
		lines.push(`Status: ${r.status}`);
		lines.push(`Created: ${new Date(r.created_at).toLocaleString()}`);
		if (r.workflow_version_id != null) lines.push(`Workflow version: ${r.workflow_version_id}`);
		if (r.app_id) lines.push(`App ID: ${r.app_id}`);
		if (r.seed != null) lines.push(`Seed: ${r.seed}`);
		if (r.execution_time != null) lines.push(`Execution time: ${r.execution_time} s`);
		if (r.local_storage_bytes != null) lines.push(`Local storage: ${formatBytes(r.local_storage_bytes)}`);
		if (r.remote_storage_bytes != null) lines.push(`Remote (ComfyUI): ${formatBytes(r.remote_storage_bytes)}`);
		if (r.prompt_id) lines.push(`Prompt ID: ${r.prompt_id}`);
		if (r.error) lines.push(`Error: ${r.error}`);
		if (r.deleted_at) lines.push('Run: Deleted (lineage preserved)');
		return lines.join('\n');
	}

	function openInputLightbox(index: number) {
		const r = run;
		if (!r || !inputMediaEntries.length) return;
		inputLightboxItems = inputMediaEntries.map((ent, i) => ({
			id: `input-${r.id}-${i}-${ent.filename}`,
			url: ent.url,
			filename: ent.filename,
			mediaType: ent.mediaType
		}));
		inputLightboxIndex = Math.min(Math.max(0, index), inputLightboxItems.length - 1);
		inputLightboxOpen = true;
	}

	function closeInputLightbox() {
		inputLightboxOpen = false;
	}

	async function downloadInputFile(filename: string) {
		const r = run;
		if (!r || !filename) return;
		const url = `${apiBase}/runs/${encodeURIComponent(r.id)}/input-media?filename=${encodeURIComponent(filename)}`;
		const res = await fetch(url);
		if (!res.ok) return;
		const blob = await res.blob();
		const blobUrl = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = blobUrl;
		a.download = filename || 'input';
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(blobUrl);
	}

	function openMediaBrowserForInput(filename: string) {
		const name = filename.trim();
		if (!name) return;
		mediaBrowserVaultFilename = name;
		mediaBrowserOpen = true;
	}

	function closeInputMediaBrowser() {
		mediaBrowserOpen = false;
		mediaBrowserVaultFilename = null;
	}

	const dialogTitle = $derived(mode === 'output' ? 'Output metadata' : 'Run metadata');
</script>

<div class="metadata-panel-overlay" role="dialog" aria-modal="true" aria-label={dialogTitle} tabindex="-1" onclick={(e) => { if (e.target === e.currentTarget) onClose(); }} onkeydown={(e) => { if (e.key === 'Escape') onClose(); if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (e.target === e.currentTarget) onClose(); } }}>
	<div class="metadata-panel" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
		<div class="metadata-panel-header">
			<h2>{dialogTitle}</h2>
			<button type="button" class="metadata-panel-close" onclick={onClose} aria-label="Close">×</button>
		</div>
		{#if loading}
			<div class="metadata-panel-loading">Loading…</div>
		{:else if error}
			<div class="metadata-panel-error">{error}</div>
		{:else if run}
			<div class="metadata-panel-two-panel" class:run-only={mode === 'run'}>
				<aside class="metadata-left-panel">
					{#if mode === 'output' && outputList.length}
						<section class="generation-output-block" aria-labelledby="gen-out-heading">
							<h3 id="gen-out-heading" class="generation-output-title">Generation output</h3>
						<div class="image-card">
							{#if outputList[0].remote_deleted && imageLoadFailed.has(imageKey(0))}
								<div class="run-detail-deleted">Deleted</div>
							{:else if primaryMediaKind(outputList[0]) === 'video'}
								<video
									src={imageUrl(outputList[0], run.id)}
									controls
									playsinline
									class="run-detail-media"
									preload="metadata"
									onerror={() => markImageLoadFailed(0)}
								></video>
							{:else if primaryMediaKind(outputList[0]) === 'audio'}
								<audio src={imageUrl(outputList[0], run.id)} controls class="run-detail-media run-detail-audio" onerror={() => markImageLoadFailed(0)}></audio>
							{:else}
								<img src={imageUrl(outputList[0], run.id)} alt="Generation output" class="run-detail-media" onerror={() => markImageLoadFailed(0)} />
							{/if}
							{#if outputList.length > 1}
								<p class="image-card-more">+{outputList.length - 1} more output{outputList.length === 2 ? '' : 's'}</p>
							{/if}
							<div class="image-card-footer">
								<div class="file-embed-rows" role="status" aria-live="polite">
									<div class="file-embed-row">
										<span class="embed-kind">ComfyUI</span>
										{#if fileEmbedComfyui === 'loading'}
											<span class="embed-pill embed-pill-loading">Checking…</span>
										{:else if fileEmbedComfyui === 'yes'}
											<span class="embed-pill embed-pill-yes" title="PNG contains ComfyUI prompt/workflow text chunks (Save Image)">
												<svg class="embed-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
													<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
													<polyline points="22 4 12 14.01 9 11.01" />
												</svg>
												Embedded in file
											</span>
										{:else if fileEmbedComfyui === 'no'}
											<span class="embed-pill embed-pill-no" title="No ComfyUI metadata found (PNG text chunks or MP4 moov)">
												<svg class="embed-pill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
													<circle cx="12" cy="12" r="10" />
													<path d="M4.93 4.93l14.14 14.14" />
												</svg>
												Not in file
											</span>
										{:else if fileEmbedComfyui === 'na'}
											<span class="embed-pill embed-pill-na" title="ComfyUI metadata is detected in PNG (text chunks) and MP4 (moov). This file type is not scanned.">
												N/A
											</span>
										{:else if fileEmbedComfyui === 'unavailable'}
											<span class="embed-pill embed-pill-unknown" title="Could not read the file">
												Unknown
											</span>
										{/if}
									</div>
								</div>
								{#if outputList[0].filename}
									<p class="image-card-filename" title={outputList[0].filename}>
										{outputList[0].filename}
									</p>
								{/if}
								<div class="image-card-actions">
									<button
										type="button"
										class="image-card-action-btn"
										title="Download file"
										aria-label="Download file"
										onclick={downloadPrimaryOutput}
									>
										<svg class="image-card-action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
											<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
											<path d="M7 10l5 5 5-5" />
											<path d="M12 15V3" />
										</svg>
									</button>
									{#if projectId}
										<button
											type="button"
											class="image-card-action-btn"
											title="Send this output to app"
											aria-label="Send this output to app"
											onclick={() => sendToAppOutputIndex = 0}
										>
											<svg class="image-card-action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
												<path d="M5 12h14M12 5l7 7-7 7" />
											</svg>
										</button>
									{/if}
								</div>
							</div>
						</div>
						</section>
					{/if}
					<div class="meta-card">
						<div class="meta-card-heading">
							<h3>Run metadata</h3>
							<button
								type="button"
								class="copy-btn"
								title="Copy to clipboard"
								aria-label="Copy run metadata to clipboard"
								onclick={() => copyToClipboard(runMetaAsText(run!), 'run')}
							>
								<svg class="copy-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/></svg>
								{#if copiedId === 'run'}
									<span class="copy-feedback">Copied!</span>
								{/if}
							</button>
						</div>
						<dl>
							<dt>Run ID</dt>
							<dd><code>{run.id}</code></dd>
							<dt>Status</dt>
							<dd>{run.status}</dd>
							<dt>Created</dt>
							<dd>{new Date(run.created_at).toLocaleString()}</dd>
							{#if run.workflow_version_id != null}
								<dt>Workflow version</dt>
								<dd><code>{run.workflow_version_id}</code></dd>
							{/if}
							{#if run.app_id}
								<dt>App ID</dt>
								<dd><code>{run.app_id}</code></dd>
							{/if}
							{#if run.seed != null}
								<dt>Seed</dt>
								<dd>{run.seed}</dd>
							{/if}
							{#if run.execution_time != null}
								<dt>Execution time</dt>
								<dd>{run.execution_time} s</dd>
							{/if}
							{#if run.local_storage_bytes != null}
								<dt>Local storage</dt>
								<dd>{formatBytes(run.local_storage_bytes)}</dd>
							{/if}
							{#if run.remote_storage_bytes != null}
								<dt>Remote (ComfyUI)</dt>
								<dd>{formatBytes(run.remote_storage_bytes)}</dd>
							{/if}
							{#if outputList.length > 0}
								<dt>Outputs</dt>
								<dd>{outputList.length} image{outputList.length === 1 ? '' : 's'}</dd>
							{/if}
							{#if outputList.length > 0}
								<dt>ComfyUI metadata</dt>
								<dd class="embed-dd">
									{#if fileEmbedComfyui === 'loading'}
										<span class="muted">Checking…</span>
									{:else if fileEmbedComfyui === 'yes'}
										<span class="embed-inline embed-inline-yes">Embedded</span>
									{:else if fileEmbedComfyui === 'no'}
										<span class="embed-inline embed-inline-no">Not in file</span>
									{:else if fileEmbedComfyui === 'na'}
										<span class="muted">N/A</span>
									{:else if fileEmbedComfyui === 'unavailable'}
										<span class="muted">Unknown</span>
									{/if}
								</dd>
							{/if}
							{#if mode === 'output' && outputList[0]?.filename}
								<dt>Filename</dt>
								<dd>{outputList[0].filename}</dd>
							{/if}
							{#if run.prompt_id}
								<dt>Prompt ID</dt>
								<dd><code>{run.prompt_id}</code></dd>
							{/if}
							{#if run.error}
								<dt>Error</dt>
								<dd class="error-text">{run.error}</dd>
							{/if}
							{#if run.deleted_at}
								<dt>Run</dt>
								<dd class="muted">Deleted (lineage preserved)</dd>
							{/if}
						</dl>
						{#if run.parent_run_id || (run.child_run_ids && run.child_run_ids.length > 0)}
							<h4>Lineage</h4>
							<dl>
								{#if run.parent_run_id}
									<dt>Source</dt>
									<dd>
										{#if run.parent_app_title}
											<span class="muted">{run.parent_app_title}</span>
											<span class="muted"> · </span>
										{/if}
										{#if projectId}
											<a href="/projects/{projectId}/runs/{run.parent_run_id}">Run {run.parent_run_id.slice(0, 8)}…</a>
										{:else}
											<code>{run.parent_run_id}</code>
										{/if}
										{#if run.parent_media_id}
											<span class="muted"> · Media {run.parent_media_id}</span>
										{/if}
									</dd>
								{/if}
								{#if run.child_run_ids && run.child_run_ids.length > 0}
									<dt>Derived runs</dt>
									<dd>
										<ul class="lineage-list">
											{#each run.child_run_ids as cid}
												<li>
													{#if projectId}
														<a href="/projects/{projectId}/runs/{cid}">Run {cid.slice(0, 8)}…</a>
													{:else}
														<code>{cid}</code>
													{/if}
												</li>
											{/each}
										</ul>
									</dd>
								{/if}
							</dl>
						{/if}
						{#if inputMediaEntries.length}
							<h4>Input media</h4>
							<p class="hint input-media-hint">
								Click the preview to open the viewer. Hover actions for details.
							</p>
							<ul class="input-media-list" aria-label="Input media">
								{#each inputMediaEntries as ent, i (`${ent.key}:${ent.filename}:${i}`)}
									<li class="input-media-card">
										<button
											type="button"
											class="input-media-thumb-btn"
											title="Open in viewer — {ent.filename}"
											onclick={() => openInputLightbox(i)}
											aria-label="Open {ent.label} in viewer"
										>
											{#if ent.mediaType === 'video'}
												<span class="input-media-kind-badge" aria-hidden="true">Video</span>
											{:else if ent.mediaType === 'audio'}
												<span class="input-media-kind-badge" aria-hidden="true">Audio</span>
											{:else if inputThumbFailed.has(ent.url)}
												<span class="input-media-missing">Not on disk</span>
											{:else}
												<img
													src={ent.url}
													alt=""
													class="input-media-thumb"
													loading="lazy"
													onerror={() => {
														inputThumbFailed = new Set([...inputThumbFailed, ent.url]);
													}}
												/>
											{/if}
										</button>
										<div class="input-media-body">
											<div class="input-media-caption">
												<span class="input-media-label" title="{ent.label} — {ent.filename}">{ent.label}</span>
												<span class="input-media-filename" title={ent.filename}>{ent.filename}</span>
											</div>
											<div class="input-media-actions">
												<button
													type="button"
													class="input-media-btn input-media-btn-download input-media-btn-icon-only"
													title="Save this input file to your device."
													aria-label="Download input file {ent.filename}"
													onclick={() => void downloadInputFile(ent.filename)}
												>
													<svg class="input-media-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
														<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
														<polyline points="7 10 12 15 17 10" />
														<line x1="12" y1="15" x2="12" y2="3" />
													</svg>
												</button>
												<button
													type="button"
													class="input-media-btn input-media-btn-generations"
													title="Browse outputs in the media browser from runs that used this file as an input."
													aria-label="Browse generations that used this input file"
													onclick={() => openMediaBrowserForInput(ent.filename)}
												>
													<svg class="input-media-btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
														<rect x="3" y="3" width="7" height="7" rx="1" />
														<rect x="14" y="3" width="7" height="7" rx="1" />
														<rect x="3" y="14" width="7" height="7" rx="1" />
														<rect x="14" y="14" width="7" height="7" rx="1" />
													</svg>
													Find uses
												</button>
											</div>
										</div>
									</li>
								{/each}
							</ul>
						{/if}
						{#if run.metadata_snapshot && Object.keys(run.metadata_snapshot).length > 0}
							<div class="meta-subsection">
								<h4>Metadata snapshot</h4>
								<button type="button" class="copy-btn" title="Copy to clipboard" aria-label="Copy metadata snapshot to clipboard" onclick={() => copyToClipboard(JSON.stringify(run!.metadata_snapshot, null, 2), 'snapshot')}>
									<svg class="copy-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/></svg>
									{#if copiedId === 'snapshot'}
										<span class="copy-feedback">Copied!</span>
									{/if}
								</button>
							</div>
							<pre class="json-block">{JSON.stringify(run.metadata_snapshot, null, 2)}</pre>
						{/if}
						{#if run.deleted_outputs?.length}
							<h4>Deleted outputs</h4>
							<p class="hint">Outputs removed from ComfyUI (no local copy). Seeds kept for recovery.</p>
							<dl class="deleted-outputs-list">
								{#each run.deleted_outputs as entry}
									<div class="deleted-output-entry">
										<dt>Output #{entry.output_index + 1}</dt>
										<dd>
											{#if entry.master_seed != null}
												<span title="Master seed (workflow)">Master seed: <code>{entry.master_seed}</code></span>
												{#if entry.seed != null && entry.seed !== entry.master_seed}
													<span title="Prompt seed"> · Seed: <code>{entry.seed}</code></span>
												{/if}
											{:else if entry.seed != null}
												<span>Seed: <code>{entry.seed}</code></span>
											{/if}
											{#if entry.filename}
												<span class="deleted-filename"> · {entry.filename}</span>
											{/if}
										</dd>
									</div>
								{/each}
							</dl>
						{/if}
					</div>
				</aside>
				{#if mode === 'output'}
				<div class="metadata-right-panel">
					<div class="input-snapshot-section">
						<h3>Input snapshot</h3>
						<p class="hint">Exactly what was used for this run (stored at execution).</p>
						{#if run.input_snapshot}
							<div class="copyable-block">
								<pre class="json-block">{JSON.stringify(run.input_snapshot, null, 2)}</pre>
								<button type="button" class="copy-btn" title="Copy to clipboard" aria-label="Copy input snapshot to clipboard" onclick={() => copyToClipboard(JSON.stringify(run!.input_snapshot, null, 2), 'input')}>
									<svg class="copy-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/></svg>
									{#if copiedId === 'input'}
										<span class="copy-feedback">Copied!</span>
									{/if}
								</button>
							</div>
						{:else}
							<p class="muted">No input snapshot stored.</p>
						{/if}
					</div>
				</div>
				{/if}
			</div>
		{/if}
	</div>
</div>

{#if sendToAppOutputIndex != null && run && projectId}
	<SendToAppDialog
		open={true}
		sendFromRun={run.id}
		sendFromOutput={sendToAppOutputIndex}
		{projectId}
		onClose={() => { sendToAppOutputIndex = null; }}
	/>
{/if}

<LightboxViewer
	open={inputLightboxOpen}
	items={inputLightboxItems}
	index={inputLightboxIndex}
	onIndexChange={(i) => {
		inputLightboxIndex = i;
	}}
	onClose={closeInputLightbox}
	onDownload={(item) => {
		const fn = item.filename?.trim();
		if (fn) void downloadInputFile(fn);
	}}
	showCloseLabel={false}
	ariaTitle="Input media viewer"
/>

<MediaBrowserDialog
	open={mediaBrowserOpen}
	initialProjectId={projectId}
	filterByVaultInputFilename={mediaBrowserVaultFilename}
	onClose={closeInputMediaBrowser}
/>

<style>
	.metadata-panel-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}
	.metadata-panel {
		background: var(--bg, #eef2f7);
		border: 1px solid var(--border, rgba(30, 41, 59, 0.08));
		border-radius: 12px;
		max-width: 95vw;
		max-height: 90vh;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		color: var(--text, #0f172a);
	}
	.metadata-panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem 1rem;
		border-bottom: 1px solid var(--border, rgba(30, 41, 59, 0.08));
	}
	.metadata-panel-header h2 {
		margin: 0;
		font-size: 1.1rem;
		color: var(--text, #0f172a);
	}
	.metadata-panel-close {
		background: none;
		border: none;
		color: var(--text-muted, var(--muted, #64748b));
		font-size: 1.5rem;
		cursor: pointer;
		padding: 0 0.25rem;
		line-height: 1;
	}
	.metadata-panel-close:hover {
		color: var(--text, #0f172a);
	}
	.metadata-panel-loading,
	.metadata-panel-error {
		padding: 2rem;
		text-align: center;
		color: var(--text-muted, var(--muted, #64748b));
	}
	.metadata-panel-error {
		color: var(--error, #dc2626);
	}
	.metadata-panel-two-panel {
		display: grid;
		grid-template-columns: 384px 1fr;
		gap: 1.5rem;
		min-height: 0;
		flex: 1;
		overflow: auto;
		padding: 1rem;
	}
	.metadata-panel-two-panel.run-only {
		grid-template-columns: 1fr;
	}
	.metadata-left-panel {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-width: 0;
	}
	.metadata-right-panel {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		min-width: 0;
	}
	.image-card {
		background: var(--card-bg, var(--card, #ffffff));
		border: 1px solid var(--border, rgba(30, 41, 59, 0.08));
		border-radius: 10px;
		overflow: hidden;
		padding: 0;
		flex-shrink: 0;
	}
	.run-detail-media {
		width: 100%;
		display: block;
		max-height: 320px;
		object-fit: contain;
		background: var(--input-bg, var(--surface, #f6f9fc));
	}
	.run-detail-audio {
		width: 100%;
		min-height: 40px;
	}
	.generation-output-block {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-width: 0;
	}
	.generation-output-title {
		margin: 0;
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--text, #0f172a);
	}
	.run-detail-deleted {
		min-height: 120px;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--text-muted, var(--muted, #64748b));
	}
	.image-card-more {
		margin: 0;
		padding: 0.35rem 0.75rem;
		font-size: 0.8rem;
		color: var(--text-muted, var(--muted, #64748b));
		border-top: 1px solid var(--border, rgba(30, 41, 59, 0.08));
	}
	.image-card-footer {
		padding: 0.5rem 0.75rem 0.6rem;
		border-top: 1px solid var(--border, rgba(30, 41, 59, 0.06));
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.file-embed-rows {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
	}
	.file-embed-row {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.35rem 0.5rem;
		min-height: 1.45rem;
	}
	.embed-kind {
		font-size: 0.72rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--text-muted, var(--muted, #64748b));
		min-width: 4.5rem;
		flex-shrink: 0;
	}
	.embed-pill {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.75rem;
		font-weight: 600;
		padding: 0.2rem 0.5rem;
		border-radius: 999px;
		line-height: 1.2;
	}
	.embed-pill-icon {
		width: 0.95rem;
		height: 0.95rem;
		flex-shrink: 0;
	}
	.embed-pill-yes {
		background: rgba(22, 163, 74, 0.12);
		color: var(--success, #15803d);
		border: 1px solid rgba(22, 163, 74, 0.35);
	}
	.embed-pill-no {
		background: rgba(100, 116, 139, 0.12);
		color: var(--text-muted, var(--muted, #64748b));
		border: 1px solid rgba(100, 116, 139, 0.25);
	}
	.embed-pill-loading {
		color: var(--text-muted, var(--muted, #64748b));
		font-weight: 500;
	}
	.embed-pill-unknown {
		background: rgba(234, 179, 8, 0.12);
		color: #a16207;
		border: 1px solid rgba(234, 179, 8, 0.35);
	}
	.embed-pill-na {
		background: rgba(148, 163, 184, 0.15);
		color: var(--text-muted, var(--muted, #64748b));
		border: 1px solid rgba(148, 163, 184, 0.35);
		font-weight: 600;
		font-size: 0.72rem;
		padding: 0.2rem 0.45rem;
	}
	.embed-dd {
		display: flex;
		align-items: center;
	}
	.embed-inline-yes {
		color: var(--success, #15803d);
		font-weight: 600;
	}
	.embed-inline-no {
		color: var(--text-muted, var(--muted, #64748b));
		font-weight: 600;
	}
	.image-card-filename {
		margin: 0;
		font-size: 0.8rem;
		color: var(--text-muted, var(--muted, #64748b));
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.image-card-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
		align-items: center;
	}
	.image-card-action-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 32px;
		padding: 0;
		margin: 0;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
		box-shadow: none;
		cursor: pointer;
		font: inherit;
		transition:
			background 0.12s ease,
			border-color 0.12s ease;
	}
	.image-card-action-btn:hover {
		transform: none;
		background: color-mix(in srgb, var(--text) 6%, var(--surface));
		border-color: color-mix(in srgb, var(--muted) 50%, var(--border));
	}
	.image-card-action-btn:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.image-card-action-icon {
		width: 16px;
		height: 16px;
		flex-shrink: 0;
	}
	.meta-card {
		background: var(--card-bg, var(--card, #ffffff));
		border: 1px solid var(--border, rgba(30, 41, 59, 0.08));
		border-radius: 10px;
		padding: 1rem;
		color: var(--text, #0f172a);
	}
	.meta-card h3, .input-snapshot-section h3 {
		margin: 0 0 0.5rem 0;
		font-size: 1rem;
		color: var(--text, #0f172a);
	}
	.meta-card-heading, .meta-subsection {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.meta-card-heading h3, .meta-subsection h4 {
		margin: 0;
	}
	.meta-subsection {
		margin-top: 1rem;
	}
	.meta-subsection h4 {
		margin-right: 0;
	}
	.copy-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		background: none;
		border: none;
		color: var(--text-muted, var(--muted, #64748b));
		cursor: pointer;
		padding: 0.25rem;
		border-radius: 4px;
		font-size: 0.85rem;
	}
	.copy-btn:hover {
		color: var(--text, #0f172a);
		background: var(--input-bg, var(--surface, #f6f9fc));
	}
	.copy-btn .copy-icon {
		width: 1rem;
		height: 1rem;
	}
	.copy-feedback {
		font-size: 0.75rem;
		color: var(--success, #16a34a);
	}
	.copyable-block {
		position: relative;
	}
	.copyable-block .copy-btn {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
	}
	.meta-card h4 {
		margin: 1rem 0 0.5rem 0;
		font-size: 0.95rem;
		color: var(--text-muted, var(--muted, #64748b));
	}
	.meta-card dl {
		margin: 0;
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.25rem 1rem;
		font-size: 0.9rem;
	}
	.meta-card dt {
		color: var(--text-muted, var(--muted, #64748b));
	}
	.meta-card dd {
		margin: 0;
		word-break: break-all;
		color: var(--text, #0f172a);
	}
	.meta-card code {
		font-size: 0.8rem;
		color: var(--text, #0f172a);
	}
	.error-text {
		color: var(--error, #dc2626);
	}
	.lineage-list {
		list-style: none;
		margin: 0.25rem 0 0;
		padding: 0;
	}
	.lineage-list li {
		margin: 0.25rem 0;
	}
	.send-to-app-link, .send-to-app-btn {
		display: inline-block;
		margin-top: 0.35rem;
		font-size: 0.8rem;
		color: var(--link, var(--accent, #6af));
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		text-decoration: none;
		font: inherit;
	}
	.send-to-app-btn:hover {
		text-decoration: underline;
	}
	.json-block {
		margin: 0;
		padding: 0.75rem;
		background: var(--input-bg, var(--surface, #f6f9fc));
		color: var(--text, #0f172a);
		border-radius: 6px;
		font-size: 0.8rem;
		overflow-x: auto;
		white-space: pre-wrap;
		word-break: break-all;
	}
	.copyable-block .json-block {
		padding-right: 2.5rem;
	}
	.hint {
		margin: 0 0 0.5rem 0;
		font-size: 0.85rem;
		color: var(--text-muted, var(--muted, #64748b));
	}
	.deleted-outputs-list {
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.deleted-output-entry {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.25rem 0.75rem;
		margin-bottom: 0.5rem;
		font-size: 0.9rem;
	}
	.deleted-output-entry dt {
		color: var(--text-muted, var(--muted, #64748b));
	}
	.deleted-output-entry dd {
		margin: 0;
		word-break: break-all;
		color: var(--text, #0f172a);
	}
	.deleted-filename {
		color: var(--text-muted, var(--muted, #64748b));
		font-size: 0.85rem;
	}
	.muted {
		color: var(--text-muted, var(--muted, #64748b));
	}
	.input-snapshot-section {
		color: var(--text, #0f172a);
	}
	.input-snapshot-section h3 {
		color: var(--text, #0f172a);
	}
	.input-media-hint {
		font-size: 0.78rem;
		line-height: 1.35;
		color: var(--muted);
	}
	.input-media-list {
		list-style: none;
		margin: 0.25rem 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.input-media-card {
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 0.6rem;
		padding: 0.45rem 0.55rem;
		border: 1px solid var(--border);
		border-radius: var(--radius-lg, 12px);
		background: var(--card);
		color: var(--text);
		min-width: 0;
		box-shadow: none;
	}
	.input-media-thumb-btn {
		display: block;
		flex: 0 0 auto;
		width: 56px;
		height: 56px;
		padding: 0;
		border: 1px solid var(--border);
		border-radius: 10px;
		overflow: hidden;
		cursor: pointer;
		box-shadow: none;
		background-color: var(--surface);
		background-image: repeating-conic-gradient(
			from 0deg,
			color-mix(in srgb, var(--muted) 18%, transparent) 0% 25%,
			transparent 0% 50%
		);
		background-size: 10px 10px;
		position: relative;
		transition:
			border-color 0.12s ease,
			box-shadow 0.12s ease;
	}
	.input-media-thumb-btn:hover {
		transform: none;
		border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
		box-shadow: 0 0 0 1px var(--accent-soft);
	}
	.input-media-thumb-btn:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.input-media-thumb {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.input-media-body {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: row;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.4rem 0.65rem;
	}
	.input-media-kind-badge,
	.input-media-missing {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 100%;
		height: 100%;
		font-size: 0.65rem;
		font-weight: 600;
		color: var(--muted);
		text-align: center;
		padding: 0.25rem;
		box-sizing: border-box;
	}
	.input-media-missing {
		color: var(--warning);
		background: color-mix(in srgb, var(--warning) 14%, transparent);
	}
	.input-media-caption {
		display: flex;
		flex-direction: column;
		gap: 0.06rem;
		min-width: 0;
		flex: 1 1 120px;
	}
	.input-media-label {
		font-size: 0.7rem;
		font-weight: 600;
		letter-spacing: 0.01em;
		color: var(--text);
		line-height: 1.25;
		overflow-wrap: anywhere;
	}
	.input-media-filename {
		font-size: 0.65rem;
		color: var(--muted);
		line-height: 1.3;
		overflow-wrap: anywhere;
	}
	.input-media-actions {
		display: inline-flex;
		flex-direction: row;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		gap: 0.3rem;
		flex: 0 1 auto;
	}
	.input-media-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.28rem;
		width: auto;
		max-width: 100%;
		margin: 0;
		font-size: 0.68rem;
		font-weight: 600;
		line-height: 1.2;
		white-space: nowrap;
		padding: 0.32rem 0.55rem;
		border-radius: 999px;
		cursor: pointer;
		font: inherit;
		border: 1px solid transparent;
		box-shadow: none;
		transition:
			background 0.12s ease,
			border-color 0.12s ease,
			color 0.12s ease;
	}
	.input-media-btn:hover {
		transform: none;
	}
	.input-media-btn-icon {
		width: 0.88rem;
		height: 0.88rem;
		flex-shrink: 0;
		opacity: 0.95;
	}
	.input-media-btn-icon-only {
		padding: 0;
		width: 2rem;
		height: 2rem;
		min-width: 2rem;
		justify-content: center;
	}
	.input-media-btn-icon-only .input-media-btn-icon {
		width: 0.92rem;
		height: 0.92rem;
	}
	.input-media-btn-download {
		color: var(--text);
		background: var(--surface);
		border-color: var(--border);
	}
	.input-media-btn-download:hover {
		background: color-mix(in srgb, var(--text) 6%, var(--surface));
		border-color: color-mix(in srgb, var(--muted) 50%, var(--border));
	}
	.input-media-btn-generations {
		color: var(--accent);
		background: var(--accent-soft);
		border-color: color-mix(in srgb, var(--accent) 32%, var(--border));
	}
	.input-media-btn-generations:hover {
		background: color-mix(in srgb, var(--accent) 22%, var(--surface));
		border-color: color-mix(in srgb, var(--accent) 48%, var(--border));
	}
	.input-media-btn-generations:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.input-media-btn-download:focus-visible {
		outline: 2px solid var(--muted);
		outline-offset: 2px;
	}
	@media (max-width: 700px) {
		.metadata-panel-two-panel {
			grid-template-columns: 1fr;
		}
	}
</style>
