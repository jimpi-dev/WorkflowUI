<script lang="ts">
	import { getApiBase } from '$lib/config';
	import { goto } from '$app/navigation';

	let { data }: { data: { embedWorkflowuiMetadataOnDownload?: boolean; embedWorkflowuiMetadataOnSave?: boolean } } = $props();

	type ImportState = 'idle' | 'parsing' | 'analyzing' | 'preview-ready' | 'error';

	let name = $state('');
	let jsonInput = $state('');
	let selectedFileName = $state<string | null>(null);
	let importState = $state<ImportState>('idle');
	let errorMessage = $state('');
	let preview = $state<{
		graph_hash: string;
		detected_inputs: { key: string; label?: string; type?: string; nodeId: string; field: string; classType?: string; metaTitle?: string | null }[];
		detected_outputs: { nodeId: string; type: string; label?: string; metaTitle?: string | null }[];
		is_new_workflow: boolean;
		is_new_version: boolean;
		existing_workflow_id: string | null;
		existing_version: number | null;
	} | null>(null);
	let creating = $state(false);

	let forceNewVersion = $state(false);


	let imageImporting = $state(false);
	let imageImportMessage = $state('');

	const apiBase = getApiBase() || '';

	function setState(s: ImportState, err = '') {
		importState = s;
		errorMessage = err;
	}

	function parseGraph(): { graph: object } | null {
		const raw = jsonInput.trim();
		if (!raw) return null;
		try {
			const graph = JSON.parse(raw);
			if (graph && typeof graph === 'object' && !Array.isArray(graph)) return { graph };
			return null;
		} catch {
			return null;
		}
	}

	async function handleAnalyze() {
		const trimmedName = name.trim();
		if (!trimmedName) {
			setState('error', 'Name is required');
			return;
		}
		setState('parsing');
		const parsed = parseGraph();
		if (!parsed) {
			setState('error', 'Invalid JSON or empty graph');
			return;
		}
		setState('analyzing');
		try {
			const res = await fetch(`${apiBase}/import/preview`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: trimmedName, graph: parsed.graph })
			});
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				setState('error', (d.detail as string) || res.statusText);
				return;
			}
			preview = await res.json();
			setState('preview-ready');
		} catch (e) {
			setState('error', e instanceof Error ? e.message : String(e));
		}
	}

	async function handleCreateWorkflow() {
		if (importState !== 'preview-ready' || !preview) return;
		const trimmedName = name.trim();
		const parsed = parseGraph();
		if (!parsed || !trimmedName) return;
		creating = true;
		try {
			const res = await fetch(`${apiBase}/import`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: trimmedName,
					graph: parsed.graph,
					force_new_version: forceNewVersion
				})
			});
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				const detail = typeof d.detail === 'object' && d.detail?.message != null
					? d.detail.message
					: (d.detail as string) ?? res.statusText;
				setState('error', res.status === 409
					? `${detail} Check "Create new version anyway" to create v2.`
					: detail);
				creating = false;
				return;
			}
			const data = await res.json();
			await goto(`/workflows/${data.workflow_id}`);
		} catch (e) {
			setState('error', e instanceof Error ? e.message : String(e));
			creating = false;
		}
	}

	function handleFileChange(e: Event) {
		const input = e.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;
		selectedFileName = file.name;

		const nameWithoutExt = file.name.replace(/\.json$/i, '');
		if (nameWithoutExt) name = nameWithoutExt;
		const reader = new FileReader();
		reader.onload = () => {
			jsonInput = String(reader.result ?? '');
			setState('idle');
		};
		reader.readAsText(file);
		input.value = '';
	}


	function isWorkflowuiFile(file: File): boolean {
		if (file.type.startsWith('image/')) return true;
		if (file.type === 'audio/mpeg' || file.type === 'audio/mp3') return true;
		const n = file.name.toLowerCase();
		return n.endsWith('.mp3');
	}

	let imageFileInputRef: HTMLInputElement;
	let jsonFileInputRef: HTMLInputElement;

	function chooseImageFile() {
		if (imageFileInputRef && !imageImporting) imageFileInputRef.click();
	}

	function chooseJsonFile() {
		if (jsonFileInputRef) jsonFileInputRef.click();
	}

	async function handleImageFile(files: FileList | null) {
		const file = files?.[0];
		if (!file || !isWorkflowuiFile(file)) return;
		imageImportMessage = '';
		imageImporting = true;
		try {
			const form = new FormData();
			form.append('file', file);
			const res = await fetch(`${apiBase}/import/from-file`, { method: 'POST', body: form });
			const data = await res.json().catch(() => ({}));
			if (data.action === 'open' && data.app_slug) {
				const slug = data.app_slug;
				if (data.input_snapshot != null && typeof data.input_snapshot === 'object') {
					try {
						sessionStorage.setItem('workflowui_import_prefill', JSON.stringify({ slug, input_snapshot: data.input_snapshot }));
					} catch {
					}
				}
				await goto(`/app/${slug}`);
				return;
			}
			if (data.action === 'restored' && data.app_slug) {
				const slug = data.resolved_slug ?? data.app_slug;
				if (data.input_snapshot != null && typeof data.input_snapshot === 'object') {
					try {
						sessionStorage.setItem('workflowui_import_prefill', JSON.stringify({ slug, input_snapshot: data.input_snapshot }));
					} catch {
					}
				}
				await goto(`/app/${slug}`);
				return;
			}
			if (data.action === 'ignored') {
				imageImportMessage = data.reason === 'invalid_snapshot'
					? 'Invalid or corrupted WorkflowUI metadata in this file.'
					: 'No WorkflowUI metadata in this file. Save images or audio from WorkflowUI with metadata on download/save to restore later.';
			} else {
				imageImportMessage = 'Import failed. Try again.';
			}
		} catch (e) {
			imageImportMessage = e instanceof Error ? e.message : 'Import failed.';
		} finally {
			imageImporting = false;
		}
	}
