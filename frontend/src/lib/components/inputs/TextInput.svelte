<script lang="ts">
    import { onMount } from 'svelte';
    import type { WorkflowInput } from '$lib/workflow/types';

    export let input: WorkflowInput;
    export let value: string;

    let el: HTMLTextAreaElement;

    /** false = single-line; true or undefined = textarea (default matches long prompt UX). */
    $: useMultiline = input.multiline !== false;

    function resize() {
        if (!el || !useMultiline) return;
        el.style.height = 'auto';
        el.style.height = el.scrollHeight + 'px';
    }

    onMount(() => {
        resize();
    });

    $: value, useMultiline, resize();
</script>

<label class="text-field">
    <div class="label">{input.label}</div>

    {#if useMultiline}
        <textarea
            bind:this={el}
            bind:value
            rows="3"
            placeholder={input.label}
            oninput={resize}
        ></textarea>
    {:else}
        <input type="text" class="text-input-single" bind:value placeholder={input.label} />
    {/if}
</label>

<style>
    .text-field textarea {
        min-height: 120px;
        font-size: 0.9rem;
        line-height: 1.4;
    }

    .text-input-single {
        width: 100%;
        min-height: 2.25rem;
        padding: 0.45rem 0.6rem;
        font-size: 0.9rem;
        line-height: 1.4;
        border: 1px solid var(--border);
        border-radius: 6px;
        background: var(--bg);
        color: var(--text);
        font: inherit;
        box-sizing: border-box;
    }

    .text-input-single:focus {
        outline: none;
        border-color: var(--accent);
    }

    @media (max-width: 639px) {
        .text-field {
            flex: 0 1 auto;
        }
        .text-field textarea {
            max-height: min(50vh, 320px);
            box-sizing: border-box;
        }
    }
</style>
