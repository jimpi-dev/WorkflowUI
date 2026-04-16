<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { queuePanelOpen } from '$lib/stores/queuePanelOpen';
	import { queuePanelWidth } from '$lib/stores/queuePanelWidth';
	import { getQueueGroupsCollapsedCookie, setQueueGroupsCollapsedCookie, getQueuePanelWidthCookie, setQueuePanelWidthCookie } from '$lib/cookie';
	import {
		getQueue,
		pauseQueue,
		startQueue,
		cancelRun,
		retryRun,
		reorderRun,
		moveRun,
		type QueueResponse,
		type QueueItem,
		type QueueDetailInput
	} from '$lib/queueApi';

	let queue = $state<QueueResponse | null>(null);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let actionLoading = $state<Set<string>>(new Set());
	let collapseAllByDefault = $state(getQueueGroupsCollapsedCookie());
	let collapsedGroups = $state<Set<string>>(new Set());
	let prevQueueGroupKeys = $state<string | undefined>(undefined);

	const POLL_MS = 2500;
	const QUEUE_PANEL_MIN_WIDTH = 280;
	const QUEUE_PANEL_MAX_WIDTH_RATIO = 0.33;
	let pollId: ReturnType<typeof setInterval> | null = null;

	let resizing = $state(false);
	let selectedRunId = $state<string | null>(null);
	let expandedDetailsRunId = $state<string | null>(null);
	let hoveredRunId = $state<string | null>(null);
	let hoverPreviewVisibleForRunId = $state<string | null>(null);
	let hoverTimer: ReturnType<typeof setTimeout> | null = null;
	let draggedGroupKey = $state<string | null>(null);

	function getQueuePanelMaxWidthPx(): number {
		if (typeof window === 'undefined') return 600;
		return Math.floor(window.innerWidth * QUEUE_PANEL_MAX_WIDTH_RATIO);
	}

	function clampPanelWidth(w: number): number {
		const maxPx = getQueuePanelMaxWidthPx();
		return Math.max(QUEUE_PANEL_MIN_WIDTH, Math.min(maxPx, w));
	}

	function startResize(e: MouseEvent) {
		e.preventDefault();
		resizing = true;
		const startX = e.clientX;
		const startW = $queuePanelWidth;
		function onMove(ev: MouseEvent) {
			const delta = startX - ev.clientX;
			queuePanelWidth.set(clampPanelWidth(startW + delta));
		}
		function onUp() {
			resizing = false;
			setQueuePanelWidthCookie($queuePanelWidth);
			document.removeEventListener('mousemove', onMove);
			document.removeEventListener('mouseup', onUp);
		}
		document.addEventListener('mousemove', onMove);
		document.addEventListener('mouseup', onUp);
	}

	async function fetchQueue() {
		try {
			queue = await getQueue();
			error = null;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load queue';
			queue = null;
		} finally {
			loading = false;
		}
	}

	function startPolling() {
		if (pollId) return;
		pollId = setInterval(fetchQueue, POLL_MS);
	}

	function stopPolling() {
		if (pollId) {
			clearInterval(pollId);
			pollId = null;
		}
	}

	$effect(() => {
		if ($queuePanelOpen) {
			loading = true;
			fetchQueue();
			startPolling();
		} else {
			stopPolling();
		}
	});

	$effect(() => {
		const groups = queuedByGroup;
		const keys = groups.map((g) => g.groupKey).sort().join(',');
		const prevKeys = prevQueueGroupKeys;
		prevQueueGroupKeys = keys;
		if (keys && keys !== prevKeys && collapseAllByDefault && groups.length > 0) {
			collapsedGroups = new Set(groups.map((g) => g.groupKey));
		}
	});

	function onWindowResize() {
		queuePanelWidth.set(clampPanelWidth($queuePanelWidth));
	}

	onMount(() => {
		collapseAllByDefault = getQueueGroupsCollapsedCookie();
		queuePanelWidth.set(clampPanelWidth(getQueuePanelWidthCookie()));
		if (typeof window !== 'undefined') {
			window.addEventListener('resize', onWindowResize);
		}
	});

	onDestroy(() => {
		if (typeof window !== 'undefined') {
			window.removeEventListener('resize', onWindowResize);
		}
		if (hoverTimer) clearTimeout(hoverTimer);
		stopPolling();
	});

	function closePanel() {
		queuePanelOpen.set(false);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			if (hoverPreviewVisibleForRunId) hoverPreviewVisibleForRunId = null;
			else if (expandedDetailsRunId) expandedDetailsRunId = null;
			else closePanel();
		}
	}

	function displayValue(value: unknown): string {
		if (value == null || value === '') return 'Not provided';
		if (typeof value === 'boolean') return value ? 'Enabled' : 'Disabled';
		if (typeof value === 'string') return value;
		if (typeof value === 'number') return String(value);
		if (Array.isArray(value)) return value.length ? value.map((v) => String(v)).join(', ') : '[]';
		if (typeof value === 'object') {
			try {
				return JSON.stringify(value);
			} catch {
				return '[Object]';
			}
		}
		return String(value);
	}

	function previewInputs(item: QueueItem): QueueDetailInput[] {
		const groups = item.details?.groups;
		if (!groups) return [];
		const ordered = [...groups.core, ...groups.numeric, ...groups.text, ...groups.boolean, ...groups.media, ...groups.other];
		return ordered.slice(0, 5);
	}

	function detailGroups(item: QueueItem): Array<{ title: string; key: keyof NonNullable<QueueItem['details']>['groups']; items: QueueDetailInput[] }> {
		const groups = item.details?.groups;
		if (!groups) return [];
		return [
			{ title: 'Core', key: 'core', items: groups.core },
			{ title: 'Text', key: 'text', items: groups.text },
			{ title: 'Numeric', key: 'numeric', items: groups.numeric },
			{ title: 'Boolean', key: 'boolean', items: groups.boolean },
			{ title: 'Media', key: 'media', items: groups.media },
			{ title: 'Other', key: 'other', items: groups.other }
		].filter((g) => g.items.length > 0);
	}

	function onItemHoverStart(runId: string) {
		hoveredRunId = runId;
		if (expandedDetailsRunId === runId) return;
		if (hoverTimer) clearTimeout(hoverTimer);
		hoverTimer = setTimeout(() => {
			if (hoveredRunId === runId) hoverPreviewVisibleForRunId = runId;
		}, 220);
	}

	function onItemHoverEnd(runId: string) {
		if (hoveredRunId === runId) hoveredRunId = null;
		if (hoverTimer) {
			clearTimeout(hoverTimer);
			hoverTimer = null;
		}
		if (hoverPreviewVisibleForRunId === runId && expandedDetailsRunId !== runId) hoverPreviewVisibleForRunId = null;
	}

	function toggleDetails(runId: string) {
		if (expandedDetailsRunId === runId) {
			expandedDetailsRunId = null;
			return;
		}
		expandedDetailsRunId = runId;
		hoverPreviewVisibleForRunId = null;
	}

	async function onPause() {
		try {
			await pauseQueue();
			await fetchQueue();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Pause failed';
		}
	}

	async function onStart() {
		try {
			await startQueue();
			await fetchQueue();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Start failed';
		}
	}

	async function onCancel(runId: string) {
		actionLoading = new Set([...actionLoading, runId]);
		try {
			await cancelRun(runId);
			await fetchQueue();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Cancel failed';
		} finally {
			actionLoading = new Set([...actionLoading].filter((id) => id !== runId));
		}
	}

	async function onRetry(runId: string) {
		actionLoading = new Set([...actionLoading, runId]);
		try {
			await retryRun(runId);
			await fetchQueue();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Retry failed';
		} finally {
			actionLoading = new Set([...actionLoading].filter((id) => id !== runId));
		}
	}

	async function onReorder(runId: string, direction: 'up' | 'down') {
		actionLoading = new Set([...actionLoading, `${runId}-${direction}`]);
		try {
			await reorderRun(runId, direction);
			await fetchQueue();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Reorder failed';
		} finally {
			actionLoading = new Set([...actionLoading].filter((id) => id !== `${runId}-${direction}`));
		}
	}

	async function onMoveRun(runId: string, newPosition: number) {
		actionLoading = new Set([...actionLoading, `${runId}-move`]);
		try {
			await moveRun(runId, newPosition);
			await fetchQueue();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Move failed';
		} finally {
			actionLoading = new Set([...actionLoading].filter((id) => id !== `${runId}-move`));
		}
	}

	async function onRemoveGroup(group: { items: QueueItem[] }) {
		for (const item of group.items) {
			try {
				await cancelRun(item.run_id);
			} catch {
				// continue with rest
			}
		}
		await fetchQueue();
	}

	const CLEAR_QUEUE_MESSAGE =
		'Clear the entire queue? All queued and running generations will be cancelled and cannot be recovered.';

	async function onClearQueue() {
		if (!hasItems) return;
		if (!confirm(CLEAR_QUEUE_MESSAGE)) return;
		const runIds: string[] = [];
		if (queue?.running?.run_id) runIds.push(queue.running.run_id);
		for (const item of queue?.queued ?? []) {
			runIds.push(item.run_id);
		}
		for (const runId of runIds) {
			try {
				await cancelRun(runId);
			} catch {
				// continue with rest
			}
		}
		await fetchQueue();
	}

	let draggedRunId = $state<string | null>(null);
	let dropTargetRunId = $state<string | null>(null);
	let dropTargetGroupKey = $state<string | null>(null);

	function flatQueuedRunIds(): string[] {
		return (queue?.queued ?? []).map((q) => q.run_id);
	}

	const DRAG_TYPE_RUN = 'run';
	const DRAG_TYPE_GROUP = 'group';

	function handleDragStart(e: DragEvent, runId: string) {
		draggedRunId = runId;
		draggedGroupKey = null;
		if (e.dataTransfer) {
			e.dataTransfer.setData('application/x-queue-drag-type', DRAG_TYPE_RUN);
			e.dataTransfer.setData('text/plain', runId);
			e.dataTransfer.effectAllowed = 'move';
		}
	}

	function handleGroupDragStart(e: DragEvent, groupKey: string, runIds: string[]) {
		e.stopPropagation();
		draggedRunId = null;
		draggedGroupKey = groupKey;
		if (e.dataTransfer) {
			e.dataTransfer.setData('application/x-queue-drag-type', DRAG_TYPE_GROUP);
			e.dataTransfer.setData('application/x-queue-drag-group-key', groupKey);
			e.dataTransfer.setData('application/x-queue-drag-run-ids', JSON.stringify(runIds));
			e.dataTransfer.effectAllowed = 'move';
		}
	}

	function handleDragEnd() {
		draggedRunId = null;
		draggedGroupKey = null;
		dropTargetRunId = null;
		dropTargetGroupKey = null;
	}

	function handleDragOver(e: DragEvent, runId: string) {
		if (draggedGroupKey) return;
		e.preventDefault();
		e.dataTransfer!.dropEffect = 'move';
		if (draggedRunId && draggedRunId !== runId) {
			dropTargetRunId = runId;
		}
	}

	function handleGroupHeaderDragOver(e: DragEvent, groupKey: string) {
		e.preventDefault();
		e.dataTransfer!.dropEffect = 'move';
		if (draggedGroupKey) {
			if (groupKey !== draggedGroupKey) dropTargetGroupKey = groupKey;
		} else {
			handleDragOver(e, queuedByGroup.find((g) => g.groupKey === groupKey)?.items[0]?.run_id ?? '');
		}
	}

	function handleGroupHeaderDragLeave() {
		dropTargetGroupKey = null;
	}

	function handleDragLeave() {
		/* Only clear in drop/dragend so highlight doesn't flicker when moving between items */
	}

	async function handleDrop(e: DragEvent, targetRunId: string, isGroupHeader = false) {
		e.preventDefault();
		dropTargetRunId = null;
		dropTargetGroupKey = null;
		const type = e.dataTransfer?.getData('application/x-queue-drag-type');
		if (type === DRAG_TYPE_GROUP && !isGroupHeader) return;
		const ids = flatQueuedRunIds();
		const targetIdx = ids.indexOf(targetRunId);
		if (targetIdx === -1) return;
		const targetPosition = targetIdx + 1;

		if (type === DRAG_TYPE_GROUP) {
			const runIdsJson = e.dataTransfer?.getData('application/x-queue-drag-run-ids');
			if (!runIdsJson) return;
			let runIds: string[];
			try {
				runIds = JSON.parse(runIdsJson) as string[];
			} catch {
				return;
			}
			if (!runIds.length) return;
			for (let i = 0; i < runIds.length; i++) {
				await moveRun(runIds[i], targetPosition + i);
			}
			await fetchQueue();
		} else {
			const runId = e.dataTransfer?.getData('text/plain');
			if (!runId || runId === targetRunId) return;
			await onMoveRun(runId, targetPosition);
		}
	}

	function summaryLine(item: QueueItem): string {
		const s = item.summary;
		if (!s) return '';
		const parts: string[] = [];
		if (s.latent_resolution) parts.push(s.latent_resolution);
		if (s.seed != null) parts.push(`Seed ${s.seed}`);
		if (s.key_inputs?.length) {
			parts.push(...s.key_inputs.slice(0, 2).map((k) => `${k.label}: ${k.value}`));
		}
		return parts.join(' · ');
	}

	function toggleGroup(groupKey: string) {
		collapsedGroups = new Set(collapsedGroups);
		if (collapsedGroups.has(groupKey)) collapsedGroups.delete(groupKey);
		else collapsedGroups.add(groupKey);
	}

	function setCollapseAll(collapsed: boolean) {
		collapseAllByDefault = collapsed;
		setQueueGroupsCollapsedCookie(collapsed);
		if (collapsed) {
			collapsedGroups = new Set(queuedByGroup.map((g) => g.groupKey));
		} else {
			collapsedGroups = new Set();
		}
	}

	const totalCount = $derived(
		queue ? (queue.running ? 1 : 0) + (queue.queued?.length ?? 0) : 0
	);
	const hasItems = $derived(totalCount > 0);

	type QueuedGroup = { groupKey: string; appTitle: string; appHeaderColor: string | null; projectId: string | null; projectTitle: string | null; items: QueueItem[] };
	const queuedByGroup = $derived.by((): QueuedGroup[] => {
		const list = queue?.queued ?? [];
		const map = new Map<string, QueueItem[]>();
		for (const item of list) {
			const key = item.run_group_id ?? item.run_id;
			if (!map.has(key)) map.set(key, []);
			map.get(key)!.push(item);
		}
		return Array.from(map.entries()).map(([groupKey, items]) => ({
			groupKey,
			appTitle: items[0]?.app_title ?? items[0]?.app_slug ?? 'Run',
			appHeaderColor: items[0]?.app_header_color ?? null,
			projectId: items[0]?.project_id ?? null,
			projectTitle: items[0]?.project_title ?? null,
			items
		}));
	});
