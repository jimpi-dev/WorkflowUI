<script lang="ts">
	import { onMount } from 'svelte';
	import { getApiBase } from '$lib/config';
	import { browser } from '$app/environment';
	import { invalidateAll } from '$app/navigation';
	import SendToAppDialog from '$lib/components/SendToAppDialog.svelte';
	import { pushRunOutputToGenVault } from '$lib/api/genvault';
	import { toastError, toastSuccess } from '$lib/stores/toast';

	let { data } = $props();

	let sendToAppOutputIndex = $state<number | null>(null);
	let isMobile = $state(false);
	let removingOutputIndex = $state<number | null>(null);
	let pushingOutputIndex = $state<number | null>(null);

	const apiBase = getApiBase() || '';

	function imageUrl(img: { filename: string; subfolder: string; type: string }, runId?: string) {
		let url = `${apiBase}/image?filename=${img.filename}&subfolder=${img.subfolder}&type=${img.type}`;
		if (runId) url += `&run_id=${encodeURIComponent(runId)}`;
		return url;
	}

	let imageLoadFailed = $state<Set<string>>(new Set());
	function imageKey(index: number) {
		return `${data.run!.id}_${index}`;
	}
	function markImageLoadFailed(index: number) {
		imageLoadFailed = new Set([...imageLoadFailed, imageKey(index)]);
	}

	function truncateOutputFilename(name: string, maxLen = 28): string {
		const n = (name || '').trim();
		if (n.length <= maxLen) return n;
		const keep = maxLen - 1;
		const a = Math.ceil(keep / 2);
		const b = Math.floor(keep / 2);
		return `${n.slice(0, a)}…${n.slice(-b)}`;
	}

	async function removeOutputFromRunDetail(imageIndex: number) {
		if (!data.run) return;
		removingOutputIndex = imageIndex;
		try {
			const res = await fetch(`${apiBase}/runs/${data.run.id}/remove-outputs`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ indices: [imageIndex] }),
			});
			if (res.ok) {
				imageLoadFailed = new Set();
				await invalidateAll();
			}
		} finally {
			removingOutputIndex = null;
		}
	}

	async function sendOutputToGenVault(imageIndex: number) {
		if (!data.run) return;
		pushingOutputIndex = imageIndex;
		try {
			const res = await pushRunOutputToGenVault(data.run.id, imageIndex);
			toastSuccess(res?.uploaded?.duplicate ? 'Bild ist bereits in GenVault gespeichert.' : 'An GenVault gesendet.');
		} catch (e) {
			toastError(e instanceof Error ? e.message : 'Send to GenVault failed.');
		} finally {
			pushingOutputIndex = null;
		}
	}

	onMount(() => {
		if (!browser) return;
		const mq = window.matchMedia('(max-width: 639px)');
		const update = () => {
			isMobile = mq.matches;
		};
		update();
		// Safari < 14 fallback
		if (typeof mq.addEventListener === 'function') mq.addEventListener('change', update);
		// @ts-expect-error - legacy listener
		else mq.addListener(update);
		return () => {
			if (typeof mq.removeEventListener === 'function') mq.removeEventListener('change', update);
			// @ts-expect-error - legacy listener
			else mq.removeListener(update);
		};
	});
</script>

