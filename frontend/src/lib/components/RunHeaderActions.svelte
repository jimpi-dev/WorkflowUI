<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { formatBytes } from '$lib/utils/format';

	export type StorageSummary = { label: string; tone: string } | null;

	const STORAGE_TOOLTIPS: Record<string, string> = {
		remote: 'Outputs exist only on the ComfyUI server. Save to copy them to local storage.',
		saved: 'All outputs have been copied to local storage. You can delete remote copies if desired.',
		partial: 'Some outputs were saved to local storage; others are still only on the server.',
		failed: 'Saving to local storage failed for some or all outputs.',
	};

	const TOOLTIP_REMOTE = 'Delete output files on the ComfyUI server only. Local copies (if any) are kept.';
	const TOOLTIP_LOCAL = 'Delete output files from local storage only. Files on ComfyUI server are kept.';
	const TOOLTIP_ALL = 'Delete on remote and local storage.';

	let {
		storageSummary = null,
		localStorageBytes = null as number | null | undefined,
		remoteStorageBytes = null as number | null | undefined,
		status = 'done',
		createdAt = 0,
		timeExtra = '',
		saveDisabled = false,
		saveLoading = false,
		onSave = () => {},
		saveTitle = 'Save run: copy all images in this run to local storage (downloads from ComfyUI)',
		remoteDisabled = false,
		remoteLoading = false,
		onDeleteRemote = () => {},
		remoteTitle = TOOLTIP_REMOTE,
		localDisabled = false,
		localLoading = false,
		onDeleteLocal = () => {},
		localTitle = TOOLTIP_LOCAL,
		allDisabled = false,
		allLoading = false,
		onDeleteAll = () => {},
		allTitle = TOOLTIP_ALL,
		deleteRunDisabled = false,
		deleteRunLoading = false,
		onDeleteRun = undefined as (() => void) | undefined,
		deleteRunTitle = 'Delete run completely (files and record). Works for prompts with or without images.',
		showReplicate = false,
		replicateDisabled = false,
		onReplicate = undefined as (() => void) | undefined,
		replicateTitle = 'Open this app with the same parameters to replicate the run',
		showShowMetadata = false,
		onShowMetadata = undefined as (() => void) | undefined,
		showFullscreenToggle = false,
		fullscreenActive = false,
		onToggleFullscreen = undefined as (() => void) | undefined,
		fullscreenTitle = 'Focus this run in fullscreen (Esc to exit)',
		collapseIcon = '▾',
		hasSelection = false,
	}: {
		storageSummary?: StorageSummary;
		localStorageBytes?: number | null;
		remoteStorageBytes?: number | null;
		status?: string;
		createdAt?: number;
		timeExtra?: string;
		saveDisabled?: boolean;
		saveLoading?: boolean;
		onSave?: () => void;
		saveTitle?: string;
		remoteDisabled?: boolean;
		remoteLoading?: boolean;
		onDeleteRemote?: () => void;
		remoteTitle?: string;
		localDisabled?: boolean;
		localLoading?: boolean;
		onDeleteLocal?: () => void;
		localTitle?: string;
		allDisabled?: boolean;
		allLoading?: boolean;
		onDeleteAll?: () => void;
		allTitle?: string;
		deleteRunDisabled?: boolean;
		deleteRunLoading?: boolean;
		onDeleteRun?: () => void;
		deleteRunTitle?: string;
		showReplicate?: boolean;
		replicateDisabled?: boolean;
		onReplicate?: () => void;
		replicateTitle?: string;
		showShowMetadata?: boolean;
		onShowMetadata?: () => void;
		showFullscreenToggle?: boolean;
		fullscreenActive?: boolean;
		onToggleFullscreen?: () => void;
		fullscreenTitle?: string;
		collapseIcon?: string;
		hasSelection?: boolean;
	} = $props();

	const storageTooltip = $derived(
		storageSummary ? STORAGE_TOOLTIPS[storageSummary.tone] ?? '' : ''
	);
	const collapsed = $derived(collapseIcon === '▸');
	const runActionsAllowed = $derived(status === 'done' || status === 'cancelled');

	let isMobile = $state(false);
	let isMobileResolved = $state(false);

	onMount(() => {
		if (!browser) return;
		const mq = window.matchMedia('(max-width: 639px)');
		const update = () => {
			isMobile = mq.matches;
		};
		update();
		isMobileResolved = true;

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

<div class="run-meta" role="group" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') e.stopPropagation(); }}>
	{#if storageSummary}
		<span
			class="run-storage-badge {storageSummary.tone}"
			title={storageTooltip}
		>
			{storageSummary.label}
			{#if (storageSummary.tone === 'saved' || storageSummary.tone === 'partial') && localStorageBytes != null && localStorageBytes >= 0 && remoteStorageBytes != null && remoteStorageBytes >= 0}
				<span class="run-storage-size"> · Local: {formatBytes(localStorageBytes)} · Remote: {formatBytes(remoteStorageBytes)}</span>
			{:else if (storageSummary.tone === 'saved' || storageSummary.tone === 'partial') && localStorageBytes != null && localStorageBytes >= 0}
				<span class="run-storage-size"> · {formatBytes(localStorageBytes)}</span>
			{:else if remoteStorageBytes != null && remoteStorageBytes >= 0}
				<span class="run-storage-size"> · {formatBytes(remoteStorageBytes)}</span>
			{:else if storageSummary.tone === 'remote'}
				<span class="run-storage-size" aria-hidden="true"> · —</span>
			{/if}
		</span>
	{/if}
	{#if !collapsed}
		{#if isMobileResolved && isMobile}
			<details class="run-actions-menu">
				<summary class="run-kebab-btn" aria-label="Run actions" title="Run actions">
					<!-- Kebab / three dots -->
					<svg class="kebab-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
						<circle cx="12" cy="5" r="1.5" fill="currentColor" stroke="none"/>
						<circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>
						<circle cx="12" cy="19" r="1.5" fill="currentColor" stroke="none"/>
					</svg>
				</summary>

				<div class="run-actions-menu-items" role="menu" aria-label="Run actions">
					<button
						type="button"
						class="run-menu-item-btn"
						class:context-aware={hasSelection}
						disabled={!runActionsAllowed || saveDisabled}
						onclick={(e) => { e.stopPropagation(); onSave(); }}
						title={saveTitle}
						aria-label="Save run"
					>
						{#if saveLoading}
							<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
								<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
							</svg>
						{:else}
							<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
								<path d="M4 4h12l4 4v12H4z"/>
								<path d="M7 4v6h10"/>
								<path d="M7 20v-6h10v6"/>
							</svg>
						{/if}
						<span class="run-menu-item-label">Save</span>
					</button>

					<button
						type="button"
						class="run-menu-item-btn"
						class:context-aware={hasSelection}
						disabled={!runActionsAllowed || remoteDisabled}
						onclick={(e) => { e.stopPropagation(); onDeleteRemote(); }}
						title={remoteTitle}
						aria-label="Delete remote"
					>
						{#if remoteLoading}
							<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
								<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
							</svg>
						{:else}
							<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
								<path d="M3 6h18"/>
								<path d="M8 6V4h8v2"/>
								<path d="M8 6l1 14h6l1-14"/>
							</svg>
						{/if}
						<span class="run-menu-item-label">Remote</span>
					</button>

					<button
						type="button"
						class="run-menu-item-btn"
						class:context-aware={hasSelection}
						disabled={!runActionsAllowed || localDisabled}
						onclick={(e) => { e.stopPropagation(); onDeleteLocal(); }}
						title={localTitle}
						aria-label="Delete local"
					>
						{#if localLoading}
							<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
								<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
							</svg>
						{:else}
							<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
								<path d="M3 6h18"/>
								<path d="M8 6V4h8v2"/>
								<path d="M8 6l1 14h6l1-14"/>
							</svg>
						{/if}
						<span class="run-menu-item-label">Local</span>
					</button>

					<button
						type="button"
						class="run-menu-item-btn"
						class:context-aware={hasSelection}
						disabled={!runActionsAllowed || allDisabled}
						onclick={(e) => { e.stopPropagation(); onDeleteAll(); }}
						title={allTitle}
						aria-label="Delete all"
					>
						{#if allLoading}
							<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
								<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
							</svg>
						{:else}
							<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
								<path d="M3 6h18"/>
								<path d="M8 6V4h8v2"/>
								<path d="M8 6l1 14h6l1-14"/>
								<path d="M5 4l14 16"/>
							</svg>
						{/if}
						<span class="run-menu-item-label">All</span>
					</button>

					{#if showReplicate && onReplicate}
						<button
							type="button"
							class="run-menu-item-btn"
							disabled={replicateDisabled}
							onclick={(e) => { e.stopPropagation(); if (!replicateDisabled) onReplicate(); }}
							title={replicateTitle}
							aria-label="Rerun"
						>
							<span class="run-menu-item-label">Rerun</span>
						</button>
					{/if}

					{#if showShowMetadata && onShowMetadata}
						<button
							type="button"
							class="run-menu-item-btn"
							onclick={(e) => { e.stopPropagation(); onShowMetadata(); }}
							title="Open metadata details"
							aria-label="Metadata"
						>
							<span class="run-menu-item-label">Metadata</span>
						</button>
					{/if}

					{#if showFullscreenToggle && onToggleFullscreen}
						<button
							type="button"
							class="run-menu-item-btn"
							class:context-aware={fullscreenActive}
							onclick={(e) => { e.stopPropagation(); onToggleFullscreen(); }}
							title={fullscreenActive ? 'Exit focused run fullscreen' : fullscreenTitle}
							aria-label={fullscreenActive ? 'Exit focused run fullscreen' : 'Focus this run in fullscreen (Esc to exit)'}
							aria-pressed={fullscreenActive}
						>
							<span class="run-menu-item-label">{fullscreenActive ? 'Exit focus' : 'Focus'}</span>
						</button>
					{/if}

					{#if onDeleteRun}
						<button
							type="button"
							class="run-menu-item-btn run-menu-item-btn-danger"
							disabled={deleteRunDisabled}
							onclick={(e) => { e.stopPropagation(); onDeleteRun(); }}
							title={deleteRunTitle}
							aria-label="Delete run"
						>
							{#if deleteRunLoading}
								<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
									<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
								</svg>
							{:else}
								<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
									<path d="M3 6h18"/>
									<path d="M8 6V4h8v2"/>
									<path d="M8 6l1 14h6l1-14"/>
								</svg>
							{/if}
							<span class="run-menu-item-label">Delete run</span>
						</button>
					{/if}
				</div>
			</details>
		{:else}
			<div class="run-actions">
				<button
					type="button"
					class="run-action-btn"
					class:context-aware={hasSelection}
					disabled={!runActionsAllowed || saveDisabled}
					onclick={(e) => { e.stopPropagation(); onSave(); }}
					title={saveTitle}
					aria-label="Save run"
				>
					{#if saveLoading}
						<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
							<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
						</svg>
					{:else}
						<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
							<path d="M4 4h12l4 4v12H4z"/>
							<path d="M7 4v6h10"/>
							<path d="M7 20v-6h10v6"/>
						</svg>
					{/if}
				</button>
				<button
					type="button"
					class="run-action-btn"
					class:context-aware={hasSelection}
					disabled={!runActionsAllowed || remoteDisabled}
					onclick={(e) => { e.stopPropagation(); onDeleteRemote(); }}
					title={remoteTitle}
					aria-label="Delete remote"
				>
					{#if remoteLoading}
						<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
							<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
						</svg>
					{:else}
						<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
							<path d="M3 6h18"/>
							<path d="M8 6V4h8v2"/>
							<path d="M8 6l1 14h6l1-14"/>
						</svg>
					{/if}
					<span class="run-action-label">Remote</span>
				</button>
				<button
					type="button"
					class="run-action-btn"
					class:context-aware={hasSelection}
					disabled={!runActionsAllowed || localDisabled}
					onclick={(e) => { e.stopPropagation(); onDeleteLocal(); }}
					title={localTitle}
					aria-label="Delete local"
				>
					{#if localLoading}
						<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
							<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
						</svg>
					{:else}
						<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
							<path d="M3 6h18"/>
							<path d="M8 6V4h8v2"/>
							<path d="M8 6l1 14h6l1-14"/>
						</svg>
					{/if}
					<span class="run-action-label">Local</span>
				</button>
				<button
					type="button"
					class="run-action-btn"
					class:context-aware={hasSelection}
					disabled={!runActionsAllowed || allDisabled}
					onclick={(e) => { e.stopPropagation(); onDeleteAll(); }}
					title={allTitle}
					aria-label="Delete all"
				>
					{#if allLoading}
						<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
							<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
						</svg>
					{:else}
						<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
							<path d="M3 6h18"/>
							<path d="M8 6V4h8v2"/>
							<path d="M8 6l1 14h6l1-14"/>
							<path d="M5 4l14 16"/>
						</svg>
					{/if}
					<span class="run-action-label">All</span>
				</button>
			</div>
		{/if}
	{/if}
	<span class="time">
		{new Date(createdAt).toLocaleString()}{timeExtra}
	</span>
	{#if !collapsed && !isMobile && showReplicate && onReplicate}
		<button
			type="button"
			class="run-replicate-btn"
			class:run-replicate-btn-removed={replicateDisabled}
			disabled={replicateDisabled}
			onclick={(e) => { e.stopPropagation(); if (!replicateDisabled) onReplicate(); }}
			title={replicateTitle}
		>
			Rerun
		</button>
	{/if}
	{#if !collapsed && !isMobile && showShowMetadata && onShowMetadata}
		<button type="button" class="run-open-detail-btn" onclick={(e) => { e.stopPropagation(); onShowMetadata(); }}>
			Metadata
		</button>
	{/if}
	{#if !collapsed && !isMobile && showFullscreenToggle && onToggleFullscreen}
		<button
			type="button"
			class="run-action-btn"
			class:context-aware={fullscreenActive}
			onclick={(e) => { e.stopPropagation(); onToggleFullscreen(); }}
			title={fullscreenActive ? 'Exit focused run fullscreen' : fullscreenTitle}
			aria-label={fullscreenActive ? 'Exit focused run fullscreen' : 'Focus this run in fullscreen (Esc to exit)'}
			aria-pressed={fullscreenActive}
		>
			<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
				<path d="M8 3H3v5"/>
				<path d="M16 3h5v5"/>
				<path d="M8 21H3v-5"/>
				<path d="M16 21h5v-5"/>
			</svg>
		</button>
	{/if}
	{#if !collapsed && !isMobile && onDeleteRun}
		<button
			type="button"
			class="run-action-btn delete-run-btn"
			disabled={deleteRunDisabled}
			onclick={(e) => { e.stopPropagation(); onDeleteRun(); }}
			title={deleteRunTitle}
			aria-label="Delete run"
		>
			{#if deleteRunLoading}
				<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
					<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
				</svg>
			{/if}
			<span class="run-action-label">Delete run</span>
		</button>
	{/if}
</div>

<style>
	.run-meta {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem 0.75rem;
		font-size: 0.7rem;
		color: var(--muted);
		flex-shrink: 0;
		min-width: 180px;
	}
	.run-actions {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.run-actions-menu {
		position: relative;
	}
	.run-kebab-btn {
		min-width: 26px;
		height: 26px;
		border-radius: 6px;
		border: 1px solid var(--border);
		background: rgba(0, 0, 0, 0.25);
		color: var(--text);
		display: inline-flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		list-style: none;
		padding: 0 0.35rem;
	}
	.run-kebab-btn:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.run-kebab-btn:hover:not(:disabled) {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 18%, transparent);
		color: var(--accent);
	}
	.kebab-icon {
		width: 18px;
		height: 18px;
	}
	.run-actions-menu-items {
		position: absolute;
		right: 0;
		top: calc(100% + 0.35rem);
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 10px;
		box-shadow: 0 10px 26px rgba(0, 0, 0, 0.25);
		min-width: 190px;
		padding: 0.35rem 0;
		display: flex;
		flex-direction: column;
		gap: 0.1rem;
		z-index: 60;
	}
	.run-actions-menu > summary::-webkit-details-marker {
		display: none;
	}
	.run-menu-item-btn {
		width: 100%;
		border: none;
		background: transparent;
		color: var(--text);
		padding: 0.45rem 0.7rem;
		display: flex;
		align-items: center;
		gap: 0.6rem;
		cursor: pointer;
		transition: background 0.15s ease, color 0.15s ease;
		text-align: left;
	}
	.run-menu-item-btn:hover:not(:disabled) {
		background: var(--accent-soft, rgba(109, 93, 252, 0.12));
		color: var(--accent);
	}
	.run-menu-item-btn:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.run-menu-item-btn:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}
	.run-menu-item-btn.context-aware {
		color: #e6a23c;
	}
	.run-menu-item-btn.context-aware:hover:not(:disabled) {
		color: #f0c674;
	}
	.run-menu-item-btn-danger {
		color: var(--error, #c55);
	}
	.run-menu-item-btn-danger:hover:not(:disabled) {
		color: var(--error, #e55);
		background: color-mix(in srgb, var(--error, #c55) 14%, transparent);
	}
	.run-menu-item-label {
		font-size: 0.9rem;
		font-weight: 600;
	}
	.run-action-btn {
		min-width: 26px;
		height: 26px;
		border-radius: 6px;
		border: 1px solid var(--border);
		background: rgba(0, 0, 0, 0.25);
		color: var(--text);
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 0.25rem;
		padding: 0 0.35rem;
		cursor: pointer;
		transition: border-color 0.15s ease, background 0.15s ease, color 0.15s ease, opacity 0.15s ease;
	}
	.run-action-btn .run-action-label {
		font-size: 0.65rem;
		text-transform: uppercase;
		letter-spacing: 0.03em;
	}
	.run-action-btn:hover:not(:disabled) {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 18%, transparent);
		color: var(--accent);
	}
	.run-action-btn.context-aware {
		border-color: #e6a23c;
		color: #e6a23c;
		background: color-mix(in srgb, #e6a23c 14%, transparent);
	}
	.run-action-btn.context-aware:hover:not(:disabled) {
		border-color: #f0c674;
		color: #f0c674;
		background: color-mix(in srgb, #e6a23c 22%, transparent);
	}
	.run-action-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.run-action-btn.delete-run-btn {
		border-color: var(--error, #c55);
		color: var(--error, #c55);
		background: color-mix(in srgb, var(--error, #c55) 12%, transparent);
		height: auto;
		padding: 0.25rem 0.5rem;
		min-height: unset;
		font-size: 0.8rem;
	}
	.run-action-btn.delete-run-btn .run-action-label {
		font-size: inherit;
		text-transform: none;
	}
	.run-action-btn.delete-run-btn:hover:not(:disabled) {
		border-color: var(--error, #e55);
		color: var(--error, #e55);
		background: color-mix(in srgb, var(--error, #e55) 20%, transparent);
	}
	.run-storage-badge {
		font-size: 0.65rem;
		padding: 0.15rem 0.35rem;
		border-radius: 6px;
		border: 1px solid var(--border);
		background: rgba(0, 0, 0, 0.2);
		color: var(--muted);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.run-storage-badge.saved {
		color: var(--accent);
		border-color: var(--accent);
	}
	.run-storage-badge.partial {
		color: var(--partial-badge);
		border-color: var(--partial-badge);
	}
	.run-storage-badge.failed {
		color: #e57373;
		border-color: #e57373;
	}
	.run-storage-badge.remote {
		color: var(--muted);
	}
	.run-storage-size {
		opacity: 0.9;
	}
	.run-replicate-btn {
		font-size: 0.8rem;
		padding: 0.25rem 0.5rem;
		background: var(--surface, #1c2333);
		color: var(--accent);
		border: 1px solid var(--border);
		border-radius: 6px;
		cursor: pointer;
	}
	.run-replicate-btn:hover {
		background: color-mix(in srgb, var(--accent) 15%, var(--surface));
		border-color: var(--accent);
	}
	.run-replicate-btn-removed {
		opacity: 0.6;
		color: var(--muted);
		cursor: not-allowed;
	}
	.run-replicate-btn-removed:hover {
		background: var(--surface);
		border-color: var(--border);
	}
	.run-open-detail-btn {
		font-size: 0.8rem;
		padding: 0.25rem 0.5rem;
		background: var(--surface, #1c2333);
		color: var(--accent);
		border: 1px solid var(--border);
		border-radius: 6px;
		cursor: pointer;
	}
	.run-open-detail-btn:hover {
		background: color-mix(in srgb, var(--accent) 15%, var(--surface));
		border-color: var(--accent);
	}
	.icon {
		width: 16px;
		height: 16px;
	}
	.icon.spinner {
		animation: run-header-spin 0.9s linear infinite;
	}
	@keyframes run-header-spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}
	@media (max-width: 639px) {
		.run-meta {
			min-width: 0;
			flex: 1 1 100%;
			width: 100%;
			flex-wrap: wrap;
		}
		.run-actions {
			display: flex;
			flex-wrap: wrap;
			gap: 0.35rem;
		}
		.run-action-btn {
			flex-shrink: 0;
		}
	}
</style>
