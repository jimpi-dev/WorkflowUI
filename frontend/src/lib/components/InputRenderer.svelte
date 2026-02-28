<script lang="ts">
    import { fetchOptionList } from '$lib/optionSources';
    import { NODE_SPECS } from '$lib/workflow/nodes';
    import type { WorkflowInput } from '$lib/workflow-analyzer/types';
    import { loraComboOpen, checkpointComboOpen } from '$lib/stores/loraEdit';
    import { clipComboOpen, vaeComboOpen } from '$lib/stores/clipCombo';

    import TextInput from './inputs/TextInput.svelte';
    import NumberInput from './inputs/NumberInput.svelte';
    import SeedInput from './inputs/SeedInput.svelte';
    import SelectInput from './inputs/SelectInput.svelte';
    import BoolInputNew from './inputs/BoolInputNew.svelte';
    import ImageInput from './inputs/ImageInput.svelte';
    import PresetIcon from './PresetIcon.svelte';
import LoRASection from './LoRASection.svelte';
import LatentResolutionSection from './LatentResolutionSection.svelte';
import CheckpointCombo from './CheckpointCombo.svelte';
import ClipCombo from './ClipCombo.svelte';
import VaeCombo from './VaeCombo.svelte';

    export let inputs: WorkflowInput[];
    export let values: Record<string, any>;
    export let appId: string | null = null;
    export let onLoraToggle: (() => void) | undefined = undefined;
    export let extraLoraSlots: Record<string, string[]> = {};
    export let canEditLoras = false;
    export let onAddLora: ((nodeId: string, groupKey: string) => void) | undefined = undefined;
    export let onRemoveLora: ((nodeId: string, groupKey: string) => void) | undefined = undefined;
    export let workflowLoraPaths: string[] = [];
    export let prefilledFromRun = false;
    export let prefillImageRunId: string | null = null;
    export let prefillImageInputKey: string | null = null;
    export let prefillImageFilename = '';
    export let prefillImageSubfolder = '';
    export let prefillImageType = 'image';
    export let onResolutionChange: (() => void) | undefined = undefined;
    export let masterSeedInputKey: string | undefined = undefined;
    export let presetCreationOn = false;
    export let presetKeysToSave: Set<string> | string[] = [];
    export let onPresetKeyToggle: ((key: string, included: boolean) => void) | undefined = undefined;

    $: selectedPresetKeys = Array.isArray(presetKeysToSave) ? presetKeysToSave : [...presetKeysToSave];

    function presetHasKey(key: string): boolean {
        return selectedPresetKeys.includes(key);
    }

    function groupBy<T>(arr: T[], keyFn: (v: T) => string | undefined) {
        return arr.reduce((acc, item) => {
            const key = keyFn(item) ?? '__default__';
            if (!acc[key]) acc[key] = [];
            acc[key].push(item);
            return acc;
        }, {} as Record<string, T[]>);
    }

    $: parents = groupBy(inputs, i => i.parent);

    $: parentGroups = Object.entries(parents).map(
        ([parentName, nodeInputs]) => {
            const classType = nodeInputs[0]?.classType;
            const spec = classType ? NODE_SPECS[classType] : undefined;

            return {
                parentName,
                nodeInputs,
                template: spec?.template ?? 'default',
                headerBadge: spec?.headerBadge,
                spec
            };
        }
    );

    function buildLayoutGroups(nodeInputs: WorkflowInput[]) {

        const groupedByGroup = groupBy(
            nodeInputs,
            i => i.groupKey ?? '__fixed__'
        );

        const result = [];

        for (const [groupKey, groupInputs] of Object.entries(groupedByGroup)) {

            const hasLayout = groupInputs.some(i => i.layoutRow !== undefined);

            if (!hasLayout) {
                result.push({
                    groupKey,
                    rows: groupInputs.map(i => [i])
                });
                continue;
            }

            const rows = groupBy(
                groupInputs,
                i => String(i.layoutRow ?? 999)
            );

            const sortedRows = Object.entries(rows)
                .sort(([a], [b]) => Number(a) - Number(b))
                .map(([_, rowInputs]) =>
                    rowInputs.sort(
                        (a, b) => (a.layoutCol ?? 0) - (b.layoutCol ?? 0)
                    )
                );

            result.push({
                groupKey,
                rows: sortedRows
            });
        }

        return result;
    }

    function groupLoRASlots(nodeInputs: WorkflowInput[]) {
        const slots: Record<string, WorkflowInput[]> = {};

        for (const input of nodeInputs) {
            const slotKey = input.groupKey ?? '__default__';

            if (!slots[slotKey]) {
                slots[slotKey] = [];
            }

            slots[slotKey].push(input);
        }

        return Object.values(slots);
    }

    function buildSyntheticSlotInputs(
        nodeId: string,
        groupKey: string,
        parentName: string,
        classType: string
    ): WorkflowInput[] {
        return [
            {
                key: `${nodeId}.${groupKey}.on`,
                label: 'Enabled',
                role: 'parameter',
                parent: parentName,
                type: 'boolean',
                hideLabel: true,
                default: true,
                nodeId,
                field: `${groupKey}.on`,
                classType,
                groupKey
            },
            {
                key: `${nodeId}.${groupKey}.lora`,
                label: 'LoRA',
                role: 'parameter',
                parent: parentName,
                type: 'select',
                hideLabel: true,
                default: '',
                nodeId,
                field: `${groupKey}.lora`,
                classType,
                groupKey
            },
            {
                key: `${nodeId}.${groupKey}.strength`,
                label: 'Strength',
                role: 'parameter',
                parent: parentName,
                type: 'number',
                hideLabel: false,
                default: 1,
                nodeId,
                field: `${groupKey}.strength`,
                min: 0,
                max: 2,
                step: 0.05,
                classType,
                groupKey
            }
        ];
    }

    function nextLoraGroupKey(nodeInputs: WorkflowInput[], extraKeys: string[]): string {
        const fromWorkflow = nodeInputs
            .map((i) => i.groupKey)
            .filter((k): k is string => /^lora_\d+$/.test(k ?? ''));
        const allKeys = [...new Set([...fromWorkflow, ...extraKeys])];
        let max = 0;
        for (const k of allKeys) {
            const m = /^lora_(\d+)$/.exec(k);
            if (m) max = Math.max(max, parseInt(m[1], 10));
        }
        return `lora_${max + 1}`;
    }

    function isSlotEnabled(slotInputs: WorkflowInput[]): boolean {
        const enabledInput = slotInputs.find(i => i.field?.endsWith('.on'));
        if (!enabledInput || !(enabledInput.key in values)) return false;
        return values[enabledInput.key] === true;
    }

    let loraViewMode: 'all' | 'active' = 'active';
    let appliedPrefilledLoraView = false;
    $: if (prefilledFromRun && !appliedPrefilledLoraView) {
        appliedPrefilledLoraView = true;
        loraViewMode = 'all';
    }
    $: if (!prefilledFromRun) appliedPrefilledLoraView = false;
    let collapsedGroups = new Set<string>();

    function toggleCollapsed(parentName: string) {
        collapsedGroups = new Set(collapsedGroups);
        if (collapsedGroups.has(parentName)) {
            collapsedGroups.delete(parentName);
        } else {
            collapsedGroups.add(parentName);
        }
    }

    $: loraEnabledKey = inputs
        .filter((i) => i.field?.endsWith('.on'))
        .map((i) => `${i.key}:${values[i.key]}`)
        .join('|');

    $: loraStackData = (() => {
        void loraEnabledKey;
        return parentGroups
            .filter((g) => g.template === 'lora-stack')
            .map((group) => {
                const nodeId = group.nodeInputs[0]?.nodeId ?? '';
                const workflowSlots = groupLoRASlots(group.nodeInputs);
                const extraKeys = extraLoraSlots[nodeId] ?? [];
                const syntheticSlots = extraKeys.map((gk) =>
                    buildSyntheticSlotInputs(
                        nodeId,
                        gk,
                        group.parentName,
                        group.nodeInputs[0]?.classType ?? ''
                    )
                );
                const allSlots = [...workflowSlots, ...syntheticSlots];
                const activeSlots = allSlots.filter((s) => isSlotEnabled(s));
                return {
                    group,
                    nodeId,
                    allSlots,
                    activeSlots,
                    filteredSlots: loraViewMode === 'active' ? activeSlots : allSlots,
                    nextGroupKey: nextLoraGroupKey(group.nodeInputs, extraKeys)
                };
            });
    })();

    let availableLoras: string[] = [];
    let lorasFetchRequested = false;
    $: if (canEditLoras && parentGroups.some((g) => g.template === 'lora-stack') && !lorasFetchRequested) {
        lorasFetchRequested = true;
        fetchOptionList('/loras')
            .then((list) => { availableLoras = list; })
            .catch(() => { availableLoras = []; });
    }
    $: if (!canEditLoras) lorasFetchRequested = false;

    let availableCheckpoints: string[] = [];
    let checkpointsFetchRequested = false;
    $: hasCheckpointInput = inputs.some((i) => i.optionSource === 'checkpoints');
    $: if (hasCheckpointInput && !checkpointsFetchRequested) {
        checkpointsFetchRequested = true;
        fetchOptionList('/checkpoints')
            .then((list) => { availableCheckpoints = list; })
            .catch(() => { availableCheckpoints = []; });
    }

    let availableClipModels: string[] = [];
    let clipModelsFetchRequested = false;
    $: hasClipModelsInput = parentGroups.some(
        (g) => g.spec?.optionSourceForSelect === 'clip_models'
    );
    $: if (hasClipModelsInput && !clipModelsFetchRequested) {
        clipModelsFetchRequested = true;
        fetchOptionList('/clip_models')
            .then((list) => { availableClipModels = list; })
            .catch(() => { availableClipModels = []; });
    }

    let availableVaeModels: string[] = [];
    let vaeModelsFetchRequested = false;
    $: hasVaeModelsInput = inputs.some((i) => i.optionSource === 'vae_models');
    $: if (hasVaeModelsInput && !vaeModelsFetchRequested) {
        vaeModelsFetchRequested = true;
        fetchOptionList('/vae_models')
            .then((list) => { availableVaeModels = list; })
            .catch(() => { availableVaeModels = []; });
    }

    let availableClipTypes: string[] = [];
    let clipTypesFetchRequested = false;
    $: hasClipTypesInput = inputs.some((i) => i.optionSource === 'clip_types');
    $: if (hasClipTypesInput && !clipTypesFetchRequested) {
        clipTypesFetchRequested = true;
        fetchOptionList('/clip_types')
            .then((list) => { availableClipTypes = list; })
            .catch(() => { availableClipTypes = []; });
    }

    $: loraValuesSnapshot = inputs
        .filter((i) => i.field?.endsWith('.lora'))
        .map((i) => (i.key in values ? String(values[i.key] ?? '') : ''))
        .join('\n');
    $: lorasFromWorkflow = (() => {
        void loraValuesSnapshot;
        const out: string[] = [];
        const loraInputs = inputs.filter((i) => i.field?.endsWith('.lora'));
        for (const input of loraInputs) {
            const v = input.key in values ? values[input.key] : undefined;
            if (typeof v === 'string' && v.trim()) out.push(v.trim());
        }
        return [...new Set(out)];
    })();
    $: mergedLorasForCombo = (() => {
        const set = new Set<string>(workflowLoraPaths);
        for (const l of lorasFromWorkflow) set.add(l);
        for (const l of availableLoras) set.add(l);
        return Array.from(set).sort();
    })();
