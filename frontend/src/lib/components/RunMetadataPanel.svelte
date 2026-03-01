<script lang="ts">
	import { getApiBase } from '$lib/config';
	import SendToAppDialog from '$lib/components/SendToAppDialog.svelte';

	let { runId, projectId = null, onClose, mode = 'output' }: { runId: string; projectId?: string | null; onClose: () => void; mode?: 'output' | 'run' } = $props();

	const apiBase = getApiBase() || '';

	type RunDetail = {
		id: string;
		project_id?: string;
		workflow_version_id?: string;
		app_id?: string | null;
		status: string;
		created_at: number;
		prompt_id?: string | null;
		seed?: number | null;
		images?: { filename: string; subfolder?: string; type?: string; remote_deleted?: boolean }[];
		execution_time?: number | null;
		error?: string | null;
		input_snapshot?: Record<string, unknown> | null;
		metadata_snapshot?: Record<string, unknown> | null;
		deleted_outputs?: { output_index: number; seed?: number; master_seed?: number; filename?: string; subfolder?: string; type?: string; deleted_at_ts?: number }[];
		parent_run_id?: string | null;
		parent_media_id?: string | null;
		parent_app_title?: string | null;
		root_run_id?: string | null;
		deleted_at?: number | null;
		child_run_ids?: string[];
	};

	let run = $state<RunDetail | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let sendToAppOutputIndex = $state<number | null>(null);
	let imageLoadFailed = $state<Set<string>>(new Set());
	let copiedId = $state<'run' | 'snapshot' | 'input' | null>(null);

	async function copyToClipboard(text: string, id: 'run' | 'snapshot' | 'input') {
		try {
			await navigator.clipboard.writeText(text);
			copiedId = id;
			setTimeout(() => { copiedId = null; }, 2000);
		} catch (_) {}
	}

	$effect(() => {
		const id = runId;
		if (!id) {
			run = null;
			loading = false;
			return;
		}
		loading = true;
		error = null;
		fetch(`${apiBase}/runs/${id}`)
			.then((res) => {
				if (!res.ok) throw new Error(res.status === 404 ? 'Run not found' : `Failed to load run`);
				return res.json();
			})
			.then((data: RunDetail) => {
				run = data;
				loading = false;
			})
			.catch((e: Error) => {
				error = e.message;
				run = null;
				loading = false;
			});
	});

	function imageUrl(img: { filename: string; subfolder?: string; type?: string }, rid?: string) {
		const subfolder = img.subfolder ?? '';
		const type = img.type ?? 'output';
		let url = `${apiBase}/image?filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(subfolder)}&type=${encodeURIComponent(type)}`;
		if (rid) url += `&run_id=${encodeURIComponent(rid)}`;
		return url;
	}

	function imageKey(index: number) {
		return `${run?.id ?? ''}_${index}`;
	}

	function markImageLoadFailed(index: number) {
		imageLoadFailed = new Set([...imageLoadFailed, imageKey(index)]);
	}

	function runMetaAsText(r: RunDetail): string {
		const lines: string[] = [];
		lines.push(`Run ID: ${r.id}`);
		lines.push(`Status: ${r.status}`);
		lines.push(`Created: ${new Date(r.created_at).toLocaleString()}`);
		if (r.workflow_version_id != null) lines.push(`Workflow version: ${r.workflow_version_id}`);
		if (r.app_id) lines.push(`App ID: ${r.app_id}`);
		if (r.seed != null) lines.push(`Seed: ${r.seed}`);
		if (r.execution_time != null) lines.push(`Execution time: ${r.execution_time} s`);
		if (r.prompt_id) lines.push(`Prompt ID: ${r.prompt_id}`);
		if (r.error) lines.push(`Error: ${r.error}`);
		if (r.deleted_at) lines.push('Run: Deleted (lineage preserved)');
		return lines.join('\n');
	}

	const dialogTitle = $derived(mode === 'output' ? 'Output metadata' : 'Run metadata');
</script>

