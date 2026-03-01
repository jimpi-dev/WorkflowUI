<script lang="ts">
	import { goto } from '$app/navigation';
	import { getApiBase } from '$lib/config';
	import FieldCard from '$lib/components/app-builder/FieldCard.svelte';
	import OutputCard from '$lib/components/app-builder/OutputCard.svelte';
	import {
		draftFromExistingApp,
		draftToUIConfig,
		draftToDefaultInputs,
		setInputVisible,
		setDefaultOverride,
		setInputOverride,
		setOutputVisible,
		setPrimaryOutput,
		setOutputLabel,
		moveInputNodeOrder,
		moveOutputNodeOrder,
		setMasterSeedInputKey,
		setIgnoreLoadImageDefault,
		nodeIdFromInputKey,
		type AppDraft
	} from '$lib/types/appBuilder';

	let { data } = $props();
	const appData = $derived(data?.appData ?? null);
	const slugParam = $derived(data?.slug ?? '');

	const wv = $derived(appData?.workflow_version ?? null);
	const app = $derived(appData?.app ?? null);
	const detectedInputs = $derived(wv?.detected_inputs ?? []);
	const detectedOutputs = $derived(wv?.detected_outputs ?? []);
	const internalNodes = $derived((wv as { internal_nodes?: { classType: string; label: string }[] } | null)?.internal_nodes ?? []);
	const inputKeys = $derived(detectedInputs.map((i: { key: string }) => i.key).filter(Boolean));
	const outputKeys = $derived(detectedOutputs.map((o: { nodeId: string }) => o.nodeId).filter(Boolean));

	let appDraft = $state<AppDraft | null>(null);
	let title = $state('');
	let slug = $state('');
	let description = $state('');
	let isPublic = $state(true);
	let supportedInputKinds = $state<string[]>([]);
	let headerColor = $state<string | null>(null);
	let embedMetadataOnDownload = $state(true);
	let embedMetadataOnSave = $state(true);
	const SUPPORTED_KIND_OPTIONS = ['image', 'video', 'audio'] as const;
	let activeTab = $state<'inputs' | 'outputs'>('inputs');
	let filterQuery = $state('');
	let visibilityFilter = $state<'all' | 'visible' | 'hidden'>('all');
	let saving = $state(false);
	let saveError = $state('');
	let copyError = $state('');
	let copying = $state(false);
	let draftInitialized = $state(false);
	let availableLoras = $state<string[]>([]);
	let availableCheckpoints = $state<string[]>([]);
	let availableClipModels = $state<string[]>([]);
	let availableClipTypes = $state<string[]>([]);
	let availableVaeModels = $state<string[]>([]);
	let availableDevices = $state<string[]>([]);
	let downloadingWorkflow = $state(false);

	async function downloadAppWorkflowWithDefaults() {
		if (!slugParam || downloadingWorkflow) return;
		const apiBase = getApiBase().replace(/\/$/, '');
		const url = `${apiBase}/app/${encodeURIComponent(slugParam)}/workflow/download`;
		downloadingWorkflow = true;
		try {
			const res = await fetch(url);
			if (!res.ok) throw new Error(res.status === 404 ? 'App not found' : 'Download failed');
			const blob = await res.blob();
			const disp = res.headers.get('Content-Disposition');
			const match = disp && /filename="?([^"]+)"?/.exec(disp);
			const filename = match ? match[1].trim() : `${slugParam}-workflow.json`;
			const a = document.createElement('a');
			a.href = URL.createObjectURL(blob);
			a.download = filename;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(a.href);
		} finally {
			downloadingWorkflow = false;
		}
	}

	function matchesFilter(item: { key?: string; label?: string; metaTitle?: string | null; nodeId?: string }, q: string): boolean {
		if (!q.trim()) return true;
		const lower = q.trim().toLowerCase();
		const key = (item.key ?? '').toLowerCase();
		const label = (item.label ?? '').toLowerCase();
		const meta = (item.metaTitle ?? '').toLowerCase();
		const nodeId = (item.nodeId ?? '').toLowerCase();
		return key.includes(lower) || label.includes(lower) || meta.includes(lower) || nodeId.includes(lower);
	}

	const textFilteredInputs = $derived(
		!filterQuery.trim() ? detectedInputs : detectedInputs.filter((i: { key?: string; label?: string; metaTitle?: string | null; nodeId?: string }) => matchesFilter(i, filterQuery))
	);
	const textFilteredOutputs = $derived(
		!filterQuery.trim() ? detectedOutputs : detectedOutputs.filter((o: { nodeId?: string; label?: string; metaTitle?: string | null }) => matchesFilter(o, filterQuery))
	);

	function applyVisibilityFilterInputs(list: typeof textFilteredInputs, draft: AppDraft | null) {
		if (!draft) return list;
		if (visibilityFilter === 'all') return list;
		return list.filter((i: { key: string }) =>
			visibilityFilter === 'visible' ? draft.visibleInputs.has(i.key) : !draft.visibleInputs.has(i.key)
		);
	}
	function applyVisibilityFilterOutputs(list: typeof textFilteredOutputs, draft: AppDraft | null) {
		if (!draft) return list;
		if (visibilityFilter === 'all') return list;
		return list.filter((o: { nodeId: string }) =>
			visibilityFilter === 'visible' ? draft.visibleOutputs.has(o.nodeId) : !draft.visibleOutputs.has(o.nodeId)
		);
	}
	const filteredInputs = $derived(applyVisibilityFilterInputs(textFilteredInputs, appDraft));
	const filteredOutputs = $derived(applyVisibilityFilterOutputs(textFilteredOutputs, appDraft));

	const inputGroups = $derived.by(() => {
		if (!appDraft) return [];
		const byNode = new Map<string, { nodeId: string; parent?: string; classType?: string; metaTitle?: string | null; inputs: typeof filteredInputs }>();
		for (const i of filteredInputs) {
			if (!i.key) continue;
			const nid = (i as { nodeId?: string }).nodeId ?? nodeIdFromInputKey(i.key);
			if (!byNode.has(nid)) {
				byNode.set(nid, {
					nodeId: nid,
					parent: (i as { parent?: string }).parent,
					classType: (i as { classType?: string }).classType,
					metaTitle: (i as { metaTitle?: string | null }).metaTitle ?? null,
					inputs: []
				});
			}
			byNode.get(nid)!.inputs.push(i);
		}
		const order = appDraft.inputNodeOrder;
		const ordered: { nodeId: string; parent?: string; classType?: string; metaTitle?: string | null; inputs: typeof filteredInputs }[] = [];
		const seen = new Set<string>();
		for (const nid of order) {
			const g = byNode.get(nid);
			if (g) {
				ordered.push(g);
				seen.add(nid);
			}
		}
		for (const [nid, g] of byNode) {
			if (!seen.has(nid)) ordered.push(g);
		}
		return ordered;
	});

	const visibleSeedInputs = $derived.by(() => {
		if (!appDraft) return [];
		return (filteredInputs as { key?: string; type?: string; label?: string }[]).filter(
			(i) => i.type === 'seed' && i.key != null && String(i.key).trim() !== '' && appDraft!.visibleInputs.has(i.key)
		);
	});

	const sortedOutputs = $derived.by(() => {
		if (!appDraft) return filteredOutputs;
		const order = appDraft.outputNodeOrder;
		const byId = new Map<string, (typeof filteredOutputs)[number]>();
		for (const o of filteredOutputs) {
			if (o.nodeId) byId.set(o.nodeId, o);
		}
		const ordered: (typeof filteredOutputs) = [];
		for (const nid of order) {
			const out = byId.get(nid);
			if (out) ordered.push(out);
		}
		for (const o of filteredOutputs) {
			if (o.nodeId && !order.includes(o.nodeId)) ordered.push(o);
		}
		return ordered;
	});

	function selectAllInputsInNode(keys: string[]) {
		if (!appDraft || keys.length === 0) return;
		for (const key of keys) setInputVisible(appDraft, key, true);
		appDraft = { ...appDraft, visibleInputs: new Set(appDraft.visibleInputs) };
	}
	function deselectAllInputsInNode(keys: string[]) {
		if (!appDraft || keys.length === 0) return;
		for (const key of keys) setInputVisible(appDraft, key, false);
		appDraft = { ...appDraft, visibleInputs: new Set(appDraft.visibleInputs) };
	}

	$effect(() => {
		if (!appData) return;
		const base = getApiBase() || '';
		Promise.all([
			fetch(`${base}/loras`).then((r) => (r.ok ? r.json() : { loras: [] })).then((d: { loras?: string[] }) => { availableLoras = d.loras ?? []; }).catch(() => { availableLoras = []; }),
			fetch(`${base}/checkpoints`).then((r) => (r.ok ? r.json() : { checkpoints: [] })).then((d: { checkpoints?: string[] }) => { availableCheckpoints = d.checkpoints ?? []; }).catch(() => { availableCheckpoints = []; }),
			fetch(`${base}/clip_models`).then((r) => (r.ok ? r.json() : { clip_models: [] })).then((d: { clip_models?: string[] }) => { availableClipModels = d.clip_models ?? []; }).catch(() => { availableClipModels = []; }),
			fetch(`${base}/clip_types`).then((r) => (r.ok ? r.json() : { clip_types: [] })).then((d: { clip_types?: string[] }) => { availableClipTypes = d.clip_types ?? []; }).catch(() => { availableClipTypes = []; }),
			fetch(`${base}/vae_models`).then((r) => (r.ok ? r.json() : { vae_models: [] })).then((d: { vae_models?: string[] }) => { availableVaeModels = d.vae_models ?? []; }).catch(() => { availableVaeModels = []; }),
			fetch(`${base}/devices`).then((r) => (r.ok ? r.json() : { devices: [] })).then((d: { devices?: string[] }) => { availableDevices = d.devices ?? []; }).catch(() => { availableDevices = []; })
		]);
	});

	$effect(() => {
		if (appData && app && wv && inputKeys.length >= 0 && outputKeys.length >= 0 && !draftInitialized) {
			title = app.title ?? '';
			slug = app.slug ?? slugParam;
			description = app.description ?? '';
			isPublic = app.is_public ?? true;
			const raw = (app as { supported_input_kinds?: string[] | null }).supported_input_kinds;
			supportedInputKinds = Array.isArray(raw) ? [...raw] : [];
			headerColor = (app as { header_color?: string | null }).header_color ?? null;
			embedMetadataOnDownload = (app as { embedWorkflowuiMetadataOnDownload?: boolean }).embedWorkflowuiMetadataOnDownload ?? true;
			embedMetadataOnSave = (app as { embedWorkflowuiMetadataOnSave?: boolean }).embedWorkflowuiMetadataOnSave ?? true;
			appDraft = draftFromExistingApp(
				inputKeys,
				outputKeys,
				app.ui_config as import('$lib/types/appBuilder').UIConfig | null,
				app.default_inputs as Record<string, unknown> | null
			);
			draftInitialized = true;
		}
	});

	async function save() {
		if (!appDraft || !slugParam) return;
		const visibleOutputs = Array.from(appDraft.visibleOutputs);
		if (visibleOutputs.length === 0) {
			saveError = 'At least one output must be visible';
			return;
		}
		const trimmedTitle = title.trim();
		if (!trimmedTitle) {
			saveError = 'Title is required';
			return;
		}
		saveError = '';
		saving = true;
		const apiBase = getApiBase() || '';
		try {
			const res = await fetch(`${apiBase}/apps/${slugParam}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					title: trimmedTitle,
					description: description.trim() || undefined,
					is_public: isPublic,
					header_color: headerColor,
					embed_workflowui_metadata_on_download: embedMetadataOnDownload,
					embed_workflowui_metadata_on_save: embedMetadataOnSave,
					ui_config: draftToUIConfig(appDraft),
					default_inputs: draftToDefaultInputs(appDraft),
					supported_input_kinds: supportedInputKinds.length > 0 ? supportedInputKinds : null
				})
			});
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				saveError = (d.detail as string) || res.statusText;
				saving = false;
				return;
			}
			window.location.href = `/app/${slugParam}`;
		} catch (e) {
			saveError = e instanceof Error ? e.message : String(e);
			saving = false;
		}
	}

	async function copyApp() {
		if (!slugParam || copying) return;
		copyError = '';
		copying = true;
		const apiBase = getApiBase() || '';
		try {
			const res = await fetch(`${apiBase}/apps/${slugParam}/copy`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ new_title: `Copy of ${title || slugParam}` })
			});
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				copyError = (d.detail as string) || res.statusText;
				copying = false;
				return;
			}
			const created = await res.json();
			goto(`/apps/${created.slug}/edit`);
		} catch (e) {
			copyError = e instanceof Error ? e.message : 'Failed to copy app';
			copying = false;
		}
	}
</script>

{#if !appData || !app}
	<div class="two-col-page page">
		<div class="panel-left panel-scroll card">
			<h1>Edit App</h1>
			<p>App not found.</p>
			<a href="/workflows">Back to workflows</a>
		</div>
	</div>
{:else}
	<div class="two-col-page page">
		<aside class="panel-left panel-scroll card">
			<h1>Edit App</h1>
			<p class="muted">Slug: {slugParam}</p>

			<section class="section">
				<label class="toggle-label" for="app-public-edit">
					<span class="toggle-wrap">
						<input id="app-public-edit" type="checkbox" bind:checked={isPublic} class="toggle-input" />
						<span class="toggle-track" aria-hidden="true"></span>
					</span>
					<span class="toggle-label-text">Public</span>
				</label>
			</section>
			<section class="section">
				<label for="app-title">Title</label>
				<input id="app-title" type="text" bind:value={title} placeholder="My App" />
			</section>
			<section class="section">
				<span class="field-label">Slug</span>
				<p class="slug-readonly" id="app-slug-readonly">{slugParam}</p>
			</section>
			<section class="section">
				<label for="app-desc">Description</label>
				<textarea id="app-desc" bind:value={description} rows="2" placeholder="Optional"></textarea>
			</section>
			<section class="section">
				<label for="app-header-color-edit" class="field-label">Header color</label>
				<p class="field-help">Optional. Sets the app card header color on the Apps page for quick visual grouping.</p>
				<div class="header-color-wrap">
					<input
						id="app-header-color-edit"
						type="color"
						class="header-color-input"
						value={headerColor ?? '#6d5dfc'}
						oninput={(e) => (headerColor = (e.currentTarget as HTMLInputElement).value)}
						aria-label="Header color"
					/>
					{#if headerColor}
						<button type="button" class="header-color-clear" onclick={() => (headerColor = null)}>Clear</button>
					{/if}
				</div>
			</section>
			<section class="section">
				<p class="field-label">WorkflowUI metadata</p>
				<p class="field-help">When enabled, workflow and app data are embedded so users can restore from the Import page.</p>
				<label class="toggle-label" for="app-embed-download-edit">
					<span class="toggle-wrap">
						<input id="app-embed-download-edit" type="checkbox" bind:checked={embedMetadataOnDownload} class="toggle-input" />
						<span class="toggle-track" aria-hidden="true"></span>
					</span>
					<span class="toggle-label-text">Embed metadata when user downloads images</span>
				</label>
				<label class="toggle-label" for="app-embed-save-edit">
					<span class="toggle-wrap">
						<input id="app-embed-save-edit" type="checkbox" bind:checked={embedMetadataOnSave} class="toggle-input" />
						<span class="toggle-track" aria-hidden="true"></span>
					</span>
					<span class="toggle-label-text">Embed metadata when saving to local storage</span>
				</label>
			</section>
			<section class="section">
				<span class="field-label">Send-to-App: accepted input types</span>
				<p class="field-help">When someone uses "Send to App" from a run output, only apps that accept that media type are shown. Leave all unchecked to accept any type.</p>
				<div class="supported-kinds-wrap">
					{#each SUPPORTED_KIND_OPTIONS as kind}
						<label class="toggle-label supported-kind-label">
							<span class="toggle-wrap">
								<input
									type="checkbox"
									class="toggle-input"
									checked={supportedInputKinds.includes(kind)}
									onchange={(e) => {
										const checked = (e.currentTarget as HTMLInputElement).checked;
										if (checked) supportedInputKinds = [...supportedInputKinds, kind];
										else supportedInputKinds = supportedInputKinds.filter((k) => k !== kind);
									}}
								/>
								<span class="toggle-track" aria-hidden="true"></span>
							</span>
							<span class="toggle-label-text">{kind}</span>
						</label>
					{/each}
				</div>
			</section>
			{#if appDraft}
				<section class="section">
					<label class="toggle-label" for="app-ignore-load-image-default">
						<span class="toggle-wrap">
							<input
								id="app-ignore-load-image-default"
								type="checkbox"
								checked={appDraft.ignoreLoadImageDefault}
								onchange={(e) => setIgnoreLoadImageDefault(appDraft!, (e.currentTarget as HTMLInputElement).checked)}
								class="toggle-input"
							/>
							<span class="toggle-track" aria-hidden="true"></span>
						</span>
						<span class="toggle-label-text">Never preset Load Image</span>
					</label>
					<p class="field-help">
						When on, the run form never shows the image from the workflow. The image field starts empty so users always choose or upload an image.
					</p>
				</section>
			{/if}
			{#if appDraft && visibleSeedInputs.length > 0}
				<section class="section">
					<label for="master-seed-select" class="field-label">Master seed for generation</label>
					<p class="master-seed-help">
						Only this seed is changed by &quot;Queue for generation (N×)&quot; and &quot;Random seed (N×)&quot;. Other seed fields keep their form values.
					</p>
					<select
						id="master-seed-select"
						class="master-seed-select"
						value={appDraft.masterSeedInputKey ?? ''}
						onchange={(e) => {
							const v = (e.currentTarget as HTMLSelectElement).value;
							setMasterSeedInputKey(appDraft!, v != null && v.trim() !== '' ? v.trim() : null);
						}}
					>
						<option value="">— First seed input (default) —</option>
						{#each visibleSeedInputs as seedInput}
							<option value={seedInput.key!}>{seedInput.label ?? seedInput.key}</option>
						{/each}
					</select>
				</section>
			{/if}
			{#if saveError}
				<p class="error-text">{saveError}</p>
			{/if}
			{#if copyError}
				<p class="error-text">{copyError}</p>
			{/if}
			<section class="section">
				<span class="field-label">Workflow export</span>
				<p class="field-help">Download the workflow JSON with this app's default values applied. You can import this file directly in ComfyUI (Load or drag-and-drop).</p>
				<button
					type="button"
					class="download-workflow-btn"
					disabled={downloadingWorkflow}
					onclick={downloadAppWorkflowWithDefaults}
				>
					{downloadingWorkflow ? 'Downloading…' : 'Download workflow with app defaults'}
				</button>
			</section>
			<section class="section sticky-save">
				<button onclick={save} disabled={saving}>{saving ? 'Saving…' : 'Save'}</button>
				<button type="button" class="cancel-btn" onclick={() => goto('/apps')}>Cancel</button>
				<button type="button" class="cancel-btn" onclick={copyApp} disabled={copying}>{copying ? 'Copying…' : 'Copy app'}</button>
			</section>
		</aside>

		<div class="panel-right panel-scroll card">
			{#if internalNodes.length > 0}
				<p class="internal-nodes-hint" role="status">
					Detected in workflow (no configurable input or output): {internalNodes.map((n: { label: string }) => n.label).join(', ')}
				</p>
			{/if}
			<div class="tabs-row">
				<div class="tabs">
					<button
						class="tab"
						class:active={activeTab === 'inputs'}
						onclick={() => (activeTab = 'inputs')}
					>Inputs</button>
					<button
						class="tab"
						class:active={activeTab === 'outputs'}
						onclick={() => (activeTab = 'outputs')}
					>Outputs</button>
				</div>
				<div class="visibility-filter" role="group" aria-label="Show">
					<button
						type="button"
						class="visibility-btn"
						class:active={visibilityFilter === 'all'}
						onclick={() => (visibilityFilter = 'all')}
						title="Show all"
					>All</button>
					<button
						type="button"
						class="visibility-btn"
						class:active={visibilityFilter === 'visible'}
						onclick={() => (visibilityFilter = 'visible')}
						title="Show only visible (displayed) elements"
					>Visible</button>
					<button
						type="button"
						class="visibility-btn"
						class:active={visibilityFilter === 'hidden'}
						onclick={() => (visibilityFilter = 'hidden')}
						title="Show only hidden elements"
					>Hidden</button>
				</div>
				<input
					type="search"
					class="filter-input"
					placeholder="Filter by key, label, ComfyUI title…"
					bind:value={filterQuery}
					aria-label="Filter inputs and outputs"
				/>
			</div>
			{#if activeTab === 'inputs' && appDraft}
				<div class="tab-content">
					{#each inputGroups as group (group.nodeId)}
						{#if true}
							{@const nodeLabel = group.metaTitle ?? group.parent ?? group.classType ?? group.nodeId}
							{@const nodeInputKeys = group.inputs.map((i: { key?: string }) => i.key).filter(Boolean) as string[]}
							<div class="node-group" data-node-id={group.nodeId}>
							<div class="node-group-header">
								<span class="node-group-title" title="Node {group.nodeId}">
									<span class="node-group-badge">Node {group.nodeId}</span>
									{#if nodeLabel}
										<span class="node-group-label">{nodeLabel}</span>
									{/if}
								</span>
								<div class="node-group-actions">
									{#if nodeInputKeys.length > 0}
										<button
											type="button"
											class="order-btn node-visibility-btn"
											title="Show all fields for this node in the app form"
											onclick={() => selectAllInputsInNode(nodeInputKeys)}
										>Select all</button>
										<button
											type="button"
											class="order-btn node-visibility-btn"
											title="Hide all fields for this node from the app form"
											onclick={() => deselectAllInputsInNode(nodeInputKeys)}
										>Deselect all</button>
									{/if}
									<button
										type="button"
										class="order-btn"
										title="Move node up in render order"
										onclick={() => {
											moveInputNodeOrder(appDraft!, group.nodeId, 'up');
											appDraft = { ...appDraft!, inputNodeOrder: [...appDraft!.inputNodeOrder] };
										}}
									>↑</button>
									<button
										type="button"
										class="order-btn"
										title="Move node down in render order"
										onclick={() => {
											moveInputNodeOrder(appDraft!, group.nodeId, 'down');
											appDraft = { ...appDraft!, inputNodeOrder: [...appDraft!.inputNodeOrder] };
										}}
									>↓</button>
								</div>
							</div>
							<div class="node-group-fields">
								{#each group.inputs as input (input.key)}
									{#if input.key}
										<FieldCard
											fieldKey={input.key}
											field={input.field}
											label={input.label ?? input.key}
											type={input.type}
											defaultValue={input.default}
											metaTitle={input.metaTitle ?? null}
											visible={appDraft.visibleInputs.has(input.key)}
											defaultOverride={appDraft.defaultOverrides.get(input.key)}
											override={appDraft.inputOverrides.get(input.key) ?? null}
											availableLoras={availableLoras}
											availableCheckpoints={availableCheckpoints}
											availableClipModels={availableClipModels}
											availableClipTypes={availableClipTypes}
											availableVaeModels={availableVaeModels}
											availableDevices={availableDevices}
											optionSource={input.optionSource ?? ''}
											onVisibleChange={(v) => setInputVisible(appDraft!, input.key, v)}
											onDefaultOverrideChange={(v) => {
												setDefaultOverride(appDraft!, input.key, v);
												appDraft = { ...appDraft!, defaultOverrides: new Map(appDraft!.defaultOverrides) };
											}}
											onOverrideChange={(o) => setInputOverride(appDraft!, input.key, o)}
										/>
									{/if}
								{/each}
							</div>
							</div>
						{/if}
					{/each}
				</div>
			{:else if activeTab === 'outputs' && appDraft}
				<div class="tab-content">
					{#each sortedOutputs as output (output.nodeId)}
						{#if output.nodeId}
							<div class="output-node-wrap" data-node-id={output.nodeId}>
								<div class="output-node-header">
									<span class="node-group-badge">Node {output.nodeId}</span>
									<div class="output-node-actions">
										<button
											type="button"
											class="order-btn"
											title="Move output up in render order"
											onclick={() => {
												moveOutputNodeOrder(appDraft!, output.nodeId, 'up');
												appDraft = { ...appDraft!, outputNodeOrder: [...appDraft!.outputNodeOrder] };
											}}
										>↑</button>
										<button
											type="button"
											class="order-btn"
											title="Move output down in render order"
											onclick={() => {
												moveOutputNodeOrder(appDraft!, output.nodeId, 'down');
												appDraft = { ...appDraft!, outputNodeOrder: [...appDraft!.outputNodeOrder] };
											}}
										>↓</button>
									</div>
								</div>
								<OutputCard
									outputId={output.nodeId}
									label={output.label}
									type={output.type}
									metaTitle={output.metaTitle ?? null}
									visible={appDraft.visibleOutputs.has(output.nodeId)}
									primary={appDraft.primaryOutput === output.nodeId}
									canBePrimary={appDraft.visibleOutputs.has(output.nodeId)}
									customName={appDraft.outputLabels.get(output.nodeId) ?? ''}
									onVisibleChange={(v) => setOutputVisible(appDraft!, output.nodeId, v)}
									onPrimaryChange={() => setPrimaryOutput(appDraft!, output.nodeId)}
									onCustomNameChange={(name) => setOutputLabel(appDraft!, output.nodeId, name)}
								/>
							</div>
						{/if}
					{/each}
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.muted {
		color: var(--muted);
		font-size: 0.9rem;
		margin-bottom: 1rem;
	}
	.internal-nodes-hint {
		font-size: 0.85rem;
		color: var(--muted);
		margin: 0 0 0.75rem 0;
		padding: 0.5rem 0.75rem;
		background: rgba(255, 255, 255, 0.04);
		border-radius: 8px;
		border: 1px solid var(--border);
	}
	.field-label {
		display: block;
		margin-bottom: 0.35rem;
		font-size: 0.9rem;
	}
	.slug-readonly {
		font-family: ui-monospace, monospace;
		font-size: 0.9rem;
		color: var(--muted);
		margin: 0;
	}
	.section {
		margin-bottom: 1.25rem;
	}
	.supported-kinds-wrap {
		display: flex;
		flex-wrap: wrap;
		gap: 0.75rem 1.25rem;
		margin-top: 0.35rem;
	}
	.supported-kind-label {
		text-transform: capitalize;
	}
	.field-help,
	.master-seed-help {
		font-size: 0.8rem;
		color: var(--muted);
		margin: 0 0 0.5rem 0;
		line-height: 1.35;
	}
	.master-seed-select {
		width: 100%;
		max-width: 20rem;
		padding: 0.4rem 0.5rem;
		font-size: 0.9rem;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--surface);
		color: var(--text);
	}
	.header-color-wrap {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.35rem;
	}
	.header-color-input {
		width: 2.5rem;
		height: 2.25rem;
		padding: 2px;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--surface);
		cursor: pointer;
	}
	.header-color-clear {
		padding: 0.35rem 0.6rem;
		font-size: 0.85rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		color: var(--muted);
		cursor: pointer;
	}
	.header-color-clear:hover {
		color: var(--text);
		border-color: var(--accent);
	}
	.toggle-label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		user-select: none;
	}
	.toggle-wrap {
		display: flex;
		align-items: center;
		flex-shrink: 0;
	}
	.toggle-input {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}
	.toggle-track {
		position: relative;
		width: 32px;
		height: 18px;
		background: var(--border);
		border-radius: 999px;
		transition: background 0.2s ease;
	}
	.toggle-track::before {
		content: '';
		position: absolute;
		top: 2px;
		left: 2px;
		width: 14px;
		height: 14px;
		background: white;
		border-radius: 50%;
		transition: transform 0.2s ease;
	}
	.toggle-input:checked + .toggle-track {
		background: var(--accent);
	}
	.toggle-input:checked + .toggle-track::before {
		transform: translateX(14px);
	}
	.toggle-label-text {
		font-weight: 500;
	}
	.error-text {
		color: var(--warning);
		font-size: 0.9rem;
		margin-bottom: 0.5rem;
	}
	.sticky-save {
		margin-top: auto;
		padding-top: 1rem;
	}
	.sticky-save .cancel-btn {
		margin-left: 1rem;
		font-size: 0.9rem;
		padding: 0.4rem 0.75rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		color: var(--muted);
		cursor: pointer;
	}
	.sticky-save .cancel-btn:hover {
		color: var(--text);
		border-color: var(--accent);
	}
	.download-workflow-btn {
		display: inline-block;
		font-size: 0.9rem;
		padding: 0.4rem 0.75rem;
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		border-radius: 8px;
		cursor: pointer;
	}
	.download-workflow-btn:hover:not(:disabled) {
		border-color: var(--accent);
		color: var(--accent);
	}
	.download-workflow-btn:disabled {
		opacity: 0.7;
		cursor: wait;
	}
	.tabs-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 1rem;
		border-bottom: 1px solid var(--border);
		padding-bottom: 0.5rem;
	}
	.tabs {
		display: flex;
		gap: 0.25rem;
	}
	.filter-input {
		flex: 1;
		min-width: 180px;
		padding: 0.4rem 0.6rem;
		font-size: 0.9rem;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--surface);
		color: var(--text);
	}
	.filter-input::placeholder {
		color: var(--muted);
	}
	.filter-input:focus {
		outline: none;
		border-color: var(--accent);
	}
	.visibility-filter {
		display: flex;
		gap: 0.2rem;
	}
	.visibility-btn {
		padding: 0.35rem 0.6rem;
		font-size: 0.8rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		color: var(--muted);
		cursor: pointer;
	}
	.visibility-btn:hover {
		color: var(--text);
		border-color: var(--accent);
	}
	.visibility-btn.active {
		background: var(--accent-soft);
		color: var(--accent);
		border-color: var(--accent);
	}
	.node-group {
		margin-bottom: 1.25rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		overflow: hidden;
		background: var(--surface);
	}
	.node-group-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		background: var(--card);
		border-bottom: 1px solid var(--border);
	}
	.node-group-title {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.85rem;
		min-width: 0;
	}
	.node-group-badge {
		font-family: ui-monospace, monospace;
		font-size: 0.75rem;
		padding: 0.2rem 0.45rem;
		border-radius: 6px;
		background: var(--accent-soft);
		color: var(--accent);
		flex-shrink: 0;
	}
	.node-group-label {
		color: var(--muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.node-group-actions {
		display: flex;
		gap: 0.2rem;
		flex-shrink: 0;
	}
	.node-group-fields {
		padding: 0.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.order-btn {
		padding: 0.25rem 0.5rem;
		font-size: 0.85rem;
		line-height: 1;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 4px;
		color: var(--muted);
		cursor: pointer;
	}
	.order-btn:hover {
		color: var(--accent);
		border-color: var(--accent);
	}
	.output-node-wrap {
		margin-bottom: 0.75rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		overflow: hidden;
		background: var(--surface);
	}
	.output-node-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		padding: 0.35rem 0.75rem;
		background: var(--card);
		border-bottom: 1px solid var(--border);
	}
	.output-node-actions {
		display: flex;
		gap: 0.2rem;
	}
	.output-node-wrap .output-card {
		border-radius: 0;
		border-left: none;
		border-right: none;
		border-bottom: none;
		margin-bottom: 0;
	}
	.tab {
		padding: 0.5rem 1rem;
		background: none;
		border: none;
		border-bottom: 2px solid transparent;
		margin-bottom: -1px;
		cursor: pointer;
		color: var(--muted);
	}
	.tab:hover {
		color: var(--text);
	}
	.tab.active {
		color: var(--accent);
		border-bottom-color: var(--accent);
	}
	.tab-content {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}
</style>
