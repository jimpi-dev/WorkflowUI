<script lang="ts">
	import { tick, onDestroy } from 'svelte';
	import { getApiBase } from '$lib/config';
	import { waitForAppToBeAvailable } from '$lib/api';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { createWorkflowDropdownBody } from '$lib/components/loraDropdownBody';
	import { appBooting } from '$lib/stores/appBooting';

	let { data }: { data: { embedWorkflowuiMetadataOnDownload?: boolean; embedWorkflowuiMetadataOnSave?: boolean; comfyuiWorkflows?: { id: string; label: string }[]; comfyuiWorkflowsError?: string | null } } = $props();

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
		has_workflow_ui_link?: boolean;
		workflow_ui_link_node_id?: string;
	} | null>(null);
	let creating = $state(false);
	let isMobile = $state(browser && typeof window !== 'undefined' ? window.matchMedia('(max-width: 639px)').matches : false);

	let forceNewVersion = $state(false);
	let useWorkflowUILink = $state(true);


	let imageImporting = $state(false);
	let imageImportMessage = $state('');
	let imageDropZoneDragOver = $state(false);

	type PendingMediaImport = {
		slug: string;
		input_snapshot?: object;
		appName: string;
		workflowName: string;
		isExisting: boolean;
	};
	let importConfirmOpen = $state(false);
	let pendingMediaImport = $state<PendingMediaImport | null>(null);

	let comfyuiSelectedId = $state<string>('');
	let comfyuiImporting = $state(false);
	let comfyuiImportError = $state('');
	let comfyuiWorkflowsList = $state<{ id: string; label: string }[]>([]);
	let comfyuiWorkflowsError = $state<string | null>(null);
	let comfyuiWorkflowsLoading = $state(false);
	let comfyuiFilter = $state('');
	let comfyuiComboOpen = $state(false);
	let comfyuiComboEl: HTMLDivElement;
	let comfyuiFilterInputEl: HTMLInputElement;

	const apiBase = getApiBase() || '';
	function normalizeComfyuiWorkflows(list: unknown): { id: string; label: string }[] {
		if (!Array.isArray(list)) return [];
		return list.flatMap((item) => {
			if (typeof item === 'string' && item.trim()) {
				return [{ id: item, label: item }];
			}
			if (!item || typeof item !== 'object') return [];
			const rec = item as Record<string, unknown>;
			if (typeof rec.id !== 'string' || !rec.id.trim()) return [];
			const id = rec.id;
			const label = typeof rec.label === 'string' && rec.label.trim() ? rec.label : id;
			return [{ id, label }];
		});
	}
	const comfyuiWorkflows = $derived(
		comfyuiWorkflowsList.length > 0 ? comfyuiWorkflowsList : (data?.comfyuiWorkflows ?? [])
	);
	const comfyuiErrorToShow = $derived(comfyuiWorkflowsError ?? data?.comfyuiWorkflowsError ?? null);
	const comfyuiWorkflowsFiltered = $derived.by(() => {
		const q = (comfyuiFilter || '').trim().toLowerCase();
		if (!q) return comfyuiWorkflows;
		return comfyuiWorkflows.filter(
			(w) =>
				(w.id || '').toLowerCase().includes(q) || (w.label || '').toLowerCase().includes(q)
		);
	});

	const comfyuiSelectedLabel = $derived(
		comfyuiSelectedId
			? (comfyuiWorkflows.find((w) => w.id === comfyuiSelectedId)?.label ?? comfyuiSelectedId)
			: '— Select workflow from ComfyUI —'
	);

	const getWorkflowLabel = (id: string) =>
		comfyuiWorkflows.find((w) => w.id === id)?.label ?? id;
	const comfyuiDropdownBody = createWorkflowDropdownBody(getWorkflowLabel);
	onDestroy(() => comfyuiDropdownBody.unmount());

	function openComfyuiCombo() {
		comfyuiComboOpen = true;
		comfyuiFilter = '';
		tick().then(() => {
			comfyuiFilterInputEl?.focus();
			if (!comfyuiComboEl) return;
			const rect = comfyuiComboEl.getBoundingClientRect();
			const listHeight = 280;
			const gap = 4;
			const spaceBelow = window.innerHeight - (rect.bottom + gap);
			const spaceAbove = rect.top - gap;
			const showAbove = spaceBelow < listHeight && spaceAbove > spaceBelow;
			const left = rect.left;
			const top = showAbove ? Math.max(0, rect.top - listHeight - gap) : rect.bottom + gap;
			const maxH = showAbove ? Math.min(listHeight, spaceAbove) : Math.min(listHeight, spaceBelow);
			const width = Math.max(rect.width, 280);
			comfyuiDropdownBody.mount({
				left,
				top,
				width,
				maxHeight: maxH,
				items: comfyuiWorkflowsFiltered.map((w) => w.id),
				onSelect: selectWorkflow,
				onClose: closeComfyuiCombo
			});
		});
	}

	function closeComfyuiCombo() {
		comfyuiDropdownBody.unmount();
		comfyuiComboOpen = false;
		comfyuiFilter = '';
	}

	function selectWorkflow(id: string) {
		comfyuiSelectedId = id;
		closeComfyuiCombo();
	}

	function handleComfyuiComboKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			closeComfyuiCombo();
			comfyuiFilterInputEl?.blur();
		}
	}

	$effect(() => {
		if (comfyuiComboOpen && comfyuiWorkflowsFiltered.length >= 0) {
			comfyuiDropdownBody.update(comfyuiWorkflowsFiltered.map((w) => w.id));
		}
	});

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
				body: JSON.stringify({ name: trimmedName, graph: parsed.graph, use_workflow_ui_link: useWorkflowUILink })
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

	async function refetchPreviewWithSchema() {
		const trimmedName = name.trim();
		const parsed = parseGraph();
		if (!trimmedName || !parsed) return;
		try {
			const res = await fetch(`${apiBase}/import/preview`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: trimmedName, graph: parsed.graph, use_workflow_ui_link: useWorkflowUILink })
			});
			if (res.ok) preview = await res.json();
		} catch {
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
					force_new_version: forceNewVersion,
					use_workflow_ui_link: useWorkflowUILink && preview?.has_workflow_ui_link === true
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
			if (data.warning && typeof data.warning === 'string') {
				try {
					sessionStorage.setItem('workflowui_import_warning', data.warning);
				} catch {
				}
			}
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
		if (file.type.startsWith('video/')) return true;
		const n = file.name.toLowerCase();
		return n.endsWith('.mp3') || n.endsWith('.mp4');
	}

	let imageFileInputRef: HTMLInputElement;
	let jsonFileInputRef: HTMLInputElement;

	function chooseImageFile() {
		if (imageFileInputRef && !imageImporting) imageFileInputRef.click();
	}

	function chooseJsonFile() {
		if (jsonFileInputRef) jsonFileInputRef.click();
	}

	function isJsonFile(file: File): boolean {
		const n = file.name.toLowerCase();
		return n.endsWith('.json') || file.type === 'application/json';
	}

	function handleJsonDrop(e: DragEvent) {
		e.preventDefault();
		jsonDropZoneDragOver = false;
		const file = e.dataTransfer?.files?.[0];
		if (!file || !isJsonFile(file)) return;
		selectedFileName = file.name;
		const nameWithoutExt = file.name.replace(/\.json$/i, '');
		if (nameWithoutExt) name = nameWithoutExt;
		const reader = new FileReader();
		reader.onload = () => {
			jsonInput = String(reader.result ?? '');
			setState('idle');
		};
		reader.readAsText(file);
	}

	let jsonDropZoneDragOver = $state(false);

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
				const appName = data.app_title ?? data.app_slug ?? 'App';
				const workflowName = data.workflow_name ?? 'Workflow';
				pendingMediaImport = {
					slug,
					input_snapshot:
						data.input_snapshot != null && typeof data.input_snapshot === 'object'
							? data.input_snapshot
							: undefined,
					appName,
					workflowName,
					isExisting: true,
				};
				importConfirmOpen = true;
				return;
			}
			if (data.action === 'restored' && data.app_slug) {
				const slug = data.resolved_slug ?? data.app_slug;
				const appName = data.app_title ?? data.resolved_slug ?? data.app_slug ?? 'App';
				const workflowName = data.workflow_name ?? data.resolved_workflow_name ?? 'Workflow';
				pendingMediaImport = {
					slug,
					input_snapshot:
						data.input_snapshot != null && typeof data.input_snapshot === 'object'
							? data.input_snapshot
							: undefined,
					appName,
					workflowName,
					isExisting: false,
				};
				importConfirmOpen = true;
				return;
			}
			if (data.action === 'ignored') {
				imageImportMessage = data.reason === 'invalid_snapshot'
					? 'Invalid or corrupted WorkflowUI metadata in this file.'
					: 'No WorkflowUI metadata in this file. Save images, audio, or video from WorkflowUI with metadata on download/save to restore later.';
			} else {
				imageImportMessage = 'Import failed. Try again.';
			}
		} catch (e) {
			imageImportMessage = e instanceof Error ? e.message : 'Import failed.';
		} finally {
			imageImporting = false;
		}
	}

	async function continueLoadingImportedApp() {
		const p = pendingMediaImport;
		importConfirmOpen = false;
		pendingMediaImport = null;
		if (!p) return;
		if (p.input_snapshot != null) {
			try {
				sessionStorage.setItem(
					'workflowui_import_prefill',
					JSON.stringify({ slug: p.slug, input_snapshot: p.input_snapshot })
				);
			} catch {
				// ignore
			}
		}
		appBooting.set(true);
		await waitForAppToBeAvailable(p.slug);
		await goto(`/app/${p.slug}`);
	}

	function dismissImportConfirm() {
		importConfirmOpen = false;
		pendingMediaImport = null;
	}

	$effect(() => {
		const list = data?.comfyuiWorkflows;
		const err = data?.comfyuiWorkflowsError;
		if (list && list.length > 0) {
			comfyuiWorkflowsList = normalizeComfyuiWorkflows(list);
			comfyuiWorkflowsError = null;
		} else if (err) {
			comfyuiWorkflowsError = err;
		}
	});

	async function refreshComfyuiWorkflows() {
		comfyuiWorkflowsError = null;
		comfyuiWorkflowsLoading = true;
		try {
			const res = await fetch(`${apiBase}/comfyui/workflows`);
			const body = await res.json().catch(() => ({}));
			const list = Array.isArray(body) ? body : body?.workflows;
			comfyuiWorkflowsList = normalizeComfyuiWorkflows(list);
			if (comfyuiWorkflowsList.length === 0 && typeof body?.error === 'string' && body.error) {
				comfyuiWorkflowsError = body.error;
			}
		} catch (e) {
			comfyuiWorkflowsError = e instanceof Error ? e.message : 'Failed to load workflow list';
			comfyuiWorkflowsList = [];
		} finally {
			comfyuiWorkflowsLoading = false;
		}
	}

	async function handleLoadWorkflowFromComfyui() {
		const id = comfyuiSelectedId?.trim();
		if (!id) {
			comfyuiImportError = 'Select a workflow first.';
			return;
		}
		comfyuiImportError = '';
		comfyuiImporting = true;
		setState('idle', '');
		try {
			const res = await fetch(`${apiBase}/comfyui/workflows/${encodeURIComponent(id)}`);
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				const detail = String(d.detail ?? '').trim();
				if (res.status === 404 || detail.toLowerCase().includes('not found')) {
					comfyuiImportError = `Workflow not found in ComfyUI: ${id}`;
				} else if (detail.toLowerCase().includes('plugin unreachable') || res.status === 502) {
					comfyuiImportError = detail || 'ComfyUI plugin is unreachable.';
				} else {
					comfyuiImportError = detail || res.statusText || 'Failed to load workflow';
				}
				return;
			}
			const { name: wfName, graph } = await res.json();
			if (!graph || typeof graph !== 'object') {
				comfyuiImportError = 'Invalid workflow response';
				return;
			}
			const workflowName = (typeof wfName === 'string' && wfName.trim()) ? wfName.trim() : id;
			name = workflowName;
			jsonInput = JSON.stringify(graph, null, 2);
			selectedFileName = null;
			setState('analyzing', '');
			const previewRes = await fetch(`${apiBase}/import/preview`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: workflowName, graph, use_workflow_ui_link: useWorkflowUILink })
			});
			if (!previewRes.ok) {
				const d = await previewRes.json().catch(() => ({}));
				setState('error', (d.detail as string) || previewRes.statusText);
				return;
			}
			preview = await previewRes.json();
			setState('preview-ready', '');
		} catch (e) {
			comfyuiImportError = e instanceof Error ? e.message : 'Failed to load workflow';
		} finally {
			comfyuiImporting = false;
		}
	}
