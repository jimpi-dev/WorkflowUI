<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { QUICK_RUNS_PROJECT_ID } from '$lib/constants';
	import { appConfig, getApiBase } from '$lib/config';
	import { waitForAppToBeAvailable } from '$lib/api';
	import { appBooting } from '$lib/stores/appBooting';
	import { authState } from '$lib/stores/auth';
	import { headerAppContext } from '$lib/stores/headerAppContext';
	import { presetHeaderStore, togglePresetHeaderCreation, requestOpenPresetList } from '$lib/stores/presetHeader';
	import { projectSelectorOpen } from '$lib/stores/projectSelectorOpen';
	import PresetIcon from '$lib/components/PresetIcon.svelte';

	let theme = $state('dark');

	onMount(() => {
		if (!browser) return;
		theme =
			document.documentElement.getAttribute('data-theme') ??
			localStorage.getItem('theme') ??
			(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
		document.documentElement.setAttribute('data-theme', theme);
	});

	function toggleTheme() {
		theme = theme === 'dark' ? 'light' : 'dark';
		document.documentElement.setAttribute('data-theme', theme);
		if (browser) localStorage.setItem('theme', theme);
	}

	function handleDividerKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			toggleTheme();
		}
	}

	let menuOpen = $state(false);

	function toggleMenu() {
		menuOpen = !menuOpen;
	}

	function closeMenu() {
		menuOpen = false;
	}

	async function logout() {
		const apiBase = getApiBase().replace(/\/$/, '');
		await fetch(`${apiBase}/auth/logout`, { method: 'POST', credentials: 'include' }).catch(() => {});
		authState.set({ enabled: true, authenticated: false, user: null, loaded: true });
		goto('/login');
	}

	function handleKeydown(e: KeyboardEvent) {
		if (importDialogOpen && e.key === 'Escape') {
			importDialogOpen = false;
			pendingImport = null;
			return;
		}
		if (menuOpen && e.key === 'Escape') closeMenu();
	}

	async function continueLoadingImportedApp() {
		const p = pendingImport;
		importDialogOpen = false;
		pendingImport = null;
		if (!p) return;
		if (p.input_snapshot != null) {
			try {
				sessionStorage.setItem(
					'workflowui_import_prefill',
					JSON.stringify({ slug: p.slug, input_snapshot: p.input_snapshot })
				);
			} catch {
				// ignore
			}
		}
		appBooting.set(true);
		await waitForAppToBeAvailable(p.slug);
		await goto(`/app/${p.slug}`);
	}

	function dismissImportDialog() {
		importDialogOpen = false;
		pendingImport = null;
	}

	let downloadingWorkflow = $state(false);

	let dropZoneMessage = $state('');
	let dropZoneLoading = $state(false);
	let dropZoneDragOver = $state(false);

	type PendingImport = {
		slug: string;
		input_snapshot?: object;
		appName: string;
		workflowName: string;
		isExisting: boolean;
	};
	let importDialogOpen = $state(false);
	let pendingImport = $state<PendingImport | null>(null);

	function isWorkflowuiFile(file: File): boolean {
		if (file.type.startsWith('image/')) return true;
		if (file.type === 'audio/mpeg' || file.type === 'audio/mp3') return true;
		if (file.type.startsWith('video/')) return true;
		const n = file.name.toLowerCase();
		return n.endsWith('.mp3') || n.endsWith('.mp4');
	}

	async function handleDropZoneFile(files: FileList | null) {
		const file = files?.[0];
		if (!file) return;
		if (!isWorkflowuiFile(file)) {
			dropZoneMessage = 'Drop a PNG, MP3, or MP4 saved from WorkflowUI.';
			return;
		}
		dropZoneMessage = '';
		dropZoneLoading = true;
		const apiBase = getApiBase().replace(/\/$/, '');
		try {
			const form = new FormData();
			form.append('file', file);
			const res = await fetch(`${apiBase}/import/from-file`, { method: 'POST', body: form });
			const data = await res.json().catch(() => ({}));
			if (data.action === 'open' && data.app_slug) {
				const slug = data.app_slug;
				const appName = data.app_title ?? data.app_slug ?? 'App';
				const workflowName = data.workflow_name ?? 'Workflow';
				pendingImport = {
					slug,
					input_snapshot:
						data.input_snapshot != null && typeof data.input_snapshot === 'object'
							? data.input_snapshot
							: undefined,
					appName,
					workflowName,
					isExisting: true,
				};
				importDialogOpen = true;
				return;
			}
			if (data.action === 'restored' && data.app_slug) {
				const slug = data.resolved_slug ?? data.app_slug;
				const appName = data.app_title ?? data.resolved_slug ?? data.app_slug ?? 'App';
				const workflowName = data.workflow_name ?? data.resolved_workflow_name ?? 'Workflow';
				pendingImport = {
					slug,
					input_snapshot:
						data.input_snapshot != null && typeof data.input_snapshot === 'object'
							? data.input_snapshot
							: undefined,
					appName,
					workflowName,
					isExisting: false,
				};
				importDialogOpen = true;
				return;
			}
			if (data.action === 'ignored') {
				dropZoneMessage =
					data.reason === 'invalid_snapshot'
						? 'Invalid or corrupted WorkflowUI metadata in this file.'
						: 'No WorkflowUI metadata in this file. Save images, audio, or video from WorkflowUI with metadata on download/save to restore.';
			} else {
				dropZoneMessage = 'Import failed. Try again.';
			}
		} catch (e) {
			dropZoneMessage = e instanceof Error ? e.message : 'Import failed.';
		} finally {
			dropZoneLoading = false;
		}
	}

	async function downloadAppWorkflow() {
		const slug = $headerAppContext.workflowId;
		if (!slug || downloadingWorkflow) return;
		const apiBase = getApiBase().replace(/\/$/, '');
		const url = `${apiBase}/app/${encodeURIComponent(slug)}/workflow/download`;
		downloadingWorkflow = true;
		try {
			const res = await fetch(url);
			if (!res.ok) throw new Error(res.status === 404 ? 'App not found' : 'Download failed');
			const blob = await res.blob();
			const disp = res.headers.get('Content-Disposition');
			const match = disp && /filename="?([^"]+)"?/.exec(disp);
			const filename = match ? match[1].trim() : `${slug}-workflow.json`;
			const a = document.createElement('a');
			a.href = URL.createObjectURL(blob);
			a.download = filename;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(a.href);
		} finally {
			downloadingWorkflow = false;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<header class="app-header-wrap">
	<div class="header-logo-section">
		<div class="header-row logo-container" role="presentation">
			<a href="/" class="logo-link" aria-label="WorkflowUI Home" title="Home">
				<svg
					width="720"
					height="160"
					viewBox="0 0 720 160"
					xmlns="http://www.w3.org/2000/svg"
					class="workflow-logo"
				>
					<style>
						.logo-text {
							fill: var(--text);
							transition: fill 0.25s ease;
						}
						.logo-accent {
							fill: var(--accent);
							transition: fill 0.25s ease;
						}
					</style>
					<text x="60" y="105" font-family="Inter, sans-serif" font-size="88" font-weight="500" class="logo-text">Workflow</text>
					<g
						class="logo-divider-wrap"
						role="button"
						tabindex="0"
						aria-label="Toggle theme"
						onclick={(e) => { e.preventDefault(); e.stopPropagation(); toggleTheme(); }}
						onkeydown={handleDividerKeydown}
					>
						<rect class="logo-divider-hit" x="455" y="30" width="40" height="105" fill="transparent" />
						<rect class="logo-divider" x="473" y="35" width="2" height="100" rx="1" />
					</g>
					<text x="510" y="107" font-family="Inter, sans-serif" font-size="88" font-weight="800" class="logo-accent">UI</text>
				</svg>
			</a>
		</div>
		<nav class="top-nav" aria-label="Main">
			<a href="/" class:active={$page.url.pathname === '/'}>
				<svg class="top-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
				<span>Home</span>
			</a>
			<a href="/projects/{QUICK_RUNS_PROJECT_ID}" class:active={$page.url.pathname === '/projects/' + QUICK_RUNS_PROJECT_ID}>
				<svg class="top-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
				<span>Quick runs</span>
			</a>
			<a href="/projects" data-sveltekit-preload-data="off" class:active={$page.url.pathname === '/projects' || ($page.url.pathname.startsWith('/projects/') && $page.url.pathname !== '/projects/' + QUICK_RUNS_PROJECT_ID)}>
				<svg class="top-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
				<span>Projects</span>
			</a>
			<a href="/apps" data-sveltekit-preload-data="off" class:active={$page.url.pathname === '/apps' || $page.url.pathname.startsWith('/apps/')}>
				<svg class="top-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
				<span>Apps</span>
			</a>
			<a href="/workflows" class:active={$page.url.pathname === '/workflows' || $page.url.pathname.startsWith('/workflows/')}>
				<svg class="top-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
				<span>Workflows</span>
			</a>
			<a href="/import" class:active={$page.url.pathname === '/import'}>
				<svg class="top-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
				<span>Import</span>
			</a>
			{#if $authState.user?.role === 'admin'}
				<a href="/admin/users" class:active={$page.url.pathname.startsWith('/admin/users')}>
					<span>Users</span>
				</a>
			{/if}
			{#if $authState.enabled && $authState.authenticated}
				<a href="/login" onclick={(e) => { e.preventDefault(); logout(); }}>
					<span>Logout</span>
				</a>
			{/if}
		</nav>
		<div class="header-drop-zone-wrap">
			<div
				class="header-drop-zone"
				class:drag-over={dropZoneDragOver}
				role="button"
				tabindex="0"
				aria-label="Drop media here to import WorkflowUI workflow"
				ondragover={(e) => {
					e.preventDefault();
					dropZoneDragOver = true;
				}}
				ondragleave={() => {
					dropZoneDragOver = false;
				}}
				ondrop={(e) => {
					e.preventDefault();
					dropZoneDragOver = false;
					if (!dropZoneLoading) handleDropZoneFile(e.dataTransfer?.files ?? null);
				}}
			>
				<span class="header-drop-zone-label">
					{dropZoneLoading ? 'Importing…' : 'DROP MEDIA HERE'}
				</span>
			</div>
			{#if dropZoneMessage}
				<p class="header-drop-zone-message" role="status">{dropZoneMessage}</p>
			{/if}
		</div>
		<button
			type="button"
			class="nav-toggle"
			aria-label="Open menu"
			aria-expanded={menuOpen}
			onclick={toggleMenu}
		>
			{#if menuOpen}
				<svg class="nav-toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
			{:else}
				<svg class="nav-toggle-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
			{/if}
		</button>
	</div>
	<div class="nav-drawer-backdrop" class:open={menuOpen} role="presentation" onclick={closeMenu}></div>
	<nav class="nav-drawer" class:open={menuOpen} aria-label="Main navigation">
		<a href="/" class:active={$page.url.pathname === '/'} onclick={closeMenu}>Home</a>
		<a href="/projects/{QUICK_RUNS_PROJECT_ID}" class:active={$page.url.pathname === '/projects/' + QUICK_RUNS_PROJECT_ID} onclick={closeMenu}>Quick runs</a>
		<a href="/projects" data-sveltekit-preload-data="off" class:active={$page.url.pathname === '/projects' || ($page.url.pathname.startsWith('/projects/') && $page.url.pathname !== '/projects/' + QUICK_RUNS_PROJECT_ID)} onclick={closeMenu}>Projects</a>
		<a href="/apps" data-sveltekit-preload-data="off" class:active={$page.url.pathname === '/apps' || $page.url.pathname.startsWith('/apps/')} onclick={closeMenu}>Apps</a>
		<a href="/workflows" class:active={$page.url.pathname === '/workflows' || $page.url.pathname.startsWith('/workflows/')} onclick={closeMenu}>Workflows</a>
		<a href="/import" class:active={$page.url.pathname === '/import'} onclick={closeMenu}>Import</a>
	</nav>
	{#if importDialogOpen && pendingImport}
		<div
			class="import-confirm-backdrop"
			role="dialog"
			aria-modal="true"
			aria-labelledby="import-confirm-title"
			tabindex="-1"
			onclick={dismissImportDialog}
			onkeydown={(e) => { if (e.key === 'Escape') dismissImportDialog(); }}
		>
			<div class="import-confirm-dialog" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
				<h2 id="import-confirm-title" class="import-confirm-title">Import successful</h2>
				<p class="import-confirm-desc">The following app and workflow were imported:</p>
				<p class="import-confirm-status">
					{#if pendingImport.isExisting}
						<strong>Existing app</strong> — this matched an existing app and will open it.
					{:else}
						<strong>New app</strong> — a new app was created from this import.
					{/if}
				</p>
				<dl class="import-confirm-meta">
					<dt>App</dt>
					<dd>{pendingImport.appName}</dd>
					<dt>Workflow</dt>
					<dd>{pendingImport.workflowName}</dd>
				</dl>
				<div class="import-confirm-actions">
					<button type="button" class="import-confirm-btn secondary" onclick={dismissImportDialog}>
						Don't load app now
					</button>
					<button type="button" class="import-confirm-btn primary" onclick={continueLoadingImportedApp}>
						Continue loading imported app with values
					</button>
				</div>
			</div>
		</div>
	{/if}
	{#if $headerAppContext.workflowId && $headerAppContext.displayName}
		<div class="header-subtitle-row">
			<div class="header-subtitle-divider" aria-hidden="true"></div>
			<p class="header-subtitle">
				<a
					href="/app/{$headerAppContext.workflowId}"
					class="header-subtitle-app-wrap"
					class:header-subtitle-app-has-color={$headerAppContext.headerColor}
					style={$headerAppContext.headerColor ? `--app-name-color: ${$headerAppContext.headerColor}` : ''}
					aria-label="App: {$headerAppContext.displayName}"
				>
					<svg class="header-subtitle-app-icon" viewBox="0 0 20 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
						<rect x="0" y="8" width="14" height="7" rx="1.25" />
						<rect x="2" y="4" width="14" height="7" rx="1.25" />
						<rect x="4" y="0" width="14" height="7" rx="1.25" />
					</svg>
					<span class="header-subtitle-app">{$headerAppContext.displayName}</span>
				</a>
				{#if $headerAppContext.projectId && $headerAppContext.projectName}
					<span class="header-subtitle-sep" aria-hidden="true"> · </span>
					<span class="header-subtitle-project-chip">
						<a
							href="/projects/{$headerAppContext.projectId}{$page.url.pathname ? '?from=' + encodeURIComponent($page.url.pathname) : ''}"
							class="header-subtitle-project"
							class:header-subtitle-project-has-color={$headerAppContext.projectHeaderColor}
							style={$headerAppContext.projectHeaderColor ? `--project-name-color: ${$headerAppContext.projectHeaderColor}` : ''}
							title="Go to current project (you will leave this app page)"
						>
							{$headerAppContext.projectDetail ? $headerAppContext.projectDetail.name : $headerAppContext.projectName}
							{#if $headerAppContext.projectDetail}
								<span class="header-subtitle-meta">· {$headerAppContext.projectDetail.run_count} run{$headerAppContext.projectDetail.run_count === 1 ? '' : 's'}</span>
								<span class="header-subtitle-meta">· {new Date($headerAppContext.projectDetail.created_at).toLocaleDateString()}</span>
							{/if}
						</a>
						<button
							type="button"
							class="header-switch-project-btn"
							title="Switch project"
							aria-label="Switch project"
							onclick={(e) => { e.preventDefault(); e.stopPropagation(); projectSelectorOpen.set(true); }}
						>
							<svg class="header-switch-project-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								<polyline points="17 1 21 5 17 9"/>
								<line x1="3" y1="5" x2="21" y2="5"/>
								<polyline points="7 23 3 19 7 15"/>
								<line x1="21" y1="19" x2="3" y2="19"/>
							</svg>
						</button>
					</span>
				{/if}
				{#if $headerAppContext.appId}
				<span class="header-preset-buttons">
					<button
						type="button"
						class="header-preset-btn"
						title="Download workflow (with this app's default settings)"
						aria-label="Download workflow"
						disabled={downloadingWorkflow}
						onclick={(e) => { e.preventDefault(); e.stopPropagation(); downloadAppWorkflow(); }}
					>
						{#if downloadingWorkflow}
							<span class="header-download-spinner" aria-hidden="true"></span>
						{:else}
							<svg class="header-download-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
								<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
								<polyline points="7 10 12 15 17 10"/>
								<line x1="12" y1="15" x2="12" y2="3"/>
							</svg>
						{/if}
					</button>
					{#if appConfig.presetsEnabled}
					<button
						type="button"
						class="header-preset-btn"
						aria-pressed={$presetHeaderStore.creationOn}
						title="Create preset"
						onclick={(e) => { e.preventDefault(); e.stopPropagation(); togglePresetHeaderCreation(); }}
					>
						<PresetIcon variant="p-plus" active={$presetHeaderStore.creationOn} size="md" />
					</button>
					<button
						type="button"
						class="header-preset-btn"
						title="Load preset"
						onclick={(e) => { e.preventDefault(); e.stopPropagation(); requestOpenPresetList(); }}
					>
						<PresetIcon variant="p" active={false} size="md" />
					</button>
					{/if}
				</span>
				{/if}
			</p>
		</div>
	{/if}
</header>

<style>
	.app-header-wrap {
		flex-shrink: 0;
		display: flex;
		flex-direction: column;
		background: transparent;
		padding: 0.25rem 1rem 0.1rem 1rem;
	}

	.header-logo-section {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		align-self: flex-start;
		gap: 0.5rem;
	}

	.header-row.logo-container {
		position: relative;
		display: inline-block;
		cursor: default;
		margin-bottom: -28px;
	}

	.logo-link {
		display: block;
		text-decoration: none;
		color: inherit;
	}

	.workflow-logo {
		transform: scale(0.85);
		transform-origin: left top;
	}

	.header-subtitle-row {
		position: relative;
		z-index: 1;
		width: 100%;
		margin-top: 0;
		padding-left: 51px;
	}

	.header-subtitle-divider {
		height: 1px;
		background: var(--muted);
		opacity: 0.4;
		margin-bottom: 0.35rem;
		width: 100%;
	}

	.header-subtitle {
		margin: 0;
		font-family: Inter, sans-serif;
		font-size: 1.0625rem;
		line-height: 1.45;
		letter-spacing: 0.01em;
		color: var(--text);
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.15rem;
	}

	.header-subtitle-app-wrap {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		vertical-align: middle;
		text-decoration: none;
		color: inherit;
		transition: color 0.2s ease;
	}

	a.header-subtitle-app-wrap:hover {
		color: var(--accent);
	}

	a.header-subtitle-app-wrap:hover .header-subtitle-app,
	a.header-subtitle-app-wrap:hover .header-subtitle-app-icon {
		color: var(--accent);
	}

	a.header-subtitle-app-wrap.header-subtitle-app-has-color .header-subtitle-app,
	a.header-subtitle-app-wrap.header-subtitle-app-has-color .header-subtitle-app-icon {
		color: var(--app-name-color, var(--accent));
	}

	a.header-subtitle-app-wrap.header-subtitle-app-has-color:hover .header-subtitle-app,
	a.header-subtitle-app-wrap.header-subtitle-app-has-color:hover .header-subtitle-app-icon {
		color: var(--accent);
	}

	.header-subtitle-app-icon {
		width: 1em;
		height: 1em;
		flex-shrink: 0;
		color: var(--accent);
		opacity: 0.95;
		vertical-align: middle;
	}

	.header-subtitle-app {
		font-weight: 600;
		color: var(--accent);
	}

	.header-subtitle-sep {
		color: var(--muted);
		font-weight: 400;
		user-select: none;
	}

	.header-subtitle-project {
		color: var(--muted);
		text-decoration: none;
		font-weight: 500;
		transition: color 0.2s ease;
	}

	.header-subtitle-project:hover {
		color: var(--accent);
	}

	.header-subtitle-project-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.15rem 0.35rem 0.15rem 0.5rem;
		border-radius: 999px;
		background: color-mix(in srgb, var(--accent) 8%, transparent);
		border: 1px solid transparent;
		transition: background 0.2s ease, border-color 0.2s ease;
	}

	.header-subtitle-project-chip:hover {
		background: color-mix(in srgb, var(--accent) 14%, transparent);
		border-color: color-mix(in srgb, var(--accent) 35%, transparent);
	}

	.header-subtitle-project-chip .header-subtitle-project {
		padding: 0;
	}

	.header-switch-project-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.2rem;
		background: none;
		border: none;
		border-radius: 4px;
		cursor: pointer;
		color: var(--muted);
		opacity: 0.85;
		transition: color 0.2s ease, background 0.2s ease, opacity 0.2s ease;
	}

	.header-switch-project-btn:hover {
		color: var(--accent);
		opacity: 1;
		background: rgba(255, 255, 255, 0.06);
	}

	.header-switch-project-btn:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}

	.header-switch-project-icon {
		width: 1.1rem;
		height: 1.1rem;
		display: block;
	}

	a.header-subtitle-project.header-subtitle-project-has-color {
		color: var(--project-name-color, var(--muted));
	}

	a.header-subtitle-project.header-subtitle-project-has-color:hover {
		color: var(--accent);
	}

	.header-subtitle-meta {
		font-weight: 400;
		white-space: nowrap;
	}

	.header-preset-buttons {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		margin-left: 0.5rem;
	}

	.header-preset-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.2rem;
		background: none;
		border: none;
		border-radius: 4px;
		cursor: pointer;
		color: var(--muted);
		opacity: 0.8;
	}

	.header-preset-btn:hover {
		color: var(--text);
		opacity: 1;
		background: rgba(255, 255, 255, 0.06);
	}

	.header-preset-btn[aria-pressed="true"] {
		color: var(--accent);
		opacity: 1;
	}

	.header-preset-btn:disabled {
		opacity: 0.7;
		cursor: wait;
	}

	.header-download-icon {
		width: 1.25rem;
		height: 1.25rem;
		display: block;
	}

	.header-download-spinner {
		display: block;
		width: 1.25rem;
		height: 1.25rem;
		border: 2px solid var(--muted);
		border-top-color: transparent;
		border-radius: 50%;
		animation: header-spin 0.8s linear infinite;
	}

	@keyframes header-spin {
		to {
			transform: rotate(360deg);
		}
	}

	.top-nav {
		display: flex;
		gap: 1rem;
		align-items: center;
		margin-left: 1rem;
	}

	.top-nav a {
		display: inline-flex;
		align-items: center;
		gap: 0.4rem;
		color: var(--muted);
		text-decoration: none;
		font-size: 1rem;
		font-weight: 500;
		padding: 0.5rem 0.75rem;
		border-radius: 6px;
		transition: color 0.2s ease, background 0.2s ease, transform 0.2s ease;
		transform: translateY(0);
	}

	.top-nav-icon {
		width: 1.125em;
		height: 1.125em;
		flex-shrink: 0;
		transition: transform 0.2s ease;
	}

	.top-nav a:hover {
		color: var(--accent);
		transform: translateY(-1px);
	}

	.top-nav a:hover .top-nav-icon {
		transform: scale(1.08);
	}

	.top-nav a.active {
		color: var(--text);
		background: var(--accent-soft);
	}

	.top-nav a.active:hover {
		color: var(--accent);
	}

	.header-drop-zone-wrap {
		margin-left: auto;
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 0.25rem;
	}
	.header-drop-zone {
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 56px;
		min-width: 160px;
		padding: 0.5rem 1rem;
		border: 2px dotted var(--accent);
		border-radius: 8px;
		background: color-mix(in srgb, var(--accent) 6%, transparent);
		cursor: pointer;
		transition: background 0.15s ease, outline 0.15s ease;
	}
	.header-drop-zone.drag-over {
		background: var(--accent-soft);
		outline: 2px dashed var(--accent);
		outline-offset: 2px;
	}
	.header-drop-zone:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.header-drop-zone-label {
		font-weight: 600;
		font-size: 0.85rem;
		color: var(--accent);
		text-align: center;
	}
	.header-drop-zone-message {
		color: var(--warning, #eab308);
		font-size: 0.8rem;
		margin: 0;
		max-width: 240px;
		text-align: right;
	}

	.import-confirm-backdrop {
		position: fixed;
		inset: 0;
		z-index: 2000;
		background: rgba(0, 0, 0, 0.5);
		backdrop-filter: blur(6px);
		-webkit-backdrop-filter: blur(6px);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 1rem;
	}
	.import-confirm-dialog {
		background: var(--card-bg, var(--surface));
		border-radius: 12px;
		padding: 1.25rem 1.5rem;
		max-width: min(720px, 96vw);
		width: auto;
		box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
	}
	.import-confirm-title {
		margin: 0 0 0.5rem 0;
		font-size: 1.15rem;
		font-weight: 600;
	}
	.import-confirm-desc {
		margin: 0 0 0.75rem 0;
		font-size: 0.95rem;
		color: var(--text-muted, var(--muted));
	}
	.import-confirm-status {
		margin: 0 0 0.75rem 0;
		font-size: 0.9rem;
		color: var(--text-muted, var(--muted));
	}
	.import-confirm-status strong {
		color: var(--accent);
	}
	.import-confirm-meta {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		gap: 0.25rem 1rem;
		margin: 0 0 1.25rem 0;
		font-size: 0.95rem;
	}
	.import-confirm-meta dt {
		margin: 0;
		font-weight: 600;
		color: var(--text);
	}
	.import-confirm-meta dd {
		margin: 0;
		color: var(--text);
		overflow-wrap: anywhere;
	}
	.import-confirm-actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		justify-content: flex-end;
	}
	.import-confirm-btn {
		padding: 0.5rem 1rem;
		border-radius: 8px;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
		border: none;
		transition: filter 0.15s ease, background 0.15s ease;
	}
	.import-confirm-btn.secondary {
		background: color-mix(in srgb, var(--accent) 12%, var(--surface));
		color: var(--text);
	}
	.import-confirm-btn.secondary:hover {
		background: color-mix(in srgb, var(--accent) 18%, var(--surface));
	}
	.import-confirm-btn.primary {
		background: var(--accent);
		color: var(--accent-fg, #fff);
	}
	.import-confirm-btn.primary:hover {
		filter: brightness(1.08);
	}

	.logo-divider-wrap {
		cursor: pointer;
		outline: none;
	}

	.logo-divider {
		transition: fill 0.22s ease, opacity 0.22s ease, filter 0.22s ease, transform 0.15s ease;
		transform-origin: 474px 85px;
	}

	.logo-divider-hit {
		pointer-events: all;
	}

	:global([data-theme="light"]) .logo-divider {
		fill: #9ca3af;
		opacity: 0.88;
	}

	:global([data-theme="light"]) .logo-divider-wrap:hover .logo-divider {
		fill: #6b7280;
		opacity: 1;
	}

	:global(:root) .logo-divider,
	:global([data-theme="dark"]) .logo-divider {
		fill: #14b8a6;
		filter: drop-shadow(0 0 6px rgba(20, 184, 166, 0.35));
		transform: scaleY(1.04);
	}

	:global([data-theme="light"]) .logo-divider {
		transform: scaleY(1);
	}

	:global([data-theme="dark"]) .logo-divider-wrap:hover .logo-divider {
		filter: drop-shadow(0 0 8px rgba(20, 184, 166, 0.45));
	}

	.logo-divider-wrap:active .logo-divider {
		transform: scaleY(0.88);
	}

	:global([data-theme="light"]) .logo-divider-wrap:active .logo-divider {
		transform: scaleY(0.88);
	}

	:global([data-theme="dark"]) .logo-divider-wrap:active .logo-divider {
		transform: scaleY(1.04 * 0.88);
	}

	.logo-divider-wrap:focus-visible {
		outline: 2px solid currentColor;
		outline-offset: 4px;
		border-radius: 2px;
	}

	.nav-toggle {
		display: none;
	}

	.nav-drawer-backdrop,
	.nav-drawer {
		display: none;
	}

	@media (max-width: 639px) {
		.app-header-wrap {
			position: sticky;
			top: 0;
			z-index: 100;
			background: var(--bg);
			padding: 0.2rem 0.5rem 0.1rem;
		}
		.header-logo-section {
			flex-wrap: nowrap;
			width: 100%;
			align-items: center;
		}
		.header-row.logo-container {
			flex: 1;
			min-width: 0;
			margin-bottom: 0;
			height: 5.5rem;
			overflow: hidden;
		}
		.logo-link {
			display: block;
			min-width: 0;
		}
		.workflow-logo {
			transform: scale(0.55);
			transform-origin: left top;
		}
		.nav-toggle {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			width: 40px;
			height: 40px;
			margin-left: auto;
			flex-shrink: 0;
			padding: 0;
			background: var(--surface);
			border: 1px solid var(--border);
			border-radius: 8px;
			color: var(--text);
			cursor: pointer;
		}
		.nav-toggle .nav-toggle-icon {
			width: 20px;
			height: 20px;
		}
		.nav-toggle:hover {
			background: var(--accent-soft);
			border-color: var(--accent);
			color: var(--accent);
		}
		.top-nav {
			display: none;
		}
		.header-drop-zone-wrap {
			display: none;
		}
		.header-subtitle-row {
			padding-left: 0;
		}
		.header-subtitle {
			font-size: 0.9rem;
		}
		.nav-drawer-backdrop {
			display: block;
			position: fixed;
			inset: 0;
			z-index: 9998;
			background: rgba(0, 0, 0, 0.5);
			opacity: 0;
			visibility: hidden;
			transition: opacity 0.2s ease, visibility 0.2s ease;
		}
		.nav-drawer-backdrop.open {
			opacity: 1;
			visibility: visible;
		}
		.nav-drawer {
			display: flex;
			flex-direction: column;
			position: fixed;
			top: 0;
			right: 0;
			width: min(280px, 100vw - 2rem);
			height: 100%;
			z-index: 9999;
			background: var(--card);
			border-left: 1px solid var(--border);
			box-shadow: -8px 0 24px rgba(0, 0, 0, 0.3);
			padding: 1rem 0;
			gap: 0.25rem;
			transform: translateX(100%);
			transition: transform 0.25s ease;
			overflow-y: auto;
		}
		.nav-drawer.open {
			transform: translateX(0);
		}
		.nav-drawer a {
			display: flex;
			align-items: center;
			padding: 0.75rem 1.25rem;
			min-height: 44px;
			color: var(--muted);
			text-decoration: none;
			font-size: 1rem;
			font-weight: 500;
			transition: color 0.2s ease, background 0.2s ease;
		}
		.nav-drawer a:hover {
			color: var(--accent);
			background: var(--accent-soft);
		}
		.nav-drawer a.active {
			color: var(--text);
			background: var(--accent-soft);
		}
	}
</style>
