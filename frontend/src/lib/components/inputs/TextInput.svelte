<script lang="ts">
    import { onMount } from 'svelte';

    export let input;
    export let value: string;

    let el: HTMLTextAreaElement;

    function resize() {
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = el.scrollHeight + 'px';
    }

    onMount(() => {
        resize();
    });

    $: value, resize();
</script>

<label class="text-field">
    <div class="label">{input.label}</div>

    <textarea
            bind:this={el}
            bind:value
            rows="3"
            placeholder={input.label}
            oninput={resize}
    ></textarea>
</label>

<style>
    .text-field textarea {
        min-height: 120px;
        font-size: 0.9rem;
        line-height: 1.4;
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