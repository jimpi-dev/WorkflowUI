<script lang="ts">
	type Props = {
		outputId: string;
		label: string;
		type?: string;
		metaTitle?: string | null;
		visible: boolean;
		primary: boolean;
		canBePrimary: boolean;
		customName: string;
		onVisibleChange: (visible: boolean) => void;
		onPrimaryChange: () => void;
		onCustomNameChange: (name: string) => void;
	};
	let { outputId, label, type = 'image', metaTitle = null, visible, primary, canBePrimary, customName, onVisibleChange, onPrimaryChange, onCustomNameChange }: Props =
		$props();
	const displayLabel = $derived(customName.trim() || label || outputId);
</script>

<article class="output-card" class:dimmed={!visible}>
	<div class="output-card-row">
		{#if metaTitle}
			<span class="meta-title-hint" title="Node name set in ComfyUI (helps with multiple nodes of same type)">ComfyUI: {metaTitle}</span>
		{/if}
		<label class="toggle-wrap">
			<input type="checkbox" checked={visible} onchange={(e) => onVisibleChange((e.target as HTMLInputElement).checked)} />
			<span class="output-id">{outputId}{#if displayLabel} | {displayLabel}{/if}</span>
		</label>
		{#if visible && canBePrimary}
			<label class="primary-wrap">
				<input type="radio" name="primaryOutput" checked={primary} onchange={onPrimaryChange} />
				<span>Primary</span>
			</label>
		{/if}
	</div>
	{#if visible}
		<div class="custom-name-row">
			<label for="output-custom-name-{outputId}">Custom name</label>
			<input
				id="output-custom-name-{outputId}"
				type="text"
				placeholder={label || outputId}
				value={customName}
				oninput={(e) => onCustomNameChange((e.target as HTMLInputElement).value)}
			/>
		</div>
	{/if}
</article>

<style>
	.output-card {
		padding: 0.75rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		margin-bottom: 0.5rem;
		background: var(--surface);
	}
	.output-card.dimmed {
		opacity: 0.6;
	}
	.output-card-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem;
	}
	.toggle-wrap {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		flex: 1;
		min-width: 0;
	}
	.toggle-wrap input[type='checkbox'] {
		width: auto;
		flex-shrink: 0;
	}
	.meta-title-hint {
		font-size: 0.75rem;
		color: var(--muted);
		flex-shrink: 0;
		max-width: 14rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.output-id {
		font-family: ui-monospace, monospace;
		font-size: 0.85rem;
	}
	.primary-wrap {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		cursor: pointer;
		font-size: 0.85rem;
	}
	.custom-name-row {
		margin-top: 0.5rem;
		padding-top: 0.5rem;
		border-top: 1px solid var(--border);
	}
	.custom-name-row label {
		display: block;
		font-size: 0.75rem;
		color: var(--muted);
		margin-bottom: 0.25rem;
	}
	.custom-name-row input {
		width: 100%;
		padding: 0.35rem 0.5rem;
		font-size: 0.9rem;
	}
</style>