</script>

<div class="two-col-page page">
	<aside class="panel-left panel-scroll card">
		<h1>Import workflow</h1>
		<p class="page-subline muted">Add a ComfyUI workflow from its JSON.</p>

		<!-- Import from ComfyUI: browse workflows on ComfyUI and import as app (top) -->
		<details class="section comfyui-import-section" open={comfyuiWorkflows.length > 0}>
			<summary class="media-restore-summary">Import from ComfyUI</summary>
			<div class="comfyui-import-inner">
				<p class="media-restore-hint comfyui-hint">Load a workflow from the ComfyUI WorkflowUI plugin. The workflow will appear in the preview below so you can review detected nodes, then save it with <strong>Create workflow</strong>. The plugin must expose <code>GET /workflowui/workflows</code> and <code>GET /workflowui/workflows/:id</code>.</p>
				{#if comfyuiWorkflows.length === 0}
					<div class="comfyui-empty-state">
						<button
							type="button"
							class="choose-file-btn comfyui-refresh-btn"
							disabled={comfyuiWorkflowsLoading}
							onclick={refreshComfyuiWorkflows}
							aria-label="Refresh workflow list from ComfyUI"
						>
							{comfyuiWorkflowsLoading ? 'Loading…' : 'Refresh list'}
						</button>
						{#if comfyuiErrorToShow}
							<p class="error-text comfyui-error-msg">{comfyuiErrorToShow}</p>
							<p class="muted comfyui-tips">Check: (1) Backend .env has <code>COMFYUI_URL</code> pointing at ComfyUI (e.g. http://localhost:8188). (2) ComfyUI is running and WorkflowUIPlugin is loaded. (3) Plugin workflows folder exists (default: ComfyUI <code>user/default/workflows/</code>) or <code>WORKFLOWUI_WORKFLOWS_DIR</code> is set, with .json files inside.</p>
						{:else}
							<p class="muted">No workflows from ComfyUI. Add .json workflow files to the plugin's workflows folder (default: ComfyUI <code>user/default/workflows/</code> or set <code>WORKFLOWUI_WORKFLOWS_DIR</code>), then click <strong>Refresh list</strong>.</p>
						{/if}
					</div>
				{:else}
					<div class="comfyui-flow">
						<div class="comfyui-combo-wrap" bind:this={comfyuiComboEl}>
							{#if comfyuiComboOpen}
								<div
									class="comfyui-combo"
									role="combobox"
									aria-expanded="true"
									aria-haspopup="listbox"
									aria-controls="workflow-combo-listbox"
									aria-label="Select workflow from ComfyUI"
								>
									<input
										bind:this={comfyuiFilterInputEl}
										type="text"
										class="comfyui-combo-input"
										placeholder="Filter workflows…"
										bind:value={comfyuiFilter}
										onkeydown={handleComfyuiComboKeydown}
										aria-label="Filter workflow list"
									/>
								</div>
							{:else}
								<button
									type="button"
									class="comfyui-combo-trigger"
									title={comfyuiSelectedLabel}
									onclick={openComfyuiCombo}
									disabled={comfyuiImporting}
									aria-label="Select workflow from ComfyUI"
								>
									{comfyuiSelectedLabel}
								</button>
							{/if}
						</div>
						<div class="comfyui-actions">
							<button
								type="button"
								class="choose-file-btn primary comfyui-load-btn"
								disabled={comfyuiImporting || !comfyuiSelectedId}
								onclick={handleLoadWorkflowFromComfyui}
								aria-label="Load selected workflow into form and show preview"
							>
								{comfyuiImporting ? 'Loading…' : 'Load workflow'}
							</button>
							<button
								type="button"
								class="choose-file-btn"
								disabled={comfyuiWorkflowsLoading}
								onclick={refreshComfyuiWorkflows}
								aria-label="Refresh workflow list from ComfyUI"
							>
								{comfyuiWorkflowsLoading ? 'Loading…' : 'Refresh list'}
							</button>
						</div>
					</div>
					{#if comfyuiImportError}
						<p class="error-text comfyui-error-msg">{comfyuiImportError}</p>
					{/if}
				{/if}
			</div>
		</details>

		<!-- Drop workflow JSON or paste -->
		<section class="section">
			<label for="import-graph-json" class="section-label">Workflow JSON</label>
			<div
				class="json-drop-zone"
				class:drag-over={jsonDropZoneDragOver}
				role="button"
				tabindex="0"
				aria-label="Drop workflow JSON file here or click to browse"
				ondragover={(e) => { e.preventDefault(); jsonDropZoneDragOver = true; }}
				ondragleave={() => { jsonDropZoneDragOver = false; }}
				ondrop={handleJsonDrop}
				onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chooseJsonFile(); } }}
				onclick={() => chooseJsonFile()}
			>
				<input
					id="import-graph-json"
					type="file"
					accept=".json,application/json"
					onchange={handleFileChange}
					class="file-input file-input-hidden"
					bind:this={jsonFileInputRef}
					aria-label="Choose JSON file"
				/>
				<span class="json-drop-zone-label">
					{selectedFileName ? selectedFileName : 'Drop workflow JSON here or click to browse'}
				</span>
				<span class="json-drop-zone-hint">.json file or paste below</span>
			</div>
			<p class="paste-label">Or paste JSON</p>
			<textarea
				class="import-textarea"
				placeholder={'{ "3": { "class_type": "KSampler" }, ... }'}
				bind:value={jsonInput}
				rows="10"
				aria-label="Paste workflow JSON"
			></textarea>
		</section>

		<section class="section">
			<label for="import-name">Workflow name</label>
			<input id="import-name" type="text" bind:value={name} placeholder="My Workflow" />
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

		<!-- Secondary: Restore from image or audio -->
		<details class="section media-restore-section">
			<summary class="media-restore-summary">Or restore from image or audio</summary>
			<div
				class="media-restore-inner"
				class:drag-over={imageDropZoneDragOver}
				ondragover={(e) => { e.preventDefault(); imageDropZoneDragOver = true; }}
				ondragleave={() => { imageDropZoneDragOver = false; }}
				ondrop={(e) => {
					e.preventDefault();
					imageDropZoneDragOver = false;
					handleImageFile(e.dataTransfer?.files ?? null);
				}}
			>
				<input
					id="import-workflow-file"
					type="file"
					accept="image/*,.png,audio/mpeg,.mp3"
					class="file-input file-input-hidden"
					bind:this={imageFileInputRef}
					disabled={imageImporting}
					onchange={(e) => handleImageFile((e.target as HTMLInputElement).files)}
					aria-label="Choose image, audio, or video file (PNG, MP3, or MP4)"
				/>
				<p class="media-restore-hint">PNG, MP3, or MP4 saved from WorkflowUI with embedded metadata can reopen or restore that app.</p>
				<p class="metadata-status" role="status">
					Metadata on download: <strong>{data?.embedWorkflowuiMetadataOnDownload ? 'Yes' : 'No'}</strong>
					· on save: <strong>{data?.embedWorkflowuiMetadataOnSave ? 'Yes' : 'No'}</strong>
					{#if data?.embedWorkflowuiMetadataOnDownload || data?.embedWorkflowuiMetadataOnSave}
						— drop those files here to restore.
					{:else}
						— enable in backend .env to attach metadata.
					{/if}
				</p>
				<button type="button" class="choose-file-btn" disabled={imageImporting} onclick={(e) => { e.stopPropagation(); chooseImageFile(); }} aria-label="Choose image or audio file">
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
		</details>
	</aside>

	{#if importConfirmOpen && pendingMediaImport}
		<div
			class="import-confirm-backdrop"
			role="dialog"
			aria-modal="true"
			aria-labelledby="import-confirm-title"
			tabindex="-1"
			onclick={dismissImportConfirm}
			onkeydown={(e) => { if (e.key === 'Escape') dismissImportConfirm(); }}
		>
			<div class="import-confirm-dialog" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
				<h2 id="import-confirm-title" class="import-confirm-title">Import successful</h2>
				<p class="import-confirm-desc">The following app and workflow were imported:</p>
				<p class="import-confirm-status">
					{#if pendingMediaImport.isExisting}
						<strong>Existing app</strong> — this matched an existing app and will open it.
					{:else}
						<strong>New app</strong> — a new app was created from this import.
					{/if}
				</p>
				<dl class="import-confirm-meta">
					<dt>App</dt>
					<dd>{pendingMediaImport.appName}</dd>
					<dt>Workflow</dt>
					<dd>{pendingMediaImport.workflowName}</dd>
				</dl>
				<div class="import-confirm-actions">
					<button type="button" class="import-confirm-btn secondary" onclick={dismissImportConfirm}>
						Don't load app now
					</button>
					<button type="button" class="import-confirm-btn primary" onclick={continueLoadingImportedApp}>
						Continue loading imported app with values
					</button>
				</div>
			</div>
		</div>
	{/if}

	<div class="panel-right panel-scroll card">
		{#if importState !== 'preview-ready' || !preview}
			<div class="empty-state">
				<div class="empty-state-icon" aria-hidden="true">
					<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
						<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z" />
						<polyline points="14 2 14 8 20 8" />
						<path d="M12 18v-6" />
						<path d="M9 15l3 3 3-3" />
					</svg>
				</div>
				<h2>Preview your workflow</h2>
				<ol class="empty-state-steps">
					<li>Drop a workflow JSON file, paste JSON on the left, or load one from the ComfyUI workflows list above.</li>
					<li>Enter a name and click <strong>Analyze</strong> (or use <strong>Load workflow</strong> when importing directly from ComfyUI).</li>
					<li>Review metadata and detected inputs/outputs here, then <strong>Create workflow</strong>.</li>
				</ol>
			</div>
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

			<details class="import-accordion" open={!isMobile}>
				<summary>Detected inputs</summary>
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
			</details>

			<details class="import-accordion" open={!isMobile}>
				<summary>Detected outputs</summary>
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
			</details>

			<!-- Actions: schema choice, force version, Create (moved from left) -->
			<div class="sticky-actions">
				{#if preview.has_workflow_ui_link}
					<details class="import-accordion import-accordion--schema-choice" open={!isMobile}>
						<summary>Schema options</summary>
						<div class="schema-choice-section">
						<div class="schema-choice-banner">
							<p class="schema-choice-banner-headline">WorkflowUI Link node detected</p>
							<p class="schema-choice-banner-subtext">This workflow contains a WorkflowUI Link node. You can use it as a shorthand for app creation—it exposes only the fields you defined in ComfyUI.</p>
						</div>
						<div
							class="schema-segmented-control"
							role="tablist"
							aria-label="Schema source"
							onkeydown={(e) => {
								if (e.key === 'ArrowLeft' && !useWorkflowUILink) {
									e.preventDefault();
									useWorkflowUILink = true;
									refetchPreviewWithSchema();
								} else if (e.key === 'ArrowRight' && useWorkflowUILink) {
									e.preventDefault();
									useWorkflowUILink = false;
									refetchPreviewWithSchema();
								}
							}}
						>
							<button
								type="button"
								role="tab"
								class="schema-option"
								class:active={useWorkflowUILink}
								aria-pressed={useWorkflowUILink}
								aria-selected={useWorkflowUILink}
								tabindex={useWorkflowUILink ? 0 : -1}
								onclick={() => { useWorkflowUILink = true; void refetchPreviewWithSchema(); }}
							>
								<span class="schema-option-label">WorkflowUI Link schema</span>
								<span class="schema-option-desc">Exposes only the fields you defined in the WorkflowUI Link node. Best for workflows designed for app creation.</span>
							</button>
							<button
								type="button"
								role="tab"
								class="schema-option"
								class:active={!useWorkflowUILink}
								aria-pressed={!useWorkflowUILink}
								aria-selected={!useWorkflowUILink}
								tabindex={!useWorkflowUILink ? 0 : -1}
								onclick={() => { useWorkflowUILink = false; void refetchPreviewWithSchema(); }}
							>
								<span class="schema-option-label">Full workflow (all nodes)</span>
								<span class="schema-option-desc">Uses every detected input from the entire workflow—KSampler, CLIPTextEncode, LoadImage, and more.</span>
							</button>
						</div>
						<p class="schema-cross-hint">You can import the same workflow again later with the other option to switch schema source.</p>
						</div>
					</details>
				{/if}
				{#if !preview.is_new_workflow && !preview.is_new_version}
					<label class="force-version-wrap">
						<input type="checkbox" bind:checked={forceNewVersion} />
						<span>Create new version anyway</span>
					</label>
					<p class="hint">Same graph as latest; import would normally be skipped. Check to create v2 (e.g. to refresh detected inputs).</p>
				{/if}
				<button type="button" onclick={handleCreateWorkflow} disabled={creating} class="primary">
					{creating ? 'Creating…' : 'Complete import and create App'}
				</button>
				<p class="hint">Redirects to workflow detail. No app creation.</p>
			</div>
		{/if}
	</div>
</div>

<style>
	.page-subline {
		margin-bottom: 1.25rem;
	}
	.section {
		margin-bottom: 1.25rem;
	}
	.section-label {
		display: block;
		margin-bottom: 0.5rem;
		font-weight: 600;
	}
	.json-drop-zone {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		min-height: 140px;
		padding: 1.25rem;
		margin-bottom: 0.75rem;
		border: 2px dashed var(--border);
		border-radius: var(--radius-lg);
		background: var(--surface);
		cursor: pointer;
		transition: border-color 0.2s ease, background 0.2s ease;
	}
	.json-drop-zone:hover {
		border-color: var(--muted);
		background: color-mix(in srgb, var(--surface) 95%, var(--accent-soft));
	}
	.json-drop-zone.drag-over {
		border-color: var(--accent);
		background: var(--accent-soft);
		outline: none;
	}
	.json-drop-zone-label {
		font-weight: 500;
		color: var(--text);
		text-align: center;
	}
	.json-drop-zone-hint {
		font-size: 0.85rem;
		color: var(--muted);
		margin-top: 0.25rem;
	}
	.paste-label {
		font-size: 0.9rem;
		color: var(--muted);
		margin-bottom: 0.35rem;
	}
	.metadata-status {
		font-size: 0.85rem;
		color: var(--text);
		margin: 0.5rem 0;
		line-height: 1.4;
	}
	:global(.metadata-status code) {
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
		min-height: 160px;
		font-family: ui-monospace, monospace;
		font-size: 0.85rem;
	}

	.media-restore-section {
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--surface);
		padding: 0 0.75rem;
	}
	.media-restore-summary {
		list-style: none;
		cursor: pointer;
		font-weight: 500;
		color: var(--muted);
		font-size: 0.9rem;
		padding: 0.75rem 0;
	}
	.media-restore-summary::-webkit-details-marker {
		display: none;
	}
	.media-restore-summary::before {
		content: '▸ ';
		display: inline-block;
		transition: transform 0.2s ease;
	}
	.media-restore-section[open] .media-restore-summary::before {
		transform: rotate(90deg);
	}
	.media-restore-inner {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		padding-bottom: 0.75rem;
		border-radius: 6px;
	}
	.media-restore-inner.drag-over {
		background: var(--accent-soft);
		outline: 2px dashed var(--accent);
		outline-offset: 2px;
	}
	.comfyui-import-section {
		margin-top: 1rem;
	}
	.comfyui-import-inner {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding-bottom: 0.75rem;
		min-width: 0;
	}
	.comfyui-hint {
		margin: 0;
		word-wrap: break-word;
		overflow-wrap: break-word;
	}
	.comfyui-empty-state {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-width: 0;
	}
	.comfyui-refresh-btn {
		align-self: flex-start;
	}
	.comfyui-flow {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		min-width: 0;
		max-width: 100%;
	}
	.comfyui-actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
	}
	.comfyui-load-btn {
		flex-shrink: 0;
	}
	.comfyui-error-msg {
		margin-bottom: 0.5rem;
		overflow-wrap: break-word;
		word-wrap: break-word;
	}
	.comfyui-tips {
		font-size: 0.85rem;
		margin-top: 0.5rem;
		line-height: 1.4;
		overflow-wrap: break-word;
		word-wrap: break-word;
	}
	.comfyui-tips code {
		font-size: 0.8rem;
		background: var(--surface);
		padding: 0.1rem 0.25rem;
		border-radius: 4px;
	}
	.comfyui-combo-wrap {
		min-width: 0;
		position: relative;
		max-width: 100%;
		width: 100%;
	}
	.comfyui-combo {
		position: relative;
		width: 100%;
		min-width: 0;
	}
	.comfyui-combo-input {
		width: 100%;
		padding: 0.35rem 0.5rem;
		font-size: 0.85rem;
		color: var(--text);
		background: var(--accent-soft);
		border: 1px solid var(--accent);
		border-radius: 6px;
		outline: none;
		box-sizing: border-box;
	}
	.comfyui-combo-input:focus {
		border-color: var(--accent);
		box-shadow: 0 0 0 2px var(--accent-soft);
	}
	.comfyui-combo-trigger {
		display: block;
		width: 100%;
		box-sizing: border-box;
		text-align: left;
		padding: 0.4rem 0.6rem;
		font: inherit;
		font-weight: 500;
		font-size: 0.9rem;
		color: inherit;
		background: var(--accent-soft);
		border: 1px solid var(--border);
		border-radius: 6px;
		cursor: pointer;
		border-bottom: 1px dotted transparent;
		transition: background 0.15s, border-color 0.15s;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		min-width: 0;
	}
	.comfyui-combo-trigger:hover:not(:disabled) {
		background: var(--accent-soft);
		border-color: var(--accent);
		border-bottom-color: var(--accent);
	}
	.comfyui-combo-trigger:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.media-restore-hint {
		width: 100%;
		font-size: 0.85rem;
		color: var(--muted);
		margin: 0 0 0.25rem 0;
	}

	.import-confirm-backdrop {
		position: fixed;
		inset: 0;
		z-index: 2000;
		background: rgba(0, 0, 0, 0.5);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
	}
	.import-confirm-dialog {
		background: var(--card-bg, var(--surface));
		border-radius: 12px;
		padding: 1.25rem 1.5rem;
		max-width: min(720px, 96vw);
		width: auto;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
	}
	.import-confirm-title {
		margin: 0 0 0.5rem 0;
		font-size: 1.15rem;
		font-weight: 600;
	}
	.import-confirm-desc {
		margin: 0 0 0.75rem 0;
		font-size: 0.95rem;
		color: var(--text-muted, var(--muted));
	}
	.import-confirm-status {
		margin: 0 0 0.75rem 0;
		font-size: 0.9rem;
		color: var(--text-muted, var(--muted));
	}
	.import-confirm-status strong {
		color: var(--accent);
	}
	.import-confirm-meta {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 0.25rem 1rem;
		margin: 0 0 1.25rem 0;
		font-size: 0.95rem;
	}
	.import-confirm-meta dt {
		margin: 0;
		font-weight: 600;
		color: var(--text);
	}
	.import-confirm-meta dd {
		margin: 0;
		color: var(--text);
		overflow-wrap: anywhere;
	}
	.import-confirm-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		justify-content: flex-end;
	}
	.import-confirm-btn {
		padding: 0.5rem 1rem;
		border-radius: 8px;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
		border: none;
		transition: filter 0.15s ease, background 0.15s ease;
	}
	.import-confirm-btn.secondary {
		background: color-mix(in srgb, var(--accent) 12%, var(--surface));
		color: var(--text);
	}
	.import-confirm-btn.secondary:hover {
		background: color-mix(in srgb, var(--accent) 18%, var(--surface));
	}
	.import-confirm-btn.primary {
		background: var(--accent);
		color: var(--accent-fg, #fff);
	}
	.import-confirm-btn.primary:hover {
		filter: brightness(1.08);
	}

	.import-confirm-backdrop {
		position: fixed;
		inset: 0;
		z-index: 2000;
		background: rgba(0, 0, 0, 0.5);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
	}
	.import-confirm-dialog {
		background: var(--card-bg, var(--surface));
		border-radius: 12px;
		padding: 1.25rem 1.5rem;
		max-width: 420px;
		width: 100%;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
	}
	.import-confirm-title {
		margin: 0 0 0.5rem 0;
		font-size: 1.15rem;
		font-weight: 600;
	}
	.import-confirm-desc {
		margin: 0 0 0.75rem 0;
		font-size: 0.95rem;
		color: var(--text-muted, var(--muted));
	}
	.import-confirm-meta {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.25rem 1rem;
		margin: 0 0 1.25rem 0;
		font-size: 0.95rem;
	}
	.import-confirm-meta dt {
		margin: 0;
		font-weight: 600;
		color: var(--text);
	}
	.import-confirm-meta dd {
		margin: 0;
		color: var(--text);
	}
	.import-confirm-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		justify-content: flex-end;
	}
	.import-confirm-btn {
		padding: 0.5rem 1rem;
		border-radius: 8px;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
		border: none;
		transition: filter 0.15s ease, background 0.15s ease;
	}
	.import-confirm-btn.secondary {
		background: color-mix(in srgb, var(--accent) 12%, var(--surface));
		color: var(--text);
	}
	.import-confirm-btn.secondary:hover {
		background: color-mix(in srgb, var(--accent) 18%, var(--surface));
	}
	.import-confirm-btn.primary {
		background: var(--accent);
		color: var(--accent-fg, #fff);
	}
	.import-confirm-btn.primary:hover {
		filter: brightness(1.08);
	}

	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		text-align: center;
		padding: 2rem 1rem;
	}
	.empty-state-icon {
		color: var(--muted);
		margin-bottom: 1rem;
	}
	.empty-state h2 {
		font-size: 1.1rem;
		margin: 0 0 1rem 0;
	}
	.empty-state-steps {
		text-align: left;
		margin: 0;
		padding-left: 1.25rem;
		font-size: 0.95rem;
		color: var(--muted);
		line-height: 1.6;
	}
	.empty-state-steps li {
		margin-bottom: 0.5rem;
	}

	.sticky-actions {
		margin-top: 1.5rem;
		padding-top: 1rem;
		padding-bottom: 0.5rem;
		border-top: 1px solid var(--border);
		position: sticky;
		bottom: 0;
		background: var(--card);
	}
	.sticky-actions .hint {
		font-size: 0.8rem;
		color: var(--muted);
		margin-top: 0.5rem;
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
	.schema-choice-section {
		margin-bottom: 1rem;
	}
	.schema-choice-banner {
		padding: 0.75rem 1rem;
		background: var(--accent-soft);
		border-left: 4px solid var(--accent);
		border-radius: 0 8px 8px 0;
		margin-bottom: 1rem;
	}
	.schema-choice-banner-headline {
		font-weight: 600;
		margin: 0 0 0.25rem 0;
		font-size: 0.95rem;
	}
	.schema-choice-banner-subtext {
		margin: 0;
		font-size: 0.85rem;
		color: var(--muted);
		line-height: 1.4;
	}
	.schema-segmented-control {
		display: flex;
		gap: 0;
		border: 1px solid var(--border);
		border-radius: 8px;
		overflow: hidden;
	}
	.schema-option {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.25rem;
		padding: 0.75rem 1rem;
		background: var(--surface);
		border: none;
		border-right: 1px solid var(--border);
		cursor: pointer;
		text-align: left;
		color: var(--text);
		font-size: 0.9rem;
		transition: background 0.2s ease;
	}
	.schema-option:last-child {
		border-right: none;
	}
	.schema-option:hover {
		background: color-mix(in srgb, var(--surface) 90%, var(--accent-soft));
	}
	.schema-option.active {
		background: var(--accent-soft);
		box-shadow: inset 0 -2px 0 0 var(--accent);
	}
	.schema-option-label {
		font-weight: 600;
	}
	.schema-option-desc {
		font-size: 0.8rem;
		color: var(--muted);
		line-height: 1.35;
	}
	.schema-cross-hint {
		margin: 0.5rem 0 0;
		font-size: 0.8rem;
		color: var(--muted);
		font-style: italic;
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
	.import-accordion {
		margin: 1rem 0 0.5rem;
		border-radius: 10px;
		border: 1px solid var(--border);
		background: rgba(0, 0, 0, 0.05);
		overflow: hidden;
	}
	.import-accordion[open] {
		/* Desktop: keep the original “just show the tables” feel. */
		border: none;
		background: transparent;
	}
	.import-accordion > summary {
		list-style: none;
		cursor: pointer;
		min-height: 44px;
		padding: 0.75rem 1rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
		font-weight: 600;
		color: var(--text);
	}
	.import-accordion > summary::-webkit-details-marker {
		display: none;
	}
	.import-accordion[open] > summary {
		display: none;
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