</script>

<!-- Panel: in-flow layout column, no fixed positioning; width is applied by layout via queuePanelWidth store -->
<div
	class="queue-panel"
	class:resizing
	role="dialog"
	aria-labelledby="queue-panel-title"
	aria-modal="false"
	onkeydown={handleKeydown}
>
	<div
		class="queue-panel-resize-handle"
		role="separator"
		aria-valuenow={$queuePanelWidth}
		aria-valuemin={QUEUE_PANEL_MIN_WIDTH}
		aria-valuemax={getQueuePanelMaxWidthPx()}
		aria-label="Resize queue panel"
		onmousedown={startResize}
	></div>
	<button
		type="button"
		class="queue-panel-collapse-tab"
		onclick={closePanel}
		title="Close queue panel"
		aria-label="Close queue panel"
	>
		<span class="queue-panel-collapse-icon" aria-hidden="true">
			<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
				<rect x="2" y="5" width="20" height="14" rx="2"/>
				<path d="M2 10h20"/>
			</svg>
		</span>
		<span class="queue-panel-collapse-count">{totalCount || '0'}</span>
	</button>
	<div class="queue-panel-inner">
		<header class="queue-panel-header">
			<div class="queue-panel-header-top">
				<h2 id="queue-panel-title" class="queue-panel-title">Run queue</h2>
				<span class="queue-panel-summary">
					{#if hasItems}
						<span class="queue-panel-total">{totalCount} generation{totalCount === 1 ? '' : 's'}</span>
						{#if queue?.processing_halted}
							<span class="queue-panel-halted">· Paused</span>
						{/if}
						{#if queue?.running}
							· 1 running
						{/if}
						{#if (queue?.queued?.length ?? 0) > 0}
							{queue.queued.length} queued
						{/if}
					{:else if !loading}
						Empty
					{/if}
				</span>
			</div>
			<div class="queue-panel-actions">
				{#if queuedByGroup.length > 0}
					<button
						type="button"
						class="queue-btn queue-btn-text"
						onclick={() => setCollapseAll(!collapseAllByDefault)}
						title={collapseAllByDefault ? 'Expand all groups' : 'Collapse all groups'}
					>
						{collapseAllByDefault ? 'Expand all' : 'Collapse all'}
					</button>
				{/if}
				{#if hasItems}
					<button
						type="button"
						class="queue-btn queue-btn-danger-outline"
						onclick={onClearQueue}
						title="Clear entire queue (all queued and running will be cancelled)"
					>
						Clear queue
					</button>
					{#if queue?.processing_halted}
						<button
							type="button"
							class="queue-btn queue-btn-primary"
							onclick={onStart}
							title="Start sending jobs to ComfyUI"
						>
							Start queue processing
						</button>
					{:else}
						<button
							type="button"
							class="queue-btn queue-btn-secondary"
							onclick={onPause}
							title="Pause: stop current run and do not start more"
						>
							Pause
						</button>
					{/if}
				{/if}
				<button type="button" class="queue-btn queue-btn-close" onclick={closePanel} aria-label="Close">×</button>
			</div>
		</header>
		{#if error}
			<p class="queue-error" role="alert">{error}</p>
		{/if}
		<div class="queue-panel-body">
			{#if loading && !queue}
				<p class="queue-loading">Loading queue…</p>
			{:else}
				{#if queue?.running}
					<section class="queue-section">
						<h3 class="queue-section-title">Currently running</h3>
						<div
							class="queue-item queue-item-running"
							class:details-expanded={expandedDetailsRunId === queue.running.run_id}
							style={queue.running.app_header_color
								? `--app-badge-color: ${queue.running.app_header_color}`
								: ''}
							onmouseenter={() => onItemHoverStart(queue.running!.run_id)}
							onmouseleave={() => onItemHoverEnd(queue.running!.run_id)}
						>
							<span class="queue-item-pos">#1</span>
							<span class="queue-item-app-badge">{queue.running.app_title ?? queue.running.app_slug ?? 'Run'}</span>
							<span class="queue-item-status">Generating…</span>
							{#if queue.running.summary}
								<span class="queue-item-summary">{summaryLine(queue.running)}</span>
							{/if}
							<button
								type="button"
								class="queue-item-btn queue-item-btn-details"
								onclick={() => toggleDetails(queue.running!.run_id)}
								aria-expanded={expandedDetailsRunId === queue.running.run_id}
								title="Toggle generation input details"
							>
								{expandedDetailsRunId === queue.running.run_id ? 'Hide details' : 'Details'}
							</button>
							<button
								type="button"
								class="queue-item-btn queue-item-btn-cancel"
								onclick={() => onCancel(queue.running!.run_id)}
								disabled={actionLoading.has(queue.running!.run_id)}
								title="Cancel"
							>
								Cancel
							</button>
							{#if hoverPreviewVisibleForRunId === queue.running.run_id && expandedDetailsRunId !== queue.running.run_id}
								<div class="queue-details-popover" role="note">
									<div class="queue-details-popover-title">Quick inputs preview</div>
									{#if previewInputs(queue.running).length > 0}
										{#each previewInputs(queue.running) as input}
											<div class="queue-details-row">
												<span class="queue-details-key">{input.label}</span>
												<div class="queue-details-value-wrap">
													{#if input.media_type === 'image' && input.preview_url}
														<a
															href={input.preview_url}
															target="_blank"
															rel="noreferrer"
															download
															class="queue-details-media-link"
															title="Click to download"
														>
															<img src={input.preview_url} alt={input.label} class="queue-details-thumb queue-details-thumb-preview" loading="lazy" />
														</a>
													{/if}
													<span class="queue-details-value">{displayValue(input.display_value)}</span>
												</div>
											</div>
										{/each}
									{:else}
										<div class="queue-details-empty">No captured inputs</div>
									{/if}
								</div>
							{/if}
							{#if expandedDetailsRunId === queue.running.run_id}
								<div class="queue-details-panel">
									<div class="queue-details-facts">
										<span class="queue-details-fact">Inputs: {queue.running.details?.total_inputs ?? 0}</span>
										<span class="queue-details-fact">Media: {queue.running.details?.media_count ?? 0}</span>
										{#if queue.running.summary?.latent_resolution}
											<span class="queue-details-fact">Resolution: {queue.running.summary.latent_resolution}</span>
										{/if}
										{#if queue.running.summary?.seed != null}
											<span class="queue-details-fact">Seed: {queue.running.summary.seed}</span>
										{/if}
									</div>
									{#each detailGroups(queue.running) as group}
										<div class="queue-details-group">
											<div class="queue-details-group-title">{group.title}</div>
											{#each group.items as input (`${queue.running.run_id}-${input.key}`)}
												<div class="queue-details-row">
													<span class="queue-details-key">{input.label}</span>
													<div class="queue-details-value-wrap">
														{#if input.media_type === 'image' && input.preview_url}
															<a href={input.preview_url} target="_blank" rel="noreferrer" download class="queue-details-media-link" title="Click to download">
																<img src={input.preview_url} alt={input.label} class="queue-details-thumb" loading="lazy" />
															</a>
														{/if}
														<span class="queue-details-value">{displayValue(input.display_value)}</span>
													</div>
												</div>
											{/each}
										</div>
									{/each}
								</div>
							{/if}
						</div>
					</section>
				{/if}
				{#if queuedByGroup.length > 0}
					<section class="queue-section">
						<h3 class="queue-section-title">Queued</h3>
						<div class="queue-groups">
							{#each queuedByGroup as group (group.groupKey)}
								<div
									class="queue-group"
									class:group-dragging={draggedGroupKey === group.groupKey}
								>
									<div
										class="queue-group-header"
										class:drop-target-group={!!draggedGroupKey && dropTargetGroupKey === group.groupKey}
										style={group.appHeaderColor ? `--app-badge-color: ${group.appHeaderColor}` : ''}
										ondragover={(e) => handleGroupHeaderDragOver(e, group.groupKey)}
										ondragleave={handleGroupHeaderDragLeave}
										ondrop={(e) => { e.preventDefault(); if (group.items[0]?.run_id) handleDrop(e, group.items[0].run_id, true); }}
									>
										<span
											class="queue-group-drag-handle"
											draggable="true"
											title="Drag to reorder group"
											aria-label="Drag to reorder group"
											ondragstart={(e) => handleGroupDragStart(e, group.groupKey, group.items.map((it) => it.run_id))}
											ondragend={handleDragEnd}
										>⋮⋮</span>
										<button
											type="button"
											class="queue-group-header-left"
											onclick={() => toggleGroup(group.groupKey)}
											aria-expanded={!collapsedGroups.has(group.groupKey)}
										>
											<span class="queue-group-pos">#{group.items[0]?.queue_position ?? 0}</span>
											<span class="queue-group-badge">{group.appTitle}</span>
											<span class="queue-group-count" title="{group.items.length} generation{group.items.length === 1 ? '' : 's'}">{group.items.length}×</span>
											{#if group.projectId && group.projectTitle}
												<a href="/projects/{group.projectId}" class="queue-group-project-link" title="Open project" onclick={(e) => e.stopPropagation()}>{group.projectTitle}</a>
											{/if}
											<span class="queue-group-chevron" aria-hidden="true">{collapsedGroups.has(group.groupKey) ? '▶' : '▼'}</span>
										</button>
										<button
											type="button"
											class="queue-group-remove"
											title="Remove all runs in this group from queue"
											aria-label="Remove group from queue"
											onclick={(e) => { e.stopPropagation(); onRemoveGroup(group); }}
										>
											<svg class="queue-group-remove-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
												<polyline points="3 6 5 6 21 6"/>
												<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
												<line x1="10" y1="11" x2="10" y2="17"/>
												<line x1="14" y1="11" x2="14" y2="17"/>
											</svg>
										</button>
									</div>
									{#if !collapsedGroups.has(group.groupKey)}
										<ul
											class="queue-list"
											class:group-drag-active={!!draggedGroupKey}
											ondragover={(e) => { if (draggedGroupKey) { e.preventDefault(); e.dataTransfer && (e.dataTransfer.dropEffect = 'none'); } }}
											ondrop={(e) => { if (draggedGroupKey) e.preventDefault(); }}
										>
											{#each group.items as item, i (`${item.run_id}-${i}`)}
												<li
													class="queue-item queue-item-queued"
													class:selected={selectedRunId === item.run_id}
													class:details-expanded={expandedDetailsRunId === item.run_id}
													class:dragging={draggedRunId === item.run_id}
													class:drop-target={dropTargetRunId === item.run_id}
													draggable="true"
													data-run-id={item.run_id}
													ondragstart={(e) => handleDragStart(e, item.run_id)}
													ondragend={handleDragEnd}
													ondragover={(e) => handleDragOver(e, item.run_id)}
													ondragleave={handleDragLeave}
													ondrop={(e) => handleDrop(e, item.run_id, false)}
													onclick={() => selectedRunId = item.run_id}
													onmouseenter={() => onItemHoverStart(item.run_id)}
													onmouseleave={() => onItemHoverEnd(item.run_id)}
												>
													<span class="queue-item-drag-handle" title="Drag to reorder" aria-hidden="true">⋮⋮</span>
													<span class="queue-item-pos">#{item.queue_position ?? i + 1}</span>
													{#if item.summary}
														<span class="queue-item-summary">{summaryLine(item)}</span>
													{/if}
													{#if item.comfyui_unreachable_warning}
														<span class="queue-badge queue-badge-warning">ComfyUI unreachable</span>
													{/if}
													<div class="queue-item-actions" onclick={(e) => e.stopPropagation()}>
														<button
															type="button"
															class="queue-item-btn queue-item-btn-icon"
															title="Show generation input details"
															onclick={() => toggleDetails(item.run_id)}
															aria-expanded={expandedDetailsRunId === item.run_id}
														>
															Details
														</button>
														{#if item.comfyui_unreachable_warning}
															<button
																type="button"
																class="queue-item-btn queue-item-btn-icon"
																title="Retry (move to front)"
																disabled={actionLoading.has(item.run_id)}
																onclick={() => onRetry(item.run_id)}
															>
																Retry
															</button>
														{/if}
														<button
															type="button"
															class="queue-item-btn queue-item-btn-icon queue-item-btn-danger queue-item-btn-remove"
															title="Remove from queue"
															disabled={actionLoading.has(item.run_id)}
															onclick={() => onCancel(item.run_id)}
															aria-label="Remove"
														>
															<svg class="queue-item-remove-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>
														</button>
													</div>
													{#if hoverPreviewVisibleForRunId === item.run_id && expandedDetailsRunId !== item.run_id}
														<div class="queue-details-popover" role="note">
															<div class="queue-details-popover-title">Quick inputs preview</div>
															{#if previewInputs(item).length > 0}
																{#each previewInputs(item) as input}
																	<div class="queue-details-row">
																		<span class="queue-details-key">{input.label}</span>
																		<div class="queue-details-value-wrap">
																			{#if input.media_type === 'image' && input.preview_url}
																				<a
																					href={input.preview_url}
																					target="_blank"
																					rel="noreferrer"
																					download
																					class="queue-details-media-link"
																					title="Click to download"
																				>
																					<img src={input.preview_url} alt={input.label} class="queue-details-thumb queue-details-thumb-preview" loading="lazy" />
																				</a>
																			{/if}
																			<span class="queue-details-value">{displayValue(input.display_value)}</span>
																		</div>
																	</div>
																{/each}
															{:else}
																<div class="queue-details-empty">No captured inputs</div>
															{/if}
														</div>
													{/if}
													{#if expandedDetailsRunId === item.run_id}
														<div class="queue-details-panel">
															<div class="queue-details-facts">
																<span class="queue-details-fact">Inputs: {item.details?.total_inputs ?? 0}</span>
																<span class="queue-details-fact">Media: {item.details?.media_count ?? 0}</span>
																{#if item.summary?.latent_resolution}
																	<span class="queue-details-fact">Resolution: {item.summary.latent_resolution}</span>
																{/if}
																{#if item.summary?.seed != null}
																	<span class="queue-details-fact">Seed: {item.summary.seed}</span>
																{/if}
															</div>
															{#each detailGroups(item) as group}
																<div class="queue-details-group">
																	<div class="queue-details-group-title">{group.title}</div>
																	{#each group.items as input (`${item.run_id}-${input.key}`)}
																		<div class="queue-details-row">
																			<span class="queue-details-key">{input.label}</span>
																			<div class="queue-details-value-wrap">
																				{#if input.media_type === 'image' && input.preview_url}
																					<a href={input.preview_url} target="_blank" rel="noreferrer" download class="queue-details-media-link" title="Click to download">
																						<img src={input.preview_url} alt={input.label} class="queue-details-thumb" loading="lazy" />
																					</a>
																				{/if}
																				<span class="queue-details-value">{displayValue(input.display_value)}</span>
																			</div>
																		</div>
																	{/each}
																</div>
															{/each}
														</div>
													{/if}
												</li>
											{/each}
										</ul>
									{/if}
								</div>
							{/each}
						</div>
					</section>
				{/if}
				{#if !hasItems && !loading}
					<p class="queue-empty">No runs in queue. Add jobs from an app to get started.</p>
				{/if}
			{/if}
		</div>
	</div>
</div>

<style>
	.queue-panel {
		flex: 1;
		min-height: 0;
		min-width: 0;
		overflow: hidden;
		display: flex;
		flex-direction: row;
		background: var(--card);
		border-left: 1px solid var(--border);
		box-shadow: -4px 0 24px rgba(0, 0, 0, 0.15);
	}
	.queue-panel.resizing {
		user-select: none;
	}
	.queue-panel-resize-handle {
		flex-shrink: 0;
		width: 6px;
		cursor: col-resize;
		background: transparent;
	}
	.queue-panel-resize-handle:hover {
		background: color-mix(in srgb, var(--accent) 20%, transparent);
	}
	.queue-panel.resizing .queue-panel-resize-handle {
		background: color-mix(in srgb, var(--accent) 25%, transparent);
	}
	.queue-panel-collapse-tab {
		flex-shrink: 0;
		width: 28px;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.2rem;
		padding: 0.5rem 0;
		background: color-mix(in srgb, var(--accent) 8%, var(--card));
		border: none;
		border-right: 1px solid var(--border);
		border-radius: 0;
		color: color-mix(in srgb, var(--text) 65%, transparent);
		font-size: 0.75rem;
		font-weight: 600;
		cursor: pointer;
		transition: background 0.15s, color 0.15s;
	}
	.queue-panel-collapse-tab:hover {
		background: color-mix(in srgb, var(--accent) 18%, var(--card));
		color: var(--accent);
	}
	.queue-panel-collapse-icon {
		width: 18px;
		height: 18px;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	.queue-panel-collapse-icon svg {
		width: 100%;
		height: 100%;
	}
	.queue-panel-collapse-count {
		font-size: 0.7rem;
	}
	.queue-panel-inner {
		flex: 1;
		display: flex;
		flex-direction: column;
		min-width: 0;
	}
	.queue-panel-header {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		padding: 0.75rem 1rem;
		border-bottom: 1px solid var(--border);
		flex-shrink: 0;
	}
	.queue-panel-header-top {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		min-width: 0;
	}
	.queue-panel-title {
		margin: 0;
		font-size: 1rem;
		font-weight: 600;
		flex-shrink: 0;
	}
	.queue-panel-summary {
		font-size: 0.875rem;
		color: color-mix(in srgb, var(--text) 60%, transparent);
		flex: 1;
		min-width: 0;
	}
	.queue-panel-total {
		font-weight: 600;
		color: var(--text);
	}
	.queue-panel-halted {
		color: var(--warning);
		font-weight: 500;
		margin-right: 0.25rem;
	}
	.queue-group-pos {
		font-weight: 600;
		font-size: 0.8rem;
		color: color-mix(in srgb, var(--text) 55%, transparent);
		min-width: 1.75rem;
		flex-shrink: 0;
	}
	.queue-panel-actions {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.5rem;
		justify-content: flex-end;
	}
	.queue-btn-text {
		background: transparent;
		border-color: transparent;
		color: color-mix(in srgb, var(--text) 60%, transparent);
	}
	.queue-btn-text:hover {
		color: var(--text);
		background: color-mix(in srgb, var(--accent) 8%, transparent);
	}
	.queue-btn-danger-outline {
		border-color: color-mix(in srgb, var(--warning) 50%, var(--border));
		color: var(--warning);
	}
	.queue-btn-danger-outline:hover {
		background: color-mix(in srgb, var(--warning) 12%, var(--bg));
		border-color: var(--warning);
	}
	.queue-btn {
		padding: 0.35rem 0.65rem;
		font-size: 0.8rem;
		border-radius: 6px;
		border: 1px solid var(--border);
		background: var(--bg);
		color: var(--text);
		cursor: pointer;
	}
	.queue-btn:hover:not(:disabled) {
		background: color-mix(in srgb, var(--accent) 12%, var(--bg));
		border-color: var(--accent);
	}
	.queue-btn-primary {
		background: var(--accent);
		color: var(--card);
		border-color: var(--accent);
	}
	.queue-btn-primary:hover:not(:disabled) {
		background: color-mix(in srgb, black 12%, var(--accent));
		border-color: color-mix(in srgb, black 18%, var(--accent));
		color: var(--card);
	}
	.queue-btn-close {
		font-size: 1.25rem;
		line-height: 1;
		padding: 0.25rem 0.5rem;
		min-width: 2rem;
		display: inline-flex;
		align-items: center;
		justify-content: center;
	}
	.queue-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.queue-error {
		margin: 0 1rem;
		padding: 0.35rem 0;
		font-size: 0.875rem;
		color: var(--warning);
	}
	.queue-panel-body {
		overflow-y: auto;
		padding: 0.75rem 1rem;
		flex: 1;
		min-height: 0;
	}
	.queue-loading,
	.queue-empty {
		margin: 0;
		color: color-mix(in srgb, var(--text) 60%, transparent);
		font-size: 0.875rem;
	}
	.queue-section {
		margin-bottom: 1rem;
	}
	.queue-section-title {
		margin: 0 0 0.5rem 0;
		font-size: 0.8rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.02em;
		color: color-mix(in srgb, var(--text) 55%, transparent);
	}
	.queue-item-app-badge,
	.queue-group-badge {
		display: inline-block;
		padding: 0.2rem 0.5rem;
		border-radius: 6px;
		font-size: 0.8rem;
		font-weight: 600;
		background: var(--app-badge-color, var(--accent));
		color: var(--card);
	}
	.queue-groups {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.queue-group {
		border: 1px solid var(--border);
		border-radius: 8px;
		overflow: hidden;
		background: var(--bg);
	}
	.queue-group-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0;
		gap: 0.5rem;
		min-height: 2rem;
		border-bottom: 1px solid var(--border);
		border-left: 3px solid var(--app-badge-color, var(--border));
	}
	.queue-group-header-left {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		flex: 1;
		min-width: 0;
		padding: 0.35rem 0.5rem;
		text-align: left;
		background: none;
		border: none;
		border-radius: 0;
		cursor: pointer;
		font: inherit;
		font-size: 0.875rem;
		color: var(--text);
		appearance: none;
	}
	.queue-group-header-left:hover .queue-group-chevron {
		color: color-mix(in srgb, var(--accent) 80%, transparent);
	}
	.queue-group-header-left:focus-visible {
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.queue-group-badge {
		flex-shrink: 0;
	}
	.queue-group-count {
		font-size: 0.75rem;
		font-weight: 600;
		color: color-mix(in srgb, var(--text) 60%, transparent);
		margin-left: 0.25rem;
		flex-shrink: 0;
	}
	.queue-group-chevron {
		font-size: 0.65rem;
		color: color-mix(in srgb, var(--text) 55%, transparent);
		margin-left: 0.1rem;
		flex-shrink: 0;
	}
	.queue-group-project-link {
		font-size: 0.75rem;
		color: color-mix(in srgb, var(--text) 70%, transparent);
		text-decoration: none;
		margin-left: 0.35rem;
		padding: 0.15rem 0.4rem;
		border-radius: 4px;
		background: color-mix(in srgb, var(--muted) 25%, transparent);
		border: 1px solid color-mix(in srgb, var(--border) 80%, transparent);
		max-width: 8rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.queue-group-project-link:hover {
		color: var(--accent);
		background: color-mix(in srgb, var(--accent) 15%, var(--bg));
		border-color: color-mix(in srgb, var(--accent) 50%, var(--border));
	}
	.queue-group-remove {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		padding: 0;
		margin: 0.15rem 0.35rem 0.15rem 0;
		border: none;
		border-radius: 4px;
		background: transparent;
		color: color-mix(in srgb, var(--text) 55%, transparent);
		cursor: pointer;
	}
	.queue-group-remove:hover {
		background: color-mix(in srgb, var(--warning) 18%, var(--bg));
		color: var(--warning);
	}
	.queue-group-remove-icon {
		width: 13px;
		height: 13px;
	}
	.queue-group-drag-handle {
		cursor: grab;
		color: color-mix(in srgb, var(--text) 50%, transparent);
		font-size: 0.7rem;
		padding: 0.25rem 0.2rem;
		flex-shrink: 0;
		user-select: none;
	}
	.queue-group-drag-handle:active {
		cursor: grabbing;
	}
	.queue-group.group-dragging {
		border-color: var(--accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 35%, transparent);
		background: color-mix(in srgb, var(--accent) 6%, var(--bg));
	}
	.queue-list.group-drag-active .queue-item {
		opacity: 0.45;
		pointer-events: none;
	}
	.queue-group-header.drop-target-group {
		background: color-mix(in srgb, var(--accent) 12%, var(--bg));
		box-shadow: inset 0 0 0 2px var(--accent);
		border-radius: 6px;
	}
	.queue-list {
		list-style: none;
		margin: 0;
		padding: 0;
	}
	.queue-item {
		position: relative;
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.35rem 0.5rem;
		padding: 0.4rem 0.5rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--bg);
		margin-bottom: 0.4rem;
	}
	.queue-item.selected {
		border-color: var(--accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 30%, transparent);
	}
	.queue-item.details-expanded {
		border-color: color-mix(in srgb, var(--accent) 55%, var(--border));
		background: color-mix(in srgb, var(--accent) 4%, var(--bg));
	}
	.queue-item.dragging {
		opacity: 0.5;
	}
	.queue-item.drop-target {
		border-color: var(--accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent);
	}
	.queue-item-drag-handle {
		cursor: grab;
		color: color-mix(in srgb, var(--text) 55%, transparent);
		font-size: 0.75rem;
		line-height: 1;
		padding: 0.2rem;
		flex-shrink: 0;
		user-select: none;
	}
	.queue-item.dragging .queue-item-drag-handle {
		cursor: grabbing;
	}
	.queue-item-pos {
		font-weight: 600;
		font-size: 0.8rem;
		color: color-mix(in srgb, var(--text) 55%, transparent);
		min-width: 1.5rem;
	}
	.queue-item-summary {
		font-size: 0.8rem;
		color: color-mix(in srgb, var(--text) 65%, transparent);
	}
	.queue-item-status {
		font-size: 0.85rem;
		color: var(--accent);
	}
	.queue-item-running {
		gap: 0.5rem;
	}
	.queue-item-actions {
		display: flex;
		align-items: center;
		gap: 0.2rem;
		margin-left: auto;
		flex-shrink: 0;
	}
	.queue-item-btn {
		padding: 0.25rem 0.5rem;
		font-size: 0.75rem;
		border-radius: 4px;
		border: 1px solid var(--border);
		background: var(--card) !important;
		color: var(--text) !important;
		box-shadow: none !important;
		transform: none !important;
		cursor: pointer;
	}
	.queue-item-btn-cancel {
		border-color: var(--warning) !important;
		color: var(--warning) !important;
		background: color-mix(in srgb, var(--warning) 14%, var(--card)) !important;
	}
	.queue-item-btn-cancel:hover:not(:disabled) {
		background: color-mix(in srgb, var(--warning) 24%, var(--card)) !important;
		color: var(--warning) !important;
	}
	.queue-item-btn-icon {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-width: 1.75rem;
		min-height: 1.75rem;
		padding: 0.2rem;
	}
	.queue-item-btn-details {
		border-color: color-mix(in srgb, var(--accent) 35%, var(--border)) !important;
	}
	.queue-details-popover {
		position: absolute;
		top: calc(100% + 0.35rem);
		left: 1.8rem;
		width: min(27rem, calc(100% - 2rem));
		z-index: 8;
		padding: 0.5rem 0.6rem;
		border-radius: 8px;
		border: 1px solid color-mix(in srgb, var(--accent) 30%, var(--border));
		background: var(--card);
		box-shadow: 0 8px 20px rgba(0, 0, 0, 0.18);
	}
	.queue-details-popover-title {
		font-size: 0.72rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.02em;
		margin-bottom: 0.35rem;
		color: color-mix(in srgb, var(--text) 58%, transparent);
	}
	.queue-details-panel {
		width: 100%;
		margin-top: 0.3rem;
		padding: 0.5rem;
		border-radius: 7px;
		border: 1px solid color-mix(in srgb, var(--border) 88%, transparent);
		background: color-mix(in srgb, var(--card) 65%, var(--bg));
	}
	.queue-details-facts {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin-bottom: 0.45rem;
	}
	.queue-details-fact {
		font-size: 0.72rem;
		padding: 0.15rem 0.4rem;
		border-radius: 999px;
		border: 1px solid color-mix(in srgb, var(--border) 82%, transparent);
		background: color-mix(in srgb, var(--muted) 18%, transparent);
	}
	.queue-details-group {
		margin-top: 0.35rem;
		padding-top: 0.35rem;
		border-top: 1px dashed color-mix(in srgb, var(--border) 88%, transparent);
	}
	.queue-details-group-title {
		font-size: 0.73rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.02em;
		color: color-mix(in srgb, var(--text) 58%, transparent);
		margin-bottom: 0.3rem;
	}
	.queue-details-row {
		display: grid;
		grid-template-columns: minmax(6rem, 8rem) 1fr;
		gap: 0.45rem;
		align-items: start;
		margin-bottom: 0.25rem;
	}
	.queue-details-key {
		font-size: 0.74rem;
		color: color-mix(in srgb, var(--text) 60%, transparent);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.queue-details-value-wrap {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		min-width: 0;
	}
	.queue-details-value {
		font-size: 0.78rem;
		line-height: 1.3;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		min-width: 0;
	}
	.queue-details-thumb {
		width: 40px;
		height: 40px;
		border-radius: 4px;
		object-fit: cover;
		border: 1px solid color-mix(in srgb, var(--border) 85%, transparent);
		background: color-mix(in srgb, var(--muted) 20%, transparent);
		transition: transform 0.15s ease, box-shadow 0.15s ease;
		transform-origin: center center;
	}
	.queue-details-media-link {
		display: inline-flex;
		position: relative;
		overflow: visible;
	}
	.queue-details-media-link:hover .queue-details-thumb,
	.queue-details-media-link:focus-visible .queue-details-thumb {
		transform: scale(2);
		box-shadow: 0 8px 18px rgba(0, 0, 0, 0.28);
		z-index: 12;
	}
	.queue-details-thumb-preview {
		width: 28px;
		height: 28px;
	}
	.queue-details-empty {
		font-size: 0.75rem;
		color: color-mix(in srgb, var(--text) 62%, transparent);
	}
	.queue-item-remove-icon {
		width: 14px;
		height: 14px;
	}
	.queue-item-btn:hover:not(:disabled) {
		background: color-mix(in srgb, var(--accent) 15%, var(--card)) !important;
		transform: none !important;
	}
	.queue-item-btn-danger:hover:not(:disabled) {
		background: color-mix(in srgb, var(--warning) 20%, var(--card));
	}
	.queue-item-btn-remove,
	.queue-item-btn-remove .queue-item-remove-icon {
		color: color-mix(in srgb, var(--text) 55%, transparent) !important;
	}
	.queue-item-btn-remove:hover:not(:disabled),
	.queue-item-btn-remove:hover:not(:disabled) .queue-item-remove-icon {
		color: var(--warning) !important;
	}
	.queue-badge {
		font-size: 0.7rem;
		padding: 0.15rem 0.4rem;
		border-radius: 4px;
		background: color-mix(in srgb, var(--text) 12%, var(--bg));
		color: color-mix(in srgb, var(--text) 65%, transparent);
	}
	.queue-badge-warning {
		color: var(--warning);
	}

	@media (max-width: 639px) {
		.queue-panel {
			border-left: none;
			box-shadow: none;
		}
		.queue-panel-resize-handle,
		.queue-panel-collapse-tab {
			display: none;
		}
		.queue-details-popover {
			display: none;
		}
		.queue-details-row {
			grid-template-columns: 1fr;
			gap: 0.15rem;
		}
	}
</style>