</script>

<div class="form-root" class:checkpoint-combo-open={$checkpointComboOpen} class:clip-combo-open={$clipComboOpen} class:vae-combo-open={$vaeComboOpen}>
    {#each parentGroups as group}

        {#if group.template === 'lora-stack'}
            {@const data = loraStackData.find((d) => d.group === group)}
            {#if data}
            <div class="lora-stack-wrapper" class:collapsed={collapsedGroups.has(group.parentName)} class:lora-combo-open={$loraComboOpen}>
                <div
                    class="lora-stack-header"
                    role="button"
                    tabindex="0"
                    aria-expanded={!collapsedGroups.has(group.parentName)}
                    aria-label={collapsedGroups.has(group.parentName) ? 'Expand group' : 'Collapse group'}
                    onclick={() => toggleCollapsed(group.parentName)}
                    onkeydown={(e) => e.key === 'Enter' && toggleCollapsed(group.parentName)}
                >
                    <div class="lora-stack-header-left">
                        <svg class="collapse-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="6 9 12 15 18 9"/>
                        </svg>
                        <span class="lora-stack-title">
                            {group.parentName}
                            {#if group.headerBadge}
                                <span class="header-badge">{group.headerBadge}</span>
                            {/if}
                        </span>
                    </div>
                    <div
                        class="lora-view-tabs"
                        role="group"
                        aria-label="Filter LoRAs"
                    >
                        <button
                            type="button"
                            class="lora-tab"
                            class:active={loraViewMode === 'all'}
                            onclick={(e) => { e.stopPropagation(); loraViewMode = 'all'; }}
                        >
                            All ({data.allSlots.length})
                        </button>
                        <button
                            type="button"
                            class="lora-tab"
                            class:active={loraViewMode === 'active'}
                            onclick={(e) => { e.stopPropagation(); loraViewMode = 'active'; }}
                        >
                            Active ({data.activeSlots.length})
                        </button>
                        {#if canEditLoras && onAddLora}
                            <button
                                type="button"
                                class="lora-tab lora-tab-add"
                                title="Add new LoRA slot"
                                aria-label="Add LoRA"
                                onclick={(e) => { e.stopPropagation(); onAddLora(data.nodeId, data.nextGroupKey); }}
                            >
                                + Add LoRA
                            </button>
                        {/if}
                    </div>
                </div>

                <div class="lora-stack-content">
                {#if loraViewMode === 'active' && data.activeSlots.length === 0}
                    <p class="lora-empty-hint">
                        No active LoRAs. Switch to All to enable some.
                    </p>
                {:else}
                    {#each data.filteredSlots as slotInputs}
                        {@const groupKey = slotInputs[0]?.groupKey}
                        {@const isExtraSlot = groupKey && (extraLoraSlots[data.nodeId] ?? []).includes(groupKey)}
                        <LoRASection
                            groupInputs={slotInputs}
                            {values}
                            onLoraToggle={onLoraToggle}
                            canEditLoras={canEditLoras}
                            availableLoras={mergedLorasForCombo}
                            lorasFromWorkflow={lorasFromWorkflow}
                            workflowLoraPaths={workflowLoraPaths}
                            canRemove={isExtraSlot && !!onRemoveLora}
                            onRemove={isExtraSlot && onRemoveLora && groupKey ? () => onRemoveLora(data.nodeId, groupKey) : undefined}
                            presetCreationOn={presetCreationOn}
                            presetKeysToSave={presetKeysToSave}
                            onPresetKeyToggle={onPresetKeyToggle}
                        />
                    {/each}
                {/if}
                </div>
            </div>
            {/if}

        {:else if group.template === 'latent-resolution'}
            <div class="node-group-wrapper" class:collapsed={collapsedGroups.has(group.parentName)}>
                <button
                    type="button"
                    class="node-group-header"
                    onclick={() => toggleCollapsed(group.parentName)}
                    aria-expanded={!collapsedGroups.has(group.parentName)}
                    aria-label={collapsedGroups.has(group.parentName) ? 'Expand group' : 'Collapse group'}
                >
                    <svg class="collapse-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"/>
                    </svg>
                    {group.parentName}
                    {#if group.headerBadge}
                        <span class="header-badge">{group.headerBadge}</span>
                    {/if}
                </button>

                <div class="node-group-content">
                    <LatentResolutionSection
                        groupInputs={group.nodeInputs}
                        {values}
                        onResolutionChange={onResolutionChange}
                        presetCreationOn={presetCreationOn}
                        presetKeysToSave={presetKeysToSave}
                        onPresetKeyToggle={onPresetKeyToggle}
                    />
                </div>
            </div>

        {:else}

            <div class="node-group-wrapper" class:collapsed={collapsedGroups.has(group.parentName)}>
                <button
                    type="button"
                    class="node-group-header"
                    onclick={() => toggleCollapsed(group.parentName)}
                    aria-expanded={!collapsedGroups.has(group.parentName)}
                    aria-label={collapsedGroups.has(group.parentName) ? 'Expand group' : 'Collapse group'}
                >
                    <svg class="collapse-chevron" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="6 9 12 15 18 9"/>
                    </svg>
                    {group.parentName}
                    {#if group.headerBadge}
                        <span class="header-badge">{group.headerBadge}</span>
                    {/if}
                </button>

                <div class="node-group-content">
                    {#each buildLayoutGroups(group.nodeInputs) as groupLayout}
                        <div class="group-section">

                            {#each groupLayout.rows as row}
                                <div class="form-row">
                                    {#each row as input (input.key)}
                                        <div class="form-row-cell">
                                        {#if presetCreationOn && onPresetKeyToggle}
                                            <button
                                                type="button"
                                                class="preset-field-btn"
                                                title={presetHasKey(input.key) ? 'Exclude from preset' : 'Include in preset'}
                                                aria-pressed={presetHasKey(input.key)}
                                                data-preset-selected={presetHasKey(input.key)}
                                                onclick={(e) => { e.preventDefault(); e.stopPropagation(); onPresetKeyToggle(input.key, !presetHasKey(input.key)); }}
                                            >
                                                <PresetIcon variant="p" active={presetHasKey(input.key)} size="sm" />
                                            </button>
                                        {/if}
                                        <div class="form-row-input-wrap">
                                        {#if input.type === 'text'}
                                            <TextInput {input} bind:value={values[input.key]} />

                                        {:else if input.type === 'number'}
                                            <NumberInput {input} bind:value={values[input.key]} />

                                        {:else if input.type === 'seed'}
                                            {@const effectiveMasterKey = masterSeedInputKey ?? inputs.find((i) => i.role === 'seed' || i.type === 'seed')?.key}
                                            {@const keyNorm = (k: string | undefined) => (k != null ? String(k).trim() : '')}
                                            <div data-binding-key={input.key}>
                                                <SeedInput
                                                    {input}
                                                    isMasterSeed={keyNorm(input.key) === keyNorm(effectiveMasterKey)}
                                                    value={values[input.key]}
                                                    onValueChange={(v) => {
                                                        values[input.key] = v;
                                                        onResolutionChange?.();
                                                    }}
                                                />
                                            </div>

                                        {:else if input.type === 'select'}
                                            {#if input.optionSource === 'checkpoints'}
                                                <CheckpointCombo
                                                    input={input}
                                                    values={values}
                                                    availableCheckpoints={[...new Set([...(input.options || []), ...availableCheckpoints])].sort()}
                                                />
                                            {:else if input.optionSource === 'clip_models'}
                                                <ClipCombo
                                                    input={input}
                                                    values={values}
                                                    availableClipModels={[...new Set([...(input.options || []), ...availableClipModels])].sort()}
                                                />
                                            {:else if input.optionSource === 'vae_models'}
                                                <VaeCombo
                                                    input={input}
                                                    values={values}
                                                    availableVaeModels={[...new Set([...(input.options || []), ...availableVaeModels])].sort()}
                                                />
                                            {:else if input.optionSource === 'clip_types'}
                                                <SelectInput
                                                    input={{ ...input, options: [...new Set([...(input.options || []), ...availableClipTypes])].sort() }}
                                                    bind:value={values[input.key]}
                                                />
                                            {:else}
                                                <SelectInput {input} bind:value={values[input.key]} />
                                            {/if}

                                        {:else if input.type === 'boolean'}
                                            <BoolInputNew {input} bind:value={values[input.key]} />

                                        {:else if input.type === 'image'}
                                            <ImageInput
                                                {input}
                                                bind:value={values[input.key]}
                                                {appId}
                                                prefillRunId={input.key === prefillImageInputKey ? prefillImageRunId : null}
                                                prefillSubfolder={input.key === prefillImageInputKey ? prefillImageSubfolder : ''}
                                                prefillType={input.key === prefillImageInputKey ? prefillImageType : 'image'}
                                                overrideDisplayValue={input.key === prefillImageInputKey && prefillImageFilename ? prefillImageFilename : undefined}
                                            />

                                        {:else if input.type === 'string' && input.readonly}
                                            <div class="readonly-field">
                                                {values[input.key]}
                                            </div>
                                        {/if}
                                        </div>
                                        </div>
                                    {/each}
                                </div>
                            {/each}

                        </div>
                    {/each}
                </div>
            </div>

        {/if}

    {/each}
</div>

<style>
    .form-root {
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
        min-width: 0;
    }

    .form-root.checkpoint-combo-open,
    .form-root.clip-combo-open,
    .form-root.vae-combo-open {
        overflow: visible;
    }

    .node-group-wrapper {
        display: grid;
        grid-template-rows: auto 1fr;
        min-width: 0;
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
        background: rgba(0, 0, 0, 0.2);
        transition: grid-template-rows 0.2s ease-out;
    }

    .node-group-wrapper.collapsed {
        grid-template-rows: auto 0fr;
    }

    .node-group-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        width: 100%;
        text-align: left;
        font: inherit;
        font-weight: 600;
        opacity: 0.9;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.75rem 1rem;
        background: rgba(0, 0, 0, 0.15);
        border: none;
        border-bottom: 1px solid var(--border);
        color: inherit;
        cursor: pointer;
        transition: background 0.15s ease;
    }

    .node-group-header:hover {
        background: rgba(255, 255, 255, 0.04);
    }

    .node-group-header .collapse-chevron {
        flex-shrink: 0;
        opacity: 0.7;
        transition: transform 0.2s ease;
    }

    .node-group-wrapper.collapsed .node-group-header .collapse-chevron {
        transform: rotate(-90deg);
    }

    .node-group-content {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        padding: 1rem;
        overflow: hidden;
        min-height: 0;
    }

    .node-group-wrapper.collapsed .node-group-content {
        padding: 0;
        margin: 0;
        gap: 0;
        border: none;
        overflow: hidden;
        max-height: 0;
    }

    .header-badge {
        font-size: 0.6rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        padding: 0.2rem 0.45rem;
        border-radius: 999px;
        background: var(--accent);
        color: white;
        opacity: 0.85;
        flex-shrink: 0;
    }

    .group-section {
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
    }

    .form-row-cell {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
        min-width: 0;
    }
	.preset-field-btn {
		flex-shrink: 0;
		background: none;
		border: none;
		padding: 0.2rem;
		cursor: pointer;
		border-radius: 4px;
		color: var(--muted);
		display: flex;
		align-items: center;
		justify-content: center;
		margin-top: 0.15rem;
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
    .form-row-input-wrap {
        flex: 1;
        min-width: 0;
    }
    .form-row {
        display: flex;
        gap: 1rem;
        align-items: flex-start;
    }

    .form-row > * {
        flex: 1;
        min-width: 0; /* verhindert overflow bugs */
    }

    .lora-stack-wrapper {
        display: grid;
        grid-template-rows: auto 1fr;
        min-width: 0;
        border: 1px solid var(--border);
        border-radius: 12px;
        overflow: hidden;
        background: rgba(0, 0, 0, 0.2);
        transition: grid-template-rows 0.2s ease-out;
    }

    .lora-stack-wrapper.collapsed {
        grid-template-rows: auto 0fr;
    }

    .lora-stack-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1rem;
        padding: 0.75rem 1rem;
        background: rgba(0, 0, 0, 0.15);
        border-bottom: 1px solid var(--border);
        cursor: pointer;
        transition: background 0.15s ease;
    }

    .lora-stack-header:hover {
        background: rgba(255, 255, 255, 0.04);
    }

    .lora-stack-header-left {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        flex: 1;
        min-width: 0;
        font-weight: 600;
        opacity: 0.9;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    .lora-stack-header .collapse-chevron {
        flex-shrink: 0;
        opacity: 0.7;
        transition: transform 0.2s ease;
    }

    .lora-stack-wrapper.collapsed .lora-stack-header .collapse-chevron {
        transform: rotate(-90deg);
    }

    .lora-stack-title {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        min-width: 0;
    }

    .lora-stack-title .header-badge {
        margin-left: 0.25rem;
    }

    .lora-stack-content {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        padding: 1rem;
        overflow: hidden;
        min-height: 0;
    }

    .lora-stack-wrapper.lora-combo-open .lora-stack-content {
        overflow: visible;
    }

    .lora-stack-wrapper.collapsed .lora-stack-content {
        padding: 0;
        margin: 0;
        gap: 0;
        border: none;
        overflow: hidden;
        max-height: 0;
    }

    .lora-view-tabs {
        display: flex;
        gap: 0.25rem;
        padding: 0.25rem;
        background: var(--border);
        border-radius: 8px;
        width: fit-content;
    }

    .lora-tab {
        padding: 0.4rem 0.75rem;
        font-size: 0.8rem;
        border-radius: 6px;
        background: transparent;
        color: var(--muted);
        border: none;
        cursor: pointer;
        transition: background 0.15s, color 0.15s;
    }

    .lora-tab:hover {
        color: var(--text);
        background: rgba(255, 255, 255, 0.05);
    }

    .lora-tab.active {
        background: var(--accent);
        color: white;
    }

    .lora-tab-add {
        margin-left: 0.25rem;
        background: var(--accent-soft);
        color: var(--accent);
    }

    .lora-tab-add:hover {
        background: var(--accent);
        color: white;
    }

    .lora-empty-hint {
        font-size: 0.85rem;
        color: var(--muted);
        margin: 0;
        padding: 1rem;
    }

</style>