<script lang="ts">
	import { getApiBase } from '$lib/config';
	import { getContrastForeground } from '$lib/utils/color';

	let {
		open = false,
		sourceProjectId,
		sourceProjectName,
		runIds = [],
		onClose = undefined,
		onMoved = undefined,
	}: {
		open?: boolean;
		sourceProjectId: string;
		sourceProjectName: string;
		runIds?: string[];
		onClose?: (() => void) | undefined;
		onMoved?: ((result: { moved: number }) => void) | undefined;
	} = $props();

	type ProjectSummary = {
		id: string;
		name: string;
		description?: string | null;
		run_count?: number;
		header_color?: string | null;
	};

	let projects = $state<ProjectSummary[]>([]);
	let loading = $state(false);
	let moving = $state(false);
	let searchQuery = $state('');
	let selectedProjectId = $state<string | null>(null);
	let errorMessage = $state<string | null>(null);
	let creatingProject = $state(false);
	let showCreateForm = $state(false);
	let newProjectName = $state('');
	let newProjectHeaderColor = $state<string | null>(null);

	const filteredProjects = $derived.by(() => {
		const q = searchQuery.trim().toLowerCase();
		const list = projects.filter((p) => p.id !== sourceProjectId);
		if (!q) return list;
		return list.filter(
			(p) =>
				(p.name ?? '').toLowerCase().includes(q) ||
				(p.description ?? '').toLowerCase().includes(q)
		);
	});

	const canMove = $derived(
		selectedProjectId != null &&
			selectedProjectId !== sourceProjectId &&
			!moving &&
			runIds.length > 0
	);

	$effect(() => {
		if (!open) {
			searchQuery = '';
			selectedProjectId = null;
			errorMessage = null;
			showCreateForm = false;
			newProjectName = '';
			newProjectHeaderColor = null;
			return;
		}
		loading = true;
		projects = [];
		const apiBase = getApiBase() || '';
		fetch(`${apiBase}/projects?archived=false&limit=200`)
			.then((r) => (r.ok ? r.json() : []))
			.then((list) => {
				projects = Array.isArray(list) ? list : [];
			})
			.catch(() => {
				projects = [];
			})
			.finally(() => {
				loading = false;
			});
	});

	async function createProject() {
		if (creatingProject) return;
		const name = newProjectName.trim() || 'Untitled project';
		creatingProject = true;
		errorMessage = null;
		const apiBase = getApiBase() || '';
		try {
			const res = await fetch(`${apiBase}/projects`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name,
					description: '',
					header_color: newProjectHeaderColor ?? undefined,
				}),
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				errorMessage = err?.detail ?? 'Failed to create project';
				return;
			}
			const project = await res.json();
			projects = [...projects, project];
			selectedProjectId = project.id;
			showCreateForm = false;
			newProjectName = '';
			newProjectHeaderColor = null;
		} finally {
			creatingProject = false;
		}
	}

	async function confirmMove() {
		if (!canMove || !selectedProjectId) return;
		moving = true;
		errorMessage = null;
		const apiBase = getApiBase() || '';
		try {
			const res = await fetch(`${apiBase}/projects/${sourceProjectId}/runs/move`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					run_ids: runIds,
					target_project_id: selectedProjectId,
				}),
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				errorMessage = err?.detail ?? 'Failed to move runs';
				return;
			}
			const result = await res.json();
			onMoved?.(result);
			onClose?.();
		} finally {
			moving = false;
		}
	}

	function handleBackdropClick(e: MouseEvent) {
		if ((e.target as HTMLElement).classList.contains('move-runs-backdrop')) onClose?.();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose?.();
	}

	let searchInputEl = $state<HTMLInputElement | null>(null);
	$effect(() => {
		if (open && !loading && projects.length > 0 && searchInputEl) {
			searchInputEl.focus();
		}
	});
</script>

