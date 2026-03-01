<script lang="ts">
	import { onMount } from 'svelte';
	import { getApiBase } from '$lib/config';
	import { goto } from '$app/navigation';
	import { invalidateAll } from '$app/navigation';

	let { data } = $props();
	const apiBase = getApiBase() || '';
	const definitions = $derived(data?.definitions ?? []);

	type DeleteDialogWorkflow = { id: string; name: string; app_count: number };
	/** When set, show delete confirm dialog (0 apps) or hint-only dialog (>0 apps). */
	let deleteDialogWf = $state<DeleteDialogWorkflow | null>(null);
	let deleteLoading = $state(false);
	let deleteError = $state<string | null>(null);

	let isMobile = $state(false);
	onMount(() => {
		const mq = window.matchMedia('(max-width: 639px)');
		const set = () => { isMobile = mq.matches; };
		set();
		mq.addEventListener('change', set);
		return () => mq.removeEventListener('change', set);
	});

	/** Backend stores created_at in milliseconds. Show e.g. "18 Feb 2025, 10:30 AM". */
	function formatImportDate(createdAt: number | null | undefined): string {
		if (createdAt == null || createdAt === 0) return '—';
		const ms = createdAt < 1e12 ? createdAt * 1000 : createdAt;
		try {
			const d = new Date(ms);
			const datePart = d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
			const timePart = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit', hour12: true });
			return `${datePart}, ${timePart}`;
		} catch {
			return '—';
		}
	}

	function downloadUrl(id: string): string {
		const base = apiBase.replace(/\/$/, '');
		return `${base}/workflow-definitions/${id}/download`;
	}

	function openDeleteDialog(wf: { id: string; name: string; app_count?: number | null }) {
		deleteDialogWf = {
			id: wf.id,
			name: wf.name ?? '',
			app_count: wf.app_count ?? 0,
		};
		deleteError = null;
	}

	function closeDeleteDialog() {
		if (!deleteLoading) {
			deleteDialogWf = null;
			deleteError = null;
		}
	}

	const canDeleteWorkflow = $derived(deleteDialogWf ? deleteDialogWf.app_count === 0 : false);

	async function confirmDeleteWorkflow() {
		if (!deleteDialogWf || deleteDialogWf.app_count !== 0 || deleteLoading) return;
		deleteError = null;
		deleteLoading = true;
		try {
			const base = apiBase.replace(/\/$/, '');
			const res = await fetch(`${base}/workflow-definitions/${deleteDialogWf.id}`, { method: 'DELETE' });
			if (res.ok) {
				deleteDialogWf = null;
				deleteError = null;
				await invalidateAll();
			} else {
				const err = await res.json().catch(() => ({}));
				deleteError = typeof err?.detail === 'string' ? err.detail : 'Failed to delete workflow';
			}
		} catch (e) {
			deleteError = e instanceof Error ? e.message : 'Failed to delete workflow';
		} finally {
			deleteLoading = false;
		}
	}
</script>

