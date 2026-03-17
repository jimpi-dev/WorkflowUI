<script lang="ts">
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

	$effect(() => {
		if (open) dontShowAgain = false;
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
</script>

{#if open}
	<div
		class="confirm-delete-overlay"
		role="dialog"
		aria-modal="true"
		aria-labelledby="confirm-delete-dialog-title"
		tabindex="-1"
		onclick={handleBackdropClick}
		onkeydown={(e) => { if (e.key === 'Escape') handleBackdropClick(); }}
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
				<button type="button" class="confirm-delete-btn secondary" onclick={handleCancel}>Cancel</button>
				<button type="button" class="confirm-delete-btn danger" onclick={handleConfirm}>{confirmLabel}</button>
			</div>
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
</style>
