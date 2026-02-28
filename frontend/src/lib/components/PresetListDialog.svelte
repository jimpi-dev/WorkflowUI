<script lang="ts">
	import type { AppPreset } from '$lib/types/presets';

	let {
		open = false,
		presets = [],
		onClose = undefined,
		onSelect = undefined,
		onDelete = undefined,
	}: {
		open?: boolean;
		presets?: AppPreset[];
		onClose?: () => void;
		onSelect?: (presetId: string) => void;
		onDelete?: (presetId: string) => void;
	} = $props();

	function handleSelect(preset: AppPreset) {
		onSelect?.(preset.id);
		onClose?.();
	}

	function handleDelete(e: MouseEvent, preset: AppPreset) {
		e.stopPropagation();
		e.preventDefault();
		if (onDelete && confirm(`Delete preset "${preset.name}"?`)) {
			onDelete(preset.id);
		}
	}

	function handleBackdropClick(e: MouseEvent) {
		if ((e.target as HTMLElement).classList.contains('preset-list-backdrop')) onClose?.();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose?.();
	}
</script>

{#if open}
	<div
		class="preset-list-backdrop"
		role="dialog"
		aria-modal="true"
		aria-label="Load preset"
		tabindex="-1"
		onclick={handleBackdropClick}
		onkeydown={handleKeydown}
	>
		<div class="preset-list-panel" role="document" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
			<div class="preset-list-header">
				<h2 class="preset-list-title">Load preset</h2>
				<button type="button" class="preset-list-close" onclick={onClose} aria-label="Close">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6L6 18M6 6l12 12"/></svg>
				</button>
			</div>
			{#if presets.length === 0}
				<div class="preset-list-empty">
					<p>No presets yet.</p>
					<p class="preset-list-empty-hint">Use the P+ button to create a preset from the current form.</p>
				</div>
			{:else}
				<ul class="preset-list" role="list">
					{#each presets as preset (preset.id)}
						<li class="preset-list-row">
							<button
								type="button"
								class="preset-list-item"
								onclick={() => handleSelect(preset)}
							>
								<span class="preset-list-item-text">
									<span class="preset-list-name">{preset.name}</span>
									{#if preset.description?.trim()}
										<span class="preset-list-desc">{preset.description}</span>
									{/if}
								</span>
							</button>
							{#if onDelete}
								<button
									type="button"
									class="preset-list-delete"
									title="Delete preset"
									aria-label="Delete preset"
									onclick={(e) => handleDelete(e, preset)}
								>
									<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
								</button>
							{/if}
						</li>
					{/each}
				</ul>
			{/if}
		</div>
	</div>
{/if}

<style>
	.preset-list-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}
	.preset-list-panel {
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		max-width: 420px;
		width: 100%;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		box-shadow: var(--shadow-md);
	}
	.preset-list-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.25rem;
		border-bottom: 1px solid var(--border);
	}
	.preset-list-title {
		margin: 0;
		font-size: 1.1rem;
		font-weight: 600;
		color: var(--text);
	}
	.preset-list-close {
		background: none;
		border: none;
		padding: 0.25rem;
		cursor: pointer;
		color: var(--muted);
		border-radius: 6px;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.preset-list-close:hover {
		color: var(--text);
		background: rgba(255, 255, 255, 0.06);
	}
	.preset-list-close svg {
		width: 20px;
		height: 20px;
	}
	.preset-list-empty {
		padding: 2rem 1.25rem;
		text-align: center;
		color: var(--muted);
	}
	.preset-list-empty-hint {
		margin: 0.5rem 0 0;
		font-size: 0.9rem;
	}
	.preset-list {
		list-style: none;
		margin: 0;
		padding: 0.5rem 0;
		overflow-y: auto;
	}
	.preset-list-row {
		list-style: none;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.preset-list-item {
		display: flex;
		flex-direction: row;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		flex: 1;
		min-width: 0;
		padding: 0.75rem 1.25rem;
		background: none;
		border: none;
		color: var(--text);
		text-align: left;
		cursor: pointer;
		font: inherit;
		transition: background 0.15s ease;
	}
	.preset-list-item:hover {
		background: var(--accent-soft);
	}
	.preset-list-item-text {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		min-width: 0;
		flex: 1;
	}
	.preset-list-delete {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2rem;
		height: 2rem;
		padding: 0;
		background: none;
		border: none;
		border-radius: 6px;
		color: var(--muted);
		cursor: pointer;
		transition: color 0.15s ease, background 0.15s ease;
	}
	.preset-list-delete:hover {
		color: #ef4444;
		background: rgba(239, 68, 68, 0.12);
	}
	.preset-list-delete svg {
		width: 18px;
		height: 18px;
	}
	.preset-list-name {
		font-weight: 500;
	}
	.preset-list-desc {
		font-size: 0.85rem;
		color: var(--muted);
		margin-top: 0.2rem;
	}
	@media (max-width: 639px) {
		.preset-list-panel {
			width: calc(100vw - 2rem);
			max-width: none;
			max-height: 85vh;
		}
	}
</style>
