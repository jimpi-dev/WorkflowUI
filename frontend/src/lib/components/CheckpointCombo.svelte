<script lang="ts">
    import { tick, onDestroy } from 'svelte';
    import { getApiBase } from '$lib/config';
    import type { WorkflowInput } from '$lib/workflow-analyzer/types';
    import { checkpointComboOpen } from '$lib/stores/loraEdit';
    import { createCheckpointDropdownBody } from '$lib/components/loraDropdownBody';

    export let input: WorkflowInput;
    export let values: Record<string, any>;
    export let availableCheckpoints: string[] = [];

    let editingCheckpoint = false;
    let filterQuery = '';
    let comboEl: HTMLDivElement;
    let filterInputEl: HTMLInputElement;
    let hiddenInputEl: HTMLInputElement;
    let hiddenInputSet = false;
    $: if (input && hiddenInputEl && !hiddenInputSet) {
        hiddenInputEl.value = (values[input.key] ?? '') || '';
        hiddenInputSet = true;
    }
    const dropdownBody = createCheckpointDropdownBody();
    onDestroy(() => dropdownBody.unmount());

    let fetchedOnOpen: string[] = [];
    let loadingCheckpoints = false;

    $: displayName = (() => {
        const raw = input && input.key in values ? values[input.key] : '';
        if (!raw) return 'Select Checkpoint';
        const path = String(raw);
        return path.includes('/')
            ? (path.split('/').pop() ?? path).replace(/\.(safetensors|ckpt)$/i, '')
            : path;
    })();

    function filterItems(items: string[], query: string): string[] {
        const terms = query
            .trim()
            .split(/\s+/)
            .filter(Boolean)
            .map((t) => t.toLowerCase());
        if (!terms.length) return items;
        return items.filter((item) => {
            const pathLower = item.toLowerCase();
            const filename = item.split('/').pop()?.toLowerCase() ?? '';
            return terms.every(
                (term) =>
                    pathLower.includes(term) || filename.includes(term)
            );
        });
    }

    $: currentValue = input && input.key in values && values[input.key]
        ? String(values[input.key]).trim()
        : '';
    $: displayList = (() => {
        const set = new Set<string>();
        if (currentValue) set.add(currentValue);
        for (const c of availableCheckpoints) set.add(c);
        for (const c of fetchedOnOpen) set.add(c);
        return Array.from(set).sort();
    })();
    $: filteredItems = filterItems(displayList, filterQuery);

    function openCombo() {
        if (!input) return;
        editingCheckpoint = true;
        checkpointComboOpen.set(true);
        filterQuery = '';
        fetchedOnOpen = [];
        if (availableCheckpoints.length === 0 && !loadingCheckpoints) {
            loadingCheckpoints = true;
            fetch(`${getApiBase() || ''}/checkpoints`)
                .then((r) => r.json())
                .then((d) => {
                    fetchedOnOpen = d.checkpoints ?? [];
                })
                .catch(() => { fetchedOnOpen = []; })
                .finally(() => { loadingCheckpoints = false; });
        }
        tick().then(() => {
            filterInputEl?.focus();
            if (!comboEl) return;
            const rect = comboEl.getBoundingClientRect();
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
                items: filteredItems,
                onSelect: selectCheckpoint,
                onClose: closeCombo
            });
        });
    }

    $: if (editingCheckpoint && filteredItems.length >= 0) {
        dropdownBody.update(filteredItems);
    }

    function closeCombo() {
        dropdownBody.unmount();
        editingCheckpoint = false;
        checkpointComboOpen.set(false);
        filterQuery = '';
    }

    function selectCheckpoint(path: string) {
        if (input) {
            values[input.key] = path;
            if (hiddenInputEl) hiddenInputEl.value = path;
        }
        closeCombo();
    }

    function handleComboKeydown(e: KeyboardEvent) {
        if (e.key === 'Escape') {
            e.preventDefault();
            closeCombo();
            filterInputEl?.blur();
        }
    }
</script>

{#if input}
    <input type="hidden" data-binding-key={input.key} bind:this={hiddenInputEl} />
    <label class="checkpoint-combo-wrap">
        {#if !input.hideLabel}
            <div class="label">{input.label}</div>
        {/if}
        <div class="checkpoint-combo-inner" bind:this={comboEl}>
            {#if editingCheckpoint}
                <div
                    class="checkpoint-combo"
                    role="combobox"
                    aria-expanded="true"
                    aria-haspopup="listbox"
                    aria-controls="checkpoint-combo-listbox"
                    aria-label="Select Checkpoint"
                >
                    <input
                        bind:this={filterInputEl}
                        type="text"
                        class="checkpoint-combo-input"
                        placeholder="Filter (e.g. SDXL model)..."
                        bind:value={filterQuery}
                        onkeydown={handleComboKeydown}
                    />
                </div>
            {:else}
                <button
                    type="button"
                    class="checkpoint-combo-trigger"
                    title={displayName}
                    onclick={openCombo}
                >
                    {displayName}
                </button>
            {/if}
        </div>
    </label>
{/if}

<style>
    .checkpoint-combo-wrap {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
        min-width: 0;
    }
    .checkpoint-combo-wrap .label {
        font-size: 0.8rem;
        font-weight: 500;
        color: var(--muted);
    }
    .checkpoint-combo-inner {
        min-width: 0;
        position: relative;
    }
    .checkpoint-combo {
        position: relative;
        width: 100%;
        min-width: 0;
    }
    .checkpoint-combo-input {
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
    .checkpoint-combo-input:focus {
        border-color: var(--accent);
        box-shadow: 0 0 0 2px var(--accent-soft);
    }
    .checkpoint-combo-trigger {
        display: block;
        width: 100%;
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
    }
    .checkpoint-combo-trigger:hover {
        background: var(--accent-soft);
        border-color: var(--accent);
        border-bottom-color: var(--accent);
    }
</style>