<div class="metadata-panel-overlay" role="dialog" aria-modal="true" aria-label={dialogTitle} tabindex="-1" onclick={(e) => { if (e.target === e.currentTarget) onClose(); }} onkeydown={(e) => { if (e.key === 'Escape') onClose(); if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); if (e.target === e.currentTarget) onClose(); } }}>
	<div class="metadata-panel" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
		<div class="metadata-panel-header">
			<h2>{dialogTitle}</h2>
			<button type="button" class="metadata-panel-close" onclick={onClose} aria-label="Close">×</button>
		</div>
		{#if loading}
			<div class="metadata-panel-loading">Loading…</div>
		{:else if error}
			<div class="metadata-panel-error">{error}</div>
		{:else if run}
			<div class="metadata-panel-two-panel" class:run-only={mode === 'run'}>
				<aside class="metadata-left-panel">
					{#if mode === 'output' && run.images?.length}
						<div class="image-card">
							{#if run.images[0].remote_deleted && imageLoadFailed.has(imageKey(0))}
								<div class="run-detail-deleted">Deleted</div>
							{:else if run.images[0].type === 'video'}
								<video src={imageUrl(run.images[0], run.id)} controls playsinline class="run-detail-media" onerror={() => markImageLoadFailed(0)}><track kind="captions" /></video>
							{:else}
								<img src={imageUrl(run.images[0], run.id)} alt="Generation output" class="run-detail-media" onerror={() => markImageLoadFailed(0)} />
							{/if}
							{#if run.images.length > 1}
								<p class="image-card-more">+{run.images.length - 1} more output{run.images.length === 2 ? '' : 's'}</p>
							{/if}
							{#if projectId}
								<button type="button" class="send-to-app-link send-to-app-btn" title="Send to App" onclick={() => sendToAppOutputIndex = 0}>Send to App</button>
							{/if}
						</div>
					{/if}
					<div class="meta-card">
						<div class="meta-card-heading">
							<h3>Run metadata</h3>
							<button
								type="button"
								class="copy-btn"
								title="Copy to clipboard"
								aria-label="Copy run metadata to clipboard"
								onclick={() => copyToClipboard(runMetaAsText(run!), 'run')}
							>
								<svg class="copy-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/></svg>
								{#if copiedId === 'run'}
									<span class="copy-feedback">Copied!</span>
								{/if}
							</button>
						</div>
						<dl>
							<dt>Run ID</dt>
							<dd><code>{run.id}</code></dd>
							<dt>Status</dt>
							<dd>{run.status}</dd>
							<dt>Created</dt>
							<dd>{new Date(run.created_at).toLocaleString()}</dd>
							{#if run.workflow_version_id != null}
								<dt>Workflow version</dt>
								<dd><code>{run.workflow_version_id}</code></dd>
							{/if}
							{#if run.app_id}
								<dt>App ID</dt>
								<dd><code>{run.app_id}</code></dd>
							{/if}
							{#if run.seed != null}
								<dt>Seed</dt>
								<dd>{run.seed}</dd>
							{/if}
							{#if run.execution_time != null}
								<dt>Execution time</dt>
								<dd>{run.execution_time} s</dd>
							{/if}
							{#if run.prompt_id}
								<dt>Prompt ID</dt>
								<dd><code>{run.prompt_id}</code></dd>
							{/if}
							{#if run.error}
								<dt>Error</dt>
								<dd class="error-text">{run.error}</dd>
							{/if}
							{#if run.deleted_at}
								<dt>Run</dt>
								<dd class="muted">Deleted (lineage preserved)</dd>
							{/if}
						</dl>
						{#if run.parent_run_id || (run.child_run_ids && run.child_run_ids.length > 0)}
							<h4>Lineage</h4>
							<dl>
								{#if run.parent_run_id}
									<dt>Source</dt>
									<dd>
										{#if run.parent_app_title}
											<span class="muted">{run.parent_app_title}</span>
											<span class="muted"> · </span>
										{/if}
										{#if projectId}
											<a href="/projects/{projectId}/runs/{run.parent_run_id}">Run {run.parent_run_id.slice(0, 8)}…</a>
										{:else}
											<code>{run.parent_run_id}</code>
										{/if}
										{#if run.parent_media_id}
											<span class="muted"> · Media {run.parent_media_id}</span>
										{/if}
									</dd>
								{/if}
								{#if run.child_run_ids && run.child_run_ids.length > 0}
									<dt>Derived runs</dt>
									<dd>
										<ul class="lineage-list">
											{#each run.child_run_ids as cid}
												<li>
													{#if projectId}
														<a href="/projects/{projectId}/runs/{cid}">Run {cid.slice(0, 8)}…</a>
													{:else}
														<code>{cid}</code>
													{/if}
												</li>
											{/each}
										</ul>
									</dd>
								{/if}
							</dl>
						{/if}
						{#if run.metadata_snapshot && Object.keys(run.metadata_snapshot).length > 0}
							<div class="meta-subsection">
								<h4>Metadata snapshot</h4>
								<button type="button" class="copy-btn" title="Copy to clipboard" aria-label="Copy metadata snapshot to clipboard" onclick={() => copyToClipboard(JSON.stringify(run.metadata_snapshot, null, 2), 'snapshot')}>
									<svg class="copy-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/></svg>
									{#if copiedId === 'snapshot'}
										<span class="copy-feedback">Copied!</span>
									{/if}
								</button>
							</div>
							<pre class="json-block">{JSON.stringify(run.metadata_snapshot, null, 2)}</pre>
						{/if}
						{#if run.deleted_outputs?.length}
							<h4>Deleted outputs</h4>
							<p class="hint">Outputs removed from ComfyUI (no local copy). Seeds kept for recovery.</p>
							<dl class="deleted-outputs-list">
								{#each run.deleted_outputs as entry}
									<div class="deleted-output-entry">
										<dt>Output #{entry.output_index + 1}</dt>
										<dd>
											{#if entry.master_seed != null}
												<span title="Master seed (workflow)">Master seed: <code>{entry.master_seed}</code></span>
												{#if entry.seed != null && entry.seed !== entry.master_seed}
													<span title="Prompt seed"> · Seed: <code>{entry.seed}</code></span>
												{/if}
											{:else if entry.seed != null}
												<span>Seed: <code>{entry.seed}</code></span>
											{/if}
											{#if entry.filename}
												<span class="deleted-filename"> · {entry.filename}</span>
											{/if}
										</dd>
									</div>
								{/each}
							</dl>
						{/if}
					</div>
				</aside>
				{#if mode === 'output'}
				<div class="metadata-right-panel">
					<div class="input-snapshot-section">
						<h3>Input snapshot</h3>
						<p class="hint">Exactly what was used for this run (stored at execution).</p>
						{#if run.input_snapshot}
							<div class="copyable-block">
								<pre class="json-block">{JSON.stringify(run.input_snapshot, null, 2)}</pre>
								<button type="button" class="copy-btn" title="Copy to clipboard" aria-label="Copy input snapshot to clipboard" onclick={() => copyToClipboard(JSON.stringify(run!.input_snapshot, null, 2), 'input')}>
									<svg class="copy-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/></svg>
									{#if copiedId === 'input'}
										<span class="copy-feedback">Copied!</span>
									{/if}
								</button>
							</div>
						{:else}
							<p class="muted">No input snapshot stored.</p>
						{/if}
					</div>
				</div>
				{/if}
			</div>
		{/if}
	</div>
</div>

{#if sendToAppOutputIndex != null && run && projectId}
	<SendToAppDialog
		open={true}
		sendFromRun={run.id}
		sendFromOutput={sendToAppOutputIndex}
		{projectId}
		onClose={() => { sendToAppOutputIndex = null; }}
	/>
{/if}

<style>
	.metadata-panel-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.6);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}
	.metadata-panel {
		background: var(--bg, #eef2f7);
		border: 1px solid var(--border, rgba(30, 41, 59, 0.08));
		border-radius: 12px;
		max-width: 95vw;
		max-height: 90vh;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		color: var(--text, #0f172a);
	}
	.metadata-panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.75rem 1rem;
		border-bottom: 1px solid var(--border, rgba(30, 41, 59, 0.08));
	}
	.metadata-panel-header h2 {
		margin: 0;
		font-size: 1.1rem;
		color: var(--text, #0f172a);
	}
	.metadata-panel-close {
		background: none;
		border: none;
		color: var(--text-muted, var(--muted, #64748b));
		font-size: 1.5rem;
		cursor: pointer;
		padding: 0 0.25rem;
		line-height: 1;
	}
	.metadata-panel-close:hover {
		color: var(--text, #0f172a);
	}
	.metadata-panel-loading,
	.metadata-panel-error {
		padding: 2rem;
		text-align: center;
		color: var(--text-muted, var(--muted, #64748b));
	}
	.metadata-panel-error {
		color: var(--error, #dc2626);
	}
	.metadata-panel-two-panel {
		display: grid;
		grid-template-columns: 384px 1fr;
		gap: 1.5rem;
		min-height: 0;
		flex: 1;
		overflow: auto;
		padding: 1rem;
	}
	.metadata-panel-two-panel.run-only {
		grid-template-columns: 1fr;
	}
	.metadata-left-panel {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-width: 0;
	}
	.metadata-right-panel {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		min-width: 0;
	}
	.image-card {
		background: var(--card-bg, var(--card, #ffffff));
		border: 1px solid var(--border, rgba(30, 41, 59, 0.08));
		border-radius: 10px;
		overflow: hidden;
		padding: 0;
		flex-shrink: 0;
	}
	.run-detail-media {
		width: 100%;
		display: block;
		max-height: 320px;
		object-fit: contain;
		background: var(--input-bg, var(--surface, #f6f9fc));
	}
	.run-detail-deleted {
		min-height: 120px;
		display: flex;
		align-items: center;
		justify-content: center;
		color: var(--text-muted, var(--muted, #64748b));
	}
	.image-card-more {
		margin: 0;
		padding: 0.35rem 0.75rem;
		font-size: 0.8rem;
		color: var(--text-muted, var(--muted, #64748b));
		border-top: 1px solid var(--border, rgba(30, 41, 59, 0.08));
	}
	.meta-card {
		background: var(--card-bg, var(--card, #ffffff));
		border: 1px solid var(--border, rgba(30, 41, 59, 0.08));
		border-radius: 10px;
		padding: 1rem;
		color: var(--text, #0f172a);
	}
	.meta-card h3, .input-snapshot-section h3 {
		margin: 0 0 0.5rem 0;
		font-size: 1rem;
		color: var(--text, #0f172a);
	}
	.meta-card-heading, .meta-subsection {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.meta-card-heading h3, .meta-subsection h4 {
		margin: 0;
	}
	.meta-subsection {
		margin-top: 1rem;
	}
	.meta-subsection h4 {
		margin-right: 0;
	}
	.copy-btn {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		background: none;
		border: none;
		color: var(--text-muted, var(--muted, #64748b));
		cursor: pointer;
		padding: 0.25rem;
		border-radius: 4px;
		font-size: 0.85rem;
	}
	.copy-btn:hover {
		color: var(--text, #0f172a);
		background: var(--input-bg, var(--surface, #f6f9fc));
	}
	.copy-btn .copy-icon {
		width: 1rem;
		height: 1rem;
	}
	.copy-feedback {
		font-size: 0.75rem;
		color: var(--success, #16a34a);
	}
	.copyable-block {
		position: relative;
	}
	.copyable-block .copy-btn {
		position: absolute;
		top: 0.5rem;
		right: 0.5rem;
	}
	.meta-card h4 {
		margin: 1rem 0 0.5rem 0;
		font-size: 0.95rem;
		color: var(--text-muted, var(--muted, #64748b));
	}
	.meta-card dl {
		margin: 0;
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.25rem 1rem;
		font-size: 0.9rem;
	}
	.meta-card dt {
		color: var(--text-muted, var(--muted, #64748b));
	}
	.meta-card dd {
		margin: 0;
		word-break: break-all;
		color: var(--text, #0f172a);
	}
	.meta-card code {
		font-size: 0.8rem;
		color: var(--text, #0f172a);
	}
	.error-text {
		color: var(--error, #dc2626);
	}
	.lineage-list {
		list-style: none;
		margin: 0.25rem 0 0;
		padding: 0;
	}
	.lineage-list li {
		margin: 0.25rem 0;
	}
	.send-to-app-link, .send-to-app-btn {
		display: inline-block;
		margin-top: 0.35rem;
		font-size: 0.8rem;
		color: var(--link, var(--accent, #6af));
		background: none;
		border: none;
		cursor: pointer;
		padding: 0;
		text-decoration: none;
		font: inherit;
	}
	.send-to-app-btn:hover {
		text-decoration: underline;
	}
	.json-block {
		margin: 0;
		padding: 0.75rem;
		background: var(--input-bg, var(--surface, #f6f9fc));
		color: var(--text, #0f172a);
		border-radius: 6px;
		font-size: 0.8rem;
		overflow-x: auto;
		white-space: pre-wrap;
		word-break: break-all;
	}
	.copyable-block .json-block {
		padding-right: 2.5rem;
	}
	.hint {
		margin: 0 0 0.5rem 0;
		font-size: 0.85rem;
		color: var(--text-muted, var(--muted, #64748b));
	}
	.deleted-outputs-list {
		margin: 0;
		padding: 0;
		list-style: none;
	}
	.deleted-output-entry {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.25rem 0.75rem;
		margin-bottom: 0.5rem;
		font-size: 0.9rem;
	}
	.deleted-output-entry dt {
		color: var(--text-muted, var(--muted, #64748b));
	}
	.deleted-output-entry dd {
		margin: 0;
		word-break: break-all;
		color: var(--text, #0f172a);
	}
	.deleted-filename {
		color: var(--text-muted, var(--muted, #64748b));
		font-size: 0.85rem;
	}
	.muted {
		color: var(--text-muted, var(--muted, #64748b));
	}
	.input-snapshot-section {
		color: var(--text, #0f172a);
	}
	.input-snapshot-section h3 {
		color: var(--text, #0f172a);
	}
	@media (max-width: 700px) {
		.metadata-panel-two-panel {
			grid-template-columns: 1fr;
		}
	}
</style>
