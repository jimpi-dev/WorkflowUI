<script lang="ts">
    export let input;
    export let value: string;
</script>

<label>
    {#if !input.hideLabel}
    <div class="label">{input.label}</div>
    {/if} 

    {#if input.options && input.options.length}
        <select bind:value>
            {#each input.options as opt}
                <option value={opt}>{opt}</option>
            {/each}
        </select>

    {:else}
        <select disabled>
            <option>{value}</option>
        </select>
    {/if}
</label>
