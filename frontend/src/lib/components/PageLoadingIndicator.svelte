<script lang="ts">
	let { message = 'Loading…' }: { message?: string } = $props();
</script>

<div class="page-loading" role="status" aria-live="polite" aria-label={message}>
	<div class="page-loading-spinner" aria-hidden="true"></div>
	<p class="page-loading-text">{message}</p>
</div>

<style>
	.page-loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 1rem;
		padding: 2rem;
		min-height: 120px;
		color: var(--muted);
	}
	.page-loading-spinner {
		width: 32px;
		height: 32px;
		border: 3px solid color-mix(in srgb, var(--accent) 30%, transparent);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: page-loading-spin 0.8s linear infinite;
	}
	.page-loading-text {
		margin: 0;
		font-size: 0.95rem;
		font-weight: 500;
		color: var(--text-muted, var(--muted));
	}
	@keyframes page-loading-spin {
		to {
			transform: rotate(360deg);
		}
	}
</style>
