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

	let diagnosticsOpen = $state(false);
	let diagnosticsLoading = $state(false);
	let diagnosticsError = $state<string | null>(null);
	let diagnosticsData = $state<{
		row_count: number;
		columns: Record<string, { bytes: number; searchable: boolean }>;
		total_bytes: number;
	} | null>(null);

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

	function formatBytes(bytes: number): string {
		if (bytes >= MB) return `${(bytes / MB).toFixed(2)} MB`;
		if (bytes >= 1024) return `${(bytes / 1024).toFixed(2)} KB`;
		return `${bytes} B`;
	}

	async function runDiagnostics() {
		const base = getApiBase() || '';
		diagnosticsError = null;
		diagnosticsData = null;
		diagnosticsOpen = true;
		diagnosticsLoading = true;
		try {
			const res = await fetch(`${base}/config/diagnostics/run-table`, {
				signal: AbortSignal.timeout(10000),
			});
			if (!res.ok) throw new Error(`Diagnostics failed: ${res.status}`);
			const data = await res.json();
			if (data && typeof data.row_count === 'number') {
				diagnosticsData = {
					row_count: data.row_count,
					columns: data.columns && typeof data.columns === 'object' ? data.columns : {},
					total_bytes: typeof data.total_bytes === 'number' ? data.total_bytes : 0,
				};
			} else {
				diagnosticsError = 'Invalid response';
			}
		} catch (e) {
			diagnosticsError = e instanceof Error ? e.message : 'Diagnostics failed';
		} finally {
			diagnosticsLoading = false;
		}
	}

	function closeDiagnostics() {
		diagnosticsOpen = false;
		diagnosticsError = null;
		diagnosticsData = null;
	}

	const COLUMN_ORDER = [
		'input_snapshot_json',
		'metadata_snapshot_json',
		'images_json',
		'media_json',
		'deleted_outputs_json',
		'error',
	];
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
	<button
		type="button"
		class="diagnostics-btn secondary"
		title="Run table column size diagnostics"
		aria-label="DB diagnostics"
		disabled={diagnosticsLoading}
		onclick={runDiagnostics}
	>
		{#if diagnosticsLoading}
			<span class="vacuum-spinner" aria-hidden="true"></span>
			<span class="vacuum-text">…</span>
		{:else}
			Db Diagnostics
		{/if}
	</button>
	{#if vacuumError}
		<span class="vacuum-error" role="alert">{vacuumError}</span>
	{/if}
	{#if diagnosticsOpen}
		<div
			class="diagnostics-overlay"
			role="dialog"
			aria-modal="true"
			aria-labelledby="diagnostics-dialog-title"
			tabindex="-1"
			onclick={closeDiagnostics}
			onkeydown={(e) => {
				if (e.key === 'Escape') closeDiagnostics();
			}}
		>
			<div
				class="diagnostics-dialog"
				role="presentation"
				tabindex="-1"
				onclick={(e) => e.stopPropagation()}
				onkeydown={(e) => e.stopPropagation()}
			>
				<h2 id="diagnostics-dialog-title" class="diagnostics-title">Run table diagnostics</h2>
				{#if diagnosticsLoading}
					<p class="diagnostics-loading">Loading…</p>
				{:else if diagnosticsError}
					<p class="diagnostics-error">{diagnosticsError}</p>
				{:else if diagnosticsData}
					<div class="diagnostics-content">
						<p class="diagnostics-summary">
							{diagnosticsData.row_count.toLocaleString()} rows, {formatBytes(diagnosticsData.total_bytes)} total
						</p>
						<table class="diagnostics-table">
							<thead>
								<tr>
									<th>Column</th>
									<th>Size</th>
								</tr>
							</thead>
							<tbody>
								{#each COLUMN_ORDER as col}
									{#if diagnosticsData.columns[col]}
										{@const entry = diagnosticsData.columns[col]}
										<tr>
											<td><code>{col}</code></td>
											<td>{formatBytes(entry.bytes)}</td>
										</tr>
									{/if}
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
				<div class="diagnostics-actions">
					<button type="button" class="diagnostics-close secondary" onclick={closeDiagnostics}>
						Close
					</button>
				</div>
			</div>
		</div>
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
	.vacuum-btn,
	.diagnostics-btn {
		padding: 0.2rem 0.5rem;
		font-size: 0.7rem;
		min-height: 22px;
		border-radius: 6px;
	}
	.vacuum-btn:disabled,
	.diagnostics-btn:disabled {
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

	.diagnostics-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}
	.diagnostics-dialog {
		background: var(--card);
		border-radius: 10px;
		border: 1px solid var(--border);
		padding: 1.25rem;
		max-width: 420px;
		width: 100%;
		max-height: 80vh;
		overflow-y: auto;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
	}
	.diagnostics-title {
		margin: 0 0 1rem;
		font-size: 1rem;
		font-weight: 600;
	}
	.diagnostics-loading,
	.diagnostics-error {
		margin: 0 0 1rem;
		color: var(--muted);
		font-size: 0.9rem;
	}
	.diagnostics-error {
		color: var(--warning);
	}
	.diagnostics-content {
		margin-bottom: 1rem;
	}
	.diagnostics-summary {
		margin: 0 0 0.75rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.diagnostics-table {
		width: 100%;
		border-collapse: collapse;
		font-size: 0.8rem;
	}
	.diagnostics-table th,
	.diagnostics-table td {
		padding: 0.35rem 0.5rem;
		text-align: left;
		border-bottom: 1px solid var(--border);
	}
	.diagnostics-table th {
		font-weight: 600;
		color: var(--muted);
	}
	.diagnostics-table code {
		font-size: 0.75rem;
		word-break: break-all;
	}
	.diagnostics-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
	}
	.diagnostics-close {
		padding: 0.35rem 0.75rem;
		font-size: 0.8rem;
		border-radius: 6px;
	}

	@media (max-width: 639px) {
		.db-size-bar {
			width: 80px;
			height: 16px;
		}
		.db-size-label {
			font-size: 0.65rem;
		}
		.vacuum-btn,
		.diagnostics-btn {
			padding: 0.15rem 0.35rem;
			font-size: 0.65rem;
		}
		.vacuum-error {
			display: none;
		}
	}
</style>
