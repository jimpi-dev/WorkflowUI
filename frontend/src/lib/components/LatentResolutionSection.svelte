<script lang="ts">
    import NumberInput from './inputs/NumberInput.svelte';
    import PresetIcon from './PresetIcon.svelte';
    import type { WorkflowInput } from '$lib/workflow-analyzer/types';
    import { LATENT_SIZE_WIDTH_FIELDS, LATENT_SIZE_HEIGHT_FIELDS, LATENT_SIZE_BATCH_FIELD } from '$lib/workflow/nodes/latentSizeBase';

    export let groupInputs: WorkflowInput[];
    export let values: Record<string, any>;
    export let onResolutionChange: (() => void) | undefined = undefined;
    export let presetCreationOn = false;
    export let presetKeysToSave: Set<string> | string[] = [];
    export let onPresetKeyToggle: ((key: string, included: boolean) => void) | undefined = undefined;

    $: selectedPresetKeys = Array.isArray(presetKeysToSave) ? presetKeysToSave : [...presetKeysToSave];

    function presetHasKey(key: string): boolean {
        return selectedPresetKeys.includes(key);
    }

    const isWidthField = (f: string) => (LATENT_SIZE_WIDTH_FIELDS as readonly string[]).includes(f);
    const isHeightField = (f: string) => (LATENT_SIZE_HEIGHT_FIELDS as readonly string[]).includes(f);

    $: widthInput = groupInputs.find((i) => isWidthField(i.field));
    $: heightInput = groupInputs.find((i) => isHeightField(i.field));
    $: batchInput = groupInputs.find((i) => i.field === LATENT_SIZE_BATCH_FIELD);

    function setResolution(w: number, h: number) {
        if (!widthInput || !heightInput) return;
        values[widthInput.key] = w;
        values[heightInput.key] = h;
        onResolutionChange?.();
    }

    function setPortrait() {
        if (!widthInput || !heightInput) return;
        const w = Number(values[widthInput.key]) || 1024;
        const h = Number(values[heightInput.key]) || 1024;
        values[widthInput.key] = Math.min(w, h);
        values[heightInput.key] = Math.max(w, h);
        onResolutionChange?.();
    }

    function setWidescreen() {
        if (!widthInput || !heightInput) return;
        const w = Number(values[widthInput.key]) || 1024;
        const h = Number(values[heightInput.key]) || 1024;
        values[widthInput.key] = Math.max(w, h);
        values[heightInput.key] = Math.min(w, h);
        onResolutionChange?.();
    }

    const RESOLUTION_COMBO_OPTIONS = (() => {
        const set = new Set<string>();
        const add = (w: number, h: number) => set.add(`${w}_${h}`);

        add(512, 512); add(768, 768); add(512, 768); add(768, 512);
        add(1024, 1024); add(832, 1216); add(1216, 832); add(768, 1344); add(1344, 768);
        add(640, 1536); add(1536, 640); add(1152, 896); add(896, 1152);
        add(1280, 1280); add(1280, 720); add(720, 1280);
        add(1920, 1080); add(1080, 1920);
        add(1440, 1440); add(1024, 1280); add(1280, 1024);

        const list = Array.from(set)
            .map((key) => {
                const [w, h] = key.split('_').map(Number);
                return { w, h };
            })
            .sort((a, b) => a.w * a.h - b.w * b.h || a.w - b.w);
        return list;
    })();

    function presetValue(w: number, h: number): string {
        return `${w}_${h}`;
    }

    $: currentW = widthInput && heightInput ? Number(values[widthInput.key]) || 0 : 0;
    $: currentH = widthInput && heightInput ? Number(values[heightInput.key]) || 0 : 0;
    $: selectedPresetValue = (() => {
        const match = RESOLUTION_COMBO_OPTIONS.find((p) => p.w === currentW && p.h === currentH);
        return match ? presetValue(match.w, match.h) : 'custom';
    })();

    function onPresetSelect(e: Event) {
        const val = (e.target as HTMLSelectElement).value;
        if (val === 'custom') return;
        const [ws, hs] = val.split('_');
        const w = Number(ws);
        const h = Number(hs);
        if (!Number.isNaN(w) && !Number.isNaN(h)) setResolution(w, h);
    }
</script>

