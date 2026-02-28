<script lang="ts">
    export let input;
    export let value: number;

    const min = input.min ?? 0;
    const max = input.max ?? 100;
    const step = input.step ?? 1;

    let localValue: number = typeof value === 'number' && !Number.isNaN(value) ? value : (Number(value) || min);
    $: if (value !== undefined && value !== null) {
        const n = Number(value);
        if (!Number.isNaN(n) && n !== localValue) localValue = n;
    }

    function onRangeInput(e: Event) {
        const target = e.currentTarget as HTMLInputElement;
        const n = Number(target.value);
        localValue = n;
        value = n;
    }

    function onNumberInput(e: Event) {
        const target = e.currentTarget as HTMLInputElement;
        const v = target.value;
        const n = v === '' ? min : Number(v);
        localValue = n;
        value = n;
    }
</script>

<label class="number-field">
    <div class="label-row">
        <span class="label">{input.label}</span>
        <span class="value">{localValue}</span>
    </div>

    {#if input.slider !== false}
        <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={localValue}
                on:input={onRangeInput}
        />
    {/if}

    <input
            type="number"
            min={min}
            max={max}
            step={step}
            value={localValue}
            on:input={onNumberInput}
    />
</label>
