<script lang="ts">
	import { goto, invalidate } from '$app/navigation';
	import { getApiBase } from '$lib/config';

	let { data } = $props();
	const workflow = $derived(data?.workflow ?? null);
	const versions = $derived(workflow?.versions ?? []);
	let selectedVersionId = $state<string | null>(null);
	let downloading = $state(false);
	// Sync selected version when data loads or when current selection is no longer in list
	$effect(() => {
		const v = workflow?.versions ?? [];
		if (!v.length) return;
		const currentValid = selectedVersionId != null && v.some((x: { id: string }) => x.id === selectedVersionId);
		if (!currentValid) selectedVersionId = v[0].id;
	});
	const selectedVersion = $derived(versions.find((v) => v.id === selectedVersionId) ?? versions[0]);
	const apps = $derived(selectedVersion?.apps ?? []);
	/** All apps across all versions (for delete confirmation message). */
	const allApps = $derived(
		versions.flatMap((v: { apps?: { title: string; slug: string }[] }) => v.apps ?? [])
	);
	let showDeleteModal = $state(false);
	let deleting = $state(false);

	let appToDelete = $state<{ slug: string; title: string } | null>(null);
	let deleteAppError = $state<string | null>(null);
	let deleteAppLoading = $state(false);
	let downloadingAppSlug = $state<string | null>(null);

	async function downloadAppWorkflowWithDefaults(appSlug: string) {
		if (!appSlug || downloadingAppSlug) return;
		const apiBase = getApiBase().replace(/\/$/, '');
		const url = `${apiBase}/app/${encodeURIComponent(appSlug)}/workflow/download`;
		downloadingAppSlug = appSlug;
		try {
			const res = await fetch(url);
			if (!res.ok) throw new Error(res.status === 404 ? 'App not found' : 'Download failed');
			const blob = await res.blob();
			const disp = res.headers.get('Content-Disposition');
			const match = disp && /filename="?([^"]+)"?/.exec(disp);
			const filename = match ? match[1].trim() : `${appSlug}-workflow.json`;
			const a = document.createElement('a');
			a.href = URL.createObjectURL(blob);
			a.download = filename;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(a.href);
		} finally {
			downloadingAppSlug = null;
		}
	}

	function requestDeleteApp(app: { slug: string; title: string }) {
		appToDelete = { slug: app.slug, title: app.title };
		deleteAppError = null;
	}

	function closeDeleteAppDialog() {
		if (!deleteAppLoading) {
			appToDelete = null;
			deleteAppError = null;
		}
	}

	async function confirmDeleteApp() {
		if (!appToDelete || deleteAppLoading) return;
		deleteAppError = null;
		deleteAppLoading = true;
		try {
			const base = getApiBase() || '';
			const res = await fetch(`${base}/apps/${appToDelete.slug}`, { method: 'DELETE' });
			if (!res.ok) {
				const d = await res.json().catch(() => ({}));
				throw new Error(
					typeof d?.detail === 'string' ? d.detail : res.status === 404 ? 'App not found' : 'Failed to delete app'
				);
			}
			appToDelete = null;
			invalidate('app:workflow');
		} catch (e) {
			deleteAppError = e instanceof Error ? e.message : 'Failed to delete app';
		} finally {
			deleteAppLoading = false;
		}
	}

	async function deleteWorkflow() {
		if (!workflow) return;
		deleting = true;
		try {
			const apiBase = getApiBase() || '';
			const res = await fetch(`${apiBase}/workflow-definitions/${workflow.id}`, { method: 'DELETE' });
			if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? 'Delete failed');
			goto('/workflows');
		} finally {
			deleting = false;
		}
	}

	async function downloadWorkflowJson() {
		if (!selectedVersion || !workflow) return;
		downloading = true;
		try {
			const apiBase = getApiBase() || '';
			const res = await fetch(`${apiBase}/workflow-versions/${selectedVersion.id}/graph`);
			if (!res.ok) throw new Error('Failed to fetch workflow');
			const graph = await res.json();
			const blob = new Blob([JSON.stringify(graph, null, 2)], { type: 'application/json' });
			const url = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = url;
			a.download = `${workflow.name.replace(/[^\w\s-]/g, '')}-v${selectedVersion.version}.json`;
			a.click();
			URL.revokeObjectURL(url);
		} finally {
			downloading = false;
		}
	}
</script>