<div class="workflows-page page">
	<div class="panel-scroll card">
		<div class="page-header">
			<div class="page-title-row">
				<h1>Workflows</h1>
				<button type="button" class="btn-import" onclick={() => goto('/import')}>Import workflow</button>
			</div>
			<p class="muted table-sub">Imported workflow definitions. Open to manage versions and apps, download to export JSON.</p>
		</div>
		{#if definitions.length === 0}
			<p class="empty-state">No imported workflows yet. <a href="/import">Import a workflow</a> to get started.</p>
		{:else if isMobile}
			<div class="workflow-cards">
				{#each definitions as wf}
					<div class="workflow-card">
						<div class="workflow-card-header">
							<a class="table-link" href="/workflows/{wf.id}">{wf.name}</a>
							{#if wf.created_from_image_import}
								<span class="badge-from-image" title="Created from workflow image import">From image</span>
							{/if}
							<span class="table-id">{wf.id.slice(0, 8)}…</span>
						</div>
						<div class="workflow-card-meta">
							<span class="date">{formatImportDate(wf.created_at)}</span>
							<span>Versions: {wf.version_count ?? 0}</span>
							<span>Apps: {wf.app_count ?? 0}</span>
						</div>
						<div class="workflow-card-actions">
							<a class="btn-open" href="/workflows/{wf.id}">Open</a>
							{#if wf.latest_version_id}
								<a class="btn-download" href={downloadUrl(wf.id)} download>Download</a>
							{/if}
							<button type="button" class="btn-delete" onclick={() => openDeleteDialog(wf)} title="Delete workflow">Delete</button>
						</div>
					</div>
				{/each}
			</div>
		{:else}
			<div class="table-wrap">
				<table class="admin-table">
					<thead>
						<tr>
							<th>Workflow</th>
							<th>Import date</th>
							<th class="num">Versions</th>
							<th class="num">Apps</th>
							<th class="actions">Actions</th>
						</tr>
					</thead>
					<tbody>
						{#each definitions as wf}
							<tr>
								<td>
									<a class="table-link" href="/workflows/{wf.id}">{wf.name}</a>
									{#if wf.created_from_image_import}
										<span class="badge-from-image" title="Created from workflow image import">From image</span>
									{/if}
									<span class="table-id">{wf.id.slice(0, 8)}…</span>
								</td>
								<td class="date">{formatImportDate(wf.created_at)}</td>
								<td class="num">{wf.version_count ?? 0}</td>
								<td class="num">{wf.app_count ?? 0}</td>
								<td class="actions">
									<a class="btn-open" href="/workflows/{wf.id}">Open</a>
									{#if wf.latest_version_id}
										<a class="btn-download" href={downloadUrl(wf.id)} download>Download JSON</a>
									{:else}
										<span class="no-download" title="No versions">—</span>
									{/if}
									<button type="button" class="btn-delete" onclick={() => openDeleteDialog(wf)} title="Delete workflow">Delete</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>
	{#if deleteDialogWf}
		<div
			class="dialog-backdrop"
			role="dialog"
			aria-modal="true"
			aria-labelledby="delete-workflow-dialog-title"
			tabindex="-1"
			onclick={closeDeleteDialog}
			onkeydown={(e) => { if (e.key === 'Escape') closeDeleteDialog(); }}
		>
			<div class="dialog-box delete-workflow-dialog" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
				<h2 id="delete-workflow-dialog-title" class="dialog-title">
					{canDeleteWorkflow ? 'Delete workflow?' : 'Cannot delete workflow'}
				</h2>
				{#if canDeleteWorkflow}
					<p class="dialog-desc">
						Delete <strong>{deleteDialogWf.name || 'this workflow'}</strong>? This cannot be undone.
					</p>
				{:else}
					<p class="dialog-desc">
						This workflow has apps based on it, so it cannot be deleted until all its apps have been deleted. Open the workflow to remove apps, or delete them from the <a href="/apps">Apps</a> page.
					</p>
				{/if}
				{#if deleteError}
					<p class="dialog-error">{deleteError}</p>
				{/if}
				<div class="dialog-actions">
					<button type="button" class="dialog-btn secondary" onclick={closeDeleteDialog} disabled={deleteLoading}>
						{canDeleteWorkflow ? 'Cancel' : 'OK'}
					</button>
					{#if canDeleteWorkflow}
						<button
							type="button"
							class="dialog-btn danger"
							disabled={deleteLoading}
							onclick={confirmDeleteWorkflow}
						>
							{deleteLoading ? '…' : 'Delete'}
						</button>
					{/if}
				</div>
			</div>
		</div>
	{/if}
</div>

<style>
	.workflows-page {
		display: flex;
		flex-direction: column;
		min-height: 0;
		width: 100%;
	}
	.workflows-page .panel-scroll.card {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}
	.page-header {
		margin-bottom: 1rem;
	}
	.page-title-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin-bottom: 0.25rem;
	}
	.page-title-row h1 {
		margin: 0;
	}
	.btn-import {
		padding: 0.4rem 0.85rem;
		background: var(--accent);
		color: white;
		border: none;
		border-radius: 6px;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
	}
	.btn-import:hover {
		background: var(--accent-hover);
	}
	.muted {
		color: var(--muted);
		font-size: 0.9rem;
		margin: 0;
	}
	.table-sub {
		margin-top: 0.25rem;
		margin-bottom: 0;
	}
	.empty-state {
		color: var(--muted);
	}
	.empty-state a {
		color: var(--accent);
		text-decoration: none;
	}
	.empty-state a:hover {
		text-decoration: underline;
	}
	.table-wrap {
		overflow-x: auto;
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		background: var(--surface);
	}
	.admin-table {
		width: 100%;
		min-width: 520px;
		border-collapse: collapse;
		font-size: 0.9rem;
	}
	.admin-table th,
	.admin-table td {
		padding: 0.75rem 1rem;
		text-align: left;
		border-bottom: 1px solid var(--border);
	}
	.admin-table th {
		font-weight: 600;
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.03em;
		font-size: 0.75rem;
	}
	.admin-table tbody tr:hover {
		background: rgba(255, 255, 255, 0.02);
	}
	.admin-table .num {
		text-align: right;
		font-variant-numeric: tabular-nums;
	}
	.admin-table .date {
		white-space: nowrap;
		color: var(--muted);
		font-size: 0.85rem;
	}
	.admin-table .actions {
		white-space: nowrap;
	}
	.table-link {
		color: var(--text);
		font-weight: 500;
		text-decoration: none;
	}
	.table-link:hover {
		color: var(--accent);
	}
	.badge-from-image {
		display: inline-block;
		margin-left: 0.5rem;
		padding: 0.15rem 0.45rem;
		font-size: 0.7rem;
		border-radius: 4px;
		background: var(--accent-soft);
		color: var(--accent);
		font-weight: 500;
	}
	.table-id {
		display: block;
		font-size: 0.75rem;
		color: var(--muted);
		font-family: ui-monospace, monospace;
		margin-top: 0.15rem;
	}
	.btn-open,
	.btn-download {
		display: inline-block;
		padding: 0.35rem 0.65rem;
		margin-right: 0.5rem;
		border-radius: 6px;
		font-size: 0.8rem;
		text-decoration: none;
		font-weight: 500;
	}
	.btn-open {
		background: var(--accent-soft);
		color: var(--accent);
		border: 1px solid var(--accent);
	}
	.btn-open:hover {
		background: var(--accent);
		color: white;
	}
	.btn-download {
		background: var(--surface);
		color: var(--text);
		border: 1px solid var(--border);
	}
	.btn-download:hover {
		border-color: var(--accent);
		color: var(--accent);
	}
	.no-download {
		color: var(--muted);
		font-size: 0.85rem;
	}
	.btn-delete {
		padding: 0.35rem 0.65rem;
		margin-left: 0.25rem;
		border-radius: 6px;
		font-size: 0.8rem;
		background: transparent;
		color: var(--muted);
		border: 1px solid var(--border);
		cursor: pointer;
	}
	.btn-delete:hover {
		border-color: var(--warning);
		color: var(--warning);
	}

	/* Mobile card layout: only when isMobile (≤639px); desktop always sees table */
	.workflow-cards {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.workflow-card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: var(--radius-lg);
		padding: 1rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.workflow-card-header {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.35rem;
	}
	.workflow-card-meta {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
		font-size: 0.85rem;
		color: var(--muted);
	}
	.workflow-card-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin-top: 0.25rem;
	}
	.workflow-card-actions .btn-open,
	.workflow-card-actions .btn-download {
		min-height: 44px;
		display: inline-flex;
		align-items: center;
	}
	.workflow-card-actions .btn-delete {
		min-height: 44px;
	}

	/* Delete workflow dialog (same style as DeleteProjectDialog / delete-run-dialog) */
	.dialog-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1rem;
	}
	.dialog-box {
		background: var(--card-bg, var(--card));
		border: 1px solid var(--border);
		border-radius: 12px;
		padding: 1.5rem;
		min-width: 320px;
		max-width: 440px;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
	}
	.delete-workflow-dialog .dialog-desc a {
		color: var(--accent);
		text-decoration: none;
	}
	.delete-workflow-dialog .dialog-desc a:hover {
		text-decoration: underline;
	}
	.dialog-title {
		margin: 0 0 0.5rem 0;
		font-size: 1.2rem;
		color: var(--text);
	}
	.dialog-desc {
		margin: 0 0 1rem 0;
		font-size: 0.9rem;
		color: var(--muted);
	}
	.dialog-error {
		margin: 0 0 1rem 0;
		font-size: 0.9rem;
		color: var(--error, #dc2626);
	}
	.dialog-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.dialog-btn {
		padding: 0.5rem 1rem;
		font-size: 0.9rem;
		border-radius: 8px;
		cursor: pointer;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
	}
	.dialog-btn:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}
	.dialog-btn.secondary:hover:not(:disabled) {
		background: color-mix(in srgb, var(--accent) 15%, var(--surface));
		border-color: var(--accent);
	}
	.dialog-btn.danger {
		background: var(--error, #c55);
		color: white;
		border-color: var(--error, #c55);
	}
	.dialog-btn.danger:hover:not(:disabled) {
		background: var(--error-hover, #e55);
		border-color: var(--error-hover, #e55);
	}
</style>
