<script lang="ts">
	import { queuePanelOpen } from '$lib/stores/queuePanelOpen';
	import { queueState, queueItemCount } from '$lib/stores/queueState';

	const totalCount = $derived(queueItemCount($queueState.queue));
	const hasItems = $derived(totalCount > 0);
</script>

{#if !$queuePanelOpen}
	<button
		type="button"
		class="queue-badge"
		class:active={hasItems && !$queueState.queue?.processing_halted}
		class:paused={hasItems && !!$queueState.queue?.processing_halted}
		onclick={() => queuePanelOpen.set(true)}
		title="Open run queue"
		aria-label="Open run queue panel"
		aria-pressed="false"
	>
		<span class="queue-badge-icon" aria-hidden="true">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<rect x="2" y="5" width="20" height="14" rx="2"/>
				<path d="M2 10h20"/>
			</svg>
		</span>
		<span class="queue-badge-count">{totalCount || '0'}</span>
	</button>
{/if}

<style>
	.queue-badge {
		position: fixed;
		right: 0;
		top: 50%;
		transform: translateY(-50%);
		z-index: 9990;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.25rem;
		padding: 0.6rem 0.5rem;
		background: var(--card);
		border: 1px solid var(--border);
		border-right: none;
		border-radius: 10px 0 0 10px;
		box-shadow:
			-2px 0 12px rgba(0, 0, 0, 0.12),
			0 0 0 1px color-mix(in srgb, var(--muted) 20%, transparent);
		cursor: pointer;
		color: color-mix(in srgb, var(--text) 60%, transparent);
		font-size: 0.85rem;
		font-weight: 600;
		transition: background 0.2s, color 0.2s, box-shadow 0.2s, border-color 0.2s;
	}
	.queue-badge:hover {
		background: color-mix(in srgb, var(--accent) 12%, var(--card));
		color: var(--text);
		box-shadow:
			-2px 0 14px rgba(0, 0, 0, 0.18),
			0 0 14px color-mix(in srgb, var(--accent) 35%, transparent),
			0 0 0 1px color-mix(in srgb, var(--accent) 40%, var(--border));
		border-color: color-mix(in srgb, var(--accent) 50%, var(--border));
	}
	.queue-badge.active {
		color: var(--accent);
		box-shadow:
			-2px 0 12px rgba(0, 0, 0, 0.12),
			0 0 12px color-mix(in srgb, var(--accent) 30%, transparent),
			0 0 0 1px color-mix(in srgb, var(--accent) 45%, var(--border));
		border-color: color-mix(in srgb, var(--accent) 50%, var(--border));
	}
	.queue-badge.active:hover {
		box-shadow:
			-2px 0 14px rgba(0, 0, 0, 0.18),
			0 0 18px color-mix(in srgb, var(--accent) 45%, transparent),
			0 0 0 1px color-mix(in srgb, var(--accent) 60%, var(--border));
	}
	.queue-badge.paused {
		color: var(--warning);
		box-shadow:
			-2px 0 12px rgba(0, 0, 0, 0.12),
			0 0 12px color-mix(in srgb, var(--warning) 25%, transparent),
			0 0 0 1px color-mix(in srgb, var(--warning) 40%, var(--border));
		border-color: color-mix(in srgb, var(--warning) 45%, var(--border));
	}
	.queue-badge.paused:hover {
		box-shadow:
			-2px 0 14px rgba(0, 0, 0, 0.18),
			0 0 16px color-mix(in srgb, var(--warning) 35%, transparent),
			0 0 0 1px color-mix(in srgb, var(--warning) 55%, var(--border));
	}
	.queue-badge-icon {
		width: 24px;
		height: 24px;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.queue-badge-icon svg {
		width: 100%;
		height: 100%;
	}
	.queue-badge-count {
		line-height: 1;
		min-width: 1.25em;
		text-align: center;
	}
</style>