</script>

<div class="two-col-page page">
	<aside class="panel-left panel-scroll card">
		<h1>Import Workflow</h1>
		<p class="muted">Engine-level graph ingestion. No app creation here.</p>

		<section
			class="section import-from-image-section"
			role="button"
			tabindex="0"
			ondragover={(e) => { e.preventDefault(); (e.currentTarget as HTMLElement).classList.add('drag-over'); }}
			ondragleave={(e) => { (e.currentTarget as HTMLElement).classList.remove('drag-over'); }}
			ondrop={(e) => {
				e.preventDefault();
				(e.currentTarget as HTMLElement).classList.remove('drag-over');
				handleImageFile(e.dataTransfer?.files ?? null);
			}}
		>
			<label>Import from workflow file</label>
			<p class="hint">Drop or select a PNG or MP3 saved from WorkflowUI (with metadata) to open or restore that workflow and app.</p>
			<p class="metadata-status" role="status">
				Metadata appended on download: <strong>{data?.embedWorkflowuiMetadataOnDownload ? 'Yes' : 'No'}</strong>
				· on save to local storage: <strong>{data?.embedWorkflowuiMetadataOnSave ? 'Yes' : 'No'}</strong>
				{#if data?.embedWorkflowuiMetadataOnDownload || data?.embedWorkflowuiMetadataOnSave}
					— drop those files here to restore.
				{:else}
					— enable in backend .env (<code>WORKFLOWUI_EMBED_METADATA_ON_DOWNLOAD</code> / <code>WORKFLOWUI_EMBED_METADATA_ON_SAVE</code>) to attach metadata.
				{/if}
			</p>
			<div class="import-json-options">
				<input
					type="file"
					accept="image/*,.png,audio/mpeg,.mp3"
					class="file-input file-input-hidden"
					bind:this={imageFileInputRef}
					disabled={imageImporting}
					onchange={(e) => handleImageFile((e.target as HTMLInputElement).files)}
					aria-label="Choose workflow file (PNG or MP3)"
				/>
				<button type="button" class="choose-file-btn" disabled={imageImporting} onclick={chooseImageFile} aria-label="Choose workflow file">
					Choose file
				</button>
				{#if imageImporting}
					<span class="selected-file">Importing…</span>
				{:else if imageImportMessage}
					<span class="error-text">{imageImportMessage}</span>
				{:else}
					<span class="no-file">No file chosen</span>
				{/if}
			</div>
		</section>

		<section class="section">
			<label for="import-name">Workflow name</label>
			<input id="import-name" type="text" bind:value={name} placeholder="My Workflow" />
		</section>

		<section class="section">
			<label>Graph JSON</label>
			<div class="import-json-options">
				<input
					type="file"
					accept=".json,application/json"
					onchange={handleFileChange}
					class="file-input file-input-hidden"
					bind:this={jsonFileInputRef}
					aria-label="Choose JSON file"
				/>
				<button type="button" class="choose-file-btn" onclick={chooseJsonFile} aria-label="Choose JSON file">
					Choose file
				</button>
				{#if selectedFileName}
					<span class="selected-file" title={selectedFileName}>{selectedFileName}</span>
				{:else}
					<span class="no-file">No file chosen</span>
					<span class="muted">· or paste below</span>
				{/if}
			</div>
			<textarea
				class="import-textarea"
				placeholder={'{ "3": { "class_type": "KSampler" }, ... }'}
				bind:value={jsonInput}
				rows="12"
			></textarea>
		</section>

		<section class="section">
			<button type="button" onclick={handleAnalyze} disabled={importState === 'analyzing'}>
				{importState === 'analyzing' ? 'Analyzing…' : 'Analyze'}
			</button>
		</section>

		<section class="section status-section">
			<span class="status-label">Status:</span>
			<span class="status-value" data-state={importState}>
				{#if importState === 'idle'}idle
				{:else if importState === 'parsing'}parsing
				{:else if importState === 'analyzing'}analyzing
				{:else if importState === 'preview-ready'}preview-ready
				{:else if importState === 'error'}error
				{:else}{importState}{/if}
			</span>
			{#if errorMessage}
				<p class="error-text">{errorMessage}</p>
			{/if}
		</section>

		{#if importState === 'preview-ready' && preview}
			<section class="section sticky-save">
				{#if !preview.is_new_workflow && !preview.is_new_version}
					<label class="force-version-wrap">
						<input type="checkbox" bind:checked={forceNewVersion} />
						<span>Create new version anyway</span>
					</label>
					<p class="hint">Same graph as latest; import would normally be skipped. Check to create v2 (e.g. to refresh detected inputs).</p>
				{/if}
				<button type="button" onclick={handleCreateWorkflow} disabled={creating} class="primary">
					{creating ? 'Creating…' : (preview.is_new_workflow ? 'Create Workflow' : 'Import')}
				</button>
				<p class="hint">Redirects to workflow detail. No app creation.</p>
			</section>
		{/if}
	</aside>

	<div class="panel-right panel-scroll card">
		{#if importState !== 'preview-ready' || !preview}
			<p class="muted">Analyze a workflow to see metadata and detected inputs/outputs.</p>
		{:else}
			<h2>Graph metadata</h2>
			<dl class="meta-dl">
				<dt>Version preview</dt>
				<dd>{preview.is_new_workflow ? 'v1 (new)' : preview.is_new_version ? 'new version' : 'unchanged (duplicate)'}</dd>
				<dt>Hash</dt>
				<dd class="hash">{preview.graph_hash.slice(0, 16)}…</dd>
				<dt>Detected inputs</dt>
				<dd>{preview.detected_inputs?.length ?? 0}</dd>
				<dt>Detected outputs</dt>
				<dd>{preview.detected_outputs?.length ?? 0}</dd>
			</dl>

			<h3>Detected inputs</h3>
			<div class="table-wrap">
				<table class="compact-table">
					<thead>
						<tr>
							<th>Key</th>
							<th>Label</th>
							<th>Type</th>
							<th>Node</th>
							<th>ComfyUI title</th>
							<th>Class</th>
							<th>Field</th>
						</tr>
					</thead>
					<tbody>
						{#each preview.detected_inputs ?? [] as row}
							<tr>
								<td><code>{row.key}</code></td>
								<td>{row.label ?? '—'}</td>
								<td>{row.type ?? '—'}</td>
								<td><code>{row.nodeId}</code></td>
								<td>{row.metaTitle ?? '—'}</td>
								<td>{row.classType ?? '—'}</td>
								<td><code>{row.field}</code></td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<h3>Detected outputs</h3>
			<div class="table-wrap">
				<table class="compact-table">
					<thead>
						<tr>
							<th>Node</th>
							<th>Type</th>
							<th>Label</th>
							<th>ComfyUI title</th>
						</tr>
					</thead>
					<tbody>
						{#each preview.detected_outputs ?? [] as row}
							<tr>
								<td><code>{row.nodeId}</code></td>
								<td>{row.type}</td>
								<td>{row.label ?? '—'}</td>
								<td>{row.metaTitle ?? '—'}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
</div>

<style>
	.section {
		margin-bottom: 1.25rem;
	}
	.import-from-image-section {
		border-radius: 8px;
		padding: 0.5rem 0;
	}
	.import-from-image-section.drag-over {
		background: var(--accent-soft);
		outline: 2px dashed var(--accent);
		outline-offset: 2px;
	}
	.metadata-status {
		font-size: 0.85rem;
		color: var(--text);
		margin: 0.5rem 0;
		line-height: 1.4;
	}
	.metadata-status code {
		font-size: 0.75rem;
		background: var(--surface);
		padding: 0.1rem 0.3rem;
		border-radius: 4px;
	}
	.muted {
		color: var(--muted);
		font-size: 0.9rem;
		margin-bottom: 1rem;
	}
	.import-json-options {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		flex-wrap: wrap;
	}
	.file-input-hidden {
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
	.no-file {
		font-size: 0.9rem;
		color: var(--muted, #888);
	}
	.file-input {
		width: auto;
	}
	.selected-file {
		font-size: 0.9rem;
		color: var(--text);
		max-width: 12rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.import-textarea {
		width: 100%;
		min-height: 180px;
		font-family: ui-monospace, monospace;
		font-size: 0.85rem;
	}
	.status-section {
		padding: 0.75rem;
		background: var(--surface);
		border-radius: 8px;
		border: 1px solid var(--border);
	}
	.status-label {
		font-weight: 600;
		margin-right: 0.5rem;
	}
	.status-value[data-state='error'] {
		color: var(--warning);
	}
	.status-value[data-state='preview-ready'] {
		color: var(--success);
	}
	.error-text {
		color: var(--warning);
		margin-top: 0.5rem;
		font-size: 0.9rem;
	}
	.force-version-wrap {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
	}
	.force-version-wrap input {
		width: auto;
	}
	.sticky-save {
		margin-top: auto;
		padding-top: 1rem;
	}
	.sticky-save .hint {
		font-size: 0.8rem;
		color: var(--muted);
		margin-top: 0.5rem;
	}
	button.primary {
		background: var(--accent);
		color: white;
	}
	.meta-dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.25rem 1.5rem;
		margin-bottom: 1.5rem;
		font-size: 0.9rem;
	}
	.meta-dl dt {
		color: var(--muted);
	}
	.meta-dl dd {
		margin: 0;
	}
	.meta-dl .hash {
		font-family: ui-monospace, monospace;
		font-size: 0.85rem;
		word-break: break-all;
	}
	h2 {
		font-size: 1.1rem;
		margin-bottom: 0.75rem;
	}
	h3 {
		font-size: 1rem;
		margin: 1rem 0 0.5rem;
	}
	.table-wrap {
		overflow: auto;
		max-height: 280px;
		border: 1px solid var(--border);
		border-radius: 8px;
	}
	.compact-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.85rem;
	}
	.compact-table th,
	.compact-table td {
		padding: 0.4rem 0.6rem;
		text-align: left;
		border-bottom: 1px solid var(--border);
	}
	.compact-table th {
		background: var(--surface);
		color: var(--muted);
		font-weight: 600;
		position: sticky;
		top: 0;
	}
	.compact-table code {
		font-size: 0.8rem;
		background: var(--surface);
		padding: 0.15rem 0.35rem;
		border-radius: 4px;
	}
</style>