{#if !workflow}
	<div class="two-col-page page">
		<div class="panel-left panel-scroll card">
			<p>Workflow not found.</p>
			<a href="/workflows">Back to workflows</a>
		</div>
	</div>
{:else}
	<div class="two-col-page page">
		<aside class="panel-left panel-scroll card">
			<nav class="back-nav">
				<button type="button" class="back-btn secondary" onclick={() => goto('/workflows')}>← Workflows</button>
			</nav>
			<h1>{workflow.name}</h1>
			<p class="muted">Workflow ID: {workflow.id.slice(0, 8)}…</p>

			<section class="section">
				<label for="version-select">Version</label>
				<select
					id="version-select"
					class="version-select"
					value={selectedVersionId ?? ''}
					onchange={(e) => (selectedVersionId = (e.target as HTMLSelectElement).value || null)}
				>
					{#each versions as v}
						<option value={v.id}>v{v.version}</option>
					{/each}
				</select>
			</section>

			<section class="section">
				{#if selectedVersion}
					<dl class="meta-dl">
						<dt>Hash</dt>
						<dd class="hash">{selectedVersion.graph_hash.slice(0, 12)}…</dd>
					</dl>
					<div class="action-buttons">
						<button
							type="button"
							class="btn-primary"
							title="Starts the app wizard"
							onclick={() => goto(`/apps/create?versionId=${selectedVersion.id}`)}
						>Create App</button>
						<button
							type="button"
							class="btn-secondary"
							title="Download current workflow as JSON"
							onclick={downloadWorkflowJson}
							disabled={downloading}
						>{downloading ? 'Downloading…' : 'Download as JSON'}</button>
						<button
							type="button"
							class="btn-danger"
							title="Remove this workflow and its apps. Projects and runs are kept."
							onclick={() => (showDeleteModal = true)}
						>Delete workflow</button>
					</div>
				{/if}
			</section>
		</aside>

		{#if showDeleteModal}
			<div class="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="delete-modal-title">
				<div class="modal-card">
					<h2 id="delete-modal-title">Delete workflow</h2>
					{#if allApps.length > 0}
						<p>This workflow has the following app(s) configured. They will be removed. Projects and run history are not affected.</p>
						<ul class="delete-apps-list">
							{#each allApps as app (app.slug)}
								<li><strong>{app.title}</strong> <span class="muted">/{app.slug}</span></li>
							{/each}
						</ul>
					{:else}
						<p>Remove this workflow? Projects and run history are not affected.</p>
					{/if}
					<p class="modal-hint">This action cannot be undone.</p>
					<div class="modal-actions">
						<button type="button" class="btn-secondary" onclick={() => (showDeleteModal = false)} disabled={deleting}>Cancel</button>
						<button type="button" class="btn-danger" onclick={deleteWorkflow} disabled={deleting}>{deleting ? 'Deleting…' : 'Delete'}</button>
					</div>
				</div>
			</div>
		{/if}

		{#if appToDelete}
			<div
				class="modal-overlay"
				role="dialog"
				aria-modal="true"
				aria-labelledby="delete-app-modal-title"
				onclick={closeDeleteAppDialog}
			>
				<div class="modal-card" onclick={(e) => e.stopPropagation()}>
					<h2 id="delete-app-modal-title">Delete app?</h2>
					<p>
						<strong>{appToDelete.title}</strong> will be removed. No generated data (runs, outputs, or media) is deleted. You can still view run history in projects.
					</p>
					{#if deleteAppError}
						<p class="modal-error">{deleteAppError}</p>
					{/if}
					<div class="modal-actions">
						<button type="button" class="btn-secondary" onclick={closeDeleteAppDialog} disabled={deleteAppLoading}>Cancel</button>
						<button type="button" class="btn-danger" disabled={deleteAppLoading} onclick={confirmDeleteApp}>
							{deleteAppLoading ? '…' : 'Delete'}
						</button>
					</div>
				</div>
			</div>
		{/if}

		<div class="panel-right panel-scroll card">
			<h2>Apps (version {selectedVersion?.version ?? '—'})</h2>
			<div class="app-cards">
				{#each apps as app}
					<article class="app-card">
						<div class="app-card-header">
							<span class="app-title">{app.title}</span>
							<span class="app-slug">/{app.slug}</span>
							{#if app.is_public}
								<span class="badge public">public</span>
							{:else}
								<span class="badge private">private</span>
							{/if}
						</div>
						<button type="button" class="button secondary small" onclick={() => goto(`/apps/${app.slug}/edit`)}>Edit</button>
						<button type="button" class="button small" onclick={() => goto(`/app/${app.slug}`)}>Open</button>
						<button
							type="button"
							class="button secondary small"
							title="Download workflow JSON with this app's default values"
							disabled={downloadingAppSlug === app.slug}
							onclick={() => downloadAppWorkflowWithDefaults(app.slug)}
						>
							{downloadingAppSlug === app.slug ? 'Downloading…' : 'Download workflow (app defaults)'}
						</button>
						<button
							type="button"
							class="button small app-delete-btn"
							aria-label="Delete app"
							title="Delete app"
							onclick={() => requestDeleteApp(app)}
						>X</button>
					</article>
				{:else}
					<p class="muted">No apps for this version. Create one to expose this version as an app.</p>
				{/each}
			</div>
		</div>
	</div>
{/if}

<style>
	.muted {
		color: var(--muted);
		font-size: 0.9rem;
		margin-bottom: 1rem;
	}
	.section {
		margin-bottom: 1.25rem;
	}
	.version-select {
		width: 100%;
		padding: 0.5rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--text);
	}
	.meta-dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0.25rem 1rem;
		font-size: 0.85rem;
		margin-bottom: 1rem;
	}
	.meta-dl dt {
		color: var(--muted);
	}
	.meta-dl dd {
		margin: 0;
	}
	.hash {
		font-family: ui-monospace, monospace;
		word-break: break-all;
	}
	.back-nav {
		margin-bottom: 1rem;
	}
	.back-btn {
		padding: 0.4rem 0.75rem;
		font-size: 0.9rem;
	}
	.btn-primary {
		display: inline-block;
		background: var(--accent);
		color: white;
		border: none;
		cursor: pointer;
		padding: 0.6rem 1rem;
		border-radius: 8px;
		font-weight: 500;
	}
	.btn-primary:hover {
		background: var(--accent-hover);
	}
	.action-buttons {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}
	.btn-secondary {
		display: inline-block;
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
		cursor: pointer;
		padding: 0.6rem 1rem;
		border-radius: 8px;
		font-weight: 500;
	}
	.btn-secondary:hover:not(:disabled) {
		background: var(--accent-soft);
		border-color: var(--accent);
	}
	.btn-secondary:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}
	.btn-danger {
		display: inline-block;
		background: var(--error, #dc2626);
		color: white;
		border: none;
		cursor: pointer;
		padding: 0.6rem 1rem;
		border-radius: 8px;
		font-weight: 500;
	}
	.btn-danger:hover:not(:disabled) {
		opacity: 0.9;
	}
	.btn-danger:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}
	.modal-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}
	.modal-card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 1.5rem;
		max-width: 28rem;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
	}
	.modal-card h2 {
		margin-top: 0;
		margin-bottom: 1rem;
		font-size: 1.25rem;
	}
	.modal-card p {
		margin-bottom: 0.75rem;
	}
	.modal-hint {
		font-size: 0.9rem;
		color: var(--muted);
	}
	.delete-apps-list {
		margin: 0.75rem 0;
		padding-left: 1.25rem;
	}
	.delete-apps-list li {
		margin-bottom: 0.25rem;
	}
	.modal-actions {
		display: flex;
		gap: 0.75rem;
		justify-content: flex-end;
		margin-top: 1.25rem;
	}
	.button.secondary {
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
	}
	.button.small {
		padding: 0.4rem 0.75rem;
		font-size: 0.85rem;
	}
	.app-delete-btn {
		border: 1px solid var(--error, #c55);
		color: var(--error, #c55);
		background: color-mix(in srgb, var(--error, #c55) 12%, transparent);
	}
	.app-delete-btn:hover:not(:disabled) {
		border-color: var(--error, #e55);
		color: var(--error, #e55);
		background: color-mix(in srgb, var(--error, #e55) 20%, transparent);
	}
	.modal-error {
		color: var(--error, #dc2626);
		font-size: 0.9rem;
		margin-bottom: 0.75rem;
	}
	h2 {
		font-size: 1.1rem;
		margin-bottom: 1rem;
	}
	.app-cards {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.app-card {
		padding: 1rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.75rem;
	}
	.app-card-header {
		flex: 1;
		min-width: 0;
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.app-title {
		font-weight: 600;
	}
	.app-slug {
		font-size: 0.9rem;
		color: var(--muted);
	}
	.badge {
		font-size: 0.75rem;
		padding: 0.2rem 0.5rem;
		border-radius: 4px;
	}
	.badge.public {
		background: rgba(34, 197, 94, 0.2);
		color: var(--success);
	}
	.badge.private {
		background: rgba(248, 250, 252, 0.15);
		color: var(--muted);
	}
</style>
