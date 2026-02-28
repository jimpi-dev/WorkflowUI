<script lang="ts">
	import { goto } from '$app/navigation';
	import { getApiBase } from '$lib/config';
	import { appBooting } from '$lib/stores/appBooting';
	import { getContrastForeground } from '$lib/utils/color';

	let {
		open = false,
		sendFromRun,
		sendFromOutput,
		projectId,
		onClose = undefined,
	}: {
		open?: boolean;
		sendFromRun: string;
		sendFromOutput: number;
		projectId: string;
		onClose?: (() => void) | undefined;
	} = $props();

	type AppSummary = {
		id: string;
		slug: string;
		title: string;
		description?: string | null;
		supported_input_kinds?: string[] | null;
		header_color?: string | null;
	};

	let apps = $state<AppSummary[]>([]);
	let loading = $state(false);
	let mediaKind = $state<string | null>(null);
	let searchQuery = $state('');
	let capturedRunId = $state<string | null>(null);
	let capturedOutputIndex = $state<number | null>(null);

	const filteredApps = $derived.by(() => {
		const q = searchQuery.trim().toLowerCase();
		if (!q) return apps;
		return apps.filter(
			(a) =>
				(a.title ?? '').toLowerCase().includes(q) ||
				(a.description ?? '').toLowerCase().includes(q)
		);
	});

	const mediaKindLabel = $derived(mediaKind ? mediaKind.charAt(0).toUpperCase() + mediaKind.slice(1) : null);

	$effect(() => {
		if (open && sendFromRun != null && sendFromOutput != null && String(sendFromRun) !== '' && String(sendFromRun) !== 'null') {
			capturedRunId = String(sendFromRun);
			capturedOutputIndex = Number(sendFromOutput);
		}
		if (!open) {
			capturedRunId = null;
			capturedOutputIndex = null;
			searchQuery = '';
		}
	});
	$effect(() => {
		if (!open || !sendFromRun || sendFromOutput == null) return;
		if (String(sendFromRun) === '' || String(sendFromRun) === 'null') return;
		loading = true;
		apps = [];
		mediaKind = null;
		const apiBase = getApiBase() || '';

		Promise.all([
			fetch(`${apiBase}/apps`).then((r) => (r.ok ? r.json() : [])),
			sendFromRun
				? fetch(`${apiBase}/runs/${sendFromRun}`).then((r) => (r.ok ? r.json() : null))
				: Promise.resolve(null),
		])
			.then(([appsList, run]: [AppSummary[], { media?: { kind?: string; type?: string }[]; images?: { type?: string }[] } | null]) => {
				let list = Array.isArray(appsList) ? appsList : [];
				const outputIndex = Number(sendFromOutput);
				let resolvedKind: string | null = null;
				if (run && !Number.isNaN(outputIndex)) {
					const mediaList = run?.media ?? run?.images;
					if (Array.isArray(mediaList) && outputIndex >= 0 && outputIndex < mediaList.length) {
						const ent = mediaList[outputIndex];
						if (ent && typeof ent === 'object') {
							let raw =
								(ent as { kind?: string }).kind ??
								(ent as { type?: string }).type ??
								'image';
							if ((raw ?? '').toLowerCase() === 'output') raw = 'image';
							resolvedKind = raw;
						}
					}
				}
				mediaKind = resolvedKind;
				if (resolvedKind && list.length > 0) {
					const kindLower = resolvedKind.toLowerCase();
					list = list.filter((a) => {
						const kinds = a.supported_input_kinds;
						if (!kinds || kinds.length === 0) return false;
						return kinds.some((k) => (k ?? '').toLowerCase() === kindLower);
					});
				}
				apps = list;
			})
			.catch(() => {})
			.finally(() => {
				loading = false;
			});
	});

	function openApp(slug: string) {
		onClose?.();
		appBooting.set(true);
		const params = new URLSearchParams();
		const runId = capturedRunId ?? sendFromRun;
		const outputIndex = capturedOutputIndex ?? sendFromOutput;
		if (runId != null && String(runId) !== '' && String(runId) !== 'null' && outputIndex != null && !Number.isNaN(Number(outputIndex))) {
			params.set('send_from_run', String(runId));
			params.set('send_from_output', String(outputIndex));
		}
		if (projectId) params.set('project', projectId);
		goto(`/app/${slug}?${params.toString()}`);
	}

	function handleBackdropClick(e: MouseEvent) {
		if ((e.target as HTMLElement).classList.contains('send-to-app-backdrop')) onClose?.();
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose?.();
	}

	let searchInputEl = $state<HTMLInputElement | null>(null);
	$effect(() => {
		if (open && !loading && apps.length > 0 && searchInputEl) {
			searchInputEl.focus();
		}
	});
</script>

