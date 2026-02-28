<script lang="ts">
    import { tick, onDestroy } from 'svelte';
    import { getApiBase } from '$lib/config';
    import type { WorkflowInput } from '$lib/workflow-analyzer/types';
    import { loraComboOpen } from '$lib/stores/loraEdit';
    import { createLoraDropdownBody } from '$lib/components/loraDropdownBody';
    import PresetIcon from '$lib/components/PresetIcon.svelte';

    export let groupInputs: WorkflowInput[] = [];
    export let values: Record<string, any> = {};
    export let onLoraToggle: (() => void) | undefined = undefined;
    export let canEditLoras = false;
    export let availableLoras: string[] = [];
    export let lorasFromWorkflow: string[] = [];
    export let workflowLoraPaths: string[] = [];
    export let canRemove = false;
    export let onRemove: (() => void) | undefined = undefined;
    export let presetCreationOn = false;
    export let presetKeysToSave: Set<string> | string[] = [];
    export let onPresetKeyToggle: ((key: string, included: boolean) => void) | undefined = undefined;

    $: selectedPresetKeys = Array.isArray(presetKeysToSave) ? presetKeysToSave : [...presetKeysToSave];

    function presetHasKey(key: string): boolean {
        return selectedPresetKeys.includes(key);
    }

    $: enabledInput = groupInputs.find((i) => i.field?.endsWith('.on'));
    $: nameInput = groupInputs.find((i) => i.field?.endsWith('.lora'));
    $: strengthInput = groupInputs.find((i) => i.field?.endsWith('.strength'));

    $: enabled =
        enabledInput && enabledInput.key in values
            ? values[enabledInput.key]
            : false;

    $: displayName = (() => {
        const raw = nameInput && nameInput.key in values ? values[nameInput.key] : '';
        if (!raw) return canEditLoras ? 'Select LoRA' : 'Unnamed LoRA';
        return typeof raw === 'string' && raw.includes('/')
            ? (raw.split('/').pop() ?? raw).replace(/\.safetensors$/i, '')
            : String(raw);
    })();

    function filterLoras(loras: string[], query: string): string[] {
        const terms = query
            .trim()
            .split(/\s+/)
            .filter(Boolean)
            .map((t) => t.toLowerCase());
        if (!terms.length) return loras;
        return loras.filter((lora) => {
            const pathLower = lora.toLowerCase();
            const filename = lora.split('/').pop()?.toLowerCase() ?? '';
            return terms.every(
                (term) =>
                    pathLower.includes(term) || filename.includes(term)
            );
        });
    }

    $: strengthValue =
        strengthInput && strengthInput.key in values
            ? Number(values[strengthInput.key]) || 1
            : 1;

    $: strengthMin = strengthInput?.min ?? 0;
    $: strengthMax = strengthInput?.max ?? 2;
    $: strengthStep = (strengthInput as { step?: number })?.step ?? 0.05;

    let expanded = false;
    let editingStrength = false;
    let strengthEditBuffer = '';
    let strengthInputEl: HTMLInputElement;

    let editingLora = false;
    let loraFilterQuery = '';
    let loraComboEl: HTMLDivElement;
    let loraInputEl: HTMLInputElement;
    let loraHiddenInputEl: HTMLInputElement;
    let loraDomValueSet = false;
    $: if (nameInput && loraHiddenInputEl && !loraDomValueSet) {
        loraHiddenInputEl.value = (values[nameInput.key] ?? '') || '';
        loraDomValueSet = true;
    }
    const dropdownBody = createLoraDropdownBody();
    onDestroy(() => dropdownBody.unmount());
    let fetchedLorasOnOpen: string[] = [];
    let loadingLoras = false;

    $: currentLoraValue = nameInput && nameInput.key in values && values[nameInput.key]
        ? String(values[nameInput.key]).trim()
        : '';
    $: displayList = (() => {
        const set = new Set<string>();
        if (currentLoraValue) set.add(currentLoraValue);
        for (const l of workflowLoraPaths) if (l && typeof l === 'string') set.add(l.trim());
        for (const l of lorasFromWorkflow) if (l && typeof l === 'string') set.add(l.trim());
        for (const l of availableLoras) set.add(l);
        for (const l of fetchedLorasOnOpen) set.add(l);
        return Array.from(set).sort();
    })();
    $: filteredLoras = filterLoras(displayList, loraFilterQuery);

    function openLoraCombo() {
        if (!canEditLoras || !nameInput) return;
        editingLora = true;
        loraComboOpen.set(true);
        loraFilterQuery = '';
        fetchedLorasOnOpen = [];
        if (availableLoras.length === 0 && !loadingLoras) {
            loadingLoras = true;
            fetch(`${getApiBase() || ''}/loras`)
                .then((r) => r.json())
                .then((d) => {
                    fetchedLorasOnOpen = d.loras ?? [];
                })
                .catch(() => { fetchedLorasOnOpen = []; })
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
                onSelect: selectLora,
                onClose: closeLoraCombo
            });
        });
    }

    $: if (editingLora && filteredLoras.length >= 0) {
        dropdownBody.update(filteredLoras);
    }

    function closeLoraCombo() {
        dropdownBody.unmount();
        editingLora = false;
        loraComboOpen.set(false);
        loraFilterQuery = '';
    }

    function selectLora(loraPath: string) {
        if (nameInput) {
            values[nameInput.key] = loraPath;
            if (loraHiddenInputEl) {
                loraHiddenInputEl.value = loraPath;
            }
        }
        closeLoraCombo();
    }

    function handleLoraComboKeydown(e: KeyboardEvent) {
        if (e.key === 'Escape') {
            e.preventDefault();
            closeLoraCombo();
            loraInputEl?.blur();
        }
    }

    function handleMouseEnter() {
        if (enabled) expanded = true;
    }

    function handleMouseLeave() {
        expanded = false;
    }

    function handleSliderFocus() {
        if (enabled) expanded = true;
    }

    function handleSliderBlur() {
        expanded = false;
    }

    function startEditStrength() {
        if (!enabled || !strengthInput) return;
        strengthEditBuffer = String(strengthValue);
        editingStrength = true;
        tick().then(() => {
            strengthInputEl?.focus();
            strengthInputEl?.select();
        });
    }

    function clampStrength(val: number): number {
        return Math.min(strengthMax, Math.max(strengthMin, val));
    }

    function commitStrengthEdit() {
        if (!strengthInput) return;
        const parsed = parseFloat(strengthEditBuffer);
        const clamped = Number.isFinite(parsed) ? clampStrength(parsed) : strengthValue;
        values[strengthInput.key] = clamped;
        editingStrength = false;
    }

    function cancelStrengthEdit() {
        strengthEditBuffer = String(strengthValue);
        editingStrength = false;
    }

    function handleStrengthKeydown(e: KeyboardEvent) {
        if (e.key === 'Enter') {
            e.preventDefault();
            commitStrengthEdit();
        } else if (e.key === 'Escape') {
            e.preventDefault();
            cancelStrengthEdit();
            strengthInputEl?.blur();
        }
    }
