<script lang="ts">
    import { COMFYUI_MAX_SEED } from '$lib/config';

    export let input;
    export let value: number;
    export let isMasterSeed = false;
    export let onValueChange: ((v: number) => void) | undefined = undefined;

    let localValue = value ?? 0;
    $: if (value !== undefined && value !== null) {
        const num = Number(value);
        if (!Number.isNaN(num) && num !== localValue) localValue = num;
    }

    function randomize() {
        const next = Math.floor(Math.random() * (COMFYUI_MAX_SEED + 1));
        onValueChange?.(next);
        value = next;
        localValue = next;
    }

    function increment(delta: number) {
        const next = Math.max(0, (localValue ?? 0) + delta);
        onValueChange?.(next);
        value = next;
        localValue = next;
    }

    function onInputChange() {
        const n = localValue;
        onValueChange?.(n);
        value = n;
    }
</script>

<label class="seed-field">
    <div class="label-row">
        <div class="label">{input.label}</div>

        <button
                type="button"
                class="info"
                aria-label={`Used by ${input.parent}`}
        >
            ⓘ
            <span class="tooltip">
                Used by <strong>{input.parent}</strong>
            </span>
        </button>
    </div>
    
    <div class="seed-row">
        <input
                type="number"
                min="0"
                bind:value={localValue}
                oninput={onInputChange}
        />

        <button type="button" onmousedown={(e) => { e.preventDefault(); e.stopPropagation(); }} onclick={(e) => { e.stopPropagation(); increment(-1); }} aria-label="Decrement seed">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
        </button>
        <button type="button" onmousedown={(e) => { e.preventDefault(); e.stopPropagation(); }} onclick={(e) => { e.stopPropagation(); increment(1); }} aria-label="Increment seed">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"/>
                <line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
        </button>
        <button type="button" onmousedown={(e) => { e.preventDefault(); e.stopPropagation(); }} onclick={(e) => { e.stopPropagation(); randomize(); }} aria-label="Randomize seed">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="4" y="4" width="16" height="16" rx="2"/>
                <circle cx="8" cy="8" r="1.5" fill="currentColor"/>
                <circle cx="16" cy="8" r="1.5" fill="currentColor"/>
                <circle cx="12" cy="12" r="1.5" fill="currentColor"/>
                <circle cx="8" cy="16" r="1.5" fill="currentColor"/>
                <circle cx="16" cy="16" r="1.5" fill="currentColor"/>
            </svg>
        </button>
    </div>

    {#if localValue === 0}
        <div class="hint">Random seed</div>
    {/if}
    {#if isMasterSeed}
        <div class="hint hint-master">Master seed — changed by run buttons (Queue N× / Random N×)</div>
    {:else}
        <div class="hint hint-fixed">Fixed for this run (not changed by run buttons)</div>
    {/if}
</label>

<style>
    .seed-field {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
    }

    .seed-row {
        display: flex;
        gap: 0.35rem;
        align-items: center;
    }

    .seed-row input {
        flex: 1;
    }

    .seed-row button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        padding: 0;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid var(--border);
        border-radius: 6px;
        color: var(--muted);
        cursor: pointer;
        transition: background 0.15s, color 0.15s, border-color 0.15s;
    }

    .seed-row button:hover {
        background: rgba(255, 255, 255, 0.1);
        color: var(--text);
        border-color: rgba(109, 93, 252, 0.3);
    }

    .hint-master {
        color: var(--accent);
        font-weight: 500;
    }
    .hint-fixed {
        color: var(--muted);
        font-size: 0.75rem;
    }
    .seed-row button:active {
        background: rgba(109, 93, 252, 0.15);
        color: var(--accent);
    }

    .label-row {
        display: flex;
        align-items: center;
        gap: 6px;
    }

    .info {
        position: relative;
        font-size: 0.7rem;
        color: var(--muted);
        cursor: help;
        background: none;
        border: none;
        padding: 0;
        font: inherit;
    }

    .info:focus {
        outline: none;
    }

    .tooltip {
        position: absolute;
        bottom: 140%;
        left: 50%;
        transform: translateX(-50%);

        background: rgba(20,20,20,0.95);
        color: white;
        padding: 6px 8px;
        border-radius: 8px;

        font-size: 0.7rem;
        white-space: nowrap;

        opacity: 0;
        pointer-events: none;
        transition: opacity 0.15s ease;
    }

    .info:hover .tooltip,
    .info:focus .tooltip {
        opacity: 1;
    }

</style>