<div class="latent-resolution-section">
    <div class="resolution-fields">
        {#if widthInput}
            <div class="field-wrap field-wrap-with-preset" data-binding-key={widthInput.key}>
                {#if presetCreationOn && onPresetKeyToggle}
                    <button
                        type="button"
                        class="preset-field-btn"
                        title={presetHasKey(widthInput.key) ? 'Exclude from preset' : 'Include in preset'}
                        aria-pressed={presetHasKey(widthInput.key)}
                        data-preset-selected={presetHasKey(widthInput.key)}
                        onclick={(e) => { e.preventDefault(); e.stopPropagation(); onPresetKeyToggle(widthInput.key, !presetHasKey(widthInput.key)); }}
                    >
                        <PresetIcon variant="p" active={presetHasKey(widthInput.key)} size="sm" />
                    </button>
                {/if}
                <NumberInput input={widthInput} bind:value={values[widthInput.key]} />
            </div>
        {/if}
        {#if heightInput}
            <div class="field-wrap field-wrap-with-preset" data-binding-key={heightInput.key}>
                {#if presetCreationOn && onPresetKeyToggle}
                    <button
                        type="button"
                        class="preset-field-btn"
                        title={presetHasKey(heightInput.key) ? 'Exclude from preset' : 'Include in preset'}
                        aria-pressed={presetHasKey(heightInput.key)}
                        data-preset-selected={presetHasKey(heightInput.key)}
                        onclick={(e) => { e.preventDefault(); e.stopPropagation(); onPresetKeyToggle(heightInput.key, !presetHasKey(heightInput.key)); }}
                    >
                        <PresetIcon variant="p" active={presetHasKey(heightInput.key)} size="sm" />
                    </button>
                {/if}
                <NumberInput input={heightInput} bind:value={values[heightInput.key]} />
            </div>
        {/if}
    </div>

    <div class="shortcuts" role="group" aria-label="Resolution presets">
        <span class="shortcuts-label">Presets</span>
        <div class="preset-row">
            <label class="preset-combo-wrap">
                <select
                    class="preset-combo"
                    aria-label="Resolution preset"
                    value={selectedPresetValue}
                    onchange={onPresetSelect}
                >
                    <option value="custom">Custom {#if currentW && currentH}({currentW}×{currentH}){/if}</option>
                    {#each RESOLUTION_COMBO_OPTIONS as opt}
                        <option value={presetValue(opt.w, opt.h)}>{opt.w}×{opt.h}</option>
                    {/each}
                </select>
            </label>
            <div class="format-shortcuts" role="group" aria-label="Orientation">
                <button
                    type="button"
                    class="format-btn"
                    title="Portrait (swap to height &gt; width)"
                    onclick={setPortrait}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <rect x="7" y="3" width="10" height="18" rx="2"/>
                    </svg>
                </button>
                <button
                    type="button"
                    class="format-btn"
                    title="Widescreen (swap to width &gt; height)"
                    onclick={setWidescreen}
                >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                        <rect x="3" y="7" width="18" height="10" rx="2"/>
                    </svg>
                </button>
            </div>
        </div>
    </div>

    {#if batchInput}
        <div class="batch-row field-wrap-with-preset" data-binding-key={batchInput.key}>
            {#if presetCreationOn && onPresetKeyToggle}
                <button
                    type="button"
                    class="preset-field-btn"
                    title={presetHasKey(batchInput.key) ? 'Exclude from preset' : 'Include in preset'}
                    aria-pressed={presetHasKey(batchInput.key)}
                    data-preset-selected={presetHasKey(batchInput.key)}
                    onclick={(e) => { e.preventDefault(); e.stopPropagation(); onPresetKeyToggle(batchInput.key, !presetHasKey(batchInput.key)); }}
                >
                    <PresetIcon variant="p" active={presetHasKey(batchInput.key)} size="sm" />
                </button>
            {/if}
            <NumberInput input={batchInput} bind:value={values[batchInput.key]} />
        </div>
    {/if}
</div>

<style>
    .latent-resolution-section {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        min-width: 0;
    }

    .resolution-fields {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 1rem;
    }

    .field-wrap {
        min-width: 0;
    }

    .field-wrap-with-preset :global(.number-field) {
        flex: 1;
        min-width: 0;
    }

    .field-wrap-with-preset,
    .batch-row.field-wrap-with-preset {
        display: flex;
        align-items: center;
        gap: 0.35rem;
    }

    .preset-field-btn {
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

    .preset-field-btn[aria-pressed="true"] :global(.preset-icon rect) {
        fill: var(--accent-soft, rgba(109, 93, 252, 0.25)) !important;
        stroke: var(--accent, #6d5dfc) !important;
    }
    .preset-field-btn[aria-pressed="true"] :global(.preset-icon text) {
        fill: var(--accent, #6d5dfc) !important;
    }

    .preset-field-btn:hover {
        color: var(--text);
        background: rgba(255, 255, 255, 0.06);
    }

    .format-shortcuts {
        display: flex;
        gap: 0.5rem;
        align-items: center;
    }

    .format-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 2.5rem;
        height: 2.5rem;
        padding: 0;
        border-radius: 8px;
        background: var(--surface);
        border: 1px solid var(--border);
        color: var(--text);
        cursor: pointer;
        transition: background 0.15s, border-color 0.15s, color 0.15s;
    }

    .format-btn svg {
        width: 1.25rem;
        height: 1.25rem;
    }

    .format-btn:hover {
        background: var(--accent-soft);
        border-color: var(--accent);
        color: var(--accent);
    }

    .format-btn:active {
        background: var(--accent);
        color: white;
        border-color: var(--accent);
    }

    .shortcuts {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .shortcuts-label {
        font-size: 0.7rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 0.25rem;
    }

    .preset-row {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex-wrap: wrap;
        min-width: 0;
    }

    .preset-row .preset-combo-wrap {
        flex: 1;
        min-width: 0;
    }

    .preset-row .preset-combo {
        max-width: none;
    }

    .preset-combo-wrap {
        display: block;
        min-width: 0;
    }

    .preset-combo {
        width: 100%;
        max-width: 20rem;
        padding: 0.5rem 0.6rem;
        font-size: 0.8rem;
        border-radius: 8px;
        background: var(--surface);
        border: 1px solid var(--border);
        color: var(--text);
        cursor: pointer;
    }

    .preset-combo:hover {
        border-color: var(--accent);
    }

    .preset-combo:focus {
        outline: none;
        border-color: var(--accent);
        box-shadow: 0 0 0 2px var(--accent-soft);
    }

    .batch-row {
        min-width: 0;
    }
</style>
