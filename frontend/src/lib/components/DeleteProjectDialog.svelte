<script lang="ts">
	import { get } from 'svelte/store';
	import { getApiBase } from '$lib/config';
	import { QUICK_RUNS_PROJECT_ID } from '$lib/constants';
	import { activeProject } from '$lib/stores/activeProject';

	type Option = 'keep_local' | 'keep_remote' | 'archive' | 'delete_all';

	let {
		open = false,
		projectId = '',
		projectName = '',
		hasLocalData = undefined,
		hasRemoteData = undefined,
		onClose = () => {},
		onSuccess = () => {},
	}: {
		open?: boolean;
		projectId: string;
		projectName: string;
		hasLocalData?: boolean;
		hasRemoteData?: boolean;
		onClose?: () => void;
		onSuccess?: () => void;
	} = $props();

	let selectedOption = $state<Option>('archive');
	let loading = $state(false);
	let optionsLoading = $state(false);
	let error = $state<string | null>(null);
	let resolvedHasLocal = $state<boolean>(false);
	let resolvedHasRemote = $state<boolean>(false);

	const isSystemProject = $derived(projectId === QUICK_RUNS_PROJECT_ID);

	const canKeepLocal = $derived(resolvedHasLocal);
	const canKeepRemote = $derived(resolvedHasRemote);

	$effect(() => {
		if (!open || !projectId) return;
		error = null;
		selectedOption = 'archive';
		if (hasLocalData !== undefined && hasRemoteData !== undefined) {
			resolvedHasLocal = hasLocalData;
			resolvedHasRemote = hasRemoteData;
			return;
		}
		optionsLoading = true;
		const base = getApiBase() || '';
		fetch(`${base}/projects/${projectId}`)
			.then((r) => {
				if (!r.ok) throw new Error(r.status === 404 ? 'Project not found' : 'Failed to load project');
				return r.json();
			})
			.then((data: { has_local_data?: boolean; has_remote_data?: boolean }) => {
				resolvedHasLocal = Boolean(data.has_local_data);
				resolvedHasRemote = Boolean(data.has_remote_data);
			})
			.catch((e) => {
				error = e instanceof Error ? e.message : 'Failed to load options';
			})
			.finally(() => {
				optionsLoading = false;
			});
	});

	async function handleSubmit() {
		if (loading) return;
		error = null;
		loading = true;
		const base = getApiBase() || '';
		try {
			if (selectedOption === 'archive') {
				const res = await fetch(`${base}/projects/${projectId}`, {
					method: 'PATCH',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ archived_at: Date.now() }),
				});
				if (!res.ok) {
					const d = await res.json().catch(() => ({}));
					throw new Error(d?.detail ?? 'Failed to archive');
				}
			} else {
				const keep =
					selectedOption === 'keep_local' ? 'local' : selectedOption === 'keep_remote' ? 'remote' : 'none';
				const res = await fetch(`${base}/projects/${projectId}`, {
					method: 'DELETE',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ keep }),
				});
				if (!res.ok) {
					const d = await res.json().catch(() => ({}));
					throw new Error(d?.detail ?? 'Failed to delete project');
				}
			}
			const current = get(activeProject);
			if (current?.id === projectId) {
				activeProject.clear();
			}
			onSuccess();
			onClose();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Something went wrong';
		} finally {
			loading = false;
		}
	}

	function handleBackdropClick() {
		if (!loading) onClose();
	}
</script>

