<script lang="ts">
	import { getApiBase } from '$lib/config';
	import SendToAppDialog from '$lib/components/SendToAppDialog.svelte';

	let { data } = $props();

	let sendToAppOutputIndex = $state<number | null>(null);

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
					{:else if data.run.images[0].type === 'video'}
						<video src={imageUrl(data.run.images[0], data.run.id)} controls playsinline class="run-detail-media" onerror={() => markImageLoadFailed(0)}>Output 1</video>
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
					<h3>Metadata snapshot</h3>
					<pre class="json-block">{JSON.stringify(data.run.metadata_snapshot, null, 2)}</pre>
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
					<pre class="json-block">{JSON.stringify(data.run.input_snapshot, null, 2)}</pre>
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
								{:else if img.type === 'video'}
									<video src={imageUrl(img, data.run.id)} controls playsinline class="output-media" onerror={() => markImageLoadFailed(i)}>Output {i + 1}</video>
								{:else}
									<img src={imageUrl(img, data.run.id)} alt="Output {i + 1}" onerror={() => markImageLoadFailed(i)} />
								{/if}
								<button type="button" class="send-to-app-link send-to-app-btn" title="Send to App" onclick={() => sendToAppOutputIndex = i}>Send to App</button>
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
	.output-deleted-placeholder {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 120px;
		background: var(--surface);
		color: var(--text-muted);
		font-size: 0.9rem;
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
	}
	.output-img-wrap img,
	.output-img-wrap video {
		width: 100%;
		height: 100%;
		object-fit: contain;
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
</style>