{#if !data.run}
	<p class="error">Run not found.</p>
{:else}
	<div class="run-inspector fill-height">
		<a href="/projects/{data.projectId}" class="back-link">← Back to project</a>
	<div class="two-panel fill-height">
		<aside class="left-panel">
			{#if data.run.images?.length}
				<div class="image-card">
					{#if data.run.images[0].remote_deleted && imageLoadFailed.has(imageKey(0))}
						<div class="run-detail-deleted">Deleted</div>
					{:else if !data.run.images[0].remote_deleted && imageLoadFailed.has(imageKey(0))}
						<div class="output-not-found-detail">
							<span class="output-not-found-detail-title">Not found</span>
							<span class="output-not-found-detail-fn" title={data.run.images[0].filename ?? ''}>{truncateOutputFilename(data.run.images[0].filename ?? '')}</span>
							<button
								type="button"
								class="output-remove-from-run-btn"
								disabled={removingOutputIndex === 0}
								onclick={() => removeOutputFromRunDetail(0)}
							>
								{removingOutputIndex === 0 ? 'Removing…' : 'Remove from run'}
							</button>
						</div>
					{:else if data.run.images[0].type === 'video'}
						<video src={imageUrl(data.run.images[0], data.run.id)} controls playsinline class="run-detail-media" onerror={() => markImageLoadFailed(0)}><track kind="captions" /></video>
					{:else}
						<img src={imageUrl(data.run.images[0], data.run.id)} alt="Generation output" class="run-detail-media" onerror={() => markImageLoadFailed(0)} />
					{/if}
					{#if data.run.images.length > 1}
						<p class="image-card-more">+{data.run.images.length - 1} more output{data.run.images.length === 2 ? '' : 's'}</p>
					{/if}
				</div>
			{/if}
			<div class="meta-card">
				<h2>Run metadata</h2>
				<dl>
					<dt>Run ID</dt>
					<dd><code>{data.run.id}</code></dd>
					<dt>Status</dt>
					<dd>{data.run.status}</dd>
					<dt>Created</dt>
					<dd>{new Date(data.run.created_at).toLocaleString()}</dd>
					<dt>Workflow version</dt>
					<dd><code>{data.run.workflow_version_id}</code></dd>
					{#if data.run.app_id}
						<dt>App ID</dt>
						<dd><code>{data.run.app_id}</code></dd>
					{/if}
					{#if data.run.seed != null}
						<dt>Seed</dt>
						<dd>{data.run.seed}</dd>
					{/if}
					{#if data.run.execution_time != null}
						<dt>Execution time</dt>
						<dd>{data.run.execution_time} s</dd>
					{/if}
					{#if data.run.prompt_id}
						<dt>Prompt ID</dt>
						<dd><code>{data.run.prompt_id}</code></dd>
					{/if}
					{#if data.run.error}
						<dt>Error</dt>
						<dd class="error-text">{data.run.error}</dd>
					{/if}
					{#if data.run.deleted_at}
						<dt>Run</dt>
						<dd class="muted">Deleted (lineage preserved)</dd>
					{/if}
				</dl>
				{#if data.run.parent_run_id || (data.run.child_run_ids && data.run.child_run_ids.length > 0)}
					<h3>Lineage</h3>
					<dl>
						{#if data.run.parent_run_id}
							<dt>Source</dt>
							<dd>
								{#if data.run.parent_app_title}
									<span class="muted">{data.run.parent_app_title}</span>
									<span class="muted"> · </span>
								{/if}
								<a href="/projects/{data.projectId}/runs/{data.run.parent_run_id}">Run {data.run.parent_run_id.slice(0, 8)}…</a>
								{#if data.run.parent_media_id}
									<span class="muted"> · Media {data.run.parent_media_id}</span>
								{/if}
							</dd>
						{/if}
						{#if data.run.child_run_ids && data.run.child_run_ids.length > 0}
							<dt>Derived runs</dt>
							<dd>
								<ul class="lineage-list">
									{#each data.run.child_run_ids as cid}
										<li><a href="/projects/{data.projectId}/runs/{cid}">Run {cid.slice(0, 8)}…</a></li>
									{/each}
								</ul>
							</dd>
						{/if}
					</dl>
				{/if}
				{#if data.run.metadata_snapshot && Object.keys(data.run.metadata_snapshot).length > 0}
					<details class="json-accordion json-accordion--always-summary" open={!isMobile}>
						<summary>Metadata snapshot</summary>
						<pre class="json-block">{JSON.stringify(data.run.metadata_snapshot, null, 2)}</pre>
					</details>
				{/if}
				{#if data.run.deleted_outputs?.length}
					<h3>Deleted outputs</h3>
					<p class="hint">Outputs removed from ComfyUI (no local copy). Seeds kept for recovery.</p>
					<dl class="deleted-outputs-list">
						{#each data.run.deleted_outputs as entry}
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
		<div class="right-panel">
			<div class="input-snapshot-section">
				<h2>Input snapshot</h2>
				<p class="hint">Exactly what was used for this run (stored at execution).</p>
				{#if data.run.input_snapshot}
					<details class="json-accordion" open={!isMobile}>
						<summary>Input snapshot JSON</summary>
						<pre class="json-block">{JSON.stringify(data.run.input_snapshot, null, 2)}</pre>
					</details>
				{:else}
					<p class="muted">No input snapshot stored.</p>
				{/if}
			</div>
			<div class="outputs-section">
				<h2>Outputs</h2>
				{#if data.run.images?.length}
					<div class="output-images">
						{#each data.run.images as img, i (i)}
							<div class="output-img-wrap">
								{#if img.remote_deleted && imageLoadFailed.has(imageKey(i))}
									<div class="output-deleted-placeholder">Deleted</div>
								{:else if !img.remote_deleted && imageLoadFailed.has(imageKey(i))}
									<div class="output-not-found-placeholder-detail">
										<span class="output-not-found-detail-title">Not found</span>
										<span class="output-not-found-detail-fn" title={img.filename ?? ''}>{truncateOutputFilename(img.filename ?? '')}</span>
										<button
											type="button"
											class="output-remove-from-run-btn"
											disabled={removingOutputIndex === i}
											onclick={() => removeOutputFromRunDetail(i)}
										>
											{removingOutputIndex === i ? 'Removing…' : 'Remove from run'}
										</button>
									</div>
								{:else if img.type === 'video'}
									<video src={imageUrl(img, data.run.id)} controls playsinline class="output-media" onerror={() => markImageLoadFailed(i)}><track kind="captions" /></video>
								{:else}
									<img src={imageUrl(img, data.run.id)} alt="Output {i + 1}" onerror={() => markImageLoadFailed(i)} />
								{/if}
								{#if pushingOutputIndex === i}
									<div class="genvault-transfer-overlay" aria-hidden="true">
										<span class="genvault-transfer-label">Sending to GenVault…</span>
										<span class="genvault-transfer-bar"><span class="genvault-transfer-bar-fill"></span></span>
									</div>
								{/if}
								{#if !imageLoadFailed.has(imageKey(i))}
									<div class="output-actions-row">
										<button type="button" class="send-to-app-link send-to-app-btn" title="Send to App" onclick={() => sendToAppOutputIndex = i}>Send to App</button>
										<button
											type="button"
											class="send-to-app-link send-to-app-btn"
											title="Send to GenVault"
											disabled={pushingOutputIndex === i}
											onclick={() => void sendOutputToGenVault(i)}
										>
											{pushingOutputIndex === i ? 'Sending…' : 'Send to GenVault'}
										</button>
									</div>
								{/if}
							</div>
						{/each}
					</div>
				{:else}
					<p class="muted">No outputs.</p>
				{/if}
			</div>
		</div>
	</div>
</div>

	{#if sendToAppOutputIndex != null && data.run}
		<SendToAppDialog
			open={true}
			sendFromRun={data.run.id}
			sendFromOutput={sendToAppOutputIndex}
			projectId={data.projectId}
			onClose={() => { sendToAppOutputIndex = null; }}
		/>
	{/if}
{/if}

<style>
	.fill-height {
		flex: 1;
		min-height: 0;
		padding: 1rem;
	}
	.two-panel {
		display: grid;
		grid-template-columns: 320px 1fr;
		gap: 1.5rem;
		min-height: 0;
		height: 100%;
	}
	.left-panel {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		overflow-y: auto;
	}
	.image-card {
		background: var(--card-bg);
		border: 1px solid var(--border);
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
		background: var(--input-bg);
	}
	.run-detail-deleted,
	.lineage-list {
		list-style: none;
		margin: 0.25rem 0 0;
		padding: 0;
	}
	.lineage-list li { margin: 0.25rem 0; }
	.send-to-app-link {
		display: inline-block;
		margin-top: 0.35rem;
		font-size: 0.8rem;
		color: var(--link);
	}
	.send-to-app-btn {
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
	.output-actions-row {
		display: flex;
		gap: 0.6rem;
		align-items: center;
	}
	.output-deleted-placeholder {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 120px;
		background: var(--surface);
		color: var(--text-muted);
		font-size: 0.9rem;
	}
	.output-not-found-detail,
	.output-not-found-placeholder-detail {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		min-height: 120px;
		padding: 0.75rem;
		text-align: center;
		background: var(--surface);
		color: var(--text-muted);
		font-size: 0.85rem;
	}
	.output-not-found-detail-title {
		font-weight: 600;
		color: var(--text);
	}
	.output-not-found-detail-fn {
		word-break: break-all;
		font-size: 0.8rem;
		line-height: 1.25;
	}
	.output-remove-from-run-btn {
		padding: 0.35rem 0.65rem;
		font-size: 0.8rem;
		border-radius: 6px;
		border: 1px solid var(--border);
		background: var(--input-bg);
		color: var(--text);
		cursor: pointer;
	}
	.output-remove-from-run-btn:hover:not(:disabled) {
		border-color: var(--accent);
		color: var(--accent);
	}
	.output-remove-from-run-btn:disabled {
		opacity: 0.65;
		cursor: not-allowed;
	}
	.run-detail-deleted {
		max-height: 320px;
	}
	.image-card-more {
		margin: 0;
		padding: 0.35rem 0.75rem;
		font-size: 0.8rem;
		color: var(--text-muted);
		border-top: 1px solid var(--border);
	}
	.right-panel {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
		min-height: 0;
		overflow-y: auto;
	}
	.meta-card {
		background: var(--card-bg);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 1rem;
	}
	.meta-card h2, .input-snapshot-section h2, .outputs-section h2 {
		margin: 0 0 0.5rem 0;
		font-size: 1.1rem;
	}
	.meta-card h3 {
		margin: 1rem 0 0.5rem 0;
		font-size: 0.95rem;
		color: var(--text-muted);
	}
	.meta-card dl {
		margin: 0;
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.25rem 1rem;
		font-size: 0.9rem;
	}
	.meta-card dt {
		color: var(--text-muted);
	}
	.meta-card dd {
		margin: 0;
		word-break: break-all;
	}
	.meta-card code {
		font-size: 0.8rem;
	}
	.error-text {
		color: var(--error, #e55);
	}
	.json-block {
		margin: 0;
		padding: 0.75rem;
		background: var(--input-bg);
		border-radius: 6px;
		font-size: 0.8rem;
		overflow-x: auto;
		white-space: pre-wrap;
		word-break: break-all;
	}
	.hint {
		margin: 0 0 0.5rem 0;
		font-size: 0.85rem;
		color: var(--text-muted);
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
		color: var(--text-muted);
	}
	.deleted-output-entry dd {
		margin: 0;
		word-break: break-all;
	}
	.deleted-filename {
		color: var(--text-muted);
		font-size: 0.85rem;
	}
	.output-images {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 0.75rem;
	}
	.output-img-wrap {
		aspect-ratio: 1;
		border-radius: 8px;
		overflow: hidden;
		background: var(--input-bg);
		position: relative;
	}
	.output-img-wrap img,
	.output-img-wrap video {
		width: 100%;
		height: 100%;
		object-fit: contain;
	}
	.genvault-transfer-overlay {
		position: absolute;
		inset: 0;
		z-index: 3;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		background: color-mix(in srgb, rgba(10, 12, 20, 0.72) 85%, transparent);
		backdrop-filter: blur(1.5px);
		pointer-events: none;
	}
	.genvault-transfer-label {
		font-size: 0.74rem;
		font-weight: 600;
		letter-spacing: 0.02em;
		color: rgba(255, 255, 255, 0.96);
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.7);
	}
	.genvault-transfer-bar {
		width: min(84%, 170px);
		height: 5px;
		border-radius: 999px;
		overflow: hidden;
		background: rgba(255, 255, 255, 0.22);
		border: 1px solid rgba(255, 255, 255, 0.25);
	}
	.genvault-transfer-bar-fill {
		display: block;
		height: 100%;
		width: 42%;
		border-radius: 999px;
		background: linear-gradient(
			90deg,
			rgba(255, 255, 255, 0.25) 0%,
			color-mix(in srgb, var(--accent) 80%, #9fb4ff) 38%,
			color-mix(in srgb, var(--accent) 65%, #dbe5ff) 62%,
			rgba(255, 255, 255, 0.2) 100%
		);
		animation: genvault-transfer-slide 1.15s ease-in-out infinite;
	}
	@keyframes genvault-transfer-slide {
		0% { transform: translateX(-110%); }
		100% { transform: translateX(250%); }
	}
	.error, .muted {
		color: var(--text-muted);
	}
	.back-link {
		display: inline-block;
		margin-bottom: 0.75rem;
		color: var(--text-muted);
		text-decoration: none;
		font-size: 0.9rem;
	}
	.back-link:hover {
		color: var(--accent);
	}

	.json-accordion {
		margin: 1rem 0 0.5rem 0;
		border-radius: 10px;
		border: 1px solid var(--border);
		background: rgba(0, 0, 0, 0.08);
		overflow: hidden;
	}
	.json-accordion[open] {
		/* Keep desktop close to the prior layout (JSON pre already has its own styling). */
		border: none;
		background: transparent;
	}
	.meta-card .json-accordion {
		background: transparent;
	}
	.json-accordion summary {
		list-style: none;
		cursor: pointer;
		padding: 0.75rem 1rem 0.35rem 1rem;
		color: var(--text-muted);
		font-size: 0.95rem;
		font-weight: 600;
	}
	.json-accordion summary::-webkit-details-marker {
		display: none;
	}
	.json-accordion[open] > summary {
		/* On desktop we open by default and hide the summary line to preserve prior layout. */
		display: none;
	}
	.json-accordion--always-summary[open] > summary {
		display: block;
	}

	@media (max-width: 639px) {
		.two-panel {
			grid-template-columns: 1fr;
			gap: 1rem;
		}
		.left-panel,
		.right-panel {
			overflow-y: visible;
		}
	}
</style>
