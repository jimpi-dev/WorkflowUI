<script lang="ts">
	import { tick } from 'svelte';

	let {
		open = false,
		title = 'Confirm deletion',
		message = '',
		confirmLabel = 'Delete',
		showDontAskAgain = true,
		onConfirm = () => {},
		onCancel = () => {}
	}: {
		open?: boolean;
		title?: string;
		message?: string;
		confirmLabel?: string;
		showDontAskAgain?: boolean;
		onConfirm?: (dontShowAgain: boolean) => void | Promise<void>;
		onCancel?: () => void;
	} = $props();

	let dontShowAgain = $state(false);
	let cancelBtn = $state<HTMLButtonElement | null>(null);
	let confirmBtn = $state<HTMLButtonElement | null>(null);
	let dialogEl = $state<HTMLDivElement | null>(null);

	$effect(() => {
		if (!open) return;
		dontShowAgain = false;
		void tick().then(() => cancelBtn?.focus());
	});

	function handleConfirm() {
		const save = dontShowAgain;
		onConfirm(save);
	}

	function handleCancel() {
		onCancel();
	}

	function handleBackdropClick() {
		onCancel();
	}

	function handleDialogKeydown(e: KeyboardEvent) {
		if (!open) return;
		if (e.key === 'Escape') {
			e.preventDefault();
			e.stopPropagation();
			handleCancel();
			return;
		}
		if (e.key === 'Enter' && !e.repeat) {
			const active = document.activeElement;
			if (active === cancelBtn) {
				e.preventDefault();
				e.stopPropagation();
				handleCancel();
				return;
			}
			if (active === confirmBtn || active === dialogEl) {
				e.preventDefault();
				e.stopPropagation();
				handleConfirm();
			}
		}
	}
</script>

{#if open}
	<div
		class="confirm-delete-overlay"
		role="dialog"
		aria-modal="true"
		aria-labelledby="confirm-delete-dialog-title"
		tabindex="-1"
		bind:this={dialogEl}
		onclick={handleBackdropClick}
		onkeydown={handleDialogKeydown}
	>
		<div class="confirm-delete-card" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
			<p id="confirm-delete-dialog-title" class="confirm-delete-title">{title}</p>
			<p class="confirm-delete-msg">{message}</p>
			{#if showDontAskAgain}
				<label class="confirm-delete-checkbox">
					<input type="checkbox" bind:checked={dontShowAgain} class="confirm-delete-checkbox-input" />
					<span>Don't ask again</span>
				</label>
			{/if}
			<div class="confirm-delete-actions">
				<button type="button" class="confirm-delete-btn secondary" bind:this={cancelBtn} onclick={handleCancel}>Cancel</button>
				<button type="button" class="confirm-delete-btn danger" bind:this={confirmBtn} onclick={handleConfirm}>{confirmLabel}</button>
			</div>
			<p class="confirm-delete-hints" aria-hidden="true"><kbd>Tab</kbd> move focus · <kbd>Enter</kbd> confirm · <kbd>Esc</kbd> cancel</p>
		</div>
	</div>
{/if}

<style>
	.confirm-delete-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		/* Above lightbox (.lightbox is z-index 9999) and other app overlays */
		z-index: 110000;
	}
	.confirm-delete-card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 0.75rem 1rem;
		max-width: 20rem;
		width: calc(100% - 2rem);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
	}
	.confirm-delete-title {
		margin: 0 0 0.35rem 0;
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--text);
	}
	.confirm-delete-msg {
		margin: 0 0 0.5rem 0;
		font-size: 0.85rem;
		line-height: 1.35;
		color: var(--muted);
		white-space: pre-line;
	}
	.confirm-delete-checkbox {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		margin-bottom: 0.6rem;
		cursor: pointer;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.confirm-delete-checkbox-input {
		width: 1rem;
		height: 1rem;
		flex-shrink: 0;
		accent-color: var(--accent);
		cursor: pointer;
	}
	.confirm-delete-checkbox span {
		user-select: none;
	}
	.confirm-delete-actions {
		display: flex;
		gap: 0.5rem;
		justify-content: flex-end;
		margin-top: 0.5rem;
	}
	.confirm-delete-btn {
		padding: 0.35rem 0.75rem;
		border-radius: 6px;
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
		border: 1px solid transparent;
	}
	.confirm-delete-btn.secondary {
		background: var(--surface);
		color: var(--text);
		border-color: var(--border);
	}
	.confirm-delete-btn.secondary:hover {
		background: color-mix(in srgb, var(--accent) 15%, var(--surface));
		border-color: var(--accent);
	}
	.confirm-delete-btn.danger {
		background: var(--error, #c55);
		color: white;
		border-color: var(--error, #c55);
	}
	.confirm-delete-btn.danger:hover {
		background: var(--error-hover, #e55);
		border-color: var(--error-hover, #e55);
	}
	.confirm-delete-hints {
		margin: 0.45rem 0 0;
		font-size: 0.72rem;
		color: var(--muted);
		text-align: right;
	}
	.confirm-delete-hints kbd {
		font: inherit;
		font-size: 0.68rem;
		padding: 0 0.25rem;
		border-radius: 0.25rem;
		border: 1px solid var(--border);
		background: color-mix(in srgb, var(--surface) 85%, var(--text));
	}
</style>
