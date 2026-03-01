<script lang="ts">
	import { tick, onDestroy } from 'svelte';
	import { getApiBase } from '$lib/config';
	import type { InputOverride } from '$lib/types/appBuilder';
	import { createLoraDropdownBody, createCheckpointDropdownBody, createClipDropdownBody, createVaeDropdownBody } from '$lib/components/loraDropdownBody';

	type Props = {
		fieldKey: string;
		field?: string;
		label: string;
		type?: string;
		defaultValue: unknown;
		visible: boolean;
		defaultOverride: unknown;
		override: InputOverride | null;
		metaTitle?: string | null;
		availableLoras?: string[];
		availableCheckpoints?: string[];
		availableClipModels?: string[];
		availableClipTypes?: string[];
		availableVaeModels?: string[];
		availableDevices?: string[];
		availableRifeModels?: string[];
		availableUnetGgufModels?: string[];
		optionSource?: string;
		onVisibleChange: (visible: boolean) => void;
		onDefaultOverrideChange: (value: unknown) => void;
		onOverrideChange: (override: InputOverride | null) => void;
	};
	let {
		fieldKey,
		field = '',
		label,
		type = 'text',
		defaultValue,
		visible,
		defaultOverride,
		override,
		metaTitle = null,
		availableLoras = [],
		availableCheckpoints = [],
		availableClipModels = [],
		availableClipTypes = [],
		availableVaeModels = [],
		availableDevices = [],
		availableRifeModels = [],
		availableUnetGgufModels = [],
		optionSource = '',
		onVisibleChange,
		onDefaultOverrideChange,
		onOverrideChange
	}: Props = $props();

	const isLoraField = $derived(field?.endsWith('.lora') || field === 'lora_name');
	const isCheckpointField = $derived(field === 'ckpt_name' || field === 'unet_name' || optionSource === 'checkpoints');
	const isClipField = $derived(field === 'clip_name' || optionSource === 'clip_models');
	const isClipTypeField = $derived(optionSource === 'clip_types');
	const isVaeField = $derived(field === 'vae_name' || optionSource === 'vae_models');
	const isDeviceField = $derived(field === 'device' || optionSource === 'devices');
	const isRifeModelsField = $derived(field === 'ckpt_name' && optionSource === 'rife_models');
	const isUnetGgufModelsField = $derived(optionSource === 'unet_gguf_models');

	let expanded = $state(false);
	let localDefaultDisplay = $state('');
	$effect(() => {
		if (defaultOverride !== undefined && defaultOverride !== '') localDefaultDisplay = '';
	});
	const displayDefault = $derived(
		defaultOverride !== undefined && defaultOverride !== '' ? String(defaultOverride) : ''
	);
	const effectiveComboDisplay = $derived(
		(defaultOverride !== undefined && defaultOverride !== '' ? String(defaultOverride) : null) ?? localDefaultDisplay
	);
	const defaultBool = $derived(
		defaultOverride !== undefined && defaultOverride !== ''
			? (defaultOverride === true || defaultOverride === 'true')
			: (defaultValue === true || defaultValue === 'true')
	);
	const defaultNumber = $derived(
		defaultOverride !== undefined && defaultOverride !== '' ? String(defaultOverride) : (defaultValue != null ? String(defaultValue) : '')
	);
	let localLabel = $state(override?.label ?? '');
	let localDesc = $state(override?.description ?? '');
	let localMin = $state(override?.min ?? '');
	let localMax = $state(override?.max ?? '');
	let localStep = $state(override?.step ?? '');

	function commitOverride() {
		const lab = localLabel.trim();
		const desc = localDesc.trim();
		const min = localMin === '' ? undefined : Number(localMin);
		const max = localMax === '' ? undefined : Number(localMax);
		const step = localStep === '' ? undefined : Number(localStep);
		if (lab || desc || min !== undefined || max !== undefined || step !== undefined) {
			onOverrideChange({ label: lab || undefined, description: desc || undefined, min, max, step });
		} else {
			onOverrideChange(null);
		}
	}

	let loraComboOpen = $state(false);
	let loraFilterQuery = $state('');
	let loraComboEl: HTMLDivElement;
	let loraInputEl: HTMLInputElement;
	let fetchedLoras = $state<string[]>([]);
	let loadingLoras = false;
	const dropdownBody = createLoraDropdownBody();
	onDestroy(() => dropdownBody.unmount());

	function filterLoras(loras: string[], query: string): string[] {
		const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
		if (!terms.length) return loras;
		return loras.filter((lora) => {
			const pathLower = lora.toLowerCase();
			const filename = lora.split('/').pop()?.toLowerCase() ?? '';
			return terms.every((t) => pathLower.includes(t) || filename.includes(t));
		});
	}
	const allLoras = $derived((() => {
		const set = new Set<string>();
		if (effectiveComboDisplay && isLoraField) set.add(effectiveComboDisplay);
		availableLoras.forEach((l) => set.add(l));
		fetchedLoras.forEach((l) => set.add(l));
		return Array.from(set).sort();
	})());
	const filteredLoras = $derived(filterLoras(allLoras, loraFilterQuery));

	function openLoraCombo() {
		loraComboOpen = true;
		loraFilterQuery = '';
		if (availableLoras.length === 0 && !loadingLoras) {
			loadingLoras = true;
			fetch(`${getApiBase() || ''}/loras`)
				.then((r) => r.json())
				.then((d: { loras?: string[] }) => { fetchedLoras = d.loras ?? []; })
				.catch(() => { fetchedLoras = []; })
				.finally(() => { loadingLoras = false; });
		}
		tick().then(() => {
			loraInputEl?.focus();
			if (!loraComboEl) return;
			const rect = loraComboEl.getBoundingClientRect();
			const listHeight = 280;
			const gap = 4;
			const spaceBelow = window.innerHeight - (rect.bottom + gap);
			const spaceAbove = rect.top - gap;
			const showAbove = spaceBelow < listHeight && spaceAbove > spaceBelow;
			const left = rect.left;
			const top = showAbove ? Math.max(0, rect.top - listHeight - gap) : rect.bottom + gap;
			const maxH = showAbove ? Math.min(listHeight, spaceAbove) : Math.min(listHeight, spaceBelow);
			const width = Math.max(rect.width, 280);
			dropdownBody.mount({
				left,
				top,
				width,
				maxHeight: maxH,
				items: filteredLoras,
				onSelect: (path) => {
					localDefaultDisplay = path ?? '';
					onDefaultOverrideChange(path || undefined);
					closeLoraCombo();
				},
				onClose: closeLoraCombo
			});
		});
	}
	$effect(() => {
		if (loraComboOpen && filteredLoras.length >= 0) dropdownBody.update(filteredLoras);
	});
	function closeLoraCombo() {
		dropdownBody.unmount();
		loraComboOpen = false;
		loraFilterQuery = '';
	}
	function handleLoraComboKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			closeLoraCombo();
			loraInputEl?.blur();
		}
	}

	let checkpointComboOpen = $state(false);
	let checkpointFilterQuery = $state('');
	let checkpointComboEl: HTMLDivElement;
	let checkpointInputEl: HTMLInputElement;
	let fetchedCheckpoints = $state<string[]>([]);
	let loadingCheckpoints = false;
	const checkpointDropdownBody = createCheckpointDropdownBody();
	onDestroy(() => checkpointDropdownBody.unmount());

	function filterCheckpoints(checkpoints: string[], query: string): string[] {
		const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
		if (!terms.length) return checkpoints;
		return checkpoints.filter((ckpt) => {
			const pathLower = ckpt.toLowerCase();
			const filename = ckpt.split('/').pop()?.toLowerCase() ?? '';
			return terms.every((t) => pathLower.includes(t) || filename.includes(t));
		});
	}
	const allCheckpoints = $derived((() => {
		const set = new Set<string>();
		if (effectiveComboDisplay && isCheckpointField) set.add(effectiveComboDisplay);
		availableCheckpoints.forEach((c) => set.add(c));
		fetchedCheckpoints.forEach((c) => set.add(c));
		return Array.from(set).sort();
	})());
	const filteredCheckpoints = $derived(filterCheckpoints(allCheckpoints, checkpointFilterQuery));

	function openCheckpointCombo() {
		checkpointComboOpen = true;
		checkpointFilterQuery = '';
		if (availableCheckpoints.length === 0 && !loadingCheckpoints) {
			loadingCheckpoints = true;
			fetch(`${getApiBase() || ''}/checkpoints`)
				.then((r) => r.json())
				.then((d: { checkpoints?: string[] }) => { fetchedCheckpoints = d.checkpoints ?? []; })
				.catch(() => { fetchedCheckpoints = []; })
				.finally(() => { loadingCheckpoints = false; });
		}
		tick().then(() => {
			checkpointInputEl?.focus();
			if (!checkpointComboEl) return;
			const rect = checkpointComboEl.getBoundingClientRect();
			const listHeight = 280;
			const gap = 4;
			const spaceBelow = window.innerHeight - (rect.bottom + gap);
			const spaceAbove = rect.top - gap;
			const showAbove = spaceBelow < listHeight && spaceAbove > spaceBelow;
			const left = rect.left;
			const top = showAbove ? Math.max(0, rect.top - listHeight - gap) : rect.bottom + gap;
			const maxH = showAbove ? Math.min(listHeight, spaceAbove) : Math.min(listHeight, spaceBelow);
			const width = Math.max(rect.width, 280);
			checkpointDropdownBody.mount({
				left,
				top,
				width,
				maxHeight: maxH,
				items: filteredCheckpoints,
				onSelect: (path) => {
					localDefaultDisplay = path ?? '';
					onDefaultOverrideChange(path || undefined);
					closeCheckpointCombo();
				},
				onClose: closeCheckpointCombo
			});
		});
	}
	$effect(() => {
		if (checkpointComboOpen && filteredCheckpoints.length >= 0) checkpointDropdownBody.update(filteredCheckpoints);
	});
	function closeCheckpointCombo() {
		checkpointDropdownBody.unmount();
		checkpointComboOpen = false;
		checkpointFilterQuery = '';
	}
	function handleCheckpointComboKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			closeCheckpointCombo();
			checkpointInputEl?.blur();
		}
	}

	let clipComboOpen = $state(false);
	let clipFilterQuery = $state('');
	let clipComboEl: HTMLDivElement;
	let clipInputEl: HTMLInputElement;
	let fetchedClipModels = $state<string[]>([]);
	let loadingClipModels = false;
	const clipDropdownBody = createClipDropdownBody();
	onDestroy(() => clipDropdownBody.unmount());

	function filterClipModels(items: string[], query: string): string[] {
		const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
		if (!terms.length) return items;
		return items.filter((item) => {
			const pathLower = item.toLowerCase();
			const filename = item.split('/').pop()?.toLowerCase() ?? '';
			return terms.every((t) => pathLower.includes(t) || filename.includes(t));
		});
	}
	const allClipModels = $derived((() => {
		const set = new Set<string>();
		if (effectiveComboDisplay && isClipField) set.add(effectiveComboDisplay);
		availableClipModels.forEach((c) => set.add(c));
		fetchedClipModels.forEach((c) => set.add(c));
		return Array.from(set).sort();
	})());
	const filteredClipModels = $derived(filterClipModels(allClipModels, clipFilterQuery));

	function openClipCombo() {
		clipComboOpen = true;
		clipFilterQuery = '';
		if (availableClipModels.length === 0 && !loadingClipModels) {
			loadingClipModels = true;
			fetch(`${getApiBase() || ''}/clip_models`)
				.then((r) => r.json())
				.then((d: { clip_models?: string[] }) => { fetchedClipModels = d.clip_models ?? []; })
				.catch(() => { fetchedClipModels = []; })
				.finally(() => { loadingClipModels = false; });
		}
		tick().then(() => {
			clipInputEl?.focus();
			if (!clipComboEl) return;
			const rect = clipComboEl.getBoundingClientRect();
			const listHeight = 280;
			const gap = 4;
			const spaceBelow = window.innerHeight - (rect.bottom + gap);
			const spaceAbove = rect.top - gap;
			const showAbove = spaceBelow < listHeight && spaceAbove > spaceBelow;
			const left = rect.left;
			const top = showAbove ? Math.max(0, rect.top - listHeight - gap) : rect.bottom + gap;
			const maxH = showAbove ? Math.min(listHeight, spaceAbove) : Math.min(listHeight, spaceBelow);
			const width = Math.max(rect.width, 280);
			clipDropdownBody.mount({
				left,
				top,
				width,
				maxHeight: maxH,
				items: filteredClipModels,
				onSelect: (path) => {
					localDefaultDisplay = path ?? '';
					onDefaultOverrideChange(path || undefined);
					closeClipCombo();
				},
				onClose: closeClipCombo
			});
		});
	}
	$effect(() => {
		if (clipComboOpen && filteredClipModels.length >= 0) clipDropdownBody.update(filteredClipModels);
	});
	function closeClipCombo() {
		clipDropdownBody.unmount();
		clipComboOpen = false;
		clipFilterQuery = '';
	}
	function handleClipComboKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			closeClipCombo();
			clipInputEl?.blur();
		}
	}

	let vaeComboOpen = $state(false);
	let vaeFilterQuery = $state('');
	let vaeComboEl: HTMLDivElement;
	let vaeInputEl: HTMLInputElement;
	let fetchedVaeModels = $state<string[]>([]);
	let loadingVaeModels = false;
	const vaeDropdownBody = createVaeDropdownBody();
	onDestroy(() => vaeDropdownBody.unmount());

	function filterVaeModels(items: string[], query: string): string[] {
		const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
		if (!terms.length) return items;
		return items.filter((item) => {
			const pathLower = item.toLowerCase();
			const filename = item.split('/').pop()?.toLowerCase() ?? '';
			return terms.every((t) => pathLower.includes(t) || filename.includes(t));
		});
	}
	const allVaeModels = $derived((() => {
		const set = new Set<string>();
		if (effectiveComboDisplay && isVaeField) set.add(effectiveComboDisplay);
		availableVaeModels.forEach((c) => set.add(c));
		fetchedVaeModels.forEach((c) => set.add(c));
		return Array.from(set).sort();
	})());
	const filteredVaeModels = $derived(filterVaeModels(allVaeModels, vaeFilterQuery));

	function openVaeCombo() {
		vaeComboOpen = true;
		vaeFilterQuery = '';
		if (availableVaeModels.length === 0 && !loadingVaeModels) {
			loadingVaeModels = true;
			fetch(`${getApiBase() || ''}/vae_models`)
				.then((r) => r.json())
				.then((d: { vae_models?: string[] }) => { fetchedVaeModels = d.vae_models ?? []; })
				.catch(() => { fetchedVaeModels = []; })
				.finally(() => { loadingVaeModels = false; });
		}
		tick().then(() => {
			vaeInputEl?.focus();
			if (!vaeComboEl) return;
			const rect = vaeComboEl.getBoundingClientRect();
			const listHeight = 280;
			const gap = 4;
			const spaceBelow = window.innerHeight - (rect.bottom + gap);
			const spaceAbove = rect.top - gap;
			const showAbove = spaceBelow < listHeight && spaceAbove > spaceBelow;
			const left = rect.left;
			const top = showAbove ? Math.max(0, rect.top - listHeight - gap) : rect.bottom + gap;
			const maxH = showAbove ? Math.min(listHeight, spaceAbove) : Math.min(listHeight, spaceBelow);
			const width = Math.max(rect.width, 280);
			vaeDropdownBody.mount({
				left,
				top,
				width,
				maxHeight: maxH,
				items: filteredVaeModels,
				onSelect: (path) => {
					localDefaultDisplay = path ?? '';
					onDefaultOverrideChange(path || undefined);
					closeVaeCombo();
				},
				onClose: closeVaeCombo
			});
		});
	}
	$effect(() => {
		if (vaeComboOpen && filteredVaeModels.length >= 0) vaeDropdownBody.update(filteredVaeModels);
	});
	function closeVaeCombo() {
		vaeDropdownBody.unmount();
		vaeComboOpen = false;
		vaeFilterQuery = '';
	}
	function handleVaeComboKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			closeVaeCombo();
			vaeInputEl?.blur();
		}
	}