</script>

<div
    class="lora-slot"
    class:disabled={!enabled}
    class:expanded
    role="group"
    aria-label="LoRA parameter"
    onmouseenter={handleMouseEnter}
    onmouseleave={handleMouseLeave}
>
    {#if nameInput}
        <input type="hidden" data-binding-key={nameInput.key} bind:this={loraHiddenInputEl} />
    {/if}
    <div class="lora-row-main">
        <div class="lora-left">
            {#if enabledInput}
                <label class="lora-toggle-compact">
                    <input
                        type="checkbox"
                        bind:checked={values[enabledInput.key]}
                        onchange={() => onLoraToggle?.()}
                    />
                    <span class="toggle-track"></span>
                </label>
                {#if presetCreationOn && onPresetKeyToggle}
                    <button
                        type="button"
                        class="lora-preset-btn"
                        title={presetHasKey(enabledInput.key) ? 'Exclude from preset' : 'Include in preset'}
                        aria-pressed={presetHasKey(enabledInput.key)}
                        data-preset-selected={presetHasKey(enabledInput.key)}
                        onclick={(e) => { e.preventDefault(); e.stopPropagation(); onPresetKeyToggle(enabledInput.key, !presetHasKey(enabledInput.key)); }}
                    >
                        <PresetIcon variant="p" active={presetHasKey(enabledInput.key)} size="sm" />
                    </button>
                {/if}
            {/if}

            {#if canEditLoras && nameInput}
                <div class="lora-name-wrap" bind:this={loraComboEl}>
                    {#if editingLora}
                        <div
                            class="lora-combo"
                            role="combobox"
                            aria-expanded="true"
                            aria-haspopup="listbox"
                            aria-controls="lora-combo-listbox"
                            aria-label="Select LoRA"
                        >
                            <input
                                bind:this={loraInputEl}
                                type="text"
                                class="lora-combo-input"
                                placeholder="Filter (e.g. SDXL loraA)..."
                                bind:value={loraFilterQuery}
                                onkeydown={handleLoraComboKeydown}
                            />
                        </div>
                    {:else}
                        <button
                            type="button"
                            class="lora-name lora-name-clickable"
                            title={displayName}
                            onclick={openLoraCombo}
                        >
                            {displayName}
                        </button>
                    {/if}
                </div>
                {#if presetCreationOn && onPresetKeyToggle && nameInput}
                    <button
                        type="button"
                        class="lora-preset-btn"
                        title={presetHasKey(nameInput.key) ? 'Exclude from preset' : 'Include in preset'}
                        aria-pressed={presetHasKey(nameInput.key)}
                        data-preset-selected={presetHasKey(nameInput.key)}
                        onclick={(e) => { e.preventDefault(); e.stopPropagation(); onPresetKeyToggle(nameInput.key, !presetHasKey(nameInput.key)); }}
                    >
                        <PresetIcon variant="p" active={presetHasKey(nameInput.key)} size="sm" />
                    </button>
                {/if}
            {:else}
                <div class="lora-name" title={displayName}>
                    {displayName}
                </div>
                {#if presetCreationOn && onPresetKeyToggle && nameInput}
                    <button
                        type="button"
                        class="lora-preset-btn"
                        title={presetHasKey(nameInput.key) ? 'Exclude from preset' : 'Include in preset'}
                        aria-pressed={presetHasKey(nameInput.key)}
                        data-preset-selected={presetHasKey(nameInput.key)}
                        onclick={(e) => { e.preventDefault(); e.stopPropagation(); onPresetKeyToggle(nameInput.key, !presetHasKey(nameInput.key)); }}
                    >
                        <PresetIcon variant="p" active={presetHasKey(nameInput.key)} size="sm" />
                    </button>
                {/if}
            {/if}
        </div>

        <div class="lora-strength-wrapper">
            {#if presetCreationOn && onPresetKeyToggle && strengthInput}
                <button
                    type="button"
                    class="lora-preset-btn"
                    title={presetHasKey(strengthInput.key) ? 'Exclude from preset' : 'Include in preset'}
                    aria-pressed={presetHasKey(strengthInput.key)}
                    data-preset-selected={presetHasKey(strengthInput.key)}
                    onclick={(e) => { e.preventDefault(); e.stopPropagation(); onPresetKeyToggle(strengthInput.key, !presetHasKey(strengthInput.key)); }}
                >
                    <PresetIcon variant="p" active={presetHasKey(strengthInput.key)} size="sm" />
                </button>
            {/if}
            {#if editingStrength}
                <input
                    bind:this={strengthInputEl}
                    type="text"
                    inputmode="decimal"
                    class="lora-strength-input"
                    bind:value={strengthEditBuffer}
                    onblur={commitStrengthEdit}
                    onkeydown={handleStrengthKeydown}
                    aria-label="Strength value"
                />
            {:else}
                <button
                    type="button"
                    class="lora-strength-display"
                    onclick={startEditStrength}
                    disabled={!enabled}
                    aria-label="Edit strength (currently {strengthValue})"
                >
                    Strength: <span class="lora-strength-value">{strengthValue.toFixed(2)}</span>
                </button>
            {/if}
        </div>

        {#if canRemove && onRemove}
            <button
                type="button"
                class="lora-remove"
                title="Remove this LoRA from the current view"
                aria-label="Remove LoRA"
                onclick={(e) => { e.stopPropagation(); onRemove(); }}
            >
                Remove
            </button>
        {/if}
    </div>

    {#if strengthInput && enabled}
        <div
            class="lora-expanded-row"
            class:visible={expanded}
            role="region"
            aria-label="Strength control"
        >
            <input
                type="range"
                class="lora-slider"
                min={strengthMin}
                max={strengthMax}
                step={strengthStep}
                bind:value={values[strengthInput.key]}
                onfocus={handleSliderFocus}
                onblur={handleSliderBlur}
            />
        </div>
    {/if}
</div>

<style>
    .lora-slot {
        display: flex;
        flex-direction: column;
        min-height: 44px;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        border: 1px solid var(--border);
        background: var(--accent-soft);
        transition:
            background 0.12s ease-out,
            border-color 0.15s ease-out,
            box-shadow 0.12s ease-out;
    }

    .lora-slot:hover:not(.disabled) {
        background: var(--accent-soft);
        border-color: var(--accent);
        filter: brightness(1.05);
    }

    .lora-slot.expanded:not(.disabled) {
        background: var(--accent-soft);
        border-color: var(--accent);
        box-shadow: 0 0 0 1px var(--accent);
    }

    .lora-slot.disabled {
        opacity: 0.55;
    }

    .lora-row-main {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        min-height: 44px;
    }

    .lora-left {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        flex: 1;
        min-width: 0;
    }

    .lora-toggle-compact {
        flex-shrink: 0;
        cursor: pointer;
        display: flex;
        align-items: center;
        user-select: none;
    }

    .lora-toggle-compact input {
        display: none;
    }

    .toggle-track {
        position: relative;
        width: 32px;
        height: 18px;
        background: var(--border);
        border-radius: 999px;
        transition: background 0.2s ease;
    }

    .lora-toggle-compact input:checked + .toggle-track {
        background: var(--accent);
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

    .lora-toggle-compact input:checked + .toggle-track::before {
        transform: translateX(14px);
    }

    .lora-name-wrap {
        flex: 1;
        min-width: 0;
        position: relative;
    }

    .lora-name {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-weight: 500;
        font-size: 0.9rem;
    }

    .lora-name-clickable {
        display: block;
        width: 100%;
        text-align: left;
        padding: 0.2rem 0;
        margin: -0.2rem 0;
        font: inherit;
        font-weight: 500;
        color: inherit;
        background: transparent;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        border-bottom: 1px dotted transparent;
        transition: background 0.15s, border-color 0.15s;
    }

    .lora-name-clickable:hover {
        background: var(--accent-soft);
        border-bottom-color: var(--accent);
    }

    .lora-combo {
        position: relative;
        width: 100%;
        min-width: 0;
    }

    .lora-combo-input {
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

    .lora-combo-input:focus {
        border-color: var(--accent);
        box-shadow: 0 0 0 2px var(--accent-soft);
    }

    .lora-strength-wrapper {
        flex-shrink: 0;
        min-width: 5.5rem;
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }

    .lora-preset-btn {
        flex-shrink: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0.2rem;
        background: none;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        color: var(--muted);
    }

    .lora-preset-btn[aria-pressed="true"] :global(.preset-icon rect) {
        fill: var(--accent-soft, rgba(109, 93, 252, 0.25)) !important;
        stroke: var(--accent, #6d5dfc) !important;
    }
    .lora-preset-btn[aria-pressed="true"] :global(.preset-icon text) {
        fill: var(--accent, #6d5dfc) !important;
    }

    .lora-preset-btn:hover {
        color: var(--text);
        background: rgba(255, 255, 255, 0.06);
    }

    .lora-remove {
        flex-shrink: 0;
        padding: 0.2rem 0.5rem;
        font-size: 0.75rem;
        color: var(--muted);
        background: transparent;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        transition: color 0.15s, background 0.15s;
    }

    .lora-remove:hover {
        color: var(--text);
        background: var(--accent-soft);
    }

    .lora-remove:focus-visible {
        outline: none;
        color: var(--text);
        background: var(--accent-soft);
        box-shadow: 0 0 0 1px var(--accent-soft);
    }

    .lora-strength-display {
        display: inline-flex;
        align-items: baseline;
        gap: 0.25rem;
        padding: 0.2rem 0.4rem;
        margin: -0.2rem -0.4rem;
        font-size: 0.8rem;
        color: var(--muted);
        background: transparent;
        border: none;
        border-radius: 4px;
        cursor: text;
        transition: background 0.15s, color 0.15s;
    }

    .lora-strength-display:not(:disabled):hover {
        color: var(--text);
        background: var(--accent-soft);
    }

    .lora-strength-display:not(:disabled):focus-visible {
        outline: none;
        color: var(--text);
        background: var(--accent-soft);
        box-shadow: 0 0 0 1px var(--accent-soft);
    }

    .lora-strength-display:disabled {
        cursor: default;
        opacity: 0.7;
    }

    .lora-strength-value {
        font-variant-numeric: tabular-nums;
        min-width: 2.5rem;
        text-align: right;
        border-bottom: 1px dotted var(--border);
        transition: border-color 0.15s;
    }

    .lora-strength-display:not(:disabled):hover .lora-strength-value {
        border-bottom-color: var(--accent);
    }

    .lora-strength-input {
        width: 4rem;
        padding: 0.2rem 0.4rem;
        font-size: 0.8rem;
        font-variant-numeric: tabular-nums;
        color: var(--text);
        background: var(--accent-soft);
        border: 1px solid var(--accent);
        border-radius: 4px;
        outline: none;
        text-align: right;
        transition: border-color 0.15s, box-shadow 0.15s;
    }

    .lora-strength-input:focus {
        border-color: var(--accent);
        box-shadow: 0 0 0 2px var(--accent-soft);
    }

    .lora-strength-input::selection {
        background: var(--accent-soft);
    }

    .lora-expanded-row {
        padding-left: 12px;
        padding-right: 0;
        padding-top: 0;
        padding-bottom: 0.5rem;
        max-height: 0;
        overflow: hidden;
        opacity: 0;
        transform: translateY(-8px);
        transition:
            max-height 0.2s ease-out,
            opacity 0.18s ease-out,
            transform 0.2s ease-out,
            padding 0.2s ease-out;
    }

    .lora-expanded-row.visible {
        max-height: 48px;
        opacity: 1;
        transform: translateY(0);
        padding-top: 0.35rem;
    }

    .lora-slider {
        width: 100%;
        height: 6px;
        -webkit-appearance: none;
        appearance: none;
        background: var(--border);
        border-radius: 3px;
    }

    .lora-slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: var(--accent);
        cursor: pointer;
        margin-top: -4px;
    }

    .lora-slider::-moz-range-thumb {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: var(--accent);
        cursor: pointer;
        border: none;
    }
</style>
