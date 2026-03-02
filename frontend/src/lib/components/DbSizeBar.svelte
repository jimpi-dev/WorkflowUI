<script lang="ts">
	import { getApiBase } from '$lib/config';

	const ENTITY_LABELS: Record<string, string> = {
		workflows: 'Workflows',
		apps: 'Apps',
		runs: 'Runs',
		projects: 'Projects',
		presets: 'Presets',
		comfyui: 'ComfyUI versions',
	};

	interface Props {
		sizeBytes: number | null;
		breakdown?: Record<string, number> | null;
		onVacuumComplete?: (bytes: number) => void;
	}

	let { sizeBytes = null, breakdown = null, onVacuumComplete }: Props = $props();

	const MAX_MB = 5120; // 5 GB
	const MB = 1_048_576;

	let vacuuming = $state(false);
	let vacuumError = $state<string | null>(null);

	const sizeMb = $derived(sizeBytes != null ? sizeBytes / MB : 0);
	const fillPercent = $derived(Math.min(100, (sizeMb / MAX_MB) * 100));
	const label = $derived(sizeBytes != null ? `${sizeMb.toFixed(1)} MB` : '—');

	const tooltip = $derived.by(() => {
		if (sizeBytes == null) return 'Database size';
		const lines: string[] = [`Total: ${sizeMb.toFixed(1)} MB (${sizeBytes.toLocaleString()} bytes)`];
		if (breakdown && Object.keys(breakdown).length > 0) {
			lines.push('');
			const order = ['workflows', 'apps', 'runs', 'projects', 'presets', 'comfyui'];
			for (const key of order) {
				const bytes = breakdown[key];
				if (bytes != null && bytes > 0) {
					const mb = (bytes / MB).toFixed(2);
					const label2 = ENTITY_LABELS[key] ?? key;
					lines.push(`${label2}: ${mb} MB`);
				}
			}
		}
		return lines.join('\n');
	});

	// Color based on fill: green → accent → amber → red
	function getFillColor(percent: number): string {
		if (percent < 25) return 'var(--success)';
		if (percent < 60) return 'var(--accent)';
		if (percent < 85) return 'var(--warning)';
		return '#ef4444'; // red
	}

	async function runVacuum() {
		const base = getApiBase() || '';
		vacuumError = null;
		vacuuming = true;
		try {
			const res = await fetch(`${base}/config/vacuum`, {
				method: 'POST',
				signal: AbortSignal.timeout(120000),
			});
			if (!res.ok) throw new Error(`Vacuum failed: ${res.status}`);
			const data = await res.json();
			const bytes = typeof data.dbSizeBytes === 'number' ? data.dbSizeBytes : null;
			if (bytes != null && onVacuumComplete) onVacuumComplete(bytes);
		} catch (e) {
			vacuumError = e instanceof Error ? e.message : 'Vacuum failed';
		} finally {
			vacuuming = false;
		}
	}
</script>

<div class="db-size-bar-wrap" role="status" aria-label="Database size">
	<div
		class="db-size-bar"
		title={tooltip}
		style="--fill-percent: {fillPercent}; --fill-color: {getFillColor(fillPercent)}"
	>
		<div class="db-size-bar-fill" aria-hidden="true"></div>
		<span class="db-size-label">{label}</span>
	</div>
	<button
		type="button"
		class="vacuum-btn secondary"
		title="Vacuum database to reclaim space"
		aria-label="Vacuum database"
		disabled={vacuuming}
		onclick={runVacuum}
	>
		{#if vacuuming}
			<span class="vacuum-spinner" aria-hidden="true"></span>
			<span class="vacuum-text">Vacuuming…</span>
		{:else}
			Vacuum
		{/if}
	</button>
	{#if vacuumError}
		<span class="vacuum-error" role="alert">{vacuumError}</span>
	{/if}
</div>

<style>
	.db-size-bar-wrap {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.db-size-bar {
		position: relative;
		width: 100px;
		height: 18px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--text) 10%, transparent);
		overflow: hidden;
		flex-shrink: 0;
	}
	.db-size-bar-fill {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: calc(var(--fill-percent) * 1%);
		min-width: 2px;
		background: var(--fill-color);
		border-radius: 999px 0 0 999px;
		transition: width 0.2s ease, background 0.2s ease;
	}
	.db-size-label {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 0.7rem;
		font-weight: 500;
		color: var(--text);
		text-shadow: 0 0 2px var(--card), 0 0 4px var(--card), 0 1px 2px rgba(0, 0, 0, 0.5);
		z-index: 1;
	}
	.vacuum-btn {
		padding: 0.2rem 0.5rem;
		font-size: 0.7rem;
		min-height: 22px;
		border-radius: 6px;
	}
	.vacuum-btn:disabled {
		opacity: 0.7;
		cursor: wait;
	}
	.vacuum-spinner {
		display: inline-block;
		width: 10px;
		height: 10px;
		border: 2px solid color-mix(in srgb, var(--accent) 30%, transparent);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: vacuum-spin 0.7s linear infinite;
		vertical-align: middle;
		margin-right: 0.25rem;
	}
	.vacuum-text {
		vertical-align: middle;
	}
	@keyframes vacuum-spin {
		to {
			transform: rotate(360deg);
		}
	}
	.vacuum-error {
		font-size: 0.7rem;
		color: var(--warning);
		max-width: 120px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	@media (max-width: 639px) {
		.db-size-bar {
			width: 80px;
			height: 16px;
		}
		.db-size-label {
			font-size: 0.65rem;
		}
		.vacuum-btn {
			padding: 0.15rem 0.35rem;
			font-size: 0.65rem;
		}
		.vacuum-error {
			display: none;
		}
	}
</style>
