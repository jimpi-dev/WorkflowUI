<script lang="ts">
	import { tick } from 'svelte';

	let {
		values = $bindable({}),
		formId = '',
		onSubmit = undefined,
		onQueueClick,
		onRandomClick,
		masterSeedHint = null,
		showActions = true
	}: {
		values?: Record<string, any>;
		formId?: string;
		onSubmit?: (() => void);
		onQueueClick: () => void;
		onRandomClick: () => void;
		masterSeedHint?: string | null;
		showActions?: boolean;
	} = $props();

	values.runs ??= 1;
	let sliderVal = $state(Number(values.runs) || 1);
	$effect(() => {
		const v = Number(values.runs) || 1;
		if (v >= 1 && v <= 200) sliderVal = v;
	});

	function onSliderInput(e: Event) {
		const v = Math.min(200, Math.max(1, Number((e.currentTarget as HTMLInputElement).value) || 1));
		values.runs = v;
		sliderVal = v;
	}

	function submitForm() {
		const form = document.getElementById(formId) as HTMLFormElement | null;
		if (form) form.requestSubmit();
	}

	function triggerSubmit() {
		const run = () => {
			if (onSubmit) onSubmit();
			else submitForm();
		};
		requestAnimationFrame ? requestAnimationFrame(() => run()) : run();
	}

	async function submitWithRandomSeed() {
		onRandomClick();
		await tick();
		triggerSubmit();
	}

	let touchHandled = false;
	function handleQueueTap() {
		if (touchHandled) return;
		touchHandled = true;
		onQueueClick();
		triggerSubmit();
		setTimeout(() => { touchHandled = false; }, 300);
	}
	async function handleRandomTap() {
		if (touchHandled) return;
		touchHandled = true;
		setTimeout(() => { touchHandled = false; }, 300);
		await submitWithRandomSeed();
	}

</script>

<div class="run-param-group" role="group" aria-label="Run parameter">
	<div class="run-param-header">Run Parameter</div>
	<div class="run-param-content">
		<div class="run-param-slider">
			<label for="runs-slider">Runs</label>
			<input
				id="runs-slider"
				type="range"
				min="1"
				max="200"
				value={sliderVal}
				oninput={onSliderInput}
			/>
		</div>
		{#if masterSeedHint}
			<p class="run-param-master-seed-hint" role="note">
				Only the seed <strong>{masterSeedHint}</strong> is changed by the buttons below; other seed fields keep their values.
			</p>
		{/if}
		<div class="run-param-row" role="group" aria-label="Run actions">
			<input
				type="number"
				min="1"
				max="200"
				value={sliderVal}
				oninput={(e) => {
					const v = Math.min(200, Math.max(1, Number((e.currentTarget as HTMLInputElement).value) || 1));
					sliderVal = v;
					values.runs = v;
				}}
				class="run-param-input"
			/>
			{#if showActions}
				<div class="run-param-buttons-wrap">
					<button
						type="button"
						class="run-param-trigger-btn"
						data-run-action="queue"
						onclick={handleQueueTap}
					>
						Queue for generation ({sliderVal}x)
					</button>
					<button
						type="button"
						class="run-param-trigger-btn secondary"
						data-run-action="random"
						onclick={() => handleRandomTap()}
						title="Generate with a random seed"
					>
						🎲 Random seed ({sliderVal}x)
					</button>
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.run-param-group {
		display: flex;
		flex-direction: column;
		gap: 0;
		min-width: 0;
		border: 1px solid var(--border);
		border-radius: 12px;
		overflow: hidden;
		background: rgba(0, 0, 0, 0.2);
		flex-shrink: 0;
		touch-action: manipulation;
		position: relative;
		z-index: 1;
	}

	.run-param-header {
		font-weight: 600;
		opacity: 0.9;
		font-size: 0.85rem;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		padding: 0.75rem 1rem;
		background: rgba(0, 0, 0, 0.15);
		border-bottom: 1px solid var(--border);
	}

	.run-param-content {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		padding: 1rem;
	}

	.run-param-slider {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.run-param-slider label {
		font-size: 0.8rem;
		color: var(--muted);
		margin: 0;
	}

	.run-param-master-seed-hint {
		font-size: 0.8rem;
		color: var(--muted);
		margin: 0 0 0.25rem 0;
		line-height: 1.35;
	}

	.run-param-row {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		flex-wrap: wrap;
	}

	.run-param-buttons-wrap {
		display: flex;
		gap: 0.75rem;
		align-items: center;
		flex: 1;
		min-width: 0;
	}

	.run-param-input {
		width: 4.5rem;
		flex-shrink: 0;
	}

	.run-param-row button {
		flex: 1;
		min-width: 0;
		touch-action: manipulation;
		-webkit-tap-highlight-color: transparent;
		cursor: pointer;
	}
	@media (hover: hover) and (pointer: fine) {
		.run-param-row button:hover {
			opacity: 0.95;
		}
	}
	@media (max-width: 639px) {
		.run-param-row {
			flex-direction: column;
			align-items: stretch;
		}
		.run-param-row button {
			min-height: 44px;
		}
	}
</style>