{#if open}
	<div
		class="send-to-app-backdrop"
		role="dialog"
		aria-modal="true"
		aria-label="Send to App"
		tabindex="-1"
		onclick={handleBackdropClick}
		onkeydown={handleKeydown}
	>
		<div class="send-to-app-panel" role="document" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
			<div class="send-to-app-header">
				<div class="send-to-app-header-inner">
					<span class="send-to-app-header-dot" aria-hidden="true"></span>
					<div class="send-to-app-header-text">
						<h2 class="send-to-app-title">Send to App</h2>
						{#if mediaKindLabel}
							<p class="send-to-app-subtitle">Send this {mediaKindLabel.toLowerCase()} to an app</p>
						{/if}
					</div>
				</div>
				<button type="button" class="send-to-app-close" onclick={onClose} aria-label="Close">
					<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6L6 18M6 6l12 12"/></svg>
				</button>
			</div>
			{#if loading}
				<div class="send-to-app-loading">
					<div class="send-to-app-spinner" aria-hidden="true"></div>
					<span>Loading apps…</span>
				</div>
			{:else if apps.length === 0}
				<div class="send-to-app-empty">
					<span class="send-to-app-empty-icon" aria-hidden="true">◇</span>
					<p>No apps available for this output.</p>
					<p class="send-to-app-empty-hint">Edit an app to accept this media type.</p>
				</div>
			{:else}
				<div class="send-to-app-search-wrap">
					<div class="send-to-app-search-inner">
						<span class="send-to-app-search-icon" aria-hidden="true">
							<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
						</span>
						<input
							type="search"
							class="send-to-app-search"
							placeholder="Search apps…"
							aria-label="Search apps"
							bind:value={searchQuery}
							bind:this={searchInputEl}
							autocomplete="off"
						/>
						{#if searchQuery.trim()}
							<button type="button" class="send-to-app-search-clear" aria-label="Clear search" onclick={() => (searchQuery = '')}>
								<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18M6 6l12 12"/></svg>
							</button>
						{/if}
					</div>
				</div>
				{#if filteredApps.length === 0}
					<div class="send-to-app-empty send-to-app-no-results">
						<p>No apps match “{searchQuery.trim()}”.</p>
						<p class="send-to-app-empty-hint">Try a different search.</p>
					</div>
				{:else}
					{#if searchQuery.trim()}
						<p class="send-to-app-count">Showing {filteredApps.length} of {apps.length} apps</p>
					{/if}
					<ul class="send-to-app-list" role="list">
						{#each filteredApps as app (app.id)}
						{@const contrast = app.header_color ? getContrastForeground(app.header_color) : 'dark'}
						<li>
							<button
								type="button"
								class="send-to-app-row"
								class:send-to-app-row-contrast-light={app.header_color && contrast === 'light'}
								style={app.header_color
									? `--app-color: ${app.header_color}; --app-color-soft: color-mix(in srgb, ${app.header_color} 18%, transparent); --app-color-border: color-mix(in srgb, ${app.header_color} 45%, transparent);`
									: '--app-color: var(--accent); --app-color-soft: var(--accent-soft, rgba(109, 93, 252, 0.12)); --app-color-border: color-mix(in srgb, var(--accent) 45%, transparent);'}
								onclick={() => openApp(app.slug)}
								title={app.description ?? app.title}
							>
								<span class="send-to-app-row-accent" aria-hidden="true"></span>
								<span class="send-to-app-row-symbol" aria-hidden="true">
									<span class="send-to-app-row-dot" style={app.header_color ? `background: ${app.header_color}` : ''}></span>
								</span>
								<span class="send-to-app-row-text">
									<span class="send-to-app-row-title">{app.title}</span>
									{#if app.description}
										<span class="send-to-app-row-desc">{app.description}</span>
									{/if}
								</span>
								<span class="send-to-app-row-arrow" aria-hidden="true">
									<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
								</span>
							</button>
						</li>
						{/each}
					</ul>
				{/if}
			{/if}
		</div>
	</div>
{/if}

<style>
	.send-to-app-backdrop {
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
		animation: send-to-app-fade-in 0.2s ease-out;
	}
	@keyframes send-to-app-fade-in {
		from { opacity: 0; }
		to { opacity: 1; }
	}
	.send-to-app-panel {
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
		animation: send-to-app-scale-in 0.25s cubic-bezier(0.16, 1, 0.3, 1);
	}
	@media (max-width: 639px) {
		.send-to-app-panel {
			width: calc(100vw - 2rem);
			max-width: none;
			max-height: 85vh;
		}
	}
	@keyframes send-to-app-scale-in {
		from { opacity: 0; transform: scale(0.96); }
		to { opacity: 1; transform: scale(1); }
	}
	.send-to-app-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1.125rem 1.25rem;
		border-bottom: 1px solid var(--border);
		flex-shrink: 0;
		background: linear-gradient(180deg, rgba(255, 255, 255, 0.03) 0%, transparent 100%);
	}
	.send-to-app-header-inner {
		display: flex;
		align-items: center;
		gap: 0.75rem;
	}
	.send-to-app-header-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--accent);
		flex-shrink: 0;
		opacity: 0.95;
		box-shadow: 0 0 12px color-mix(in srgb, var(--accent) 50%, transparent);
	}
	.send-to-app-header-text {
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}
	.send-to-app-title {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 600;
		color: var(--text);
		letter-spacing: -0.02em;
	}
	.send-to-app-subtitle {
		margin: 0;
		font-size: 0.8125rem;
		color: var(--muted);
		font-weight: 400;
	}
	.send-to-app-close {
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
	.send-to-app-close svg {
		width: 16px;
		height: 16px;
	}
	.send-to-app-close:hover {
		color: var(--text);
		background: var(--accent-soft, rgba(255, 255, 255, 0.06));
		transform: none;
	}
	.send-to-app-close:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.send-to-app-loading {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 1rem;
		padding: 2.5rem 1.5rem;
		text-align: center;
		font-size: 0.9375rem;
		color: var(--muted);
	}
	.send-to-app-spinner {
		width: 28px;
		height: 28px;
		border: 2px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: send-to-app-spin 0.7s linear infinite;
	}
	@keyframes send-to-app-spin {
		to { transform: rotate(360deg); }
	}
	.send-to-app-empty {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
		padding: 2.5rem 1.5rem;
		text-align: center;
		font-size: 0.9375rem;
		color: var(--muted);
	}
	.send-to-app-empty p {
		margin: 0;
	}
	.send-to-app-empty-icon {
		font-size: 1.75rem;
		opacity: 0.5;
		margin-bottom: 0.25rem;
	}
	.send-to-app-empty-hint {
		font-size: 0.8125rem;
		opacity: 0.85;
	}
	.send-to-app-no-results {
		padding: 1.5rem 1.25rem;
	}
	.send-to-app-search-wrap {
		padding: 0 1.25rem;
		margin-bottom: 0.75rem;
		flex-shrink: 0;
	}
	.send-to-app-search-inner {
		position: relative;
		height: 40px;
		display: flex;
		align-items: stretch;
	}
	.send-to-app-search-icon {
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
	.send-to-app-search {
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
	.send-to-app-search::placeholder {
		color: var(--muted);
	}
	.send-to-app-search:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent);
	}
	.send-to-app-search-clear {
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
		box-shadow: none;
		font-weight: inherit;
	}
	.send-to-app-search-clear:hover {
		color: var(--text);
		background: var(--accent-soft, rgba(255, 255, 255, 0.06));
		transform: translateY(-50%);
	}
	.send-to-app-count {
		margin: 0 1.25rem 0.5rem;
		font-size: 0.8125rem;
		color: var(--muted);
		flex-shrink: 0;
	}
	.send-to-app-list {
		list-style: none;
		margin: 0;
		padding: 0.5rem 1.25rem 1.25rem;
		overflow-y: auto;
		min-height: 0;
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}
	.send-to-app-list li {
		margin: 0;
		padding: 0;
	}
	.send-to-app-row {
		--app-color: var(--accent);
		--app-color-soft: var(--accent-soft, rgba(109, 93, 252, 0.12));
		--app-color-border: color-mix(in srgb, var(--accent) 45%, transparent);
		position: relative;
		display: flex;
		align-items: center;
		gap: 0.75rem;
		width: 100%;
		padding: 0.75rem 1rem;
		background: var(--surface, var(--card));
		border: 1px solid var(--app-color-border);
		border-radius: 10px;
		cursor: pointer;
		text-align: left;
		transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
		box-shadow: none;
	}
	.send-to-app-row:hover {
		border-color: var(--app-color);
		background: var(--app-color-soft);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
	}
	.send-to-app-row:focus-visible {
		outline: 2px solid var(--app-color);
		outline-offset: 2px;
	}
	.send-to-app-row-accent {
		position: absolute;
		left: 0;
		top: 0;
		bottom: 0;
		width: 3px;
		background: var(--app-color);
		border-radius: 10px 0 0 10px;
		opacity: 0.9;
	}
	.send-to-app-row-symbol {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 36px;
		height: 36px;
		border-radius: 8px;
		background: color-mix(in srgb, var(--app-color) 18%, transparent);
	}
	.send-to-app-row-dot {
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--app-color);
	}
	.send-to-app-row-contrast-light .send-to-app-row-symbol {
		box-shadow: inset 0 1px 0 rgba(0, 0, 0, 0.08);
	}
	.send-to-app-row-text {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		gap: 0.125rem;
	}
	.send-to-app-row-title {
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--text);
		line-height: 1.25;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.send-to-app-row-desc {
		font-size: 0.8125rem;
		color: var(--muted);
		line-height: 1.25;
		overflow: hidden;
		text-overflow: ellipsis;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
	}
	.send-to-app-row-arrow {
		flex-shrink: 0;
		color: var(--muted);
		opacity: 0.8;
	}
	.send-to-app-row:hover .send-to-app-row-arrow {
		color: var(--app-color);
	}
</style>