</script>

<article
	class="field-card"
	class:dimmed={!visible}
	class:has-default={defaultOverride !== undefined && defaultOverride !== ''}
	class:has-override={override && Object.keys(override).length > 0}
>
	<div class="field-card-row">
		{#if metaTitle}
			<span class="meta-title-hint" title="Node name set in ComfyUI (helps with multiple nodes of same type)">ComfyUI: {metaTitle}</span>
		{/if}
		<label class="toggle-wrap">
			<input type="checkbox" checked={visible} onchange={(e) => onVisibleChange((e.target as HTMLInputElement).checked)} />
			<span class="field-key">{fieldKey}{#if label} | {label}{/if}</span>
		</label>
		{#if visible}
			<div class="default-override-wrap">
				{#if type === 'boolean'}
					<label class="default-bool-wrap">
						<input
							type="checkbox"
							class="default-input"
							checked={defaultBool}
							onchange={(e) => onDefaultOverrideChange((e.target as HTMLInputElement).checked)}
						/>
						<span>Default</span>
					</label>
				{:else if type === 'number' || type === 'seed'}
					<input
						type="number"
						class="default-input"
						placeholder="Default (optional)"
						value={defaultNumber}
						oninput={(e) => {
							const v = (e.target as HTMLInputElement).value;
							const num = v === '' ? NaN : type === 'seed' ? parseInt(v, 10) : Number(v);
							onDefaultOverrideChange(v === '' || Number.isNaN(num) ? undefined : num);
						}}
					/>
				{:else if isLoraField}
					<div class="default-lora-wrap" bind:this={loraComboEl}>
						{#if loraComboOpen}
							<input
								bind:this={loraInputEl}
								type="text"
								class="default-input lora-combo-input"
								placeholder="Filter (e.g. SDXL loraA)…"
								bind:value={loraFilterQuery}
								onkeydown={handleLoraComboKeydown}
							/>
						{:else}
							<input
								type="text"
								class="default-input"
								placeholder="Default (optional)"
								value={effectiveComboDisplay}
								oninput={(e) => onDefaultOverrideChange((e.target as HTMLInputElement).value || undefined)}
							/>
							<button
								type="button"
								class="lora-select-btn secondary"
								title="Select LoRA from ComfyUI"
								onclick={openLoraCombo}
							>
								Select from ComfyUI
							</button>
						{/if}
					</div>
				{:else if isCheckpointField}
					<div class="default-checkpoint-wrap" bind:this={checkpointComboEl}>
						{#if checkpointComboOpen}
							<input
								bind:this={checkpointInputEl}
								type="text"
								class="default-input checkpoint-combo-input"
								placeholder="Filter (e.g. SDXL model)…"
								bind:value={checkpointFilterQuery}
								onkeydown={handleCheckpointComboKeydown}
							/>
						{:else}
							<input
								type="text"
								class="default-input"
								placeholder="Default (optional)"
								value={effectiveComboDisplay}
								oninput={(e) => onDefaultOverrideChange((e.target as HTMLInputElement).value || undefined)}
							/>
							<button
								type="button"
								class="checkpoint-select-btn secondary"
								title="Select Checkpoint from ComfyUI"
								onclick={openCheckpointCombo}
							>
								Select from ComfyUI
							</button>
						{/if}
					</div>
				{:else if isClipField}
					<div class="default-clip-wrap" bind:this={clipComboEl}>
						{#if clipComboOpen}
							<input
								bind:this={clipInputEl}
								type="text"
								class="default-input clip-combo-input"
								placeholder="Filter (e.g. qwen flux)…"
								bind:value={clipFilterQuery}
								onkeydown={handleClipComboKeydown}
							/>
						{:else}
							<input
								type="text"
								class="default-input"
								placeholder="Default (optional)"
								value={effectiveComboDisplay}
								oninput={(e) => onDefaultOverrideChange((e.target as HTMLInputElement).value || undefined)}
							/>
							<button
								type="button"
								class="clip-select-btn secondary"
								title="Select CLIP model from ComfyUI"
								onclick={openClipCombo}
							>
								Select from ComfyUI
							</button>
						{/if}
					</div>
				{:else if isClipTypeField}
					{#if availableClipTypes.length > 0}
						{@const clipTypeOpts = displayDefault && !availableClipTypes.includes(displayDefault) ? [displayDefault, ...availableClipTypes] : availableClipTypes}
						<select
							class="default-input"
							value={displayDefault}
							onchange={(e) => onDefaultOverrideChange((e.target as HTMLSelectElement).value || undefined)}
						>
							<option value="">Default (optional)</option>
							{#each clipTypeOpts as opt}
								<option value={opt}>{opt}</option>
							{/each}
						</select>
					{:else}
						<input
							type="text"
							class="default-input"
							placeholder="Default (optional)"
							value={displayDefault}
							oninput={(e) => onDefaultOverrideChange((e.target as HTMLInputElement).value || undefined)}
						/>
					{/if}
				{:else if isDeviceField}
					{#if availableDevices.length > 0}
						{@const deviceOpts = displayDefault && !availableDevices.includes(displayDefault) ? [displayDefault, ...availableDevices] : availableDevices}
						<select
							class="default-input"
							value={displayDefault}
							onchange={(e) => onDefaultOverrideChange((e.target as HTMLSelectElement).value || undefined)}
						>
							<option value="">Default (optional)</option>
							{#each deviceOpts as opt}
								<option value={opt}>{opt}</option>
							{/each}
						</select>
					{:else}
						<input
							type="text"
							class="default-input"
							placeholder="Default (optional)"
							value={displayDefault}
							oninput={(e) => onDefaultOverrideChange((e.target as HTMLInputElement).value || undefined)}
						/>
					{/if}
				{:else if isRifeModelsField}
					{#if availableRifeModels.length > 0}
						{@const rifeOpts = displayDefault && !availableRifeModels.includes(displayDefault) ? [displayDefault, ...availableRifeModels] : availableRifeModels}
						<select
							class="default-input"
							value={displayDefault}
							onchange={(e) => onDefaultOverrideChange((e.target as HTMLSelectElement).value || undefined)}
						>
							<option value="">Default (optional)</option>
							{#each rifeOpts as opt}
								<option value={opt}>{opt}</option>
							{/each}
						</select>
					{:else}
						<input
							type="text"
							class="default-input"
							placeholder="Default (optional)"
							value={displayDefault}
							oninput={(e) => onDefaultOverrideChange((e.target as HTMLInputElement).value || undefined)}
						/>
					{/if}
				{:else if isUnetGgufModelsField}
					{#if availableUnetGgufModels.length > 0}
						{@const unetOpts = displayDefault && !availableUnetGgufModels.includes(displayDefault) ? [displayDefault, ...availableUnetGgufModels] : availableUnetGgufModels}
						<select
							class="default-input"
							value={displayDefault}
							onchange={(e) => onDefaultOverrideChange((e.target as HTMLSelectElement).value || undefined)}
						>
							<option value="">Default (optional)</option>
							{#each unetOpts as opt}
								<option value={opt}>{opt}</option>
							{/each}
						</select>
					{:else}
						<input
							type="text"
							class="default-input"
							placeholder="Default (optional)"
							value={displayDefault}
							oninput={(e) => onDefaultOverrideChange((e.target as HTMLInputElement).value || undefined)}
						/>
					{/if}
				{:else if isVaeField}
					<div class="default-vae-wrap" bind:this={vaeComboEl}>
						{#if vaeComboOpen}
							<input
								bind:this={vaeInputEl}
								type="text"
								class="default-input vae-combo-input"
								placeholder="Filter (e.g. ae vae)…"
								bind:value={vaeFilterQuery}
								onkeydown={handleVaeComboKeydown}
							/>
						{:else}
							<input
								type="text"
								class="default-input"
								placeholder="Default (optional)"
								value={effectiveComboDisplay}
								oninput={(e) => onDefaultOverrideChange((e.target as HTMLInputElement).value || undefined)}
							/>
							<button
								type="button"
								class="vae-select-btn secondary"
								title="Select VAE from ComfyUI"
								onclick={openVaeCombo}
							>
								Select from ComfyUI
							</button>
						{/if}
					</div>
				{:else}
					<input
						type="text"
						class="default-input"
						placeholder="Default (optional)"
						value={displayDefault}
						oninput={(e) => onDefaultOverrideChange((e.target as HTMLInputElement).value || undefined)}
					/>
				{/if}
			</div>
		{/if}
		<button
			type="button"
			class="expand-btn secondary"
			onclick={() => (expanded = !expanded)}
			aria-expanded={expanded}
		>
			{expanded ? '− Advanced' : '+ Advanced'}
		</button>
	</div>
	{#if expanded}
		<div class="advanced-section">
			<div class="advanced-row">
				<label for="field-label-{fieldKey}">Label override</label>
				<input id="field-label-{fieldKey}" type="text" bind:value={localLabel} onblur={commitOverride} placeholder={label} />
			</div>
			<div class="advanced-row">
				<label for="field-desc-{fieldKey}">Description</label>
				<input id="field-desc-{fieldKey}" type="text" bind:value={localDesc} onblur={commitOverride} placeholder="Optional" />
			</div>
			{#if type === 'number' || type === 'seed'}
				<div class="advanced-row">
					<span class="minmax-label">Min / Max / Step</span>
					<div class="minmax-row">
						<label for="field-min-{fieldKey}" class="sr-only">Min</label>
						<input id="field-min-{fieldKey}" type="number" bind:value={localMin} onblur={commitOverride} placeholder="min" aria-label="Min" />
						<label for="field-max-{fieldKey}" class="sr-only">Max</label>
						<input id="field-max-{fieldKey}" type="number" bind:value={localMax} onblur={commitOverride} placeholder="max" aria-label="Max" />
						<label for="field-step-{fieldKey}" class="sr-only">Step</label>
						<input id="field-step-{fieldKey}" type="number" bind:value={localStep} onblur={commitOverride} placeholder="step" aria-label="Step" />
					</div>
				</div>
			{/if}
		</div>
	{/if}
</article>

<style>
	.field-card {
		padding: 0.75rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		margin-bottom: 0.5rem;
		background: var(--surface);
	}
	.field-card.dimmed {
		opacity: 0.6;
	}
	.field-card.has-default .field-key::after {
		content: ' • default';
		font-size: 0.75rem;
		color: var(--muted);
		font-weight: normal;
	}
	.field-card.has-override .field-key::after {
		content: ' • custom';
		font-size: 0.75rem;
		color: var(--accent);
		font-weight: normal;
	}
	.field-card-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
	}
	.toggle-wrap {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		min-width: 0;
		flex: 1;
	}
	.toggle-wrap input[type='checkbox'] {
		width: auto;
		flex-shrink: 0;
	}
	.meta-title-hint {
		font-size: 0.75rem;
		color: var(--muted);
		flex-shrink: 0;
		max-width: 14rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.field-key {
		font-family: ui-monospace, monospace;
		font-size: 0.85rem;
		word-break: break-all;
	}
	.default-override-wrap {
		flex: 1;
		min-width: 120px;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.default-override-wrap .default-input {
		flex: 1;
		min-width: 100px;
	}
	.default-bool-wrap {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		cursor: pointer;
		font-size: 0.9rem;
		color: var(--muted);
	}
	.default-bool-wrap input {
		width: auto;
	}
	.default-lora-wrap,
	.default-checkpoint-wrap,
	.default-clip-wrap,
	.default-vae-wrap {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex: 1;
		min-width: 0;
	}
	.default-lora-wrap .lora-combo-input,
	.default-checkpoint-wrap .checkpoint-combo-input,
	.default-clip-wrap .clip-combo-input,
	.default-vae-wrap .vae-combo-input {
		min-width: 140px;
	}
	.lora-select-btn,
	.checkpoint-select-btn,
	.clip-select-btn,
	.vae-select-btn {
		flex-shrink: 0;
		padding: 0.35rem 0.6rem;
		font-size: 0.8rem;
	}
	.default-input {
		width: 100%;
		padding: 0.35rem 0.5rem;
		font-size: 0.9rem;
	}
	.expand-btn {
		padding: 0.35rem 0.6rem;
		font-size: 0.8rem;
	}
	.advanced-section {
		margin-top: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--border);
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.advanced-row label {
		display: block;
		font-size: 0.75rem;
		color: var(--muted);
		margin-bottom: 0.25rem;
	}
	.minmax-label {
		display: block;
		font-size: 0.75rem;
		color: var(--muted);
		margin-bottom: 0.25rem;
	}
	.minmax-row {
		display: flex;
		gap: 0.5rem;
	}
	.minmax-row input {
		width: 5rem;
	}
	.sr-only {
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
</style>