{#if open}
	<div
		class="dialog-backdrop"
		role="dialog"
		aria-modal="true"
		aria-labelledby="delete-project-dialog-title"
		tabindex="-1"
		onclick={handleBackdropClick}
		onkeydown={(e) => { if (e.key === 'Escape') handleBackdropClick(); }}
	>
		<div class="dialog-box delete-dialog" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
			<div class="dialog-header">
				<div class="dialog-icon-wrap" aria-hidden="true">
					<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
						<path d="M3 6h18"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6"/><path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
						<line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>
					</svg>
				</div>
				<h2 id="delete-project-dialog-title" class="dialog-title">Delete or archive project?</h2>
				<p class="dialog-desc">Choose what to do with <strong class="project-name-inline">{projectName || 'this project'}</strong>.</p>
			</div>

			{#if optionsLoading}
				<div class="dialog-loading-wrap">
					<div class="dialog-loading-dots" aria-hidden="true">
						<span class="dialog-loading-dot"></span>
						<span class="dialog-loading-dot"></span>
						<span class="dialog-loading-dot"></span>
					</div>
					<p class="dialog-loading">Loading options…</p>
				</div>
			{:else if error}
				<div class="dialog-error-wrap">
					<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
						<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>
					</svg>
					<p class="dialog-error">{error}</p>
				</div>
			{:else}
				<div class="dialog-options" role="radiogroup" aria-label="Action">
					{#if canKeepLocal}
						<label class="option-row">
							<span class="option-radio-wrap">
								<input type="radio" name="delete-option" value="keep_local" bind:group={selectedOption} />
								<span class="option-radio-dot"></span>
							</span>
							<span class="option-content">
								<span class="option-label">Keep data on this computer</span>
								<span class="option-desc">Saved files stay on disk; project and run history are removed; ComfyUI outputs are deleted.</span>
							</span>
						</label>
					{/if}
					{#if canKeepRemote}
						<label class="option-row">
							<span class="option-radio-wrap">
								<input type="radio" name="delete-option" value="keep_remote" bind:group={selectedOption} />
								<span class="option-radio-dot"></span>
							</span>
							<span class="option-content">
								<span class="option-label">Keep data on ComfyUI</span>
								<span class="option-desc">Outputs stay on ComfyUI; project and run history are removed; saved files on this computer are deleted.</span>
							</span>
						</label>
					{/if}
					<label class="option-row option-row-recommended">
						<span class="option-radio-wrap">
							<input type="radio" name="delete-option" value="archive" bind:group={selectedOption} />
							<span class="option-radio-dot"></span>
						</span>
						<span class="option-content">
							<span class="option-label">Archive project</span>
							<span class="option-desc">Move to Archive. Nothing is deleted; you can restore from the Archive tab.</span>
						</span>
					</label>
					<label class="option-row option-row-danger">
						<span class="option-radio-wrap">
							<input type="radio" name="delete-option" value="delete_all" bind:group={selectedOption} />
							<span class="option-radio-dot"></span>
						</span>
						<span class="option-content">
							<span class="option-label">Delete everything</span>
							<span class="option-desc">Remove project, all run history, saved files, and ComfyUI outputs. This cannot be undone.</span>
						</span>
					</label>
				</div>
			{/if}

			<div class="dialog-actions">
				<button type="button" class="dialog-btn secondary" onclick={onClose} disabled={loading}>
					Cancel
				</button>
				<button
					type="button"
					class="dialog-btn primary"
					class:danger={selectedOption === 'delete_all'}
					disabled={loading || optionsLoading}
					onclick={handleSubmit}
				>
					{loading ? '…' : selectedOption === 'archive' ? 'Archive' : 'Delete project'}
				</button>
			</div>
		</div>
	</div>
{/if}

<style>
	.dialog-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.45);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1.5rem;
		animation: fadeIn 0.2s ease;
	}
	@keyframes fadeIn {
		from { opacity: 0; }
		to { opacity: 1; }
	}
	.dialog-box {
		background: var(--card-bg, var(--card));
		border: 1px solid var(--border);
		border-radius: 16px;
		padding: 0;
		min-width: 340px;
		max-width: 460px;
		box-shadow: 0 24px 48px rgba(0, 0, 0, 0.25), 0 0 0 1px rgba(255, 255, 255, 0.04) inset;
		animation: slideUp 0.25s ease;
	}
	@keyframes slideUp {
		from {
			opacity: 0;
			transform: translateY(12px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
	.delete-dialog {
		max-height: 90vh;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}
	.dialog-header {
		padding: 1.5rem 1.5rem 0.75rem;
		text-align: center;
	}
	.dialog-icon-wrap {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: 48px;
		height: 48px;
		margin-bottom: 1rem;
		border-radius: 12px;
		background: color-mix(in srgb, var(--accent) 18%, var(--surface));
		color: var(--accent);
	}
	.dialog-title {
		margin: 0 0 0.35rem 0;
		font-size: 1.25rem;
		font-weight: 600;
		letter-spacing: -0.02em;
		color: var(--text);
	}
	.dialog-desc {
		margin: 0;
		font-size: 0.9rem;
		color: var(--muted);
		line-height: 1.5;
	}
	.project-name-inline {
		color: var(--text);
		font-weight: 600;
	}
	.dialog-loading-wrap {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.75rem;
		padding: 1.25rem 1.5rem;
	}
	.dialog-loading-dots {
		display: flex;
		gap: 0.4rem;
		align-items: center;
	}
	.dialog-loading-dot {
		width: 6px;
		height: 6px;
		border-radius: 50%;
		background: var(--accent);
		opacity: 0.6;
		animation: pulse 1.2s ease-in-out infinite;
	}
	.dialog-loading-dot:nth-child(2) { animation-delay: 0.2s; }
	.dialog-loading-dot:nth-child(3) { animation-delay: 0.4s; }
	@keyframes pulse {
		0%, 100% { opacity: 0.4; transform: scale(0.95); }
		50% { opacity: 0.9; transform: scale(1); }
	}
	.dialog-loading,
	.dialog-error {
		margin: 0;
		font-size: 0.9rem;
		color: var(--muted);
	}
	.dialog-error-wrap {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 1rem 1.5rem;
		margin: 0 1.5rem;
		border-radius: 10px;
		background: color-mix(in srgb, var(--error, #dc2626) 12%, transparent);
		border: 1px solid color-mix(in srgb, var(--error, #dc2626) 30%, transparent);
	}
	.dialog-error-wrap svg {
		flex-shrink: 0;
		color: var(--error, #dc2626);
	}
	.dialog-error {
		color: var(--error, #dc2626) !important;
	}
	.dialog-options {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 1rem 1.5rem 1.25rem;
		overflow-y: auto;
		max-height: 50vh;
	}
	.option-row {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		cursor: pointer;
		padding: 0.85rem 1rem;
		border: 1px solid var(--border);
		border-radius: 12px;
		background: var(--surface);
		transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
	}
	.option-row:hover {
		border-color: color-mix(in srgb, var(--accent) 40%, var(--border));
		background: color-mix(in srgb, var(--accent) 6%, var(--surface));
	}
	.option-row:has(input:checked) {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 12%, var(--surface));
		box-shadow: 0 0 0 1px var(--accent);
	}
	.option-row-recommended:has(input:checked) {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 14%, var(--surface));
	}
	.option-row-danger:has(input:checked) {
		border-color: color-mix(in srgb, var(--error, #dc2626) 70%, var(--border));
		background: color-mix(in srgb, var(--error, #dc2626) 10%, var(--surface));
		box-shadow: 0 0 0 1px color-mix(in srgb, var(--error, #dc2626) 50%, transparent);
	}
	.option-radio-wrap {
		position: relative;
		flex-shrink: 0;
		width: 20px;
		height: 20px;
		margin-top: 0.15rem;
	}
	.option-radio-wrap input {
		position: absolute;
		inset: 0;
		opacity: 0;
		width: 100%;
		height: 100%;
		cursor: pointer;
		margin: 0;
	}
	.option-radio-dot {
		display: block;
		width: 20px;
		height: 20px;
		border: 2px solid var(--border);
		border-radius: 50%;
		background: var(--card);
		transition: border-color 0.2s, background 0.2s, box-shadow 0.2s;
	}
	.option-row:hover .option-radio-dot,
	.option-radio-wrap input:focus-visible + .option-radio-dot {
		border-color: var(--accent);
	}
	.option-row:has(input:checked) .option-radio-dot {
		border-color: var(--accent);
		border-width: 6px;
		background: var(--card);
		box-shadow: 0 0 0 2px var(--accent);
	}
	.option-row-danger:has(input:checked) .option-radio-dot {
		border-color: var(--error, #dc2626);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--error, #dc2626) 50%, transparent);
	}
	.option-content {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 0;
	}
	.option-label {
		font-weight: 600;
		font-size: 0.9rem;
		color: var(--text);
	}
	.option-desc {
		font-size: 0.8rem;
		color: var(--muted);
		line-height: 1.45;
	}
	.dialog-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		flex-wrap: wrap;
		padding: 1rem 1.5rem 1.5rem;
		border-top: 1px solid var(--border);
		background: color-mix(in srgb, var(--surface) 50%, transparent);
		border-radius: 0 0 16px 16px;
	}
	.dialog-btn {
		padding: 0.55rem 1.15rem;
		font-size: 0.9rem;
		font-weight: 500;
		border-radius: 10px;
		cursor: pointer;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
		transition: border-color 0.2s, background 0.2s, color 0.2s;
	}
	.dialog-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.dialog-btn.secondary:hover:not(:disabled) {
		background: color-mix(in srgb, var(--accent) 12%, var(--surface));
		border-color: var(--accent);
		color: var(--accent);
	}
	.dialog-btn.primary {
		background: var(--accent);
		color: var(--accent-fg, #fff);
		border-color: var(--accent);
	}
	.dialog-btn.primary:hover:not(:disabled) {
		filter: brightness(1.08);
		box-shadow: 0 2px 8px color-mix(in srgb, var(--accent) 40%, transparent);
	}
	.dialog-btn.primary.danger {
		background: var(--error, #dc2626);
		border-color: var(--error, #dc2626);
		color: #fff;
	}
	.dialog-btn.primary.danger:hover:not(:disabled) {
		filter: brightness(1.1);
		box-shadow: 0 2px 8px color-mix(in srgb, var(--error, #dc2626) 40%, transparent);
	}
</style>
