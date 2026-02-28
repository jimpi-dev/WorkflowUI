<script lang="ts">
    export let input;
    export let value: boolean;
</script>

<label class="bool-input">
    <input
            type="checkbox"
            bind:checked={value}
    />
    <span class="bool-label">
        {input.label}
    </span>
</label>

<style>
    .bool-input {
        display: inline-flex;
        align-items: center;
        gap: 0.6rem;

        cursor: pointer;
        user-select: none;
    }

    .bool-input input[type="checkbox"] {
        width: 16px;
        height: 16px;
        cursor: pointer;
    }

    .bool-label {
        font-size: 0.9rem;
        color: var(--text);
    }

</style>