{#if open}
	<div
		class="move-runs-backdrop"
		role="dialog"
		aria-modal="true"
		aria-labelledby="move-runs-dialog-title"
		aria-describedby="move-runs-dialog-desc"
		tabindex="-1"
		onclick={handleBackdropClick}
		onkeydown={handleKeydown}
	>
		<div class="move-runs-panel" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
			<div class="move-runs-header">
				<div class="move-runs-header-inner">
					<span class="move-runs-header-dot" aria-hidden="true"></span>
					<div class="move-runs-header-text">
						<h2 id="move-runs-dialog-title" class="move-runs-title">Move runs to project</h2>
						<p id="move-runs-dialog-desc" class="move-runs-subtitle">
							Moving {runIds.length} run{runIds.length === 1 ? '' : 's'} from <strong>{sourceProjectName || 'this project'}</strong>. Choose a destination project.
						</p>
					</div>
				</div>
				<button type="button" class="move-runs-close" onclick={onClose} aria-label="Close">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6L6 18M6 6l12 12"/></svg>
				</button>
			</div>
			{#if loading}
				<div class="move-runs-loading">
					<div class="move-runs-spinner" aria-hidden="true"></div>
					<span>Loading projects…</span>
				</div>
			{:else}
				<div class="move-runs-search-wrap">
					<div class="move-runs-search-inner">
						<span class="move-runs-search-icon" aria-hidden="true">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
						</span>
						<input
							type="search"
							class="move-runs-search"
							placeholder="Search projects…"
							aria-label="Search projects"
							bind:value={searchQuery}
							bind:this={searchInputEl}
							autocomplete="off"
						/>
						{#if searchQuery.trim()}
							<button type="button" class="move-runs-search-clear" aria-label="Clear search" onclick={() => (searchQuery = '')}>
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
							</button>
						{/if}
					</div>
				</div>
				{#if errorMessage}
					<p class="move-runs-error" role="alert">{errorMessage}</p>
				{/if}
				{#if showCreateForm}
					<div class="move-runs-create-form">
						<label class="move-runs-create-label">
							<span class="move-runs-create-label-text">Project name</span>
							<input
								type="text"
								class="move-runs-create-input"
								placeholder="New project name"
								bind:value={newProjectName}
								onkeydown={(e) => {
									if (e.key === 'Enter') createProject();
									if (e.key === 'Escape') showCreateForm = false;
								}}
							/>
						</label>
						<label class="move-runs-create-label">
							<span class="move-runs-create-label-text">Header color</span>
							<div class="move-runs-create-color-wrap">
								<input
									type="color"
									class="move-runs-create-color"
									value={newProjectHeaderColor ?? '#6d5dfc'}
									oninput={(e) => (newProjectHeaderColor = (e.currentTarget as HTMLInputElement).value)}
									aria-label="Header color"
								/>
								{#if newProjectHeaderColor}
									<button type="button" class="move-runs-create-color-clear" onclick={() => (newProjectHeaderColor = null)}>Clear</button>
								{/if}
							</div>
						</label>
						<div class="move-runs-create-actions">
							<button type="button" class="move-runs-btn secondary" onclick={() => { showCreateForm = false; newProjectName = ''; newProjectHeaderColor = null; }}>Cancel</button>
							<button type="button" class="move-runs-btn primary" disabled={creatingProject} onclick={() => createProject()}>
								{creatingProject ? 'Creating…' : 'Create and select'}
							</button>
						</div>
					</div>
				{:else}
					<button
						type="button"
						class="move-runs-create-trigger"
						onclick={() => (showCreateForm = true)}
					>
						+ Create new project
					</button>
				{/if}
				{#if filteredProjects.length === 0 && !showCreateForm}
					<div class="move-runs-empty">
						<p>{searchQuery.trim() ? `No projects match "${searchQuery.trim()}".` : 'No other projects. Create one above.'}</p>
					</div>
				{:else if !showCreateForm}
					{#if searchQuery.trim()}
						<p class="move-runs-count">Showing {filteredProjects.length} of {projects.filter((p) => p.id !== sourceProjectId).length} projects</p>
					{/if}
					<ul class="move-runs-list" role="list">
						{#each filteredProjects as project (project.id)}
							{@const contrast = project.header_color ? getContrastForeground(project.header_color) : 'dark'}
							<li>
								<button
									type="button"
									class="move-runs-row"
									class:move-runs-row-selected={selectedProjectId === project.id}
									class:move-runs-row-contrast-light={project.header_color && contrast === 'light'}
									style={project.header_color
										? `--project-color: ${project.header_color}; --project-color-soft: color-mix(in srgb, ${project.header_color} 18%, transparent); --project-color-border: color-mix(in srgb, ${project.header_color} 45%, transparent);`
										: '--project-color: var(--accent); --project-color-soft: var(--accent-soft, rgba(109, 93, 252, 0.12)); --project-color-border: color-mix(in srgb, var(--accent) 45%, transparent);'}
									onclick={() => (selectedProjectId = project.id)}
									title={project.description ?? project.name}
								>
									<span class="move-runs-row-accent" aria-hidden="true"></span>
									<span class="move-runs-row-symbol" aria-hidden="true">
										<span class="move-runs-row-dot" style={project.header_color ? `background: ${project.header_color}` : ''}></span>
									</span>
									<span class="move-runs-row-text">
										<span class="move-runs-row-title">{project.name}</span>
										<span class="move-runs-row-meta">{project.run_count ?? 0} run{(project.run_count ?? 0) === 1 ? '' : 's'}</span>
									</span>
									{#if selectedProjectId === project.id}
										<span class="move-runs-row-check" aria-hidden="true">✓</span>
									{/if}
								</button>
							</li>
						{/each}
					</ul>
				{/if}
				<div class="move-runs-actions">
					<button type="button" class="move-runs-btn secondary" onclick={onClose}>Cancel</button>
					<button
						type="button"
						class="move-runs-btn primary"
						disabled={!canMove}
						onclick={() => confirmMove()}
					>
						{moving ? 'Moving…' : 'Move runs'}
					</button>
				</div>
			{/if}
		</div>
	</div>
{/if}

<style>
	.move-runs-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
		padding: 1.5rem;
		animation: move-runs-fade-in 0.2s ease-out;
	}
	@keyframes move-runs-fade-in {
		from { opacity: 0; }
		to { opacity: 1; }
	}
	.move-runs-panel {
		background: var(--card-bg, var(--card));
		border: 1px solid var(--border);
		border-radius: var(--radius-lg, 14px);
		box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.04);
		max-width: 500px;
		width: 100%;
		max-height: 85vh;
		overflow: hidden;
		display: flex;
		flex-direction: column;
		animation: move-runs-scale-in 0.25s cubic-bezier(0.16, 1, 0.3, 1);
	}
	@media (max-width: 639px) {
		.move-runs-panel {
			width: calc(100vw - 2rem);
			max-width: none;
			max-height: 85vh;
		}
	}
	@keyframes move-runs-scale-in {
		from { opacity: 0; transform: scale(0.96); }
		to { opacity: 1; transform: scale(1); }
	}
	.move-runs-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1.125rem 1.25rem;
		border-bottom: 1px solid var(--border);
		flex-shrink: 0;
		background: linear-gradient(180deg, rgba(255, 255, 255, 0.03) 0%, transparent 100%);
	}
	.move-runs-header-inner {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	.move-runs-header-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--accent);
		flex-shrink: 0;
		opacity: 0.95;
		box-shadow: 0 0 12px color-mix(in srgb, var(--accent) 50%, transparent);
	}
	.move-runs-header-text {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}
	.move-runs-title {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 600;
		color: var(--text);
		letter-spacing: -0.02em;
	}
	.move-runs-subtitle {
		margin: 0;
		font-size: 0.8125rem;
		color: var(--muted);
		font-weight: 400;
	}
	.move-runs-subtitle strong {
		color: var(--text);
	}
	.move-runs-close {
		background: none;
		border: none;
		box-shadow: none;
		padding: 0;
		color: var(--muted);
		width: 28px;
		height: 28px;
		min-width: 28px;
		min-height: 28px;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		border-radius: 6px;
		transition: color 0.15s ease, background 0.15s ease;
	}
	.move-runs-close svg {
		width: 16px;
		height: 16px;
	}
	.move-runs-close:hover {
		color: var(--text);
		background: var(--accent-soft, rgba(255, 255, 255, 0.06));
	}
	.move-runs-close:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.move-runs-loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 2.5rem 1.5rem;
		text-align: center;
		font-size: 0.9375rem;
		color: var(--muted);
	}
	.move-runs-spinner {
		width: 28px;
		height: 28px;
		border: 2px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: move-runs-spin 0.7s linear infinite;
	}
	@keyframes move-runs-spin {
		to { transform: rotate(360deg); }
	}
	.move-runs-search-wrap {
		padding: 0 1.25rem;
		margin-bottom: 0.75rem;
		flex-shrink: 0;
	}
	.move-runs-search-inner {
		position: relative;
		height: 40px;
		display: flex;
		align-items: stretch;
	}
	.move-runs-search-icon {
		position: absolute;
		left: 0.75rem;
		top: 50%;
		transform: translateY(-50%);
		color: var(--muted);
		pointer-events: none;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.move-runs-search {
		flex: 1;
		height: 40px;
		padding: 0 2.25rem 0 2.5rem;
		border: 1px solid var(--border);
		border-radius: 10px;
		background: var(--surface, rgba(255, 255, 255, 0.04));
		color: var(--text);
		font-size: 0.9375rem;
		transition: border-color 0.2s ease, box-shadow 0.2s ease;
	}
	.move-runs-search::placeholder {
		color: var(--muted);
	}
	.move-runs-search:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent);
	}
	.move-runs-search-clear {
		position: absolute;
		right: 0.75rem;
		top: 50%;
		transform: translateY(-50%);
		width: 28px;
		height: 28px;
		padding: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		background: none;
		border: none;
		color: var(--muted);
		cursor: pointer;
		border-radius: 6px;
		transition: color 0.15s ease, background 0.15s ease;
	}
	.move-runs-search-clear:hover {
		color: var(--text);
		background: var(--accent-soft, rgba(255, 255, 255, 0.06));
	}
	.move-runs-error {
		margin: 0 1.25rem 0.75rem;
		padding: 0.5rem 0.75rem;
		background: color-mix(in srgb, var(--error, #e55) 15%, transparent);
		border: 1px solid color-mix(in srgb, var(--error, #e55) 40%, transparent);
		border-radius: 8px;
		font-size: 0.875rem;
		color: var(--error, #e55);
	}
	.move-runs-create-trigger {
		margin: 0 1.25rem 0.75rem;
		padding: 0.5rem 0.75rem;
		font-size: 0.9rem;
		background: none;
		border: 1px dashed var(--border);
		border-radius: 8px;
		color: var(--muted);
		cursor: pointer;
		transition: border-color 0.2s, color 0.2s;
		text-align: left;
	}
	.move-runs-create-trigger:hover {
		border-color: var(--accent);
		color: var(--accent);
	}
	.move-runs-create-form {
		margin: 0 1.25rem 1rem;
		padding: 1rem;
		background: var(--surface, rgba(255, 255, 255, 0.04));
		border: 1px solid var(--border);
		border-radius: 10px;
	}
	.move-runs-create-label {
		display: block;
		margin-bottom: 0.75rem;
	}
	.move-runs-create-label-text {
		display: block;
		font-size: 0.85rem;
		font-weight: 500;
		color: var(--text);
		margin-bottom: 0.35rem;
	}
	.move-runs-create-input {
		width: 100%;
		padding: 0.5rem 0.75rem;
		font-size: 0.95rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--input-bg);
		color: var(--text);
	}
	.move-runs-create-input:focus {
		outline: none;
		border-color: var(--accent);
	}
	.move-runs-create-color-wrap {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.move-runs-create-color {
		width: 2.5rem;
		height: 2.25rem;
		padding: 2px;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--surface);
		cursor: pointer;
	}
	.move-runs-create-color-clear {
		padding: 0.35rem 0.6rem;
		font-size: 0.85rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		color: var(--muted);
		cursor: pointer;
	}
	.move-runs-create-color-clear:hover {
		color: var(--text);
		border-color: var(--accent);
	}
	.move-runs-create-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		margin-top: 1rem;
	}
	.move-runs-count {
		margin: 0 1.25rem 0.5rem;
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.move-runs-list {
		list-style: none;
		margin: 0;
		padding: 0.5rem 1.25rem 1rem;
		overflow-y: auto;
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}
	.move-runs-empty {
		padding: 1.5rem 1.25rem;
		text-align: center;
		font-size: 0.9375rem;
		color: var(--muted);
	}
	.move-runs-row {
		--project-color: var(--accent);
		--project-color-soft: var(--accent-soft, rgba(109, 93, 252, 0.12));
		--project-color-border: color-mix(in srgb, var(--accent) 45%, transparent);
		position: relative;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		width: 100%;
		padding: 0.75rem 1rem;
		background: var(--surface, var(--card));
		border: 1px solid var(--project-color-border);
		border-radius: 10px;
		cursor: pointer;
		text-align: left;
		transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
		box-shadow: none;
	}
	.move-runs-row:hover {
		border-color: var(--project-color);
		background: var(--project-color-soft);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
	}
	.move-runs-row.move-runs-row-selected {
		border-color: var(--project-color);
		background: var(--project-color-soft);
	}
	.move-runs-row:focus-visible {
		outline: 2px solid var(--project-color);
		outline-offset: 2px;
	}
	.move-runs-row-accent {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 3px;
		background: var(--project-color);
		border-radius: 10px 0 0 10px;
		opacity: 0.9;
	}
	.move-runs-row-symbol {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 36px;
		height: 36px;
		border-radius: 8px;
		background: color-mix(in srgb, var(--project-color) 18%, transparent);
	}
	.move-runs-row-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--project-color);
	}
	.move-runs-row-contrast-light .move-runs-row-symbol {
		box-shadow: inset 0 1px 0 rgba(0, 0, 0, 0.08);
	}
	.move-runs-row-text {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}
	.move-runs-row-title {
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--text);
		line-height: 1.25;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.move-runs-row-meta {
		font-size: 0.8125rem;
		color: var(--muted);
	}
	.move-runs-row-check {
		flex-shrink: 0;
		color: var(--accent);
		font-weight: 700;
		font-size: 1rem;
	}
	.move-runs-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.5rem;
		padding: 1rem 1.25rem;
		border-top: 1px solid var(--border);
		flex-shrink: 0;
		background: linear-gradient(0deg, rgba(255, 255, 255, 0.02) 0%, transparent 100%);
	}
	.move-runs-btn {
		padding: 0.5rem 1rem;
		font-size: 0.9rem;
		border-radius: 8px;
		cursor: pointer;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
	}
	.move-runs-btn.secondary:hover {
		background: color-mix(in srgb, var(--accent) 15%, var(--surface));
		border-color: var(--accent);
	}
	.move-runs-btn.primary {
		background: var(--accent);
		color: var(--accent-fg, #fff);
		border-color: var(--accent);
	}
	.move-runs-btn.primary:hover:not(:disabled) {
		filter: brightness(1.1);
	}
	.move-runs-btn.primary:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.move-runs-btn:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
</style>
