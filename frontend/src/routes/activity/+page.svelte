<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { onDestroy } from 'svelte';
	import { getApiBase } from '$lib/config';
	import { THUMB_SCALE_MAX, THUMB_SCALE_MIN, getThumbFitModeCookie, getThumbSizeCookie, setThumbFitModeCookie, setThumbSizeCookie, getThumbShowFilenameCookie, setThumbShowFilenameCookie, getSkipDeleteConfirmCookie, setSkipDeleteConfirmCookie, type ThumbFitMode } from '$lib/cookie';
	import { appBooting } from '$lib/stores/appBooting';
	import { cancelRun, getQueue, getRecentRuns, type QueueItem, type RecentRunItem } from '$lib/queueApi';
	import RunAppBadge from '$lib/components/RunAppBadge.svelte';
	import RunHeaderActions from '$lib/components/RunHeaderActions.svelte';
	import ThumbnailOverlay from '$lib/components/ThumbnailOverlay.svelte';
	import RunMetadataPanel from '$lib/components/RunMetadataPanel.svelte';
	import SendToAppDialog from '$lib/components/SendToAppDialog.svelte';
	import LightboxViewer, { type LightboxItem } from '$lib/components/LightboxViewer.svelte';
	import ConfirmDeleteDialog from '$lib/components/ConfirmDeleteDialog.svelte';

	type ProjectOption = { id: string; name: string; headerColor?: string | null };

	type ActivityRun = {
		id: string;
		run_group_id: string | null;
		app_id: string | null;
		app_slug: string | null;
		app_title: string | null;
		app_header_color?: string | null;
		project_id: string | null;
		project_title: string | null;
		status: string;
		queue_position?: number | null;
		created_at: number;
		seed: number | null;
		images: { filename: string; subfolder: string; type: string; remote_deleted?: boolean }[];
		execution_time: number | null;
		error: string | null;
		local_storage_status?: string | null;
		remote_status?: string | null;
		local_path?: string | null;
		local_storage_bytes?: number | null;
		remote_storage_bytes?: number | null;
		comfyui_unreachable_warning?: string | null;
		source: 'queue' | 'recent';
	};

	type ActivityGroup = {
		groupId: string;
		firstRunId: string;
		createdAt: number;
		app_title: string | null;
		app_slug: string | null;
		app_header_color: string | null;
		app_removed: boolean;
		project_id: string | null;
		project_title: string | null;
		status: string;
		error: string | null;
		comfyui_unreachable_warning: string | null;
		runCount: number;
		runs: ActivityRun[];
	};

	const apiBase = getApiBase() || '';
	const PAGE_SIZE = 30;
	const QUEUE_POLL_MS = 3000;
	const RECENT_POLL_MS = 8000;

	let queue = $state<{ running: QueueItem | null; queued: QueueItem[]; processing_halted: boolean } | null>(null);
	let queueLoading = $state(true);
	let queueError = $state<string | null>(null);

	let recentRuns = $state<ActivityRun[]>([]);
	let totalRecent = $state(0);
	let recentLoading = $state(true);
	let recentLoadingMore = $state(false);
	let recentError = $state<string | null>(null);

	let filterProjectId = $state('');
	let filterStatus = $state('past');
	let filterQuery = $state('');
	let projectOptions = $state<ProjectOption[]>([]);
	let projectPickerOpen = $state(false);
	let projectPickerSearch = $state('');

	let savingGroupIds = $state<string[]>([]);
	let deletingGroupIds = $state<string[]>([]);
	let deletingLocalGroupIds = $state<string[]>([]);
	let deletingBothGroupIds = $state<string[]>([]);
	let deletingRunIds = $state<string[]>([]);
	let cancellingGroupIds = $state<string[]>([]);
	let cancellingRunIds = $state<string[]>([]);
	let retryingGroupIds = $state<string[]>([]);

	let metadataPanelRunId = $state<string | null>(null);
	let metadataPanelMode = $state<'output' | 'run'>('output');
	let sendToAppRunId = $state<string | null>(null);
	let sendToAppOutputIndex = $state<number | null>(null);
	let sendToAppProjectId = $state<string | null>(null);
	let thumbnailScale = $state<number>(browser ? getThumbSizeCookie() : 100);
	let thumbnailFitMode = $state<ThumbFitMode>(browser ? getThumbFitModeCookie() : 'cover');
	let showThumbFilename = $state<boolean>(browser ? getThumbShowFilenameCookie() : false);
	let lightboxOpen = $state(false);
	let lightboxImages = $state<LightboxItem[]>([]);
	let lightboxIndex = $state(0);
	let lightboxGroupId = $state<string | null>(null);
	let playingVideoThumbKey = $state<string | null>(null);
	let playingVideoThumbReady = $state(false);
	let selectedInGroup = $state<Record<string, string[]>>({});
	let deletingImageKeys = $state<string[]>([]);
	let deletingLocalImageKeys = $state<string[]>([]);
	let deletingBothImageKeys = $state<string[]>([]);
	let favorites = $state<Set<string>>(new Set());
	let projectMetadataCache = $state<Record<string, { metadata: Record<string, unknown>; favorites: string[] }>>({});
	let deleteRunGroupPending = $state<ActivityGroup | null>(null);

	let queuePollId: ReturnType<typeof setInterval> | null = null;
	let recentPollId: ReturnType<typeof setInterval> | null = null;
	let queueAbort: AbortController | null = null;
	let recentAbort: AbortController | null = null;
	let projectsAbort: AbortController | null = null;

	const activeCount = $derived((queue?.running ? 1 : 0) + (queue?.queued?.length ?? 0));
	const hasMoreRecent = $derived(recentRuns.length < totalRecent);
	const filteredProjectOptions = $derived.by(() => {
		const q = projectPickerSearch.trim().toLowerCase();
		if (!q) return projectOptions;
		return projectOptions.filter((p) => p.name.toLowerCase().includes(q));
	});
	const selectedProject = $derived.by(() => projectOptions.find((p) => p.id === filterProjectId) ?? null);

	function readProjectParam() {
		if (!browser) return;
		const p = new URLSearchParams(window.location.search).get('project');
		if (p) filterProjectId = p;
	}

	function currentStatusFilter(): string[] | undefined {
		if (filterStatus === 'past') return ['done', 'error', 'cancelled'];
		if (!filterStatus.trim()) return undefined;
		if (filterStatus === 'in_flight') return ['queued', 'running'];
		return [filterStatus];
	}

	function normalizeRecent(r: RecentRunItem): ActivityRun {
		return {
			id: r.id,
			run_group_id: r.run_group_id ?? null,
			app_id: r.app_id ?? null,
			app_slug: r.app_slug ?? null,
			app_title: r.app_title ?? null,
			app_header_color: r.app_header_color ?? null,
			project_id: r.project_id ?? null,
			project_title: r.project_title ?? null,
			status: r.status,
			queue_position: r.queue_position ?? null,
			created_at: r.created_at ?? Date.now(),
			seed: r.seed ?? null,
			images: Array.isArray(r.images) ? r.images : [],
			execution_time: r.execution_time ?? null,
			error: r.error ?? null,
			local_storage_status: r.local_storage_status ?? null,
			remote_status: r.remote_status ?? null,
			local_path: r.local_path ?? null,
			local_storage_bytes: r.local_storage_bytes ?? null,
			remote_storage_bytes: r.remote_storage_bytes ?? null,
			comfyui_unreachable_warning: r.comfyui_unreachable_warning ?? null,
			source: 'recent'
		};
	}

	function normalizeQueue(r: QueueItem): ActivityRun {
		return {
			id: r.run_id,
			run_group_id: r.run_group_id ?? null,
			app_id: null,
			app_slug: r.app_slug ?? null,
			app_title: r.app_title ?? null,
			app_header_color: r.app_header_color ?? null,
			project_id: r.project_id ?? null,
			project_title: r.project_title ?? null,
			status: r.status,
			queue_position: r.queue_position ?? null,
			created_at: r.created_at ?? Date.now(),
			seed: r.summary?.seed ?? null,
			images: [],
			execution_time: null,
			error: null,
			local_storage_status: null,
			remote_status: null,
			local_path: null,
			local_storage_bytes: null,
			remote_storage_bytes: null,
			comfyui_unreachable_warning: r.comfyui_unreachable_warning ?? null,
			source: 'queue'
		};
	}

	/** Queue + recent can list the same run while it is active; merge so {#each run (run.id)} keys stay unique. */
	function mergeQueueRunWithRecent(queue: ActivityRun, recent: ActivityRun): ActivityRun {
		return {
			...recent,
			status: queue.status,
			queue_position: queue.queue_position ?? recent.queue_position,
			comfyui_unreachable_warning: queue.comfyui_unreachable_warning ?? recent.comfyui_unreachable_warning,
			source: queue.source
		};
	}

	function buildGroups(list: ActivityRun[]): ActivityGroup[] {
		const byGroup: Record<string, ActivityRun[]> = {};
		for (const r of list) {
			const key = r.run_group_id ?? r.id;
			if (!byGroup[key]) byGroup[key] = [];
			byGroup[key].push(r);
		}
		const groups: ActivityGroup[] = [];
		for (const [groupId, groupRuns] of Object.entries(byGroup)) {
			const sorted = [...groupRuns].sort((a, b) => a.created_at - b.created_at);
			const first = sorted[0];
			const createdAt = Math.min(...sorted.map((r) => r.created_at));
			const hasError = sorted.some((r) => r.status === 'error' || (r.error && r.status !== 'cancelled'));
			const hasCancelled = sorted.some((r) => r.status === 'cancelled');
			const hasRunning = sorted.some((r) => r.status === 'running');
			const hasQueued = sorted.some((r) => r.status === 'queued');
			const status = hasError ? 'error' : hasCancelled ? 'cancelled' : hasRunning ? 'running' : hasQueued ? 'queued' : 'done';
			groups.push({
				groupId,
				firstRunId: first.id,
				createdAt,
				app_title: first.app_title,
				app_slug: first.app_slug,
				app_header_color: first.app_header_color ?? null,
				app_removed: false,
				project_id: first.project_id ?? null,
				project_title: first.project_title ?? null,
				status,
				error: sorted.find((r) => r.error)?.error ?? null,
				comfyui_unreachable_warning: sorted.find((r) => r.comfyui_unreachable_warning)?.comfyui_unreachable_warning ?? null,
				runCount: sorted.length,
				runs: sorted
			});
		}
		return groups.sort((a, b) => b.createdAt - a.createdAt);
	}

	const nowGroups = $derived.by(() => {
		const inFlight: ActivityRun[] = [];
		if (queue?.running) inFlight.push(normalizeQueue(queue.running));
		for (const q of queue?.queued ?? []) inFlight.push(normalizeQueue(q));
		const activeGroupIds = inFlight.map((r) => r.run_group_id ?? r.id);
		const relatedPast = recentRuns.filter((r) => activeGroupIds.includes(r.run_group_id ?? r.id));
		const byId = new Map<string, ActivityRun>();
		for (const r of relatedPast) byId.set(r.id, r);
		for (const q of inFlight) {
			const existing = byId.get(q.id);
			byId.set(q.id, existing ? mergeQueueRunWithRecent(q, existing) : q);
		}
		return buildGroups([...byId.values()]);
	});

	const recentGroups = $derived.by(() => {
		const nowIds = nowGroups.map((g) => g.groupId);
		return buildGroups(recentRuns.filter((r) => !nowIds.includes(r.run_group_id ?? r.id)));
	});

	function imageUrl(img: { filename: string; subfolder?: string; type?: string }, runId?: string) {
		const subfolder = img.subfolder ?? '';
		const type = img.type ?? 'output';
		let url = `${apiBase}/image?filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(subfolder)}&type=${encodeURIComponent(type)}`;
		if (runId) url += `&run_id=${encodeURIComponent(runId)}`;
		return url;
	}

	function previewImageUrl(img: { filename: string; subfolder?: string; type?: string }, runId?: string) {
		return imageUrl(img, runId) + '&preview=webp';
	}

	function videoThumbnailPreviewUrl(img: { filename: string; subfolder?: string; type?: string }, runId?: string) {
		return imageUrl(img, runId) + '&preview=webp';
	}

	function mediaType(img: { filename?: string; subfolder?: string; type?: string }): 'image' | 'video' | 'audio' {
		const t = (img?.type ?? '').toLowerCase();
		if (t === 'video') return 'video';
		if (t === 'audio') return 'audio';
		return 'image';
	}

	function setThumbnailScale(value: number) {
		const next = Math.min(THUMB_SCALE_MAX, Math.max(THUMB_SCALE_MIN, Math.round(value)));
		thumbnailScale = next;
		if (browser) setThumbSizeCookie(next);
	}

	function setThumbnailFitMode(mode: ThumbFitMode) {
		thumbnailFitMode = mode;
		if (browser) setThumbFitModeCookie(mode);
	}

	function setShowThumbFilename(value: boolean) {
		showThumbFilename = value;
		if (browser) setThumbShowFilenameCookie(value);
	}

	function getProjectInfo(projectId: string | null, projectTitle: string | null): { name: string; color: string | null } {
		if (!projectId) return { name: projectTitle ?? 'Unknown project', color: null };
		const fromList = projectOptions.find((p) => p.id === projectId);
		return {
			name: projectTitle?.trim() || fromList?.name || projectId,
			color: fromList?.headerColor ?? null
		};
	}

	function imageKey(runId: string, index: number) {
		return `${runId}_${index}`;
	}

	function isImageSelected(groupId: string, key: string): boolean {
		return (selectedInGroup[groupId] ?? []).includes(key);
	}

	function hasSelection(groupId: string): boolean {
		return (selectedInGroup[groupId]?.length ?? 0) > 0;
	}

	function toggleImageSelection(groupId: string, key: string) {
		const current = selectedInGroup[groupId] ?? [];
		const next = current.includes(key) ? current.filter((k) => k !== key) : [...current, key];
		selectedInGroup = { ...selectedInGroup, [groupId]: next };
	}

	function getSelectedByRun(group: ActivityGroup): Record<string, number[]> {
		const selected = selectedInGroup[group.groupId] ?? [];
		const byRun: Record<string, number[]> = {};
		for (const key of selected) {
			const i = key.lastIndexOf('_');
			if (i === -1) continue;
			const runId = key.slice(0, i);
			const index = Number.parseInt(key.slice(i + 1), 10);
			if (Number.isNaN(index)) continue;
			if (!byRun[runId]) byRun[runId] = [];
			byRun[runId].push(index);
		}
		return byRun;
	}

	function findRunById(runId: string): ActivityRun | undefined {
		for (const r of recentRuns) if (r.id === runId) return r;
		for (const g of nowGroups) {
			for (const r of g.runs) if (r.id === runId) return r;
		}
		return undefined;
	}

	function outputFavoriteKey(runId: string, outputIndex: number): string {
		return `${runId}:${outputIndex}`;
	}

	function parseFavoriteEntry(entry: string): { runId: string; outputIndex: number | null } {
		const lastColon = entry.lastIndexOf(':');
		if (lastColon === -1) return { runId: entry, outputIndex: null };
		const suffix = entry.slice(lastColon + 1);
		if (!/^\d+$/.test(suffix)) return { runId: entry, outputIndex: null };
		return { runId: entry.slice(0, lastColon), outputIndex: parseInt(suffix, 10) };
	}

	function runHasDisplayableOutputs(run: ActivityRun): boolean {
		const imgs = run.images ?? [];
		return imgs.some((item) => {
			const rd = !!(item as { remote_deleted?: boolean }).remote_deleted;
			if (!rd) return true;
			return run.local_storage_status === 'saved' || run.local_storage_status === 'partial';
		});
	}

	function outputIndexIsDisplayable(run: ActivityRun, index: number): boolean {
		const item = run.images?.[index];
		if (!item) return false;
		const rd = !!(item as { remote_deleted?: boolean }).remote_deleted;
		if (!rd) return true;
		return run.local_storage_status === 'saved' || run.local_storage_status === 'partial';
	}

	function isOutputFavorite(runId: string, outputIndex: number): boolean {
		if (favorites.has(outputFavoriteKey(runId, outputIndex))) return true;
		if (favorites.has(runId)) return true;
		return false;
	}

	function runHasFavoritedOutput(run: ActivityRun): boolean {
		if (!runHasDisplayableOutputs(run)) return false;
		if (favorites.has(run.id)) return true;
		const n = run.images?.length ?? 0;
		for (let i = 0; i < n; i++) {
			if (!outputIndexIsDisplayable(run, i)) continue;
			if (favorites.has(outputFavoriteKey(run.id, i))) return true;
		}
		return false;
	}

	function pruneStaleRunFavoritesForGroup(runsToCheck: ActivityRun[]) {
		const toRemove = new Set<string>();
		const idSet = new Set(runsToCheck.map((r) => r.id));
		for (const r of runsToCheck) {
			if (favorites.has(r.id) && !runHasDisplayableOutputs(r)) toRemove.add(r.id);
			const n = r.images?.length ?? 0;
			for (let i = 0; i < n; i++) {
				const k = outputFavoriteKey(r.id, i);
				if (favorites.has(k) && !outputIndexIsDisplayable(r, i)) toRemove.add(k);
			}
		}
		for (const ent of favorites) {
			const p = parseFavoriteEntry(ent);
			if (p.outputIndex == null) continue;
			if (!idSet.has(p.runId)) continue;
			const r = runsToCheck.find((x) => x.id === p.runId);
			if (!r) continue;
			const n = r.images?.length ?? 0;
			if (p.outputIndex < 0 || p.outputIndex >= n || !outputIndexIsDisplayable(r, p.outputIndex)) {
				toRemove.add(ent);
			}
		}
		if (!toRemove.size) return;
		favorites = new Set([...favorites].filter((e) => !toRemove.has(e)));
	}

	async function persistFavoritesAfterDeletedRuns(deletedIds: Set<string>, affectedRuns: ActivityRun[]) {
		if (!deletedIds.size) return;
		favorites = new Set([...favorites].filter((ent) => !deletedIds.has(parseFavoriteEntry(ent).runId)));

		const projectIds = new Set<string>();
		for (const r of affectedRuns) {
			if (r.project_id && deletedIds.has(r.id)) projectIds.add(r.project_id);
		}
		for (const projectId of projectIds) {
			try {
				const entry = await ensureProjectMetadata(projectId);
				const nextFav = entry.favorites.filter((ent) => !deletedIds.has(parseFavoriteEntry(ent).runId));
				if (nextFav.length === entry.favorites.length) continue;
				const nextMeta = { ...entry.metadata, favorites: nextFav };
				const res = await fetch(`${apiBase}/projects/${projectId}`, {
					method: 'PATCH',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ metadata: nextMeta })
				});
				if (!res.ok) continue;
				projectMetadataCache = { ...projectMetadataCache, [projectId]: { metadata: nextMeta, favorites: nextFav } };
			} catch {
				/* ignore */
			}
		}
	}

	function markDeleting(list: string[], keys: string[]): string[] {
		const next = new Set(list);
		for (const k of keys) next.add(k);
		return [...next];
	}

	function unmarkDeleting(list: string[], keys: string[]): string[] {
		const next = new Set(list);
		for (const k of keys) next.delete(k);
		return [...next];
	}

	async function ensureProjectMetadata(projectId: string): Promise<{ metadata: Record<string, unknown>; favorites: string[] }> {
		const cached = projectMetadataCache[projectId];
		if (cached) return cached;
		const res = await fetch(`${apiBase}/projects/${projectId}`);
		const data = await res.json().catch(() => ({}));
		const metadata = data?.metadata && typeof data.metadata === 'object' ? (data.metadata as Record<string, unknown>) : {};
		const fav = Array.isArray(metadata.favorites) ? metadata.favorites.map((x) => String(x)) : [];
		const entry = { metadata, favorites: fav };
		projectMetadataCache = { ...projectMetadataCache, [projectId]: entry };
		if (fav.length) favorites = new Set([...favorites, ...fav]);
		return entry;
	}

	async function toggleFavorite(run: ActivityRun) {
		if (!run.project_id) return;
		const projectId = run.project_id;
		const runId = run.id;
		const before = new Set(favorites);
		const next = new Set(before);
		if (next.has(runId)) next.delete(runId);
		else next.add(runId);
		favorites = next;
		try {
			const entry = await ensureProjectMetadata(projectId);
			const nextFav = Array.from(
				new Set([
					...entry.favorites.filter((id) => id !== runId),
					...(next.has(runId) ? [runId] : [])
				])
			);
			const nextMeta = { ...entry.metadata, favorites: nextFav };
			const res = await fetch(`${apiBase}/projects/${projectId}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ metadata: nextMeta })
			});
			if (!res.ok) throw new Error('Failed to persist favorite');
			projectMetadataCache = { ...projectMetadataCache, [projectId]: { metadata: nextMeta, favorites: nextFav } };
		} catch {
			favorites = before;
		}
	}

	function buildGroupImageList(group: ActivityGroup): LightboxItem[] {
		const list: LightboxItem[] = [];
		for (const run of group.runs) {
			for (let i = 0; i < (run.images?.length ?? 0); i++) {
				const img = run.images[i];
				if (img?.remote_deleted) continue;
				const mt = mediaType(img);
				list.push({
					id: imageKey(run.id, i),
					url: imageUrl(img, run.id),
					thumbnailUrl: mt === 'video' ? videoThumbnailPreviewUrl(img, run.id) : undefined,
					runId: run.id,
					filename: img.filename,
					mediaType: mt,
					remote_deleted: false,
					hasLocal: run.local_storage_status === 'saved' || run.local_storage_status === 'partial',
					hasRemote: true,
					seed: run.seed ?? undefined,
					executionTimeSec: run.execution_time ?? undefined,
					outputIndex: i
				});
			}
		}
		return list;
	}

	function openLightboxFromImage(group: ActivityGroup, runId: string, imgIndex: number) {
		const key = imageKey(runId, imgIndex);
		const selected = new Set(selectedInGroup[group.groupId] ?? []);
		const full = buildGroupImageList(group);
		const filtered = selected.size ? full.filter((img) => selected.has(img.id)) : full;
		const list = filtered.length ? filtered : full;
		const idx = list.findIndex((img) => img.id === key);
		if (idx === -1) return;
		lightboxImages = list;
		lightboxIndex = idx;
		lightboxGroupId = group.groupId;
		lightboxOpen = true;
	}

	function closeLightbox() {
		lightboxOpen = false;
		lightboxGroupId = null;
	}

	async function downloadLightboxItem(item: LightboxItem) {
		const res = await fetch(item.url);
		const blob = await res.blob();
		const blobUrl = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = blobUrl;
		a.download = item.filename ?? (item.mediaType === 'video' ? 'video.mp4' : item.mediaType === 'audio' ? 'audio.mp3' : 'output.png');
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(blobUrl);
	}

	async function deleteRemoteImage(runId: string, imageIndex: number) {
		const key = imageKey(runId, imageIndex);
		deletingImageKeys = markDeleting(deletingImageKeys, [key]);
		try {
			const res = await fetch(`${apiBase}/runs/${runId}/delete-remote-image/${imageIndex}`, { method: 'POST' });
			const data = await res.json().catch(() => ({}));
			if (res.ok) mergeUpdatedRuns(data.updated_runs);
		} finally {
			deletingImageKeys = unmarkDeleting(deletingImageKeys, [key]);
		}
	}

	async function deleteLocalImage(runId: string, imageIndex: number) {
		const key = imageKey(runId, imageIndex);
		deletingLocalImageKeys = markDeleting(deletingLocalImageKeys, [key]);
		try {
			const res = await fetch(`${apiBase}/runs/${runId}/delete-local-image/${imageIndex}`, { method: 'POST' });
			const data = await res.json().catch(() => ({}));
			if (res.ok) {
				if (data.updated_runs?.length) mergeUpdatedRuns(data.updated_runs);
				updateRunStorage(runId, {
					local_storage_status: data.local_storage_status ?? null,
					local_path: data.local_path ?? null
				});
			}
		} finally {
			deletingLocalImageKeys = unmarkDeleting(deletingLocalImageKeys, [key]);
		}
	}

	async function deleteBothImage(runId: string, imageIndex: number): Promise<boolean> {
		const key = imageKey(runId, imageIndex);
		deletingBothImageKeys = markDeleting(deletingBothImageKeys, [key]);
		try {
			const res = await fetch(`${apiBase}/runs/${runId}/delete-both-image/${imageIndex}`, { method: 'POST' });
			const data = await res.json().catch(() => ({}));
			if (data.updated_runs?.length) mergeUpdatedRuns(data.updated_runs);
			return res.ok;
		} finally {
			deletingBothImageKeys = unmarkDeleting(deletingBothImageKeys, [key]);
		}
	}

	function outputCount(group: ActivityGroup): number {
		return group.runs.reduce((n, r) => n + (r.images?.length ?? 0), 0);
	}

	function updateRunStorage(runId: string, patch: Partial<ActivityRun>) {
		recentRuns = recentRuns.map((r) => (r.id === runId ? { ...r, ...patch } : r));
	}

	function mergeUpdatedRuns(updatedRuns: RecentRunItem[] | undefined) {
		if (!updatedRuns?.length) return;
		const byId: Record<string, ActivityRun> = {};
		for (const r of updatedRuns) byId[r.id] = normalizeRecent(r);
		recentRuns = recentRuns.map((r) => {
			const u = byId[r.id];
			if (!u) return r;
			return { ...r, ...u, run_group_id: u.run_group_id ?? r.run_group_id };
		});
	}

	function getGroupStorageSummary(group: ActivityGroup): { label: string; tone: string } | null {
		const states = group.runs.map((r) => r.local_storage_status);
		if (!states.length) return null;
		const allSaved = states.length > 0 && states.every((s) => s === 'saved');
		const anySaved = states.some((s) => s === 'saved');
		const anyPartial = states.some((s) => s === 'partial');
		const anyFailed = states.some((s) => s === 'failed');
		if (allSaved) return { label: 'Fully Saved', tone: 'saved' };
		if (anySaved || anyPartial) return { label: 'Partially Saved', tone: 'partial' };
		if (anyFailed) return { label: 'Failed', tone: 'failed' };
		return { label: 'Remote Only', tone: 'remote' };
	}

	function sumKnownStorageBytes(group: ActivityGroup, key: 'local_storage_bytes' | 'remote_storage_bytes'): number | null {
		let total = 0;
		let hasKnown = false;
		for (const run of group.runs) {
			const value = run[key];
			if (typeof value === 'number' && Number.isFinite(value) && value >= 0) {
				total += value;
				hasKnown = true;
			}
		}
		return hasKnown ? total : null;
	}

	/** Batch-fetch sizes like the project page; group by project because the API is scoped per project. */
	async function refetchStorageSizesForActivityRuns(runsBatch: ActivityRun[]) {
		if (!runsBatch.length || !apiBase) return;
		const byProject = new Map<string, string[]>();
		for (const r of runsBatch) {
			const pid = r.project_id?.trim();
			if (!pid) continue;
			let list = byProject.get(pid);
			if (!list) {
				list = [];
				byProject.set(pid, list);
			}
			if (!list.includes(r.id)) list.push(r.id);
		}
		const allSizes: Record<string, { local_storage_bytes?: number | null; remote_storage_bytes?: number | null }> =
			{};
		await Promise.all(
			[...byProject.entries()].map(async ([projectId, runIds]) => {
				if (!runIds.length) return;
				try {
					const res = await fetch(
						`${apiBase}/projects/${projectId}/runs/storage_sizes?run_ids=${encodeURIComponent(runIds.join(','))}`
					);
					if (!res.ok) return;
					const sizes = await res.json().catch(() => ({}));
					if (typeof sizes !== 'object' || sizes === null) return;
					Object.assign(allSizes, sizes);
				} catch {
					// ignore
				}
			})
		);
		if (!Object.keys(allSizes).length) return;
		recentRuns = recentRuns.map((r) => {
			const s = allSizes[r.id];
			if (!s) return r;
			return {
				...r,
				local_storage_bytes: s.local_storage_bytes ?? null,
				remote_storage_bytes: s.remote_storage_bytes ?? null
			};
		});
	}

	async function saveRunGroup(group: ActivityGroup) {
		savingGroupIds = [...savingGroupIds, group.groupId];
		try {
			for (const run of group.runs) {
				const res = await fetch(`${apiBase}/runs/${run.id}/save`, { method: 'POST' });
				const data = await res.json().catch(() => ({}));
				if (res.ok) {
					updateRunStorage(run.id, {
						local_storage_status: data.local_storage_status,
						remote_status: data.remote_status,
						local_path: data.local_path
					});
				}
			}
			await refetchStorageSizesForActivityRuns(group.runs);
		} finally {
			savingGroupIds = savingGroupIds.filter((id) => id !== group.groupId);
		}
	}

	async function deleteRemoteRunGroup(group: ActivityGroup) {
		deletingGroupIds = [...deletingGroupIds, group.groupId];
		try {
			for (const run of group.runs) {
				const res = await fetch(`${apiBase}/runs/${run.id}/delete-remote`, { method: 'POST' });
				const data = await res.json().catch(() => ({}));
				if (res.ok) mergeUpdatedRuns(data.updated_runs);
			}
		} finally {
			deletingGroupIds = deletingGroupIds.filter((id) => id !== group.groupId);
		}
	}

	async function deleteLocalRunGroup(group: ActivityGroup) {
		deletingLocalGroupIds = [...deletingLocalGroupIds, group.groupId];
		try {
			for (const run of group.runs) {
				const res = await fetch(`${apiBase}/runs/${run.id}/delete-local`, { method: 'POST' });
				const data = await res.json().catch(() => ({}));
				if (res.ok) {
					updateRunStorage(run.id, {
						local_storage_status: data.local_storage_status,
						local_path: data.local_path
					});
				}
			}
		} finally {
			deletingLocalGroupIds = deletingLocalGroupIds.filter((id) => id !== group.groupId);
		}
	}

	async function deleteBothRunGroup(group: ActivityGroup) {
		deletingBothGroupIds = [...deletingBothGroupIds, group.groupId];
		try {
			for (const run of group.runs) {
				const res = await fetch(`${apiBase}/runs/${run.id}/delete-both`, { method: 'POST' });
				const data = await res.json().catch(() => ({}));
				if (res.ok) mergeUpdatedRuns(data.updated_runs);
			}
		} finally {
			deletingBothGroupIds = deletingBothGroupIds.filter((id) => id !== group.groupId);
		}
	}

	async function deleteRemoteSelectedOrGroup(group: ActivityGroup) {
		const byRun = getSelectedByRun(group);
		const runIds = Object.keys(byRun);
		if (!runIds.length) {
			await deleteRemoteRunGroup(group);
			return;
		}
		selectedInGroup = { ...selectedInGroup, [group.groupId]: [] };
		for (const runId of runIds) {
			const indices = byRun[runId];
			const keys = indices.map((i) => imageKey(runId, i));
			deletingImageKeys = markDeleting(deletingImageKeys, keys);
			try {
				const res = await fetch(`${apiBase}/runs/${runId}/delete-remote-images`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ indices })
				});
				const data = await res.json().catch(() => ({}));
				if (res.ok) mergeUpdatedRuns(data.updated_runs);
			} finally {
				deletingImageKeys = unmarkDeleting(deletingImageKeys, keys);
			}
		}
	}

	async function deleteLocalSelectedOrGroup(group: ActivityGroup) {
		const byRun = getSelectedByRun(group);
		const runIds = Object.keys(byRun);
		if (!runIds.length) {
			await deleteLocalRunGroup(group);
			return;
		}
		selectedInGroup = { ...selectedInGroup, [group.groupId]: [] };
		for (const runId of runIds) {
			const indices = byRun[runId];
			const keys = indices.map((i) => imageKey(runId, i));
			deletingLocalImageKeys = markDeleting(deletingLocalImageKeys, keys);
			try {
				const res = await fetch(`${apiBase}/runs/${runId}/delete-local-images`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ indices })
				});
				const data = await res.json().catch(() => ({}));
				if (res.ok) {
					if (data.updated_runs?.length) mergeUpdatedRuns(data.updated_runs);
					updateRunStorage(runId, {
						local_storage_status: data.local_storage_status ?? null,
						local_path: data.local_path ?? null
					});
				}
			} finally {
				deletingLocalImageKeys = unmarkDeleting(deletingLocalImageKeys, keys);
			}
		}
	}

	async function deleteBothSelectedOrGroup(group: ActivityGroup) {
		const byRun = getSelectedByRun(group);
		const runIds = Object.keys(byRun);
		if (!runIds.length) {
			await deleteBothRunGroup(group);
			return;
		}
		selectedInGroup = { ...selectedInGroup, [group.groupId]: [] };
		for (const runId of runIds) {
			const indices = byRun[runId];
			const keys = indices.map((i) => imageKey(runId, i));
			deletingBothImageKeys = markDeleting(deletingBothImageKeys, keys);
			try {
				const res = await fetch(`${apiBase}/runs/${runId}/delete-both-images`, {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ indices })
				});
				const data = await res.json().catch(() => ({}));
				if (res.ok) mergeUpdatedRuns(data.updated_runs);
			} finally {
				deletingBothImageKeys = unmarkDeleting(deletingBothImageKeys, keys);
			}
		}
	}

	async function deleteRunGroup(group: ActivityGroup, runIdsToDelete?: string[]) {
		const runIds = runIdsToDelete ?? group.runs.map((r) => r.id);
		if (runIds.length === 0) return;
		const runIdsSet = new Set(runIds);
		const affectedRuns = group.runs.filter((r) => runIdsSet.has(r.id));
		for (const id of runIds) deletingRunIds = [...deletingRunIds, id];
		const deletedIds = new Set<string>();
		try {
			for (const runId of runIds) {
				const res = await fetch(`${apiBase}/runs/${runId}/delete-run`, { method: 'POST' });
				const data = await res.json().catch(() => ({}));
				if (res.ok && data.deleted_run_id) {
					recentRuns = recentRuns.filter((r) => r.id !== data.deleted_run_id);
					deletedIds.add(data.deleted_run_id);
				}
				deletingRunIds = deletingRunIds.filter((id) => id !== runId);
			}
			if (deletedIds.size > 0) await persistFavoritesAfterDeletedRuns(deletedIds, affectedRuns);
		} finally {
			deletingRunIds = deletingRunIds.filter((id) => !runIds.includes(id));
			await loadQueue();
			await refreshRecentInPlace(true);
		}
	}

	function requestDeleteRunGroup(group: ActivityGroup) {
		pruneStaleRunFavoritesForGroup(group.runs);
		const hasFav = group.runs.some((r) => runHasFavoritedOutput(r));
		if (!hasFav && getSkipDeleteConfirmCookie('delete_run')) {
			void deleteRunGroup(group);
			return;
		}
		deleteRunGroupPending = group;
	}

	async function confirmDeleteRunGroup(mode: 'all' | 'non_favorites') {
		const group = deleteRunGroupPending;
		if (!group) return;
		deleteRunGroupPending = null;
		if (mode === 'non_favorites') {
			const runIdsToDelete = group.runs.filter((r) => !runHasFavoritedOutput(r)).map((r) => r.id);
			if (runIdsToDelete.length === 0) return;
			await deleteRunGroup(group, runIdsToDelete);
		} else {
			await deleteRunGroup(group);
		}
	}

	async function cancelRunGroup(group: ActivityGroup) {
		const toCancel = group.runs.filter((r) => r.status === 'queued' || r.status === 'running');
		if (!toCancel.length) return;
		cancellingGroupIds = [...cancellingGroupIds, group.groupId];
		try {
			for (const run of toCancel) {
				const res = await fetch(`${apiBase}/runs/${run.id}/cancel`, { method: 'POST' });
				if (res.ok) updateRunStorage(run.id, { status: 'cancelled', error: 'Cancelled' });
			}
			await loadQueue();
			await refreshRecentInPlace(true);
		} finally {
			cancellingGroupIds = cancellingGroupIds.filter((id) => id !== group.groupId);
		}
	}

	async function retryRunGroup(group: ActivityGroup) {
		const toRetry = group.runs.filter((r) => r.status === 'queued');
		if (!toRetry.length) return;
		retryingGroupIds = [...retryingGroupIds, group.groupId];
		try {
			for (const run of toRetry) await fetch(`${apiBase}/runs/${run.id}/retry`, { method: 'POST' });
			await loadQueue();
			await refreshRecentInPlace(true);
		} finally {
			retryingGroupIds = retryingGroupIds.filter((id) => id !== group.groupId);
		}
	}

	async function cancelSingleRun(runId: string, status: string) {
		if (status !== 'queued' && status !== 'running') return;
		cancellingRunIds = [...cancellingRunIds, runId];
		try {
			await cancelRun(runId);
			await loadQueue();
			await refreshRecentInPlace(true);
		} finally {
			cancellingRunIds = cancellingRunIds.filter((id) => id !== runId);
		}
	}

	function applyLightboxDeletion(item: LightboxItem) {
		const currentIdx = lightboxImages.findIndex((x) => x.id === item.id);
		const nextImages = lightboxImages.filter((x) => x.id !== item.id);
		if (!nextImages.length) {
			lightboxImages = [];
			lightboxIndex = 0;
			closeLightbox();
			return;
		}
		lightboxImages = nextImages;
		lightboxIndex = currentIdx >= nextImages.length ? nextImages.length - 1 : Math.max(currentIdx, 0);
	}

	async function deleteLightboxLocal(item: LightboxItem) {
		if (!item.runId || item.outputIndex == null) return;
		const hadRemote = item.hasRemote ?? !item.remote_deleted;
		await deleteLocalImage(item.runId, item.outputIndex);
		if (!hadRemote) {
			applyLightboxDeletion(item);
			return;
		}
		const idx = lightboxImages.findIndex((x) => x.id === item.id);
		if (idx !== -1) {
			const next = [...lightboxImages];
			next[idx] = { ...next[idx], hasLocal: false };
			lightboxImages = next;
		}
	}

	async function deleteLightboxRemote(item: LightboxItem) {
		if (!item.runId || item.outputIndex == null) return;
		const hadLocal = item.hasLocal ?? true;
		await deleteRemoteImage(item.runId, item.outputIndex);
		if (!hadLocal) {
			applyLightboxDeletion(item);
			return;
		}
		const idx = lightboxImages.findIndex((x) => x.id === item.id);
		if (idx !== -1) {
			const next = [...lightboxImages];
			next[idx] = { ...next[idx], hasRemote: false, remote_deleted: true };
			lightboxImages = next;
		}
	}

	async function deleteLightboxBoth(item: LightboxItem) {
		if (!item.runId || item.outputIndex == null) return;
		const ok = await deleteBothImage(item.runId, item.outputIndex);
		if (ok) applyLightboxDeletion(item);
	}

	async function thumbDownloadImage(item: { filename: string; subfolder?: string; type?: string }, runId: string) {
		const res = await fetch(imageUrl(item, runId));
		const blob = await res.blob();
		const blobUrl = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = blobUrl;
		a.download = item.filename ?? 'output.png';
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(blobUrl);
	}

	function openAppInProject(group: ActivityGroup) {
		if (!group.app_slug) return;
		const qs = new URLSearchParams();
		if (group.project_id) qs.set('project', group.project_id);
		if (group.firstRunId) qs.set('run_id', group.firstRunId);
		const path = qs.size ? `/app/${group.app_slug}?${qs.toString()}` : `/app/${group.app_slug}`;
		appBooting.set(true);
		goto(path);
	}

	async function loadProjects() {
		if (!browser) return;
		projectsAbort?.abort();
		projectsAbort = new AbortController();
		try {
			const res = await fetch(`${apiBase}/projects?limit=500`, { signal: projectsAbort.signal });
			if (!res.ok) return;
			const raw = await res.json().catch(() => []);
			if (!Array.isArray(raw)) return;
			projectOptions = raw
				.map((p) => ({
					id: String(p?.id ?? ''),
					name: String(p?.name ?? ''),
					headerColor: p?.header_color ? String(p.header_color) : null
				}))
				.filter((p) => p.id && p.name);
			for (const p of raw) {
				const projectId = String(p?.id ?? '');
				if (!projectId) continue;
				const metadata = p?.metadata && typeof p.metadata === 'object' ? (p.metadata as Record<string, unknown>) : {};
				const fav = Array.isArray(metadata.favorites) ? metadata.favorites.map((x) => String(x)) : [];
				if (fav.length) {
					favorites = new Set([...favorites, ...fav]);
					projectMetadataCache = { ...projectMetadataCache, [projectId]: { metadata, favorites: fav } };
				}
			}
		} catch {
			return;
		}
	}

	async function loadQueue() {
		queueAbort?.abort();
		queueAbort = new AbortController();
		queueLoading = queue === null;
		queueError = null;
		try {
			queue = await getQueue();
		} catch (e) {
			queueError = e instanceof Error ? e.message : 'Failed to load queue';
		} finally {
			queueLoading = false;
		}
	}

	async function loadRecent(offset = 0) {
		recentAbort?.abort();
		recentAbort = new AbortController();
		if (offset === 0) {
			recentLoading = true;
			recentError = null;
		} else {
			recentLoadingMore = true;
		}
		try {
			const data = await getRecentRuns({
				projectId: filterProjectId || undefined,
				status: currentStatusFilter(),
				q: filterQuery || undefined,
				limit: PAGE_SIZE,
				offset
			});
			const mapped = (data.runs ?? []).map(normalizeRecent);
			if (offset === 0) recentRuns = mapped;
			else recentRuns = [...recentRuns, ...mapped];
			totalRecent = typeof data.total === 'number' ? data.total : recentRuns.length;
			void refetchStorageSizesForActivityRuns(mapped);
		} catch (e) {
			recentError = e instanceof Error ? e.message : 'Failed to load recent generations';
			if (offset === 0) {
				recentRuns = [];
				totalRecent = 0;
			}
		} finally {
			recentLoading = false;
			recentLoadingMore = false;
		}
	}

	async function refreshRecentInPlace(ignoreLoadingGuard = false) {
		// Keep infinite-scroll stability: refresh the top slice without
		// replacing already loaded pages or collapsing list length.
		if (!ignoreLoadingGuard && (recentLoading || recentLoadingMore)) return;
		try {
			const data = await getRecentRuns({
				projectId: filterProjectId || undefined,
				status: currentStatusFilter(),
				q: filterQuery || undefined,
				limit: PAGE_SIZE,
				offset: 0
			});
			const top = (data.runs ?? []).map(normalizeRecent);
			const topIds = new Set(top.map((r) => r.id));
			const rest = recentRuns.filter((r) => !topIds.has(r.id));
			recentRuns = [...top, ...rest];
			totalRecent = typeof data.total === 'number' ? data.total : totalRecent;
			void refetchStorageSizesForActivityRuns(top);
		} catch {
			return;
		}
	}

	function startPolling() {
		if (!browser) return;
		if (!queuePollId) queuePollId = setInterval(loadQueue, QUEUE_POLL_MS);
		if (!recentPollId) recentPollId = setInterval(refreshRecentInPlace, RECENT_POLL_MS);
	}

	function stopPolling() {
		if (queuePollId) clearInterval(queuePollId);
		if (recentPollId) clearInterval(recentPollId);
		queuePollId = null;
		recentPollId = null;
	}

	function selectProject(projectId: string) {
		filterProjectId = projectId;
		projectPickerOpen = false;
		projectPickerSearch = '';
	}

	$effect(() => {
		if (!browser) return;
		filterProjectId;
		filterStatus;
		filterQuery;
		const timer = setTimeout(() => {
			loadRecent(0);
		}, 220);
		return () => clearTimeout(timer);
	});

	$effect(() => {
		if (!deleteRunGroupPending || !browser) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				e.preventDefault();
				deleteRunGroupPending = null;
			}
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});

	function useLoadMoreSentinel(node: HTMLElement) {
		let observer: IntersectionObserver | null = null;
		function setup() {
			observer = new IntersectionObserver(
				(entries) => {
					for (const entry of entries) {
						if (!entry.isIntersecting) continue;
						if (recentLoading || recentLoadingMore || !hasMoreRecent) continue;
						loadRecent(recentRuns.length);
					}
				},
				{ root: null, rootMargin: '300px', threshold: 0 }
			);
			observer.observe(node);
		}
		setup();
		return {
			destroy() {
				observer?.disconnect();
			}
		};
	}

	if (browser) {
		readProjectParam();
		loadProjects();
		loadQueue();
		startPolling();
	}

	onDestroy(() => {
		stopPolling();
		queueAbort?.abort();
		recentAbort?.abort();
		projectsAbort?.abort();
	});
</script>

<section class="activity-page">
	<header class="page-header">
		<h1>Activity</h1>
		<div class="gallery-controls-right">
		<div class="gallery-thumb-size">
			<label for="activity-thumb-size">Thumbnail size</label>
			<input
				id="activity-thumb-size"
				type="range"
				min={THUMB_SCALE_MIN}
				max={THUMB_SCALE_MAX}
				step="1"
				value={thumbnailScale}
				oninput={(e) => setThumbnailScale((e.currentTarget as HTMLInputElement).valueAsNumber)}
				aria-label="Thumbnail size percentage"
			/>
			<span class="thumb-size-value">{thumbnailScale}%</span>
		</div>
		<div class="gallery-thumb-fit" role="group" aria-label="Thumbnail render mode">
			<button
				type="button"
				class="thumb-fit-btn"
				class:active={thumbnailFitMode === 'cover'}
				onclick={() => setThumbnailFitMode('cover')}
				title="Default thumbnail"
				aria-label="Default thumbnail"
				aria-pressed={thumbnailFitMode === 'cover'}
			>
				Default thumbnail
			</button>
			<button
				type="button"
				class="thumb-fit-btn"
				class:active={thumbnailFitMode === 'contain'}
				onclick={() => setThumbnailFitMode('contain')}
				title="Fit into thumbnail"
				aria-label="Fit into thumbnail"
				aria-pressed={thumbnailFitMode === 'contain'}
			>
				Fit into thumbnail
			</button>
		</div>
		<label class="thumb-filename-option" title="Show output filenames on thumbnails">
			<span class="thumb-filename-label">Filenames</span>
			<button
				type="button"
				role="switch"
				aria-checked={showThumbFilename}
				class="thumb-filename-toggle"
				class:on={showThumbFilename}
				aria-label="Show filenames on thumbnails"
				onclick={() => setShowThumbFilename(!showThumbFilename)}
			>
				<span class="thumb-filename-toggle-track">
					<span class="thumb-filename-toggle-thumb"></span>
				</span>
			</button>
		</label>
		</div>
	</header>

	<section class="card">
		<div class="card-head">
			<h2>Now</h2>
			<span class="badge">{activeCount} active</span>
		</div>
		{#if queueLoading}
			<p class="muted">Loading queue…</p>
		{:else if queueError}
			<p class="error">{queueError}</p>
		{:else if !nowGroups.length}
			<p class="muted">No queued or running generations.</p>
		{:else}
			{#each nowGroups as group (group.groupId)}
				<section class="run-section">
					<header class="run-header">
						<div class="run-title">
							<span class="run-dot"></span>
							<RunAppBadge appHeaderColor={group.app_header_color ?? undefined} label={group.app_title ?? group.app_slug ?? 'App'} />
							<span class="group-project-pill" title={`Project: ${getProjectInfo(group.project_id, group.project_title).name}`}>
								<span class="group-project-dot" style={`background:${getProjectInfo(group.project_id, group.project_title).color ?? 'var(--muted)'}`}></span>
								{getProjectInfo(group.project_id, group.project_title).name}
							</span>
							{#if group.status === 'error'}
								<span class="run-status error">✗ Error</span>
							{:else if group.status === 'running'}
								<span class="run-status running">⌛ Generating…</span>
								<button type="button" class="run-header-cancel-btn" disabled={cancellingGroupIds.includes(group.groupId)} onclick={() => cancelRunGroup(group)}>
									{#if cancellingGroupIds.includes(group.groupId)}…{:else}Cancel{/if}
								</button>
							{:else if group.status === 'queued'}
								<span class="run-status queued">In queue</span>
								<button type="button" class="run-header-cancel-btn" disabled={cancellingGroupIds.includes(group.groupId)} onclick={() => cancelRunGroup(group)}>
									{#if cancellingGroupIds.includes(group.groupId)}…{:else}Cancel{/if}
								</button>
							{:else if group.status === 'cancelled'}
								<span class="run-status cancelled">Cancelled</span>
							{/if}
							<span class="run-count">{group.runCount} prompt{group.runCount === 1 ? '' : 's'} · {outputCount(group)} image{outputCount(group) === 1 ? '' : 's'}</span>
						</div>
						<RunHeaderActions
							storageSummary={getGroupStorageSummary(group)}
							localStorageBytes={sumKnownStorageBytes(group, 'local_storage_bytes')}
							remoteStorageBytes={sumKnownStorageBytes(group, 'remote_storage_bytes')}
							status={group.status}
							createdAt={group.createdAt}
							saveDisabled={savingGroupIds.includes(group.groupId)}
							saveLoading={savingGroupIds.includes(group.groupId)}
							onSave={() => saveRunGroup(group)}
							remoteDisabled={deletingGroupIds.includes(group.groupId)}
							remoteLoading={deletingGroupIds.includes(group.groupId)}
							onDeleteRemote={() => deleteRemoteSelectedOrGroup(group)}
							localDisabled={deletingLocalGroupIds.includes(group.groupId)}
							localLoading={deletingLocalGroupIds.includes(group.groupId)}
							onDeleteLocal={() => deleteLocalSelectedOrGroup(group)}
							allDisabled={deletingBothGroupIds.includes(group.groupId)}
							allLoading={deletingBothGroupIds.includes(group.groupId)}
							onDeleteAll={() => deleteBothSelectedOrGroup(group)}
							deleteRunDisabled={group.runs.some((r) => deletingRunIds.includes(r.id))}
							deleteRunLoading={group.runs.some((r) => deletingRunIds.includes(r.id))}
							onDeleteRun={() => requestDeleteRunGroup(group)}
							showReplicate={!!group.app_slug}
							onReplicate={() => openAppInProject(group)}
							showShowMetadata={true}
							onShowMetadata={() => { metadataPanelRunId = group.firstRunId; metadataPanelMode = 'run'; }}
							hasSelection={hasSelection(group.groupId)}
						/>
					</header>
					<div class="run-body">
						{#if hasSelection(group.groupId)}
							<div class="run-selection-bar">
								<span>{selectedInGroup[group.groupId]?.length ?? 0} selected</span>
								<button type="button" class="run-action-btn" onclick={() => { selectedInGroup = { ...selectedInGroup, [group.groupId]: [] }; }}>Clear</button>
							</div>
						{/if}
						{#if group.runs.some((r) => r.status === 'queued' || r.status === 'running')}
							<div class="run-queue-strip">
								{#each group.runs.filter((r) => r.status === 'queued' || r.status === 'running') as run (run.id)}
									<span class="run-queue-item">
										<span class="run-queue-status">{run.status === 'running' ? 'Generating…' : 'Queued'}{#if run.queue_position} (position {run.queue_position}){/if}</span>
										<button type="button" class="run-action-btn cancel" disabled={cancellingRunIds.includes(run.id)} onclick={() => cancelSingleRun(run.id, run.status)}>
											{#if cancellingRunIds.includes(run.id)}…{:else}Cancel{/if}
										</button>
									</span>
								{/each}
							</div>
						{/if}
						{#if group.status === 'queued' && group.comfyui_unreachable_warning}
							<div class="comfyui-unreachable-warning">
								<span>{group.comfyui_unreachable_warning}</span>
								<button type="button" class="run-action-btn" disabled={retryingGroupIds.includes(group.groupId)} onclick={() => retryRunGroup(group)}>
									{#if retryingGroupIds.includes(group.groupId)}Retrying…{:else}Retry{/if}
								</button>
							</div>
						{/if}
						<div class="output-section-body" class:thumb-fit-contain={thumbnailFitMode === 'contain'} style={`--thumb-size-scale:${thumbnailScale / 100};`}>
							{#each group.runs as run (run.id)}
								{#each (run.images ?? []) as item, origI (run.id + '_' + origI)}
									{@const isVideo = mediaType(item) === 'video'}
									{@const thumbKey = `${group.groupId}-${run.id}-${origI}`}
									{#if !item.remote_deleted}
									<div
										class="output-thumb thumb-media"
										class:thumb-selected={isImageSelected(group.groupId, imageKey(run.id, origI))}
										role="button"
										tabindex="0"
										aria-label={`Open output ${origI + 1} in viewer`}
										onmouseenter={() => {
											if (!isVideo) return;
											playingVideoThumbReady = false;
											playingVideoThumbKey = thumbKey;
										}}
										onmouseleave={() => {
											if (!isVideo || playingVideoThumbKey !== thumbKey) return;
											playingVideoThumbKey = null;
										}}
										onclick={() => openLightboxFromImage(group, run.id, origI)}
										onkeydown={(e) => {
											if (e.key === 'Enter' || e.key === ' ') {
												e.preventDefault();
												openLightboxFromImage(group, run.id, origI);
											}
										}}
									>
										<ThumbnailOverlay
											mediaType={mediaType(item)}
											seed={run.seed ?? undefined}
											executionTimeSec={run.execution_time ?? undefined}
											fileName={item.filename}
											showFilenameAlways={showThumbFilename}
											showMetadata={true}
											isFavorite={isOutputFavorite(run.id, origI)}
											isSelected={isImageSelected(group.groupId, imageKey(run.id, origI))}
											showFavorite={true}
											showSelection={true}
											showSeed={true}
											showDownload={true}
											showSendToApp={true}
											onMetadataClick={() => { metadataPanelRunId = run.id; metadataPanelMode = 'output'; }}
											onToggleFavorite={() => { void toggleFavorite(run); }}
											onToggleSelection={() => toggleImageSelection(group.groupId, imageKey(run.id, origI))}
											onDownload={() => thumbDownloadImage(item, run.id)}
											onSendToApp={() => { sendToAppRunId = run.id; sendToAppOutputIndex = origI; sendToAppProjectId = run.project_id; }}
										>
											{#if isVideo}
												{#if playingVideoThumbKey === thumbKey}
													<video
														src={imageUrl(item, run.id)}
														preload="metadata"
														autoplay
														muted
														playsinline
														loop
														aria-hidden="true"
														onloadedmetadata={() => {
															if (playingVideoThumbKey !== thumbKey) return;
															playingVideoThumbReady = true;
														}}
														onerror={() => {
															if (playingVideoThumbKey !== thumbKey) return;
															playingVideoThumbReady = true;
														}}
													></video>
												{:else}
													<img src={videoThumbnailPreviewUrl(item, run.id)} alt="" loading="lazy" />
												{/if}
												<span class="output-thumb-play" aria-hidden="true" title="Play video">
													<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
												</span>
											{:else if mediaType(item) === 'audio'}
												<audio src={imageUrl(item, run.id)} controls preload="metadata"></audio>
											{:else}
												<img src={previewImageUrl(item, run.id)} alt="" loading="lazy" />
											{/if}
										</ThumbnailOverlay>
									</div>
									{/if}
								{/each}
							{/each}
						</div>
						{#if group.runs.every((r) => (r.images ?? []).filter((img) => !img.remote_deleted).length === 0)}
							<div class="run-group-no-images">No outputs</div>
						{/if}
					</div>
				</section>
			{/each}
		{/if}
	</section>

	<section class="card">
		<div class="card-head">
			<h2>Recent</h2>
			<span class="badge">{totalRecent} total</span>
		</div>
		<div class="filters">
			<div class="project-picker-wrap">
				<label class="filter-label">Project</label>
				<button
					type="button"
					class="project-picker-toggle"
					onclick={() => (projectPickerOpen = !projectPickerOpen)}
					aria-label="Filter by project"
					aria-expanded={projectPickerOpen}
				>
					<span class="project-picker-label">
						{#if selectedProject}
							<span class="project-color-dot" style={selectedProject.headerColor ? `background:${selectedProject.headerColor}` : ''}></span>
							<span class="project-picker-name">{selectedProject.name}</span>
						{:else}
							<span class="project-color-dot neutral"></span>
							<span class="project-picker-name">All projects</span>
						{/if}
					</span>
					<span class="project-picker-chevron">▾</span>
				</button>
				{#if projectPickerOpen}
					<div class="project-picker-popover">
						<input
							type="search"
							class="project-picker-search"
							placeholder="Filter projects…"
							bind:value={projectPickerSearch}
							aria-label="Filter projects list"
						/>
						<div class="project-picker-list">
							<button type="button" class="project-option" onclick={() => selectProject('')}>
								<span class="project-color-dot neutral"></span>
								<span class="project-option-name">All projects</span>
							</button>
							{#each filteredProjectOptions as p (p.id)}
								<button type="button" class="project-option" onclick={() => selectProject(p.id)}>
									<span class="project-color-dot" style={p.headerColor ? `background:${p.headerColor}` : ''}></span>
									<span class="project-option-name">{p.name}</span>
								</button>
							{/each}
						</div>
					</div>
				{/if}
			</div>
			<label class="search">
				Search
				<input bind:value={filterQuery} placeholder="App, metadata, or project id" />
			</label>
		</div>
		{#if recentLoading}
			<p class="muted">Loading recent generations…</p>
		{:else if recentError}
			<p class="error">{recentError}</p>
		{:else if !recentGroups.length}
			<p class="muted">No recent generations match your filters.</p>
		{:else}
			{#each recentGroups as group (group.groupId)}
				<section class="run-section">
					<header class="run-header">
						<div class="run-title">
							<span class="run-dot"></span>
							<RunAppBadge appHeaderColor={group.app_header_color ?? undefined} label={group.app_title ?? group.app_slug ?? 'App'} />
							<span class="group-project-pill" title={`Project: ${getProjectInfo(group.project_id, group.project_title).name}`}>
								<span class="group-project-dot" style={`background:${getProjectInfo(group.project_id, group.project_title).color ?? 'var(--muted)'}`}></span>
								{getProjectInfo(group.project_id, group.project_title).name}
							</span>
							{#if group.status === 'error'}
								<span class="run-status error">✗ Error</span>
							{:else if group.status === 'running'}
								<span class="run-status running">⌛ Generating…</span>
							{:else if group.status === 'queued'}
								<span class="run-status queued">In queue</span>
							{:else if group.status === 'cancelled'}
								<span class="run-status cancelled">Cancelled</span>
							{/if}
							<span class="run-count">{group.runCount} prompt{group.runCount === 1 ? '' : 's'} · {outputCount(group)} image{outputCount(group) === 1 ? '' : 's'}</span>
						</div>
						<RunHeaderActions
							storageSummary={getGroupStorageSummary(group)}
							localStorageBytes={sumKnownStorageBytes(group, 'local_storage_bytes')}
							remoteStorageBytes={sumKnownStorageBytes(group, 'remote_storage_bytes')}
							status={group.status}
							createdAt={group.createdAt}
							saveDisabled={savingGroupIds.includes(group.groupId)}
							saveLoading={savingGroupIds.includes(group.groupId)}
							onSave={() => saveRunGroup(group)}
							remoteDisabled={deletingGroupIds.includes(group.groupId)}
							remoteLoading={deletingGroupIds.includes(group.groupId)}
							onDeleteRemote={() => deleteRemoteSelectedOrGroup(group)}
							localDisabled={deletingLocalGroupIds.includes(group.groupId)}
							localLoading={deletingLocalGroupIds.includes(group.groupId)}
							onDeleteLocal={() => deleteLocalSelectedOrGroup(group)}
							allDisabled={deletingBothGroupIds.includes(group.groupId)}
							allLoading={deletingBothGroupIds.includes(group.groupId)}
							onDeleteAll={() => deleteBothSelectedOrGroup(group)}
							deleteRunDisabled={group.runs.some((r) => deletingRunIds.includes(r.id))}
							deleteRunLoading={group.runs.some((r) => deletingRunIds.includes(r.id))}
							onDeleteRun={() => requestDeleteRunGroup(group)}
							showReplicate={!!group.app_slug}
							onReplicate={() => openAppInProject(group)}
							showShowMetadata={true}
							onShowMetadata={() => { metadataPanelRunId = group.firstRunId; metadataPanelMode = 'run'; }}
							hasSelection={hasSelection(group.groupId)}
						/>
					</header>
					<div class="run-body">
						{#if hasSelection(group.groupId)}
							<div class="run-selection-bar">
								<span>{selectedInGroup[group.groupId]?.length ?? 0} selected</span>
								<button type="button" class="run-action-btn" onclick={() => { selectedInGroup = { ...selectedInGroup, [group.groupId]: [] }; }}>Clear</button>
							</div>
						{/if}
						<div class="output-section-body" class:thumb-fit-contain={thumbnailFitMode === 'contain'} style={`--thumb-size-scale:${thumbnailScale / 100};`}>
							{#each group.runs as run (run.id)}
								{#each (run.images ?? []) as item, origI (run.id + '_' + origI)}
									{@const isVideo = mediaType(item) === 'video'}
									{@const thumbKey = `${group.groupId}-${run.id}-${origI}`}
									{#if !item.remote_deleted}
									<div
										class="output-thumb thumb-media"
										class:thumb-selected={isImageSelected(group.groupId, imageKey(run.id, origI))}
										role="button"
										tabindex="0"
										aria-label={`Open output ${origI + 1} in viewer`}
										onmouseenter={() => {
											if (!isVideo) return;
											playingVideoThumbReady = false;
											playingVideoThumbKey = thumbKey;
										}}
										onmouseleave={() => {
											if (!isVideo || playingVideoThumbKey !== thumbKey) return;
											playingVideoThumbKey = null;
										}}
										onclick={() => openLightboxFromImage(group, run.id, origI)}
										onkeydown={(e) => {
											if (e.key === 'Enter' || e.key === ' ') {
												e.preventDefault();
												openLightboxFromImage(group, run.id, origI);
											}
										}}
									>
										<ThumbnailOverlay
											mediaType={mediaType(item)}
											seed={run.seed ?? undefined}
											executionTimeSec={run.execution_time ?? undefined}
											fileName={item.filename}
											showFilenameAlways={showThumbFilename}
											showMetadata={true}
											isFavorite={isOutputFavorite(run.id, origI)}
											isSelected={isImageSelected(group.groupId, imageKey(run.id, origI))}
											showFavorite={true}
											showSelection={true}
											showSeed={true}
											showDownload={true}
											showSendToApp={true}
											onMetadataClick={() => { metadataPanelRunId = run.id; metadataPanelMode = 'output'; }}
											onToggleFavorite={() => { void toggleFavorite(run); }}
											onToggleSelection={() => toggleImageSelection(group.groupId, imageKey(run.id, origI))}
											onDownload={() => thumbDownloadImage(item, run.id)}
											onSendToApp={() => { sendToAppRunId = run.id; sendToAppOutputIndex = origI; sendToAppProjectId = run.project_id; }}
										>
											{#if isVideo}
												{#if playingVideoThumbKey === thumbKey}
													<video
														src={imageUrl(item, run.id)}
														preload="metadata"
														autoplay
														muted
														playsinline
														loop
														aria-hidden="true"
														onloadedmetadata={() => {
															if (playingVideoThumbKey !== thumbKey) return;
															playingVideoThumbReady = true;
														}}
														onerror={() => {
															if (playingVideoThumbKey !== thumbKey) return;
															playingVideoThumbReady = true;
														}}
													></video>
												{:else}
													<img src={videoThumbnailPreviewUrl(item, run.id)} alt="" loading="lazy" />
												{/if}
												<span class="output-thumb-play" aria-hidden="true" title="Play video">
													<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
												</span>
											{:else if mediaType(item) === 'audio'}
												<audio src={imageUrl(item, run.id)} controls preload="metadata"></audio>
											{:else}
												<img src={previewImageUrl(item, run.id)} alt="" loading="lazy" />
											{/if}
										</ThumbnailOverlay>
									</div>
									{/if}
								{/each}
							{/each}
						</div>
						{#if group.runs.every((r) => (r.images ?? []).filter((img) => !img.remote_deleted).length === 0)}
							<div class="run-group-no-images">No outputs</div>
						{/if}
					</div>
				</section>
			{/each}
			{#if hasMoreRecent}
				<div class="load-more">
					<button type="button" disabled={recentLoadingMore} onclick={() => loadRecent(recentRuns.length)}>
						{recentLoadingMore ? 'Loading…' : 'Load more'}
					</button>
				</div>
				<div class="load-more-sentinel" use:useLoadMoreSentinel aria-hidden="true"></div>
			{/if}
		{/if}
	</section>
</section>

{#if deleteRunGroupPending}
	{@const group = deleteRunGroupPending}
	{@const runIds = group.runs.map((r) => r.id)}
	{@const n = runIds.length}
	{@const hasFav = group.runs.some((r) => runHasFavoritedOutput(r))}
	{@const mainMsg = n > 1
		? `Delete ${n} generations permanently? This cannot be undone.`
		: 'Delete this prompt (and all its files) permanently? This cannot be undone.'}
	{#if hasFav}
		<div
			class="confirm-delete-overlay activity-delete-run-overlay"
			role="dialog"
			aria-modal="true"
			aria-labelledby="activity-delete-run-fav-title"
			tabindex="-1"
			onclick={() => { deleteRunGroupPending = null; }}
			onkeydown={(e) => { if (e.key === 'Escape') deleteRunGroupPending = null; }}
		>
			<div class="confirm-delete-card delete-run-fav-card" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
				<p id="activity-delete-run-fav-title" class="confirm-delete-title">Delete Run</p>
				<p class="confirm-delete-msg">This run includes favorited generations. What do you want to do?</p>
				<div class="delete-run-fav-actions">
					<button
						type="button"
						class="confirm-delete-btn danger"
						onclick={async () => { await confirmDeleteRunGroup('non_favorites'); }}
					>Delete non-favorites only</button>
					<button
						type="button"
						class="confirm-delete-btn danger"
						onclick={async () => { await confirmDeleteRunGroup('all'); }}
					>Delete all (including favorites)</button>
					<button
						type="button"
						class="confirm-delete-btn secondary"
						onclick={() => { deleteRunGroupPending = null; }}
					>Cancel</button>
				</div>
			</div>
		</div>
	{:else}
		<ConfirmDeleteDialog
			open={true}
			title="Delete Run with all of its generations"
			message={mainMsg}
			confirmLabel="Delete Run"
			onConfirm={async (dontShowAgain) => {
				if (dontShowAgain) setSkipDeleteConfirmCookie('delete_run', true);
				await confirmDeleteRunGroup('all');
			}}
			onCancel={() => { deleteRunGroupPending = null; }}
		/>
	{/if}
{/if}

{#if metadataPanelRunId}
	<RunMetadataPanel
		runId={metadataPanelRunId}
		projectId={nowGroups.find((g) => g.firstRunId === metadataPanelRunId)?.project_id ?? recentGroups.find((g) => g.firstRunId === metadataPanelRunId)?.project_id ?? null}
		mode={metadataPanelMode}
		embedWorkflowuiMetadataOnDownload={false}
		onClose={() => { metadataPanelRunId = null; }}
	/>
{/if}

{#if sendToAppRunId != null && sendToAppOutputIndex != null && sendToAppProjectId}
	<SendToAppDialog
		open={true}
		sendFromRun={sendToAppRunId}
		sendFromOutput={sendToAppOutputIndex}
		projectId={sendToAppProjectId}
		onClose={() => { sendToAppRunId = null; sendToAppOutputIndex = null; sendToAppProjectId = null; }}
	/>
{/if}

<LightboxViewer
	open={lightboxOpen}
	items={lightboxImages}
	index={lightboxIndex}
	onIndexChange={(i) => { lightboxIndex = i; }}
	onClose={closeLightbox}
	onDownload={downloadLightboxItem}
	onMetadata={(item) => { closeLightbox(); metadataPanelRunId = item.runId ?? null; metadataPanelMode = 'output'; }}
	onToggleFavorite={(item) => {
		if (!item.runId) return;
		const run = findRunById(item.runId);
		if (!run) return;
		void toggleFavorite(run);
	}}
	isFavorite={(item) =>
		!!item.runId && item.outputIndex != null && isOutputFavorite(item.runId, item.outputIndex)}
	onToggleSelection={lightboxGroupId ? (item) => toggleImageSelection(lightboxGroupId, item.id) : undefined}
	isSelected={lightboxGroupId ? (item) => isImageSelected(lightboxGroupId, item.id) : undefined}
	onSendToApp={(item) => {
		if (!item.runId || item.outputIndex == null) return;
		const run = findRunById(item.runId);
		sendToAppRunId = item.runId;
		sendToAppOutputIndex = item.outputIndex;
		sendToAppProjectId = run?.project_id ?? null;
		closeLightbox();
	}}
	onDeleteLocal={(item) => {
		if (window.confirm('Delete local file?')) void deleteLightboxLocal(item);
	}}
	onDeleteRemote={(item) => {
		if (window.confirm('Delete remote file?')) void deleteLightboxRemote(item);
	}}
	onDeleteBoth={(item) => {
		if (window.confirm('Delete local and remote file?')) void deleteLightboxBoth(item);
	}}
	showCloseLabel={false}
	ariaTitle="Activity media viewer"
/>

<style>
	.activity-page { padding: 1rem; display: flex; flex-direction: column; gap: 1rem; }
	.page-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		position: sticky;
		top: 0;
		z-index: 5;
		background: var(--bg);
		padding-bottom: 0.5rem;
		border-bottom: 1px solid var(--border);
	}
	.page-header h1 { margin: 0; }
	.gallery-controls-right { display: inline-flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; justify-content: flex-end; }
	.subtitle { margin: 0.35rem 0 0; color: var(--muted); }
	.gallery-thumb-size { display: inline-flex; align-items: center; gap: 0.5rem; }
	.gallery-thumb-size label { font-size: 0.8rem; color: var(--muted); }
	.gallery-thumb-size input[type='range'] { width: min(280px, 52vw); }
	.thumb-size-value { min-width: 3.5rem; font-size: 0.8rem; color: var(--muted); text-align: right; }
	.gallery-thumb-fit { display: inline-flex; align-items: center; gap: 0.35rem; }
	.thumb-filename-option {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		user-select: none;
		font-size: 0.8rem;
		color: var(--text-muted, var(--muted));
	}
	.thumb-filename-label {
		white-space: nowrap;
		font-weight: 500;
	}
	.thumb-filename-toggle {
		display: inline-flex;
		align-items: center;
		cursor: pointer;
		background: none;
		border: none;
		padding: 0;
		margin: 0;
		color: inherit;
	}
	.thumb-filename-toggle:focus-visible {
		outline: 1px solid var(--accent);
		outline-offset: 2px;
		border-radius: 4px;
	}
	.thumb-filename-toggle-track {
		display: inline-flex;
		align-items: center;
		width: 32px;
		height: 18px;
		border-radius: 9px;
		background: var(--border);
		transition: background 0.2s;
		padding: 2px;
	}
	.thumb-filename-toggle:hover .thumb-filename-toggle-track {
		background: color-mix(in srgb, var(--text-muted) 25%, var(--border));
	}
	.thumb-filename-toggle.on .thumb-filename-toggle-track {
		background: color-mix(in srgb, var(--accent) 60%, var(--border));
	}
	.thumb-filename-toggle-thumb {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--surface);
		box-shadow: 0 1px 2px rgba(0,0,0,0.2);
		transition: transform 0.2s ease;
	}
	.thumb-filename-toggle.on .thumb-filename-toggle-thumb {
		transform: translateX(14px);
	}
	.thumb-fit-btn { border: 1px solid var(--border); border-radius: 8px; background: var(--surface); color: var(--muted); padding: 0.28rem 0.5rem; font: inherit; font-size: 0.78rem; cursor: pointer; }
	.thumb-fit-btn.active { color: var(--text); border-color: color-mix(in srgb, var(--accent) 55%, var(--border)); box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 25%, transparent) inset; }
	.card { border: 1px solid var(--border); border-radius: 12px; padding: 0.9rem; background: var(--card); }
	.card-head { display: flex; align-items: center; justify-content: space-between; gap: 0.6rem; margin-bottom: 0.75rem; }
	.badge { font-size: 0.78rem; padding: 0.18rem 0.45rem; border-radius: 999px; border: 1px solid var(--border); color: var(--muted); }
	.filters { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.6rem; margin-bottom: 0.8rem; }
	.filters label { display: flex; flex-direction: column; gap: 0.25rem; font-size: 0.84rem; color: var(--muted); }
	.filters select, .filters input, .filters button { background: var(--surface); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 0.45rem 0.55rem; font: inherit; }
	.filter-label { display: inline-flex; margin-bottom: 0.25rem; font-size: 0.84rem; color: var(--muted); }
	.project-picker-wrap { position: relative; min-width: 0; }
	.project-picker-toggle {
		width: 100%;
		min-width: 0;
		padding: 0.45rem 0.55rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		cursor: pointer;
	}
	.project-picker-label { min-width: 0; display: flex; align-items: center; gap: 0.45rem; }
	.project-picker-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: left; }
	.project-picker-chevron { color: var(--muted); flex-shrink: 0; }
	.project-picker-popover {
		position: absolute;
		top: calc(100% + 0.35rem);
		left: 0;
		width: min(360px, 70vw);
		border: 1px solid var(--border);
		border-radius: 8px;
		background: var(--card-bg, var(--card));
		z-index: 200;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
		padding: 0.45rem;
	}
	.project-picker-search {
		width: 100%;
		margin-bottom: 0.4rem;
		padding: 0.45rem 0.55rem;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--surface);
		color: var(--text);
	}
	.project-picker-list { max-height: 260px; overflow: auto; display: flex; flex-direction: column; gap: 0.2rem; }
	.project-option {
		width: 100%;
		border: 1px solid transparent;
		border-radius: 6px;
		background: rgba(255, 255, 255, 0.02);
		color: inherit;
		cursor: pointer;
		text-align: left;
		padding: 0.35rem 0.45rem;
		display: flex;
		align-items: center;
		gap: 0.45rem;
	}
	.project-option:hover { border-color: var(--accent); background: rgba(255, 255, 255, 0.05); }
	.project-option-name { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.project-color-dot { width: 0.62rem; height: 0.62rem; border-radius: 999px; background: var(--muted); flex-shrink: 0; }
	.project-color-dot.neutral { opacity: 0.6; }
	.run-section { margin-bottom: 0.8rem; border: 1px solid var(--border); border-radius: 10px; overflow: hidden; background: var(--card-bg, var(--card)); }
	.run-header { display: flex; justify-content: space-between; gap: 0.6rem; padding: 0.5rem 0.6rem; border-bottom: 1px solid var(--border); }
	.run-title { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; min-width: 0; }
	.run-dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; background: var(--accent); }
	.group-project-pill { display: inline-flex; align-items: center; gap: 0.35rem; font-size: 0.76rem; color: var(--muted); border: 1px solid var(--border); border-radius: 999px; padding: 0.08rem 0.42rem; }
	.group-project-dot { width: 0.5rem; height: 0.5rem; border-radius: 50%; flex: 0 0 auto; }
	.run-status { font-size: 0.75rem; }
	.run-status.error { color: var(--error, #ef4444); }
	.run-status.running, .run-status.queued { color: var(--warning, #eab308); }
	.run-status.cancelled { color: var(--muted); }
	.run-header-cancel-btn { border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text); padding: 0.2rem 0.45rem; font: inherit; cursor: pointer; }
	.run-count { color: var(--muted); font-size: 0.84rem; }
	.run-body { padding: 0.6rem; }
	.run-queue-strip { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-bottom: 0.5rem; }
	.run-queue-item { display: inline-flex; align-items: center; gap: 0.4rem; border: 1px dashed var(--border); border-radius: 999px; padding: 0.2rem 0.45rem; }
	.run-selection-bar { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.45rem; color: var(--muted); font-size: 0.8rem; }
	.run-queue-status { font-size: 0.8rem; color: var(--muted); }
	.run-action-btn { border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text); padding: 0.2rem 0.45rem; font: inherit; cursor: pointer; }
	.run-action-btn.cancel { color: var(--error, #ef4444); }
	.comfyui-unreachable-warning { border: 1px solid color-mix(in srgb, var(--warning, #eab308) 45%, var(--border)); border-radius: 8px; padding: 0.4rem 0.55rem; margin-bottom: 0.55rem; display: flex; justify-content: space-between; gap: 0.5rem; color: var(--warning, #eab308); }
	.output-section-body { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.75rem; }
	.output-section-body { grid-template-columns: repeat(auto-fill, minmax(calc(260px * var(--thumb-size-scale, 1)), 1fr)); }
	.output-thumb { position: relative; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; background: var(--surface); aspect-ratio: 1; display: block; }
	.output-thumb.thumb-selected { box-shadow: 0 0 0 2px var(--accent); }
	.output-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
	.output-thumb video { width: 100%; height: 100%; object-fit: cover; display: block; }
	.output-section-body.thumb-fit-contain .output-thumb img,
	.output-section-body.thumb-fit-contain .output-thumb video { object-fit: contain; background: #0b0b0b; }
	.output-thumb audio { width: 100%; height: 100%; min-height: 70px; }
	.output-thumb[role='button'] { cursor: pointer; }
	.output-thumb-play { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; background: rgba(0, 0, 0, 0.2); pointer-events: none; transition: background 0.15s ease; }
	.output-thumb:hover .output-thumb-play { background: rgba(0, 0, 0, 0.4); }
	.output-thumb-play svg { width: 48px; height: 48px; color: #fff; filter: drop-shadow(0 1px 3px rgba(0,0,0,0.8)); }
	.load-more-sentinel { width: 100%; height: 1px; }
	.run-group-no-images { color: var(--muted); font-size: 0.84rem; padding-top: 0.45rem; }
	.load-more { margin-top: 0.75rem; }
	.muted { color: var(--muted); }
	.error { color: var(--error, #ef4444); }

	/* Delete run group + favorites (align with project page) */
	.activity-delete-run-overlay.confirm-delete-overlay {
		z-index: 110000;
	}
	.confirm-delete-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 110000;
	}
	.confirm-delete-card.delete-run-fav-card {
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		padding: 0.75rem 1rem;
		max-width: 22rem;
		width: calc(100% - 2rem);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
	}
	.confirm-delete-card .confirm-delete-title {
		margin: 0 0 0.35rem 0;
		font-size: 0.95rem;
		font-weight: 600;
		color: var(--text);
	}
	.confirm-delete-card .confirm-delete-msg {
		margin: 0 0 0.75rem 0;
		font-size: 0.85rem;
		line-height: 1.35;
		color: var(--muted);
		white-space: pre-line;
	}
	.delete-run-fav-actions {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-top: 0.5rem;
	}
	.delete-run-fav-actions .confirm-delete-btn {
		padding: 0.35rem 0.75rem;
		border-radius: 6px;
		font-size: 0.85rem;
		font-weight: 500;
		cursor: pointer;
		border: 1px solid transparent;
	}
	.delete-run-fav-actions .confirm-delete-btn.secondary {
		background: var(--surface);
		color: var(--text);
		border-color: var(--border);
	}
	.delete-run-fav-actions .confirm-delete-btn.secondary:hover {
		background: color-mix(in srgb, var(--accent) 15%, var(--surface));
		border-color: var(--accent);
	}
	.delete-run-fav-actions .confirm-delete-btn.danger {
		background: var(--error, #c55);
		color: white;
		border-color: var(--error, #c55);
	}
	.delete-run-fav-actions .confirm-delete-btn.danger:hover {
		background: var(--error-hover, #e55);
		border-color: var(--error-hover, #e55);
	}
	@media (max-width: 900px) {
		.page-header { flex-direction: column; align-items: flex-start; }
		.gallery-controls-right { width: 100%; justify-content: flex-start; }
		.filters { grid-template-columns: 1fr 1fr; }
		.run-header { flex-direction: column; }
		.output-section-body { grid-template-columns: repeat(auto-fill, minmax(calc(120px * var(--thumb-size-scale, 1)), 1fr)); }
		.project-picker-popover { width: 100%; max-width: 100%; }
	}
</style>
