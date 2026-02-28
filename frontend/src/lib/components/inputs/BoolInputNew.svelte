<script lang="ts">
    export let input;
    export let value: boolean;
    export let onchange: (() => void) | undefined = undefined;
</script>

<div class="bool-wrapper">
<label class="switch">
    <input
            type="checkbox"
            bind:checked={value}
            onchange={() => onchange?.()}
    />
    <span class="slider"></span>
    {#if !input.hideLabel}
        <span class="switch-label">
            {input.label}
        </span>
    {/if}
</label>
</div>
<style>
    .switch {
        display: inline-flex;
        align-items: center;
        gap: 0.75rem;
        cursor: pointer;
        user-select: none;
    }

    .switch input {
        display: none;
    }

    .slider {
        position: relative;
        width: 40px;
        height: 22px;
        background: var(--border);
        border-radius: 999px;
        transition: background 0.25s ease;
    }

    .slider::before {
        content: "";
        position: absolute;
        top: 3px;
        left: 3px;

        width: 16px;
        height: 16px;

        background: white;
        border-radius: 50%;

        transition: transform 0.25s ease;
    }

    .switch input:checked + .slider {
        background: var(--accent);
        box-shadow: 0 0 8px var(--accent);
    }

    .switch input:checked + .slider::before {
        transform: translateX(18px);
    }

    .switch-label {
        font-size: 0.9rem;
        color: var(--text);
    }

    .bool-wrapper {
        align-self: center;
    }
</style>