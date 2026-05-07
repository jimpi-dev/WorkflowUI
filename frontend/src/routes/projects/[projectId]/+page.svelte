<script lang="ts">
import { getApiBase } from '$lib/config';
import { goto, invalidate } from '$app/navigation';
import { page } from '$app/stores';
import { get } from 'svelte/store';
	import { browser } from '$app/environment';
	import { onMount, onDestroy, tick, untrack } from 'svelte';
	import { THUMB_SCALE_MAX, THUMB_SCALE_MIN, getThumbFitModeCookie, getThumbSizeCookie, setThumbFitModeCookie, setThumbSizeCookie, getThumbShowFilenameCookie, setThumbShowFilenameCookie, getNotesCollapsedCookie, setNotesCollapsedCookie, getLeftPanelCollapsedCookie, setLeftPanelCollapsedCookie, getSkipDeleteConfirmCookie, setSkipDeleteConfirmCookie, type ThumbFitMode, type DeleteConfirmKey } from '$lib/cookie';
	import SendToAppDialog from '$lib/components/SendToAppDialog.svelte';
	import MoveRunsDialog from '$lib/components/MoveRunsDialog.svelte';
	import ThumbnailOverlay from '$lib/components/ThumbnailOverlay.svelte';
	import PageLoadingIndicator from '$lib/components/PageLoadingIndicator.svelte';
	import RunHeaderActions from '$lib/components/RunHeaderActions.svelte';
	import RunAppBadge from '$lib/components/RunAppBadge.svelte';
	import RunMetadataPanel from '$lib/components/RunMetadataPanel.svelte';
	import DeleteProjectDialog from '$lib/components/DeleteProjectDialog.svelte';
	import ConfirmDeleteDialog from '$lib/components/ConfirmDeleteDialog.svelte';
	import LightboxViewer, { type LightboxItem } from '$lib/components/LightboxViewer.svelte';
	import InfiniteScrollLoadMore from '$lib/components/InfiniteScrollLoadMore.svelte';
	import { appBooting } from '$lib/stores/appBooting';
	import { quickRunsProject } from '$lib/stores/quickRunsProject';

	let { data }: {
		data: {
			project: {
				id: string;
				name: string;
				description?: string | null;
				created_at: number;
				updated_at: number;
				tags?: string[];
				metadata?: { notes?: { id: string; content: string; created_at: number }[]; favorites?: string[] } | null;
				run_count: number;
				apps_used: { id: string; slug: string | null; title: string | null; removed?: boolean; header_color?: string | null }[];
				storage_mode?: string | null;
				header_color?: string | null;
				has_local_data?: boolean;
				has_remote_data?: boolean;
			} | null;
			projectId: string;
			mediaStorage?: { enabled: boolean; rootPath: string; deleteRemoteAfterSave: boolean } | null;
			comfyuiDeleteSupported?: boolean;
			embedWorkflowuiMetadataOnDownload?: boolean;
			appsForNew?: { id: string; slug: string | null; title: string | null }[];
		};
	} = $props();

	const apiBase = getApiBase() || '';
	const project = $derived(data.project);

	type ApiRun = {
		id: string;
		run_group_id: string | null;
		app_id: string | null;
		app_slug: string | null;
		app_title: string | null;
		app_header_color?: string | null;
		status: string;
		queue_position?: number | null;
		created_at: number;
		seed: number | null;
		images: { filename: string; subfolder: string; type: string; remote_deleted?: boolean }[];
		execution_time: number | null;
		error: string | null;
		latent_resolution?: string | null;
		local_storage_status?: string | null;
		remote_status?: string | null;
		local_path?: string | null;
		local_storage_bytes?: number | null;
		remote_storage_bytes?: number | null;
		comfyui_unreachable_warning?: string | null;
	};
	let runs = $state<ApiRun[]>([]);
	let totalGroups = $state<number>(0);
	let statsTotalRuns = $state<number | null>(null);
	let statsTotalGenerations = $state<number | null>(null);
	const DELETED_APP_FILTER_ID = '__deleted__';
	let filterAppId = $state<string>('');
	let filterFromDate = $state<string>('');
	let filterToDate = $state<string>('');
	let filterMetaQ = $state<string>('');
	let filterFavoritesOnly = $state(false);
	let loading = $state(true);
	let loadingMore = $state(false);
	let storageMode = $state<string>('inherit');
	let storageSaving = $state(false);
	let storageError = $state<string | null>(null);
	let savingGroupIds = $state<Set<string>>(new Set());
	let deletingGroupIds = $state<Set<string>>(new Set());
	let deletingLocalGroupIds = $state<Set<string>>(new Set());
	let deletingBothGroupIds = $state<Set<string>>(new Set());
	let cancellingGroupIds = $state<Set<string>>(new Set());
	let cancellingRunIds = $state<Set<string>>(new Set());
	let retryingGroupIds = $state<Set<string>>(new Set());
	let deletingImageKeys = $state<Set<string>>(new Set());
	let deletingLocalImageKeys = $state<Set<string>>(new Set());
	let deletingBothImageKeys = $state<Set<string>>(new Set());
	let deletingRunIds = $state<Set<string>>(new Set());
	let deleteError = $state<string | null>(null);

	let thumbLoadFailed = $state<Set<string>>(new Set());
	function markThumbLoadFailed(thumbKey: string) {
		thumbLoadFailed = new Set([...thumbLoadFailed, thumbKey]);
	}
	let mediaResolutionByImageKey = $state<Record<string, { width: number; height: number }>>({});
	const videoResolutionFetchInFlight = new Set<string>();
	function setMediaResolution(key: string, width: number, height: number) {
		if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return;
		const w = Math.round(width);
		const h = Math.round(height);
		const prev = mediaResolutionByImageKey[key];
		if (prev && prev.width === w && prev.height === h) return;
		mediaResolutionByImageKey = { ...mediaResolutionByImageKey, [key]: { width: w, height: h } };
	}
	function mediaResolutionLabel(key: string): string | undefined {
		const dim = mediaResolutionByImageKey[key];
		return dim ? `${dim.width}×${dim.height}` : undefined;
	}
	function onImageThumbLoad(groupId: string, runId: string, index: number, event: Event) {
		markThumbLoaded(groupId, runId, index);
		const img = event.currentTarget as HTMLImageElement | null;
		if (!img) return;
		setMediaResolution(imageKey(runId, index), img.naturalWidth, img.naturalHeight);
	}
	function onVideoThumbMetadataLoad(
		groupId: string,
		runId: string,
		index: number,
		thumbKey: string,
		event: Event,
	) {
		// Only begin playback if the same thumb is still hovered.
		if (playingVideoThumbKey !== thumbKey) return;
		const v = event.currentTarget as HTMLVideoElement | null;
		if (v) {
			v.currentTime = 0;
			setMediaResolution(imageKey(runId, index), v.videoWidth, v.videoHeight);
		}
		playingVideoThumbReady = true;
		markThumbLoaded(groupId, runId, index);
	}
	function preloadVideoResolutionOnce(runId: string, index: number, url: string) {
		if (!browser) return;
		const key = imageKey(runId, index);
		if (mediaResolutionByImageKey[key] || videoResolutionFetchInFlight.has(key)) return;
		videoResolutionFetchInFlight.add(key);
		const el = document.createElement('video');
		el.preload = 'metadata';
		el.muted = true;
		el.playsInline = true;
		const cleanup = () => {
			el.removeAttribute('src');
			el.load();
			videoResolutionFetchInFlight.delete(key);
		};
		el.onloadedmetadata = () => {
			setMediaResolution(key, el.videoWidth, el.videoHeight);
			cleanup();
		};
		el.onerror = cleanup;
		el.src = url;
	}


	let playingAudioThumbKey = $state<string | null>(null);
	let playingVideoThumbKey = $state<string | null>(null);
	let playingVideoThumbReady = $state(false);

	let sendToAppRunId = $state<string | null>(null);
	let sendToAppOutputIndex = $state<number | null>(null);

	let deleteProjectDialogOpen = $state(false);

	let selectedRunIds = $state<Set<string>>(new Set());
	let moveDialogOpen = $state(false);

	let metadataPanelRunId = $state<string | null>(null);
	let metadataPanelMode = $state<'output' | 'run'>('output');

	let deleteRunGroupPending = $state<{ groupId: string; runs: ApiRun[] } | null>(null);
	let deleteStorageRunGroupPending = $state<
		| null
		| {
			group: (typeof runGroups)[0];
			action: 'delete_remote' | 'delete_local' | 'delete_all';
		  }
	>(null);

	type DeleteConfirmPending = {
		action: DeleteConfirmKey;
		title: string;
		message: string;
		confirmLabel: string;
		onConfirmed: () => void | Promise<void>;
	};
	let deleteConfirmPending = $state<DeleteConfirmPending | null>(null);

	let favorites = $state<Set<string>>(new Set());
let focusedGroupId = $state<string | null>(null);
let leftPanelCollapsedBeforeFocus = $state<boolean | null>(null);
let runsScrollTopBeforeFocus = $state<number | null>(null);
	$effect(() => {
		const raw = data.project?.metadata?.favorites;
		favorites = Array.isArray(raw) ? new Set(raw) : new Set();
	});

	const filterActive = $derived(!!(filterAppId.trim() || filterFromDate.trim() || filterToDate.trim() || filterMetaQ.trim() || filterFavoritesOnly));
	const runsRenderKey = $derived(
		`${data.projectId}|${filterAppId}|${filterFromDate}|${filterToDate}|${filterMetaQ}|${filterFavoritesOnly}`
	);

	const runGroups = $derived.by(() => {
		let list = runs;
		if (filterFavoritesOnly && favorites.size > 0) {
			list = list.filter((r) => runHasFavoritedOutput(r));
		} else if (filterFavoritesOnly) {
			list = [];
		}
		// For concrete apps, filter by app_id on the client as well.
		// For deleted apps we rely on the backend's deleted_app=true
		// filter and do not re-filter here.
		if (filterAppId.trim() && filterAppId !== DELETED_APP_FILTER_ID) {
			list = list.filter((r) => r.app_id === filterAppId.trim());
		}
		const byGroup = new Map<string, ApiRun[]>();
		for (const r of list) {
			const key = r.run_group_id ?? r.id;
			if (!byGroup.has(key)) byGroup.set(key, []);
			byGroup.get(key)!.push(r);
		}
		const groups: {
			groupId: string;
			firstRunId: string;
			createdAt: number;
			app_title: string | null;
			app_slug: string | null;
			app_header_color: string | null;
			app_removed: boolean;
			status: string;
			error: string | null;
			comfyui_unreachable_warning: string | null;
			runCount: number;
			runs: ApiRun[];
			latent_resolution: string | null;
		}[] = [];
		for (const [groupId, groupRuns] of byGroup) {
			const sorted = [...groupRuns].sort((a, b) => a.created_at - b.created_at);
			const first = sorted[0];
			const createdAt = Math.min(...sorted.map((r) => r.created_at));
			const hasError = sorted.some((r) => r.status === 'error' || (r.error && r.status !== 'cancelled'));
			const hasCancelled = sorted.some((r) => r.status === 'cancelled');
			const hasRunning = sorted.some((r) => r.status === 'running');
			const hasQueued = sorted.some((r) => r.status === 'queued');
			const status = hasError ? 'error' : hasCancelled ? 'cancelled' : hasRunning ? 'running' : hasQueued ? 'queued' : 'done';
			const error = sorted.find((r) => r.error)?.error ?? null;
			const comfyui_unreachable_warning = sorted.find((r) => r.comfyui_unreachable_warning)?.comfyui_unreachable_warning ?? null;
			const latent_resolution = sorted.find((r) => r.latent_resolution)?.latent_resolution ?? null;
			const app_removed = sorted.some(
				(r) => r.app_id && r.app_slug == null && r.app_title == null
			);
			const app_header_color = first.app_header_color ?? null;
			groups.push({
				groupId,
				firstRunId: first.id,
				createdAt,
				app_title: first.app_title,
				app_slug: first.app_slug,
				app_header_color,
				app_removed,
				status,
				error,
				comfyui_unreachable_warning,
				runCount: sorted.length,
				runs: sorted,
				latent_resolution,
			});
		}
		groups.sort((a, b) => b.createdAt - a.createdAt);
		return groups;
	});

	const visibleRunGroups = $derived.by(() => runGroups);
	const displayRunGroups = $derived.by(() =>
		focusedGroupId ? visibleRunGroups.filter((g) => g.groupId === focusedGroupId) : visibleRunGroups
	);

	$effect(() => {
		if (!focusedGroupId) return;
		if (!visibleRunGroups.some((g) => g.groupId === focusedGroupId)) focusedGroupId = null;
	});

	const displayRunsCount = $derived(
		filterFavoritesOnly ? visibleRunGroups.length : (statsTotalGenerations ?? totalGroups)
	);

	const displayGenerationsCount = $derived(
		filterFavoritesOnly ? visibleRunGroups.reduce((n, g) => n + g.runs.length, 0) : (statsTotalRuns ?? 0)
	);

	const loadedGroupCount = $derived.by(() => {
		const seen = new Set<string>();
		for (const r of runs) seen.add(r.run_group_id ?? r.id);
		return seen.size;
	});

	const hasInFlightRuns = $derived.by(() =>
		runGroups.some((g) => g.status === 'queued' || g.status === 'running')
	);

	const appsUsedSortedByRuns = $derived.by(() => {
		const apps = data.project?.apps_used ?? [];
		if (apps.length === 0) return [];
		const countByAppId = new Map<string, number>();
		for (const r of runs) {
			if (r.app_id) countByAppId.set(r.app_id, (countByAppId.get(r.app_id) ?? 0) + 1);
		}
		return [...apps].sort((a, b) => (countByAppId.get(b.id) ?? 0) - (countByAppId.get(a.id) ?? 0));
	});

	const appFilterOptions = $derived.by(() => {
		const options =
			appsUsedSortedByRuns
				.map((app) => ({
					id: app.id,
					title: (app.title ?? '').trim()
				}))
				.filter((app) => app.id && app.title) ?? [];

		const withDeleted = [
			{
				id: DELETED_APP_FILTER_ID,
				title: 'Deleted app (removed)'
			},
			...options
		];
		const selected = filterAppId?.trim();
		if (selected && !withDeleted.some((opt) => opt.id === selected)) {
			const label = selected === DELETED_APP_FILTER_ID ? 'Deleted app (removed)' : 'Selected app';
			return [{ id: selected, title: label }, ...withDeleted];
		}
		return withDeleted;
	});

	$effect(() => {
		if (project?.storage_mode) storageMode = project.storage_mode;
	});

	function updateRunStorage(runId: string, patch: Partial<ApiRun>) {
		runs = runs.map((r) => (r.id === runId ? { ...r, ...patch } : r));
	}
	
	function mergeUpdatedRuns(updatedRuns: ApiRun[] | undefined) {
		if (!updatedRuns?.length) return;
		const byId = new Map(updatedRuns.map((r) => [r.id, r]));
		runs = runs.map((r) => {
			const u = byId.get(r.id);
			if (!u) return r;
			// Use updated run but keep images from response (so remote_deleted/removed items are reflected)
			const merged = { ...r, ...u, run_group_id: u.run_group_id ?? r.run_group_id };
			if (Array.isArray(u.images)) merged.images = u.images;
			// Preserve already-known sizes when list response omits size info (null/undefined).
			if (
				(u.local_storage_bytes === undefined || u.local_storage_bytes === null) &&
				typeof r.local_storage_bytes === 'number'
			) {
				merged.local_storage_bytes = r.local_storage_bytes;
			}
			if (
				(u.remote_storage_bytes === undefined || u.remote_storage_bytes === null) &&
				typeof r.remote_storage_bytes === 'number'
			) {
				merged.remote_storage_bytes = r.remote_storage_bytes;
			}
			return merged;
		});
	}

	/** Matches thumbnail visibility: remote-deleted slots only show if run still has local copies. */
	function runHasDisplayableOutputs(run: ApiRun): boolean {
		const imgs = run.images ?? [];
		return imgs.some((item) => {
			const rd = !!(item as { remote_deleted?: boolean }).remote_deleted;
			if (!rd) return true;
			return run.local_storage_status === 'saved' || run.local_storage_status === 'partial';
		});
	}

	function outputIndexIsDisplayable(run: ApiRun, index: number): boolean {
		const item = run.images?.[index];
		if (!item) return false;
		const rd = !!(item as { remote_deleted?: boolean }).remote_deleted;
		if (!rd) return true;
		return run.local_storage_status === 'saved' || run.local_storage_status === 'partial';
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

	function displayableOutputIndices(run: ApiRun): number[] {
		const imgs = run.images ?? [];
		const out: number[] = [];
		for (let i = 0; i < imgs.length; i++) {
			if (outputIndexIsDisplayable(run, i)) out.push(i);
		}
		return out;
	}

	/** Per-output favorite, or legacy whole-run entry (bare run id). */
	function isOutputFavorite(runId: string, outputIndex: number): boolean {
		if (favorites.has(outputFavoriteKey(runId, outputIndex))) return true;
		if (favorites.has(runId)) return true;
		return false;
	}

	function runHasFavoritedOutput(run: ApiRun): boolean {
		if (!runHasDisplayableOutputs(run)) return false;
		if (favorites.has(run.id)) return true;
		const n = run.images?.length ?? 0;
		for (let i = 0; i < n; i++) {
			if (!outputIndexIsDisplayable(run, i)) continue;
			if (favorites.has(outputFavoriteKey(run.id, i))) return true;
		}
		return false;
	}

	function runForFavorite(runId: string): ApiRun | undefined {
		return runs.find((r) => r.id === runId);
	}

	function selectionIncludesFavorite(runId: string, indices: number[]): boolean {
		return indices.some((i) => isOutputFavorite(runId, i));
	}

	function toggleOutputFavorite(runId: string, outputIndex: number, run?: ApiRun) {
		const key = outputFavoriteKey(runId, outputIndex);
		const next = new Set(favorites);
		if (isOutputFavorite(runId, outputIndex)) {
			if (next.has(key)) {
				next.delete(key);
			} else if (next.has(runId)) {
				next.delete(runId);
				const r = run ?? runForFavorite(runId);
				if (r) {
					for (const i of displayableOutputIndices(r)) {
						if (i !== outputIndex) next.add(outputFavoriteKey(runId, i));
					}
				}
			}
		} else {
			next.add(key);
		}
		favorites = next;
		saveFavoritesMetadata([...next]);
	}

	function pruneStaleRunFavorites(runsToCheck: ApiRun[]) {
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
		const next = new Set([...favorites].filter((e) => !toRemove.has(e)));
		favorites = next;
		saveFavoritesMetadata([...next]).catch(() => {});
	}

	async function refetchStorageSizesForRunIds(
		runIds: string[],
		expectedProjectId?: string
	) {
		const projectId = expectedProjectId ?? data.projectId;
		if (!runIds.length || !projectId) return;
		try {
			const res = await fetch(
				`${apiBase}/projects/${projectId}/runs/storage_sizes?run_ids=${encodeURIComponent(runIds.join(','))}`
			);
			if (!res.ok) return;
			const sizes: Record<string, { local_storage_bytes?: number | null; remote_storage_bytes?: number | null }> =
				await res.json().catch(() => ({}));
			if (typeof sizes !== 'object') return;
			// Only merge if still on the same project (avoid overwriting after navigation)
			if (expectedProjectId != null && data.projectId !== expectedProjectId) return;
			runs = runs.map((r) => {
				const s = sizes[r.id];
				if (!s) return r;
				return {
					...r,
					local_storage_bytes: s.local_storage_bytes ?? null,
					remote_storage_bytes: s.remote_storage_bytes ?? null
				};
			});
		} catch {
			// ignore
		}
	}
	function getGroupStorageSummary(group: (typeof runGroups)[0]): { label: string; tone: string } | null {
		const states = group.runs.map((r) => r.local_storage_status);
		const allSaved = states.length > 0 && states.every((s) => s === 'saved');
		const anySaved = states.some((s) => s === 'saved');
		const anyPartial = states.some((s) => s === 'partial');
		const anyFailed = states.some((s) => s === 'failed');
		if (allSaved) return { label: 'Fully Saved', tone: 'saved' };
		if (anySaved || anyPartial) return { label: 'Partially Saved', tone: 'partial' };
		if (anyFailed) return { label: 'Failed', tone: 'failed' };
		return { label: 'Remote Only', tone: 'remote' };
	}

	function sumKnownStorageBytes(
		group: (typeof runGroups)[0],
		key: 'local_storage_bytes' | 'remote_storage_bytes'
	): number | null {
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

	async function saveRunGroup(group: (typeof runGroups)[0]) {
		savingGroupIds = new Set([...savingGroupIds, group.groupId]);
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
					if (typeof window !== 'undefined') {
						window.dispatchEvent(new CustomEvent('workflowui-refresh-storage'));
					}
				} else {
					updateRunStorage(run.id, { local_storage_status: 'failed' });
				}
			}
			refetchStorageSizesForRunIds(group.runs.map((r) => r.id));
		} finally {
			const next = new Set(savingGroupIds);
			next.delete(group.groupId);
			savingGroupIds = next;
		}
	}

	async function saveSelectedOrRunGroup(group: (typeof runGroups)[0]) {
		const byRun = getSelectedByRun(group);
		if (byRun.size === 0) {
			await saveRunGroup(group);
			return;
		}
		savingGroupIds = new Set([...savingGroupIds, group.groupId]);
		try {
			for (const [runId, indices] of byRun) {
				for (const index of indices) {
					const res = await fetch(`${apiBase}/runs/${runId}/save-image/${index}`, { method: 'POST' });
					const data = await res.json().catch(() => ({}));
					if (res.ok) {
						updateRunStorage(runId, {
							local_storage_status: data.local_storage_status,
							remote_status: data.remote_status,
							local_path: data.local_path
						});
						if (typeof window !== 'undefined') {
							window.dispatchEvent(new CustomEvent('workflowui-refresh-storage'));
						}
					} else {
						updateRunStorage(runId, { local_storage_status: 'failed' });
					}
				}
			}
			refetchStorageSizesForRunIds(Array.from(byRun.keys()));
		} finally {
			const next = new Set(savingGroupIds);
			next.delete(group.groupId);
			savingGroupIds = next;
		}
	}

	async function deleteRemoteRunGroup(
		group: (typeof runGroups)[0],
		runIdsToDelete?: string[],
		skipConfirm = false
	) {
		const runIds = runIdsToDelete ?? group.runs.map((r) => r.id);
		if (runIds.length === 0) return;
		const doDelete = async () => {
			deletingGroupIds = new Set([...deletingGroupIds, group.groupId]);
			try {
				for (const runId of runIds) {
					const res = await fetch(`${apiBase}/runs/${runId}/delete-remote`, { method: 'POST' });
					const data = await res.json().catch(() => ({}));
					if (res.ok) {
						mergeUpdatedRuns(data.updated_runs);
					} else {
						updateRunStorage(runId, { remote_status: 'exists' });
					}
				}
				refetchStorageSizesForRunIds(runIds);
			} finally {
				const next = new Set(deletingGroupIds);
				next.delete(group.groupId);
				deletingGroupIds = next;
			}
		};
		if (skipConfirm) {
			await doDelete();
			return;
		}
		if (getSkipDeleteConfirmCookie('delete_remote')) {
			await doDelete();
			return;
		}
		deleteConfirmPending = {
			action: 'delete_remote',
			title: 'Delete remote',
			message: 'Delete all remote files for this run group? Files will be removed from the ComfyUI server.',
			confirmLabel: 'Delete remote',
			onConfirmed: doDelete
		};
	}

	async function deleteLocalRunGroup(
		group: (typeof runGroups)[0],
		runIdsToDelete?: string[],
		skipConfirm = false
	) {
		const runIds = runIdsToDelete ?? group.runs.map((r) => r.id);
		if (runIds.length === 0) return;
		const doDelete = async () => {
			deletingLocalGroupIds = new Set([...deletingLocalGroupIds, group.groupId]);
			try {
				for (const runId of runIds) {
					const res = await fetch(`${apiBase}/runs/${runId}/delete-local`, { method: 'POST' });
					const data = await res.json().catch(() => ({}));
					if (res.ok) {
						updateRunStorage(runId, {
							local_storage_status: data.local_storage_status,
							local_path: data.local_path
						});
						if (typeof window !== 'undefined') {
							window.dispatchEvent(new CustomEvent('workflowui-refresh-storage'));
						}
					} else {
						updateRunStorage(runId, { local_storage_status: 'failed' });
					}
				}
				refetchStorageSizesForRunIds(runIds);
			} finally {
				const next = new Set(deletingLocalGroupIds);
				next.delete(group.groupId);
				deletingLocalGroupIds = next;
			}
		};
		if (skipConfirm) {
			await doDelete();
			return;
		}
		if (getSkipDeleteConfirmCookie('delete_local')) {
			await doDelete();
			return;
		}
		deleteConfirmPending = {
			action: 'delete_local',
			title: 'Delete local',
			message: 'Delete all local copies for this run group? Files will be removed from local storage.',
			confirmLabel: 'Delete local',
			onConfirmed: doDelete
		};
	}

	async function deleteBothRunGroup(
		group: (typeof runGroups)[0],
		runIdsToDelete?: string[],
		skipConfirm = false
	) {
		const runIds = runIdsToDelete ?? group.runs.map((r) => r.id);
		if (runIds.length === 0) return;
		const doDelete = async () => {
			deletingBothGroupIds = new Set([...deletingBothGroupIds, group.groupId]);
			try {
				for (const runId of runIds) {
					const res = await fetch(`${apiBase}/runs/${runId}/delete-both`, { method: 'POST' });
					const data = await res.json().catch(() => ({}));
					if (res.ok) {
						mergeUpdatedRuns(data.updated_runs);
					} else {
						updateRunStorage(runId, { remote_status: 'exists' });
					}
				}
				refetchStorageSizesForRunIds(runIds);
			} finally {
				const next = new Set(deletingBothGroupIds);
				next.delete(group.groupId);
				deletingBothGroupIds = next;
			}
		};
		if (skipConfirm) {
			await doDelete();
			return;
		}
		if (getSkipDeleteConfirmCookie('delete_all')) {
			await doDelete();
			return;
		}
		deleteConfirmPending = {
			action: 'delete_all',
			title: 'Delete all',
			message: 'Delete local and remote files for this run group? This cannot be undone.',
			confirmLabel: 'Delete all',
			onConfirmed: doDelete
		};
	}

	async function cancelRunGroup(group: (typeof runGroups)[0]) {
		const toCancel = group.runs.filter((r) => r.status === 'queued' || r.status === 'running');
		if (!toCancel.length) return;
		cancellingGroupIds = new Set([...cancellingGroupIds, group.groupId]);
		try {
			for (const run of toCancel) {
				const res = await fetch(`${apiBase}/runs/${run.id}/cancel`, { method: 'POST' });
				if (res.ok) {
					updateRunStorage(run.id, { status: 'cancelled', error: 'Cancelled' });
				}
			}
			await loadRuns();
		} finally {
			const next = new Set(cancellingGroupIds);
			next.delete(group.groupId);
			cancellingGroupIds = next;
		}
	}

	async function retryRunGroup(group: (typeof runGroups)[0]) {
		const toRetry = group.runs.filter((r) => r.status === 'queued' && r.comfyui_unreachable_warning);
		if (!toRetry.length) return;
		retryingGroupIds = new Set([...retryingGroupIds, group.groupId]);
		try {
			for (const run of toRetry) {
				await fetch(`${apiBase}/runs/${run.id}/retry`, { method: 'POST' });
			}
			await loadRuns();
		} finally {
			const next = new Set(retryingGroupIds);
			next.delete(group.groupId);
			retryingGroupIds = next;
		}
	}

	async function cancelRun(run: { id: string; status: string }) {
		if (run.status !== 'queued' && run.status !== 'running') return;
		cancellingRunIds = new Set([...cancellingRunIds, run.id]);
		try {
			const res = await fetch(`${apiBase}/runs/${run.id}/cancel`, { method: 'POST' });
			if (res.ok) {
				updateRunStorage(run.id, { status: 'cancelled', error: 'Cancelled' });
				await loadRuns();
			}
		} finally {
			const next = new Set(cancellingRunIds);
			next.delete(run.id);
			cancellingRunIds = next;
		}
	}

	async function deleteRunGroup(group: { groupId: string; runs: ApiRun[] }, runIdsToDelete?: string[]) {
		const runIds = runIdsToDelete ?? group.runs.map((r) => r.id);
		if (runIds.length === 0) return;
		deleteError = null;
		const deletedIds = new Set<string>();
		for (const id of runIds) deletingRunIds = new Set([...deletingRunIds, id]);
		try {
			let anyDeleted = false;
			for (const runId of runIds) {
				const res = await fetch(`${apiBase}/runs/${runId}/delete-run`, { method: 'POST' });
				const data = await res.json().catch(() => ({}));
				if (res.ok && data.deleted_run_id) {
					runs = runs.filter((r) => r.id !== data.deleted_run_id);
					anyDeleted = true;
					deletedIds.add(data.deleted_run_id);
				} else {
					deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete run failed';
				}
				deletingRunIds = new Set([...deletingRunIds].filter((id) => id !== runId));
			}
			if (anyDeleted) totalGroups = Math.max(0, totalGroups - 1);
			if (deletedIds.size > 0) {
				const nextFav = [...favorites].filter((ent) => !deletedIds.has(parseFavoriteEntry(ent).runId));
				if (nextFav.length !== favorites.size) await saveFavoritesMetadata(nextFav);
			}
			await loadStats();
		} finally {
			deletingRunIds = new Set([...deletingRunIds].filter((id) => !runIds.includes(id)));
		}
	}

	function requestDeleteRunGroup(group: (typeof runGroups)[0]) {
		pruneStaleRunFavorites(group.runs);
		const hasFav = group.runs.some((r) => runHasFavoritedOutput(r));
		if (!hasFav && getSkipDeleteConfirmCookie('delete_run')) {
			deleteRunGroup(group).catch(() => {});
			return;
		}
		deleteRunGroupPending = { groupId: group.groupId, runs: group.runs };
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

	async function confirmDeleteStorageRunGroup(mode: 'all' | 'non_favorites') {
		const pending = deleteStorageRunGroupPending;
		if (!pending) return;
		deleteStorageRunGroupPending = null;
		const { group, action } = pending;
		if (mode === 'non_favorites') {
			const runIdsToDelete = group.runs.filter((r) => !runHasFavoritedOutput(r)).map((r) => r.id);
			if (runIdsToDelete.length === 0) {
				deleteError = 'No non-favorited runs in this group to delete.';
				return;
			}
			if (action === 'delete_remote') await deleteRemoteRunGroup(group, runIdsToDelete, true);
			else if (action === 'delete_local') await deleteLocalRunGroup(group, runIdsToDelete, true);
			else await deleteBothRunGroup(group, runIdsToDelete, true);
		} else {
			if (action === 'delete_remote') await deleteRemoteRunGroup(group, undefined, true);
			else if (action === 'delete_local') await deleteLocalRunGroup(group, undefined, true);
			else await deleteBothRunGroup(group, undefined, true);
		}
	}

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

	$effect(() => {
		if (!deleteStorageRunGroupPending || !browser) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				e.preventDefault();
				deleteStorageRunGroupPending = null;
			}
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});

	$effect(() => {
		if (!deleteConfirmPending || !browser) return;
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') {
				e.preventDefault();
				deleteConfirmPending = null;
			}
		};
		window.addEventListener('keydown', onKey);
		return () => window.removeEventListener('keydown', onKey);
	});

	async function setProjectStorageMode(mode: string) {
		if (!data.project) return;
		storageSaving = true;
		storageError = null;
		try {
			const res = await fetch(`${apiBase}/projects/${data.project.id}/storage`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ storage_mode: mode })
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({}));
				storageError = err?.detail ?? 'Update failed';
				return;
			}
			storageMode = mode;
			data.project.storage_mode = mode;
		} catch {
			storageError = 'Update failed';
		} finally {
			storageSaving = false;
		}
	}

	let projectName = $state('');
	let editingProjectName = $state(false);
	let nameSaving = $state(false);
	let projectNameInputEl = $state<HTMLInputElement | null>(null);
	$effect(() => {
		if (project?.name !== undefined) projectName = project.name ?? '';
	});
	async function saveProjectName() {
		if (!project) return;
		const trimmed = projectName.trim() || 'Untitled project';
		if (trimmed === project.name) {
			editingProjectName = false;
			return;
		}
		nameSaving = true;
		try {
			const res = await fetch(`${apiBase}/projects/${project.id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: trimmed })
			});
			if (res.ok) {
				data.project.name = trimmed;
				projectName = trimmed;
			}
			editingProjectName = false;
		} finally {
			nameSaving = false;
		}
	}
	function startEditProjectName() {
		editingProjectName = true;
		tick().then(() => projectNameInputEl?.focus());
	}

	let projectDescription = $state('');
	let descriptionSaving = $state(false);
	$effect(() => {
		if (project?.description !== undefined) projectDescription = project.description ?? '';
	});
	async function saveDescription() {
		if (!project) return;
		descriptionSaving = true;
		try {
			const res = await fetch(`${apiBase}/projects/${project.id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ description: projectDescription })
			});
			if (res.ok) data.project.description = projectDescription;
		} finally {
			descriptionSaving = false;
		}
	}

	let projectTags = $state<string[]>([]);
	let projectTagInput = $state('');
	let tagsSaving = $state(false);
	$effect(() => {
		const raw = project?.tags ?? [];
		projectTags = Array.isArray(raw)
			? Array.from(
					new Set(
						raw
							.map((t) => (t ?? '').trim().toLowerCase())
							.filter(Boolean)
					)
			  )
			: [];
	});

	async function saveProjectTags() {
		if (!project) return;
		tagsSaving = true;
		try {
			const res = await fetch(`${apiBase}/projects/${project.id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ tags: projectTags }),
			});
			if (res.ok) {
				data.project.tags = [...projectTags];
			}
		} finally {
			tagsSaving = false;
		}
	}

	function addProjectTagFromInput() {
		const raw = projectTagInput.trim();
		if (!raw) return;
		const parts = raw
			.split(/[;,]/)
			.map((p) => p.trim().toLowerCase())
			.filter(Boolean);
		const next = new Set(projectTags);
		for (const p of parts) next.add(p);
		projectTags = Array.from(next);
		projectTagInput = '';
		saveProjectTags();
	}

	function removeProjectTag(tag: string) {
		projectTags = projectTags.filter((t) => t !== tag);
		saveProjectTags();
	}

	let projectHeaderColor = $state<string | null>(null);
	let headerColorSaving = $state(false);
	$effect(() => {
		if (project?.header_color !== undefined) projectHeaderColor = project.header_color ?? null;
	});
	async function saveHeaderColor() {
		if (!project) return;
		headerColorSaving = true;
		try {
			const res = await fetch(`${apiBase}/projects/${project.id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ header_color: projectHeaderColor })
			});
			if (res.ok) data.project.header_color = projectHeaderColor ?? undefined;
		} finally {
			headerColorSaving = false;
		}
	}

	type Note = { id: string; content: string; created_at: number };
	let notes = $state<Note[]>([]);
	$effect(() => {
		const raw = data.project?.metadata?.notes;
		notes = Array.isArray(raw) ? raw.map((n) => ({ id: n.id, content: n.content, created_at: n.created_at })) : [];
	});
	let notesSaving = $state(false);
	let noteDraft = $state('');
	let editingNoteId = $state<string | null>(null);
	let editingContent = $state('');
	async function saveNotesMetadata(nextNotes: Note[]) {
		if (!data.project) return;
		notesSaving = true;
		try {
			const meta = { ...(data.project.metadata ?? {}), notes: nextNotes };
			const res = await fetch(`${apiBase}/projects/${data.project.id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ metadata: meta })
			});
			if (res.ok) data.project.metadata = meta;
		} finally {
			notesSaving = false;
		}
	}
	function addNote() {
		const content = noteDraft.trim();
		if (!content) return;
		const next: Note[] = [...notes, { id: crypto.randomUUID(), content, created_at: Date.now() }];
		notes = next;
		noteDraft = '';
		saveNotesMetadata(next);
	}
	function updateNote(id: string, content: string) {
		const next = notes.map((n) => (n.id === id ? { ...n, content } : n));
		notes = next;
		editingNoteId = null;
		saveNotesMetadata(next);
	}
	function deleteNote(id: string) {
		const next = notes.filter((n) => n.id !== id);
		notes = next;
		editingNoteId = null;
		saveNotesMetadata(next);
	}
	function startEditNote(n: Note) {
		editingNoteId = n.id;
		editingContent = n.content;
	}
	function cancelEditNote() {
		editingNoteId = null;
	}

	let favoritesSaving = $state(false);
	async function saveFavoritesMetadata(nextFavorites: string[]) {
		if (!data.project) return;
		favoritesSaving = true;
		try {
			const meta = { ...(data.project.metadata ?? {}), favorites: nextFavorites };
			const res = await fetch(`${apiBase}/projects/${data.project.id}`, {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ metadata: meta })
			});
			if (res.ok) {
				data.project.metadata = meta;
			} else {
				const raw = data.project?.metadata?.favorites;
				favorites = Array.isArray(raw) ? new Set(raw) : new Set();
			}
		} catch {
			const raw = data.project?.metadata?.favorites;
			favorites = Array.isArray(raw) ? new Set(raw) : new Set();
		} finally {
			favoritesSaving = false;
		}
	}
	let notesInitialized = false;
	let isMobile = $state(browser && typeof window !== 'undefined' ? window.matchMedia('(max-width: 639px)').matches : false);
	let notesUserOpened = $state(false);

	let notesCollapsed = $state(browser ? (isMobile ? true : getNotesCollapsedCookie()) : false);
	$effect(() => {
		if (data.project && !notesInitialized) {
			const hasNotes = (data.project.metadata?.notes?.length ?? 0) > 0;
			// On mobile we collapse notes by default (unless the user opened it already during this session).
			// On desktop we preserve the existing cookie-driven behavior.
			notesCollapsed = hasNotes
				? isMobile
					? !notesUserOpened
					: false
				: browser
					? getNotesCollapsedCookie()
					: false;
			notesInitialized = true;
		}
	});
	function toggleNotesCollapsed() {
		notesCollapsed = !notesCollapsed;
		if (isMobile && !notesCollapsed) notesUserOpened = true;
		if (browser && !isMobile) setNotesCollapsedCookie(notesCollapsed);
	}

	let notesSearch = $state('');
	type ContentSegment = { type: 'text'; value: string } | { type: 'link'; url: string };
	function parseNoteContent(content: string): ContentSegment[] {
		if (!content) return [];
		const tokens = content.split(/(https?:\/\/[^\s]+)/gi);
		const segs: ContentSegment[] = [];
		for (let i = 0; i < tokens.length; i++) {
			const t = tokens[i];
			if (!t) continue;
			if (i % 2 === 1 && /^https?:\/\//i.test(t)) {
				segs.push({ type: 'link', url: t.replace(/[.,;:!?)]+$/, '') });
			} else {
				segs.push({ type: 'text', value: t });
			}
		}
		return segs.length ? segs : [{ type: 'text', value: content }];
	}
	const filteredNotes = $derived(
		notesSearch.trim()
			? notes.filter((n) => n.content.toLowerCase().includes(notesSearch.trim().toLowerCase()))
			: notes
	);

	const RUNS_PAGE_SIZE = 20;
	let runsInitialSeq = 0;
	let runsAppendSeq = 0;
	let statsRequestSeq = 0;
	let activeRunsQueryKey = '';
	let runsAbortController: AbortController | null = null;
	let statsAbortController: AbortController | null = null;

	async function loadRuns(offset: number = 0, queryKey?: string) {
		const projectIdWeFetch = data.projectId;
		const isInitial = offset === 0;
		const requestId = isInitial ? ++runsInitialSeq : ++runsAppendSeq;
		const key = queryKey ?? activeRunsQueryKey;
		if (isInitial) {
			activeRunsQueryKey = key;
			runsAppendSeq = 0;
			if (runsAbortController) runsAbortController.abort();
		}
		const controller = new AbortController();
		runsAbortController = controller;
		if (isInitial) {
			loading = true;
			allGroupsRevealed = false;
		} else {
			loadingMore = true;
		}
		try {
			const q = new URLSearchParams();
			q.set('limit', String(RUNS_PAGE_SIZE));
			q.set('offset', String(offset));
			// Ask backend to filter by deleted apps when that option is selected,
			// otherwise filter by concrete app_id when provided.
			if (filterAppId === DELETED_APP_FILTER_ID) {
				q.set('deleted_app', '1');
			} else if (filterAppId.trim()) {
				q.set('app_id', filterAppId.trim());
			}
			if (filterFromDate.trim()) {
				const fromMs = new Date(filterFromDate.trim()).setHours(0, 0, 0, 0);
				q.set('since', String(fromMs));
			}
			if (filterToDate.trim()) {
				const toMs = new Date(filterToDate.trim()).setHours(23, 59, 59, 999);
				q.set('until', String(toMs));
			}
			if (filterMetaQ.trim()) q.set('meta_q', filterMetaQ.trim());
			const url = `${apiBase}/projects/${projectIdWeFetch}/runs?${q.toString()}`;
			console.debug('[projects runs] loadRuns url', url);
			const res = await fetch(url, { signal: controller.signal });
			if (data.projectId !== projectIdWeFetch || key !== activeRunsQueryKey) return;
			if (isInitial && requestId !== runsInitialSeq) return;
			if (!isInitial && requestId !== runsAppendSeq) return;
			if (!res.ok) {
				if (isInitial) {
					runs = [];
					totalGroups = 0;
				}
				return;
			}
			const raw = await res.json();
			console.debug(
				'[projects runs] loadRuns response',
				{ status: res.status, ok: res.ok },
				Array.isArray(raw?.runs) ? raw.runs.length : Array.isArray(raw) ? raw.length : null
			);
			if (data.projectId !== projectIdWeFetch || key !== activeRunsQueryKey) return;
			if (isInitial && requestId !== runsInitialSeq) return;
			if (!isInitial && requestId !== runsAppendSeq) return;
			const mapRun = (r: ApiRun) => ({ ...r, run_group_id: r.run_group_id ?? null });
			if (raw && typeof raw === 'object' && Array.isArray(raw.runs)) {
				const newRuns = raw.runs.map(mapRun);
				if (isInitial) {
					runs = newRuns;
					totalGroups = typeof raw.total === 'number' ? raw.total : newRuns.length;
				} else {
					runs = [...runs, ...newRuns];
				}
				// Fetch storage sizes in the background and merge when ready (one batch request, no per-run list calls)
				const idsToFetch = newRuns.map((r: ApiRun) => r.id);
				if (idsToFetch.length > 0) {
					refetchStorageSizesForRunIds(idsToFetch, projectIdWeFetch);
				}
			} else if (isInitial) {
				runs = Array.isArray(raw) ? raw.map(mapRun) : [];
				totalGroups = runs.length;
			}
		} catch (e) {
			if (e instanceof DOMException && e.name === 'AbortError') return;
			if (data.projectId !== projectIdWeFetch || key !== activeRunsQueryKey) return;
			if (isInitial && requestId !== runsInitialSeq) return;
			if (!isInitial && requestId !== runsAppendSeq) return;
			if (isInitial) {
				runs = [];
				totalGroups = 0;
			}
		} finally {
			if (data.projectId === projectIdWeFetch && key === activeRunsQueryKey) {
				if (isInitial && requestId !== runsInitialSeq) return;
				if (!isInitial && requestId !== runsAppendSeq) return;
				if (isInitial) loading = false;
				else loadingMore = false;
			}
		}
	}

	function loadMoreRuns() {
		if (loading || loadingMore || loadedGroupCount >= totalGroups) return;
		loadRuns(loadedGroupCount);
	}

	let _inFlightRefreshController: AbortController | null = null;
	let _inFlightRefreshBusy = false;
	function revealThumbKeysForRuns(updatedRuns: ApiRun[]) {
		if (filterActive) return;
		if (!updatedRuns?.length) return;
		const next = { ...visibleThumbKeys };
		for (const r of updatedRuns) {
			const groupId = r.run_group_id ?? r.id;
			const imgs = r.images ?? [];
			for (let i = 0; i < imgs.length; i++) {
				next[`${groupId}-${r.id}-${i}`] = true;
			}
		}
		visibleThumbKeys = next;
	}
	async function refreshLatestRunsPage(): Promise<void> {
		if (!browser) return;
		if (!data.projectId) return;
		if (_inFlightRefreshBusy) return;
		// Avoid racing the main list loader (which can abort/replace state).
		if (loading || loadingMore) return;

		_inFlightRefreshBusy = true;
		if (_inFlightRefreshController) _inFlightRefreshController.abort();
		const controller = new AbortController();
		_inFlightRefreshController = controller;

		const projectIdWeFetch = data.projectId;
		const keyAtStart = activeRunsQueryKey;
		try {
			const q = new URLSearchParams();
			q.set('limit', String(RUNS_PAGE_SIZE));
			q.set('offset', '0');
			if (filterAppId === DELETED_APP_FILTER_ID) {
				q.set('deleted_app', '1');
			} else if (filterAppId.trim()) {
				q.set('app_id', filterAppId.trim());
			}
			if (filterFromDate.trim()) {
				const fromMs = new Date(filterFromDate.trim()).setHours(0, 0, 0, 0);
				q.set('since', String(fromMs));
			}
			if (filterToDate.trim()) {
				const toMs = new Date(filterToDate.trim()).setHours(23, 59, 59, 999);
				q.set('until', String(toMs));
			}
			if (filterMetaQ.trim()) q.set('meta_q', filterMetaQ.trim());
			const url = `${apiBase}/projects/${projectIdWeFetch}/runs?${q.toString()}`;
			const res = await fetch(url, { signal: controller.signal });
			if (!res.ok) return;
			// If navigation/filters changed mid-flight, do nothing.
			if (data.projectId !== projectIdWeFetch) return;
			if (activeRunsQueryKey !== keyAtStart) return;

			const raw = await res.json().catch(() => null);
			const mapRun = (r: ApiRun) => ({ ...r, run_group_id: r.run_group_id ?? null });
			const newRuns: ApiRun[] =
				raw && typeof raw === 'object' && Array.isArray((raw as any).runs)
					? (raw as any).runs.map(mapRun)
					: Array.isArray(raw)
						? raw.map(mapRun)
						: [];

			if (raw && typeof raw === 'object' && typeof (raw as any).total === 'number') {
				totalGroups = (raw as any).total;
			}

			if (newRuns.length) {
				// Prepend any brand-new runs so they become visible without a manual refresh.
				const existingIds = new Set(runs.map((r) => r.id));
				const missing = newRuns.filter((r) => !existingIds.has(r.id));
				if (missing.length) runs = [...missing, ...runs];
				mergeUpdatedRuns(newRuns);
				const idsToFetch = missing.map((r) => r.id);
				if (idsToFetch.length) refetchStorageSizesForRunIds(idsToFetch, projectIdWeFetch);
				// Ensure newly-arrived outputs actually get a `src` assigned (thumbSrc gating).
				revealThumbKeysForRuns(newRuns);
			}
		} catch (e) {
			if (e instanceof DOMException && e.name === 'AbortError') return;
		} finally {
			if (_inFlightRefreshController === controller) _inFlightRefreshController = null;
			_inFlightRefreshBusy = false;
		}
	}

	let _queuedRefreshTimer: number | null = null;
	function stopQueuedRefresh() {
		if (_queuedRefreshTimer != null) {
			clearInterval(_queuedRefreshTimer);
			_queuedRefreshTimer = null;
		}
		if (_inFlightRefreshController) {
			_inFlightRefreshController.abort();
			_inFlightRefreshController = null;
		}
		_inFlightRefreshBusy = false;
	}
	$effect(() => {
		if (!browser) return;
		const projectId = data.projectId;
		const shouldRun = !!projectId && hasInFlightRuns;
		if (!shouldRun) {
			stopQueuedRefresh();
			return;
		}
		if (_queuedRefreshTimer != null) return;

		// Kick once immediately, then poll lightly while work is in-flight.
		untrack(() => {
			refreshLatestRunsPage();
		});
		_queuedRefreshTimer = window.setInterval(() => {
			untrack(() => {
				refreshLatestRunsPage();
			});
		}, 2500);

		return () => stopQueuedRefresh();
	});

	async function loadStats() {
		const projectIdWeFetch = data.projectId;
		const requestId = ++statsRequestSeq;
		if (statsAbortController) statsAbortController.abort();
		const controller = new AbortController();
		statsAbortController = controller;
		const q = new URLSearchParams();
		if (filterAppId === DELETED_APP_FILTER_ID) {
			q.set('deleted_app', '1');
		} else if (filterAppId.trim()) {
			q.set('app_id', filterAppId.trim());
		}
		if (filterFromDate.trim()) {
			q.set('since', String(new Date(filterFromDate.trim()).setHours(0, 0, 0, 0)));
		}
		if (filterToDate.trim()) {
			q.set('until', String(new Date(filterToDate.trim()).setHours(23, 59, 59, 999)));
		}
		if (filterMetaQ.trim()) q.set('meta_q', filterMetaQ.trim());
		try {
			const res = await fetch(`${apiBase}/projects/${projectIdWeFetch}/runs/stats?${q.toString()}`, { signal: controller.signal });
			if (data.projectId !== projectIdWeFetch || requestId !== statsRequestSeq || !res.ok) return;
			const raw = await res.json();
			if (data.projectId !== projectIdWeFetch || requestId !== statsRequestSeq) return;
			if (typeof raw.total_runs === 'number') statsTotalRuns = raw.total_runs;
			if (typeof raw.total_generations === 'number') statsTotalGenerations = raw.total_generations;
		} catch (e) {
			if (e instanceof DOMException && e.name === 'AbortError') return;
			if (data.projectId === projectIdWeFetch && requestId === statsRequestSeq) {
				statsTotalRuns = null;
				statsTotalGenerations = null;
			}
		}
	}

	$effect(() => {
		const projectId = data.projectId;
		// Re-load runs and stats whenever filters change, but do not
		// mutate filterAppId here so the select binding remains stable.
		filterAppId;
		filterFromDate;
		filterToDate;
		filterMetaQ;
		if (projectId && browser) {
			const key = `${filterAppId}|${filterFromDate}|${filterToDate}|${filterMetaQ}|${filterFavoritesOnly}`;
			loadRuns(0, key);
			loadStats();
		}
	});

	function mediaType(img: { filename?: string; subfolder?: string; type?: string }): 'image' | 'video' | 'audio' {
		const t = (img?.type ?? '').toLowerCase();
		if (t === 'video') return 'video';
		if (t === 'audio') return 'audio';
		return 'image';
	}
	function imageUrl(img: { filename: string; subfolder?: string; type?: string }, runId?: string) {
		const subfolder = img.subfolder ?? '';
		const type = img.type ?? 'output';
		let url = `${apiBase}/image?filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(subfolder)}&type=${encodeURIComponent(type)}`;
		if (runId) url += `&run_id=${encodeURIComponent(runId)}`;
		if (runId && data.embedWorkflowuiMetadataOnDownload) url += '&embed_workflowui_metadata=1';
		return url;
	}
	function previewImageUrl(img: { filename: string; subfolder?: string; type?: string }, runId?: string) {
		return imageUrl(img, runId) + '&preview=webp';
	}
	// Preview thumbnails for video must not request `embed_workflowui_metadata=1`, because
	// thumbnails are not meant to carry WorkflowUI metadata chunks.
	function videoThumbnailPreviewUrl(img: { filename: string; subfolder?: string; type?: string }, runId?: string) {
		const subfolder = img.subfolder ?? '';
		const type = img.type ?? 'output';
		let url = `${apiBase}/image?filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(subfolder)}&type=${encodeURIComponent(type)}`;
		if (runId) url += `&run_id=${encodeURIComponent(runId)}`;
		url += '&preview=webp';
		return url;
	}

	function openAppInProject(appSlug: string) {
		appBooting.set(true);
		goto(`/app/${appSlug}?project=${data.projectId}`);
	}

	function openAppWithParams(appSlug: string, runId: string) {
		appBooting.set(true);
		goto(`/app/${appSlug}?project=${data.projectId}&run_id=${encodeURIComponent(runId)}`);
	}

	const fromPath = $derived(get(page).url.searchParams.get('from') ?? '');
	function backLabel(path: string): string {
		if (path.startsWith('/app/')) return 'Back to workflow';
		if (path === '/workflows' || path.startsWith('/workflows/')) return 'Back to workflows';
		if (path === '/') return 'Back to home';
		return 'Back to previous page';
	}

	const LEFT_PANEL_MIN = 220;
	const LEFT_PANEL_MAX = 560;
	const LEFT_PANEL_DEFAULT = 280;
	let leftPanelWidth = $state(LEFT_PANEL_DEFAULT);
	let leftPanelResizing = $state(false);
	let resizeStartX = 0;
	let resizeStartWidth = 0;
	function startResize(e: MouseEvent) {
		e.preventDefault();
		leftPanelResizing = true;
		resizeStartX = e.clientX;
		resizeStartWidth = leftPanelWidth;
	}
	function onResizeMove(e: MouseEvent) {
		if (!leftPanelResizing) return;
		const delta = e.clientX - resizeStartX;
		const next = Math.min(LEFT_PANEL_MAX, Math.max(LEFT_PANEL_MIN, resizeStartWidth + delta));
		leftPanelWidth = next;
	}
	function onResizeUp() {
		leftPanelResizing = false;
	}

	let leftPanelCollapsed = $state(browser ? (isMobile ? true : getLeftPanelCollapsedCookie()) : false);
	function toggleLeftPanel() {
		leftPanelCollapsed = !leftPanelCollapsed;
		if (browser && !isMobile) setLeftPanelCollapsedCookie(leftPanelCollapsed);
	}

	$effect(() => {
		if (!browser) return;
		if (leftPanelResizing) {
			window.addEventListener('mousemove', onResizeMove);
			window.addEventListener('mouseup', onResizeUp);
			document.body.style.cursor = 'col-resize';
			document.body.style.userSelect = 'none';
		}
		return () => {
			window.removeEventListener('mousemove', onResizeMove);
			window.removeEventListener('mouseup', onResizeUp);
			document.body.style.cursor = '';
			document.body.style.userSelect = '';
		};
	});

	let collapsedGroups = $state<Set<string>>(new Set());
	let defaultNewGroupsCollapsed = $state(false);
	function toggleGroup(groupId: string) {
		const next = new Set(collapsedGroups);
		if (next.has(groupId)) next.delete(groupId);
		else next.add(groupId);
		collapsedGroups = next;
	}
	function expandAll() {
		defaultNewGroupsCollapsed = false;
		collapsedGroups = new Set();
	}
	function collapseAll() {
		defaultNewGroupsCollapsed = true;
		collapsedGroups = new Set(runGroups.map((g) => g.groupId));
	}
	function toggleGroupFocus(groupId: string) {
		if (focusedGroupId === groupId) {
			focusedGroupId = null;
			const scrollTopToRestore = runsScrollTopBeforeFocus;
			runsScrollTopBeforeFocus = null;
			if (leftPanelCollapsedBeforeFocus != null) {
				leftPanelCollapsed = leftPanelCollapsedBeforeFocus;
				leftPanelCollapsedBeforeFocus = null;
			}
			// Focusing hides the left panel content; preserve the inner runs list scroll.
			if (browser && scrollTopToRestore != null) {
				tick().then(() => {
					requestAnimationFrame(() => {
						if (!runsScrollEl) return;
						runsScrollEl.scrollTop = scrollTopToRestore;
					});
				});
			}
			return;
		}
		// Only capture scroll position on unfocused -> focused transition.
		if (browser && focusedGroupId == null && runsScrollEl) {
			runsScrollTopBeforeFocus = runsScrollEl.scrollTop;
		}
		leftPanelCollapsedBeforeFocus = leftPanelCollapsed;
		leftPanelCollapsed = true;
		focusedGroupId = groupId;
	}

	$effect(() => {
		if (!browser || !focusedGroupId) return;
		const onKeyDown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') toggleGroupFocus(focusedGroupId);
		};
		window.addEventListener('keydown', onKeyDown);
		return () => window.removeEventListener('keydown', onKeyDown);
	});

	let thumbnailScale = $state<number>(browser ? getThumbSizeCookie() : 100);
	function setThumbnailScale(value: number) {
		const next = Math.min(THUMB_SCALE_MAX, Math.max(THUMB_SCALE_MIN, Math.round(value)));
		thumbnailScale = next;
		if (browser) setThumbSizeCookie(next);
	}
	let thumbnailFitMode = $state<ThumbFitMode>(browser ? getThumbFitModeCookie() : 'cover');
	function setThumbnailFitMode(mode: ThumbFitMode) {
		thumbnailFitMode = mode;
		if (browser) setThumbFitModeCookie(mode);
	}
	let showThumbFilename = $state<boolean>(browser ? getThumbShowFilenameCookie() : false);
	function setShowThumbFilename(value: boolean) {
		showThumbFilename = value;
		if (browser) setThumbShowFilenameCookie(value);
	}

	let loadedThumbIds = $state<Record<string, boolean>>({});
	let _pendingLoadedKeys = new Set<string>();
	let _flushScheduled = false;
	function flushLoadedThumbIds() {
		if (_pendingLoadedKeys.size === 0) return;
		const next = { ...loadedThumbIds };
		for (const k of _pendingLoadedKeys) next[k] = true;
		_pendingLoadedKeys = new Set();
		_flushScheduled = false;
		loadedThumbIds = next;
	}
	function markThumbLoaded(groupId: string, runId: string, index: number) {
		const key = `${groupId}-${runId}-${index}`;
		if (loadedThumbIds[key]) return;
		_pendingLoadedKeys.add(key);
		if (!_flushScheduled) {
			_flushScheduled = true;
			queueMicrotask(flushLoadedThumbIds);
		}
	}
	let imagePreviewFailed = $state<Record<string, boolean>>({});
	function markImagePreviewFailed(thumbKey: string) {
		if (imagePreviewFailed[thumbKey]) return;
		imagePreviewFailed = { ...imagePreviewFailed, [thumbKey]: true };
	}
	
	function thumbLoadFallback(
		_node: HTMLElement,
		params: { groupId: string; runId: string; index: number; thumbKey?: string },
	) {
		const t = setTimeout(() => {
			if (params.thumbKey && visibleThumbKeys[params.thumbKey]) markThumbLoaded(params.groupId, params.runId, params.index);
		}, 3000);
		return { destroy() { clearTimeout(t); } };
	}
	
	let visibleThumbKeys = $state<Record<string, boolean>>({});
	function getThumbKeysForGroupId(groupId: string): string[] {
		const group = runGroups.find((g) => g.groupId === groupId);
		if (!group) return [];
		const keys: string[] = [];
		for (const run of group.runs) {
			for (let i = 0; i < (run.images?.length ?? 0); i++) {
				keys.push(`${group.groupId}-${run.id}-${i}`);
			}
		}
		return keys;
	}
	function setThumbKeysVisibleForGroup(groupId: string) {
		const keys = getThumbKeysForGroupId(groupId);
		if (keys.length === 0) return;
		const next = { ...visibleThumbKeys };
		for (const k of keys) next[k] = true;
		visibleThumbKeys = next;
	}
	let _scrollObserver: IntersectionObserver | null = null;
	function getScrollObserver(): IntersectionObserver | null {
		if (_scrollObserver) return _scrollObserver;
		if (!runsScrollEl) return null;
		_scrollObserver = new IntersectionObserver(
			(entries) => {
				for (const e of entries) {
					if (!e.isIntersecting) continue;
					const groupId = (e.target as HTMLElement).getAttribute('data-group-id');
					if (groupId) setThumbKeysVisibleForGroup(groupId);
				}
			},
			{ root: runsScrollEl, rootMargin: '400px', threshold: 0 }
		);
		return _scrollObserver;
	}
	
	function useSentinel(node: HTMLElement, groupId: string) {
		node.setAttribute('data-group-id', groupId);
		const obs = getScrollObserver();
		if (obs) obs.observe(node);
		return {
			destroy() {
				_scrollObserver?.unobserve(node);
			},
		};
	}
	
	function useLoadMoreSentinel(node: HTMLElement, scrollRoot: HTMLElement | null) {
		let observer: IntersectionObserver | null = null;
		let currentRoot: HTMLElement | null = scrollRoot;
		function setup(root: HTMLElement | null) {
			if (!root) return;
			observer = new IntersectionObserver(
				(entries) => {
					for (const e of entries) {
						if (e.isIntersecting) loadMoreRuns();
					}
				},
				{ root, rootMargin: '300px', threshold: 0 }
			);
			observer.observe(node);
		}
		function teardown() {
			if (observer) {
				observer.disconnect();
				observer = null;
			}
		}
		setup(currentRoot);
		return {
			update(root: HTMLElement | null) {
				if (root === currentRoot) return;
				teardown();
				currentRoot = root;
				setup(currentRoot);
			},
			destroy: teardown,
		};
	}
	function thumbSrc(thumbKey: string, url: string): string | undefined {
		if (filterActive) return url;
		return visibleThumbKeys[thumbKey] ? url : undefined;
	}
	
	const THUMB_REVEAL_BATCH_SIZE = 8;
	const THUMB_REVEAL_DELAY_MS = 60;
	let allGroupsRevealed = $state(false);
	let _thumbRevealCount = 0;
	$effect(() => {
		if (!browser || loading || runGroups.length === 0) return;

		if (allGroupsRevealed && runGroups.length > _thumbRevealCount) allGroupsRevealed = false;
		if (allGroupsRevealed) return;
		const projectIdForBatch = data.projectId;
		let revealedCount = _thumbRevealCount;
		let timeoutId: ReturnType<typeof setTimeout>;
		function runBatch() {
			if (data.projectId !== projectIdForBatch) return;
			const groups = runGroups;
			const start = revealedCount;
			const end = Math.min(start + THUMB_REVEAL_BATCH_SIZE, groups.length);
	
			const next = { ...untrack(() => visibleThumbKeys) };
			for (let i = start; i < end; i++) {
				for (const k of getThumbKeysForGroupId(groups[i].groupId)) next[k] = true;
			}
			visibleThumbKeys = next;
			revealedCount = end;
			_thumbRevealCount = end;
			if (revealedCount >= groups.length) {
				allGroupsRevealed = true;
				return;
			}
			timeoutId = setTimeout(runBatch, THUMB_REVEAL_DELAY_MS);
		}
		timeoutId = setTimeout(runBatch, 0);
		return () => clearTimeout(timeoutId);
	});

	$effect(() => {
		if (!browser || loading) return;
		if (!filterActive) return;
		const groups = runGroups;
		if (groups.length === 0) return;
		const next: Record<string, boolean> = {};
		for (const g of groups) {
			for (const k of getThumbKeysForGroupId(g.groupId)) next[k] = true;
		}
		visibleThumbKeys = next;
		_thumbRevealCount = groups.length;
		allGroupsRevealed = true;
	});

	let _prevProjectId = $state<string | undefined>(undefined);
	$effect(() => {
		const projectId = data.projectId;
		if (_prevProjectId !== undefined && _prevProjectId !== projectId) {
			_thumbRevealCount = 0;
			allGroupsRevealed = false;
			visibleThumbKeys = {};
			loadedThumbIds = {};
			imagePreviewFailed = {};
		}
		_prevProjectId = projectId;
	});
	
	let _prevFilterFavoritesOnly = $state<boolean | undefined>(undefined);
	$effect(() => {
		const on = filterFavoritesOnly;
		if (_prevFilterFavoritesOnly !== undefined && _prevFilterFavoritesOnly !== on) {
			_thumbRevealCount = 0;
			allGroupsRevealed = false;
		}
		_prevFilterFavoritesOnly = on;
	});

	let _prevFilterSignature = $state<string | undefined>(undefined);
	$effect(() => {
		const sig = `${filterAppId}|${filterFromDate}|${filterToDate}|${filterMetaQ}`;
		if (_prevFilterSignature !== undefined && _prevFilterSignature !== sig) {
			_thumbRevealCount = 0;
			allGroupsRevealed = false;
			visibleThumbKeys = {};
			loadedThumbIds = {};
			imagePreviewFailed = {};
			thumbLoadFailed = new Set();
		}
		_prevFilterSignature = sig;
	});
	
	$effect(() => {
		if (!filterFavoritesOnly || loading || loadingMore) return;
		if (loadedGroupCount >= totalGroups || totalGroups <= 0) return;
		if (loadedGroupCount === 0) return;
		loadMoreRuns();
	});

	let _prevLoadedGroupIds = $state<Set<string>>(new Set());
	$effect(() => {
		const ids = new Set<string>();
		for (const r of runs) ids.add(r.run_group_id ?? r.id);
		const prev = _prevLoadedGroupIds;
		const sameAsPrev = ids.size === prev.size && [...ids].every((id) => prev.has(id));
		if (sameAsPrev) return;
		if (ids.size <= prev.size) {
			_prevLoadedGroupIds = new Set(ids);
			return;
		}
		const newIds: string[] = [];
		for (const id of ids) if (!prev.has(id)) newIds.push(id);
		if (defaultNewGroupsCollapsed && newIds.length) {
			collapsedGroups = new Set([...collapsedGroups, ...newIds]);
		}
		_prevLoadedGroupIds = new Set(ids);
	});

	let selectedInGroup = $state<Record<string, Set<string>>>({});
	function imageKey(runId: string, i: number) {
		return `${runId}_${i}`;
	}
	function toggleImageSelection(groupId: string, key: string) {
		const prev = selectedInGroup[groupId] ?? new Set();
		const next = new Set(prev);
		if (next.has(key)) next.delete(key);
		else next.add(key);
		selectedInGroup = { ...selectedInGroup, [groupId]: next };
	}
	function isImageSelected(groupId: string, key: string): boolean {
		return selectedInGroup[groupId]?.has(key) ?? false;
	}
	function hasSelection(groupId: string): boolean {
		return (selectedInGroup[groupId]?.size ?? 0) > 0;
	}

	function setCheckboxIndeterminate(el: HTMLInputElement, value: boolean) {
		el.indeterminate = !!value;
		return {
			update(value: boolean) {
				el.indeterminate = !!value;
			},
		};
	}

	function getSelectedByRun(group: (typeof runGroups)[0]): Map<string, number[]> {
		const sel = selectedInGroup[group.groupId];
		if (!sel?.size) return new Map();
		const byRun = new Map<string, number[]>();
		for (const key of sel) {
			const lastUnderscore = key.lastIndexOf('_');
			if (lastUnderscore === -1) continue;
			const runId = key.slice(0, lastUnderscore);
			const idx = parseInt(key.slice(lastUnderscore + 1), 10);
			if (Number.isNaN(idx)) continue;
			if (!byRun.has(runId)) byRun.set(runId, []);
			byRun.get(runId)!.push(idx);
		}
		return byRun;
	}

	async function deleteRemoteImage(runId: string, imageIndex: number) {
		deleteError = null;
		const key = `${runId}_${imageIndex}`;
		deletingImageKeys = new Set([...deletingImageKeys, key]);
		try {
			const res = await fetch(`${apiBase}/runs/${runId}/delete-remote-image/${imageIndex}`, { method: 'POST' });
			const data = await res.json().catch(() => ({}));
			if (res.ok) {
				mergeUpdatedRuns(data.updated_runs);
				refetchStorageSizesForRunIds([runId]);
			} else {
				deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete failed';
			}
		} finally {
			const next = new Set(deletingImageKeys);
			next.delete(key);
			deletingImageKeys = next;
		}
	}

	async function deleteLocalImage(runId: string, imageIndex: number) {
		deleteError = null;
		const key = `${runId}_${imageIndex}`;
		deletingLocalImageKeys = new Set([...deletingLocalImageKeys, key]);
		try {
			const res = await fetch(`${apiBase}/runs/${runId}/delete-local-image/${imageIndex}`, { method: 'POST' });
			const data = await res.json().catch(() => ({}));
			if (res.ok) {
				if (data.updated_runs?.length) mergeUpdatedRuns(data.updated_runs);
				updateRunStorage(runId, { local_storage_status: data.local_storage_status, local_path: data.local_path });
				refetchStorageSizesForRunIds([runId]);
			} else {
				deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete failed';
			}
		} finally {
			const next = new Set(deletingLocalImageKeys);
			next.delete(key);
			deletingLocalImageKeys = next;
		}
	}

	async function deleteBothImage(runId: string, imageIndex: number): Promise<boolean> {
		deleteError = null;
		const key = `${runId}_${imageIndex}`;
		deletingBothImageKeys = new Set([...deletingBothImageKeys, key]);
		try {
			const res = await fetch(`${apiBase}/runs/${runId}/delete-both-image/${imageIndex}`, { method: 'POST' });
			const data = await res.json().catch(() => ({}));
			if (data.updated_runs?.length) mergeUpdatedRuns(data.updated_runs);
			if (res.ok) {
				refetchStorageSizesForRunIds([runId]);
				return true;
			}
			deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete failed';
			return false;
		} finally {
			const next = new Set(deletingBothImageKeys);
			next.delete(key);
			deletingBothImageKeys = next;
		}
	}

	function truncateOutputFilename(name: string, maxLen = 28): string {
		const n = (name || '').trim();
		if (n.length <= maxLen) return n;
		const keep = maxLen - 1;
		const a = Math.ceil(keep / 2);
		const b = Math.floor(keep / 2);
		return `${n.slice(0, a)}…${n.slice(-b)}`;
	}

	async function removeOutputsFromRun(groupId: string, runId: string, imageIndex: number) {
		deleteError = null;
		const key = `${runId}_${imageIndex}`;
		deletingImageKeys = new Set([...deletingImageKeys, key]);
		try {
			const res = await fetch(`${apiBase}/runs/${runId}/remove-outputs`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ indices: [imageIndex] }),
			});
			const payload = await res.json().catch(() => ({}));
			if (res.ok) {
				mergeUpdatedRuns(payload.updated_runs);
				refetchStorageSizesForRunIds([runId]);
				selectedInGroup = { ...selectedInGroup, [groupId]: new Set() };
				thumbLoadFailed = new Set(
					[...thumbLoadFailed].filter((k) => !k.startsWith(`${groupId}-${runId}-`)),
				);
			} else {
				deleteError =
					typeof payload?.detail === 'string' ? payload.detail : payload?.error ?? 'Remove failed';
			}
		} finally {
			const next = new Set(deletingImageKeys);
			next.delete(key);
			deletingImageKeys = next;
		}
	}

	async function deleteRemoteSelectedOrGroup(group: (typeof runGroups)[0]) {
		const byRun = getSelectedByRun(group);
		if (byRun.size > 0) {
			const total = [...byRun.values()].reduce((s, arr) => s + arr.length, 0);
			if (total > 0) {
				const hasFav = [...byRun.entries()].some(([runId, indices]) => selectionIncludesFavorite(runId, indices));
				const message = hasFav
					? `Selection includes favorited run(s). They will be removed from favorites.\n\nDelete remote for ${total} selected image(s)? Files will be removed from ComfyUI server.`
					: `Delete remote for ${total} selected image(s)? Files will be removed from ComfyUI server.`;
				const doDelete = async () => {
					deleteError = null;
					selectedInGroup = { ...selectedInGroup, [group.groupId]: new Set() };
					for (const [runId, indices] of byRun) {
						const groupKey = `group-${group.groupId}-${runId}`;
						const imageKeys = indices.map((idx) => imageKey(runId, idx));
						deletingImageKeys = new Set([...deletingImageKeys, groupKey, ...imageKeys]);
						try {
							const res = await fetch(`${apiBase}/runs/${runId}/delete-remote-images`, {
								method: 'POST',
								headers: { 'Content-Type': 'application/json' },
								body: JSON.stringify({ indices })
							});
							const data = await res.json().catch(() => ({}));
							if (res.ok) {
								mergeUpdatedRuns(data.updated_runs);
							} else {
								deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete failed';
							}
						} finally {
							const next = new Set(deletingImageKeys);
							next.delete(groupKey);
							for (const k of imageKeys) next.delete(k);
							deletingImageKeys = next;
						}
					}
					refetchStorageSizesForRunIds(Array.from(byRun.keys()));
				};
				// Always confirm when favorites are involved ("Don't ask again" must not skip that warning).
				if (getSkipDeleteConfirmCookie('delete_remote') && !hasFav) {
					await doDelete();
					return;
				}
				deleteConfirmPending = {
					action: 'delete_remote',
					title: 'Delete remote',
					message,
					confirmLabel: 'Delete remote',
					onConfirmed: doDelete
				};
				return;
			}
		}
		deleteError = null;
		if (byRun.size > 0) {
		} else {
			pruneStaleRunFavorites(group.runs);
			const hasFav = group.runs.some((r) => runHasFavoritedOutput(r));
			if (hasFav) {
				deleteStorageRunGroupPending = { group, action: 'delete_remote' };
				return;
			}
			await deleteRemoteRunGroup(group);
		}
	}

	async function deleteLocalSelectedOrGroup(group: (typeof runGroups)[0]) {
		const byRun = getSelectedByRun(group);
		if (byRun.size > 0) {
			const total = [...byRun.values()].reduce((s, arr) => s + arr.length, 0);
			if (total > 0) {
				const hasFav = [...byRun.entries()].some(([runId, indices]) => selectionIncludesFavorite(runId, indices));
				const message = hasFav
					? `Selection includes favorited run(s). They will be removed from favorites.\n\nDelete local copy for ${total} selected image(s)? Files will be removed from local storage.`
					: `Delete local copy for ${total} selected image(s)? Files will be removed from local storage.`;
				const doDelete = async () => {
					deleteError = null;
					selectedInGroup = { ...selectedInGroup, [group.groupId]: new Set() };
					for (const [runId, indices] of byRun) {
						const imageKeys = indices.map((idx) => imageKey(runId, idx));
						deletingLocalImageKeys = new Set([...deletingLocalImageKeys, ...imageKeys]);
						try {
							const res = await fetch(`${apiBase}/runs/${runId}/delete-local-images`, {
								method: 'POST',
								headers: { 'Content-Type': 'application/json' },
								body: JSON.stringify({ indices })
							});
							const data = await res.json().catch(() => ({}));
							if (res.ok) {
								if (data.updated_runs?.length) mergeUpdatedRuns(data.updated_runs);
								updateRunStorage(runId, { local_storage_status: data.local_storage_status, local_path: data.local_path });
								if (typeof window !== 'undefined') {
									window.dispatchEvent(new CustomEvent('workflowui-refresh-storage'));
								}
							} else deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete failed';
						} finally {
							const next = new Set(deletingLocalImageKeys);
							for (const k of imageKeys) next.delete(k);
							deletingLocalImageKeys = next;
						}
					}
					refetchStorageSizesForRunIds(Array.from(byRun.keys()));
				};
				if (getSkipDeleteConfirmCookie('delete_local') && !hasFav) {
					await doDelete();
					return;
				}
				deleteConfirmPending = {
					action: 'delete_local',
					title: 'Delete local',
					message,
					confirmLabel: 'Delete local',
					onConfirmed: doDelete
				};
				return;
			}
		}
		deleteError = null;
		if (byRun.size > 0) {
		} else {
			pruneStaleRunFavorites(group.runs);
			const hasFav = group.runs.some((r) => runHasFavoritedOutput(r));
			if (hasFav) {
				deleteStorageRunGroupPending = { group, action: 'delete_local' };
				return;
			}
			await deleteLocalRunGroup(group);
		}
	}

	async function deleteBothSelectedOrGroup(group: (typeof runGroups)[0]) {
		const byRun = getSelectedByRun(group);
		if (byRun.size > 0) {
			const total = [...byRun.values()].reduce((s, arr) => s + arr.length, 0);
			if (total > 0) {
				const hasFav = [...byRun.entries()].some(([runId, indices]) => selectionIncludesFavorite(runId, indices));
				const message = hasFav
					? `Selection includes favorited run(s). They will be removed from favorites.\n\nDelete local and remote for ${total} selected image(s)? This cannot be undone.`
					: `Delete local and remote for ${total} selected image(s)? This cannot be undone.`;
				const doDelete = async () => {
					deleteError = null;
					selectedInGroup = { ...selectedInGroup, [group.groupId]: new Set() };
					for (const [runId, indices] of byRun) {
						const imageKeys = indices.map((idx) => imageKey(runId, idx));
						deletingBothImageKeys = new Set([...deletingBothImageKeys, ...imageKeys]);
						try {
							const res = await fetch(`${apiBase}/runs/${runId}/delete-both-images`, {
								method: 'POST',
								headers: { 'Content-Type': 'application/json' },
								body: JSON.stringify({ indices })
							});
							const data = await res.json().catch(() => ({}));
							if (data.updated_runs?.length) mergeUpdatedRuns(data.updated_runs);
							if (res.ok) {
								updateRunStorage(runId, { local_storage_status: data.local_storage_status, remote_status: data.remote_status });
							} else deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete failed';
						} finally {
							const next = new Set(deletingBothImageKeys);
							for (const k of imageKeys) next.delete(k);
							deletingBothImageKeys = next;
						}
					}
					refetchStorageSizesForRunIds(Array.from(byRun.keys()));
				};
				if (getSkipDeleteConfirmCookie('delete_all') && !hasFav) {
					await doDelete();
					return;
				}
				deleteConfirmPending = {
					action: 'delete_all',
					title: 'Delete all',
					message,
					confirmLabel: 'Delete all',
					onConfirmed: doDelete
				};
				return;
			}
		}
		deleteError = null;
		if (byRun.size > 0) {
		} else {
			pruneStaleRunFavorites(group.runs);
			const hasFav = group.runs.some((r) => runHasFavoritedOutput(r));
			if (hasFav) {
				deleteStorageRunGroupPending = { group, action: 'delete_all' };
				return;
			}
			await deleteBothRunGroup(group);
		}
	}

let lightboxOpen = $state(false);
let lightboxImages = $state<LightboxItem[]>([]);
let lightboxIndex = $state(0);
let lightboxGroupId = $state<string | null>(null);
let lightboxDeletePending = $state<
	| null
	| {
			item: LightboxItem;
			message: string;
			confirmLabel: string;
			action: DeleteConfirmKey;
	  }
>(null);
	let lightboxFavoriteDeletePending = $state<null | { item: LightboxItem; kind: 'local' | 'remote' | 'both' }>(
		null
	);
	let runsScrollEl = $state<HTMLDivElement | null>(null);
	$effect(() => {
		if (runsScrollEl) return;
		if (_scrollObserver) {
			_scrollObserver.disconnect();
			_scrollObserver = null;
		}
	});

		function buildGroupImageList(group: (typeof runGroups)[0]): LightboxItem[] {
		const list: LightboxItem[] = [];
		for (const run of group.runs) {
			for (let i = 0; i < (run.images?.length ?? 0); i++) {
				const img = run.images![i];
				const mt = mediaType(img);
				const remote_deleted = !!(img as { remote_deleted?: boolean }).remote_deleted;
				const hasLocal = run.local_storage_status === 'saved' || run.local_storage_status === 'partial';
				const hasRemote = !remote_deleted;
				const fullUrl = imageUrl(img, run.id);
				const thumbUrl = mt === 'video' ? videoThumbnailPreviewUrl(img, run.id) : undefined;
				list.push({
					id: imageKey(run.id, i),
					url: fullUrl,
					thumbnailUrl: thumbUrl,
					runId: run.id,
					filename: img.filename,
					mediaType: mt,
					remote_deleted,
					hasLocal,
					hasRemote,
					seed: run.seed,
					executionTimeSec: run.execution_time,
					outputIndex: i,
				});
			}
		}
		return list;
	}
	function getLightboxList(group: (typeof runGroups)[0]): LightboxItem[] {
		const all = buildGroupImageList(group);
		const sel = selectedInGroup[group.groupId];
		if (sel?.size) {
			const order = all.filter((img) => sel.has(img.id));
			return order.length ? order : all;
		}
		return all;
	}
	function openLightboxFromImage(
		group: (typeof runGroups)[0],
		run: ApiRun,
		imgIndex: number,
	) {
		document.querySelectorAll('audio').forEach((a) => a.pause());
		document.querySelectorAll('video').forEach((v) => v.pause());
		playingAudioThumbKey = null;
		playingVideoThumbKey = null;
		playingVideoThumbReady = false;

		if (group?.groupId) setThumbKeysVisibleForGroup(group.groupId);
		markThumbLoaded(group.groupId, run.id, imgIndex);
		const key = imageKey(run.id, imgIndex);
		let list = getLightboxList(group);
		let idx = list.findIndex((img) => img.id === key);
		if (idx === -1) {
			list = buildGroupImageList(group);
			idx = list.findIndex((img) => img.id === key);
			if (idx === -1) return;
		}
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
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = item.filename ?? (item.mediaType === 'video' ? 'video.mp4' : item.mediaType === 'audio' ? 'audio.mp3' : 'image.png');
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	}

	function applyLightboxDeletion(item: LightboxItem) {
		const currentId = item.id;
		const currentIdx = lightboxImages.findIndex((x) => x.id === currentId);
		const nextImages = lightboxImages.filter((x) => x.id !== currentId);
		if (!nextImages.length) {
			// Carousel empty after delete — if this run still has outputs, show them from the start.
			const gid = lightboxGroupId;
			const runId = item.runId;
			if (gid && runId) {
				const group = runGroups.find((g) => g.groupId === gid);
				if (group) {
					const forRun = buildGroupImageList(group).filter((img) => img.runId === runId);
					if (forRun.length > 0) {
						lightboxImages = forRun;
						lightboxIndex = 0;
						return;
					}
				}
			}
			lightboxImages = [];
			lightboxIndex = 0;
			closeLightbox();
			return;
		}
		lightboxImages = nextImages;
		// Stay on the slot that was "next" (same index), or previous item if we deleted the last.
		const nextIndex =
			currentIdx < 0
				? 0
				: currentIdx >= nextImages.length
					? nextImages.length - 1
					: currentIdx;
		lightboxIndex = nextIndex;
	}

	async function deleteLightboxLocal(item: LightboxItem) {
		const runId = item.runId;
		const index = item.outputIndex;
		if (!runId || index == null) return;
	const hadRemote = item.hasRemote ?? !item.remote_deleted;
		await deleteLocalImage(runId, index);
	if (!hadRemote) {
		// This was the last copy (local-only); remove from lightbox.
		applyLightboxDeletion(item);
		return;
	}
	const currentIdx = lightboxImages.findIndex((x) => x.id === item.id);
	if (currentIdx !== -1) {
		const updated: LightboxItem = { ...lightboxImages[currentIdx], hasLocal: false };
		const next = [...lightboxImages];
		next[currentIdx] = updated;
		lightboxImages = next;
	}
	}

	async function deleteLightboxRemote(item: LightboxItem) {
		const runId = item.runId;
		const index = item.outputIndex;
		if (!runId || index == null) return;
	const hadLocal = item.hasLocal ?? true;
		await deleteRemoteImage(runId, index);
	if (!hadLocal) {
		// This was the last copy (remote-only); remove from lightbox.
		applyLightboxDeletion(item);
		return;
	}
	const currentIdx = lightboxImages.findIndex((x) => x.id === item.id);
	if (currentIdx !== -1) {
		const updated: LightboxItem = {
			...lightboxImages[currentIdx],
			hasRemote: false,
			remote_deleted: true
		};
		const next = [...lightboxImages];
		next[currentIdx] = updated;
		lightboxImages = next;
	}
	}

	async function deleteLightboxBoth(item: LightboxItem) {
		const runId = item.runId;
		const index = item.outputIndex;
		if (!runId || index == null) return;
		const ok = await deleteBothImage(runId, index);
		if (ok) applyLightboxDeletion(item);
	}

	function proceedLightboxDeletePrompt(item: LightboxItem, kind: 'local' | 'remote' | 'both') {
		const name = item.filename && item.filename.trim().length ? item.filename : null;
		if (kind === 'local') {
			if (getSkipDeleteConfirmCookie('delete_local')) {
				deleteLightboxLocal(item).catch(() => {});
				return;
			}
			const message = name
				? `Delete this local file?\n\n'${name}' will be removed from local storage.`
				: 'Delete this local file from local storage?';
			lightboxDeletePending = {
				item,
				message,
				confirmLabel: 'Delete local file',
				action: 'delete_local'
			};
			return;
		}
		if (kind === 'remote') {
			if (getSkipDeleteConfirmCookie('delete_remote')) {
				deleteLightboxRemote(item).catch(() => {});
				return;
			}
			const message = name
				? `Delete this remote file?\n\n'${name}' will be removed from the ComfyUI server.`
				: 'Delete this remote file from the ComfyUI server?';
			lightboxDeletePending = {
				item,
				message,
				confirmLabel: 'Delete remote file',
				action: 'delete_remote'
			};
			return;
		}
		if (getSkipDeleteConfirmCookie('delete_all')) {
			deleteLightboxBoth(item).catch(() => {});
			return;
		}
		const message = name
			? `Delete this file from local and remote storage?\n\n'${name}' will be removed from local storage and the ComfyUI server.`
			: 'Delete this file from local storage and the ComfyUI server?';
		lightboxDeletePending = {
			item,
			message,
			confirmLabel: 'Delete local and remote',
			action: 'delete_all'
		};
	}

	function requestDeleteLightboxLocal(item: LightboxItem) {
		if (item.runId != null && item.outputIndex != null && isOutputFavorite(item.runId, item.outputIndex)) {
			lightboxFavoriteDeletePending = { item, kind: 'local' };
			return;
		}
		proceedLightboxDeletePrompt(item, 'local');
	}

	function requestDeleteLightboxRemote(item: LightboxItem) {
		if (item.runId != null && item.outputIndex != null && isOutputFavorite(item.runId, item.outputIndex)) {
			lightboxFavoriteDeletePending = { item, kind: 'remote' };
			return;
		}
		proceedLightboxDeletePrompt(item, 'remote');
	}

	function requestDeleteLightboxBoth(item: LightboxItem) {
		if (item.runId != null && item.outputIndex != null && isOutputFavorite(item.runId, item.outputIndex)) {
			lightboxFavoriteDeletePending = { item, kind: 'both' };
			return;
		}
		proceedLightboxDeletePrompt(item, 'both');
	}
	
	let thumbDownloading = $state(false);
	async function thumbDownloadImage(item: { filename: string; subfolder?: string; type?: string }, runId: string) {
		if (thumbDownloading) return;
		const url = imageUrl(item, runId);
		const filename = item.filename ?? 'output.png';
		thumbDownloading = true;
		try {
			const res = await fetch(url);
			const blob = await res.blob();
			const blobUrl = URL.createObjectURL(blob);
			const a = document.createElement('a');
			a.href = blobUrl;
			a.download = filename;
			document.body.appendChild(a);
			a.click();
			document.body.removeChild(a);
			URL.revokeObjectURL(blobUrl);
		} finally {
			thumbDownloading = false;
		}
	}
	function handleLightboxKey(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			if (lightboxOpen && lightboxImages.length) closeLightbox();
			else if (filterFavoritesOnly) filterFavoritesOnly = false;
		}
	}
	onMount(() => {
		if (browser) window.addEventListener('keydown', handleLightboxKey);
	});
	onDestroy(() => {
		if (browser) window.removeEventListener('keydown', handleLightboxKey);
		if (_scrollObserver && runsScrollEl) {
			_scrollObserver.disconnect();
			_scrollObserver = null;
		}
	});
</script>

{#if !data.project}
	<p class="error">Project not found.</p>
{:else}
	<div class="project-detail two-panel fill-height">
		<aside class="left-panel" class:collapsed={leftPanelCollapsed} style={leftPanelCollapsed ? undefined : `width: ${leftPanelWidth}px`}>
			<div
				class="left-panel-toggle"
				role="button"
				tabindex="0"
				aria-expanded={!leftPanelCollapsed}
				aria-label={leftPanelCollapsed ? 'Show project & filters' : 'Hide project & filters'}
				title={leftPanelCollapsed ? 'Show project & filters' : 'Hide project & filters'}
				onclick={toggleLeftPanel}
				onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleLeftPanel(); } }}
			>
				<span class="left-panel-toggle-chevron" aria-hidden="true">
					{#if leftPanelCollapsed}
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
					{:else}
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
					{/if}
				</span>
				{#if !leftPanelCollapsed}
					<span class="left-panel-toggle-label">Project & filters</span>
				{/if}
			</div>
			<div class="left-panel-content">
			{#if fromPath}
				<a href={fromPath} class="back-link">← {backLabel(fromPath)}</a>
			{/if}
			<section class="left-panel-section project-section" role="group" aria-label="Project">
			<div class="project-meta-card">
				<h3 class="section-title">Project</h3>
				{#if editingProjectName}
					<div class="project-name-edit">
						<input
							type="text"
							class="project-name-input"
							bind:value={projectName}
							bind:this={projectNameInputEl}
							disabled={nameSaving}
							onkeydown={(e) => {
								if (e.key === 'Enter') saveProjectName();
								if (e.key === 'Escape') { projectName = data.project?.name ?? ''; editingProjectName = false; }
							}}
							onblur={() => saveProjectName()}
						/>
					</div>
				{:else}
					<button type="button" class="project-name-display" onclick={startEditProjectName} title="Rename project">
						<span class="project-name-text">{data.project.name || 'Untitled project'}</span>
						<svg class="project-name-edit-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
							<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
						</svg>
					</button>
				{/if}
				<p class="meta">Created {new Date(data.project.created_at).toLocaleDateString()} · {data.project.run_count} runs</p>
				<p class="meta">
					<button
						type="button"
						class="activity-link"
						onclick={() => {
							if (typeof window !== 'undefined') {
								window.location.href = `/activity?project=${encodeURIComponent(data.project.id)}`;
							}
						}}
					>
						View project activity in global queue/recent feed
					</button>
				</p>
				<label class="description-label">
					<span class="filter-label">Description</span>
					<textarea
						class="description-textarea"
						placeholder="What is this project about?"
						bind:value={projectDescription}
						onblur={() => saveDescription()}
						disabled={descriptionSaving}
						rows="4"
					></textarea>
					{#if descriptionSaving}
						<span class="save-hint">Saving…</span>
					{/if}
				</label>
				<div class="project-tags-section">
					<div class="tags-input-wrap">
						<div class="tags-chips">
							{#if projectTags.length === 0}
								<span class="tags-placeholder">Add tags like “client”, “internal”, “image”, “video”…</span>
							{/if}
							{#each projectTags as tag (tag)}
								<button
									type="button"
									class="tag-chip tag-chip-editable"
									onclick={() => removeProjectTag(tag)}
									title="Remove tag"
								>
									<span class="tag-chip-label">{tag}</span>
									<span class="tag-chip-remove">×</span>
								</button>
							{/each}
						</div>
						<input
							type="text"
							class="tags-text-input"
							placeholder="Type tags, separate with “;”, then press Enter"
							bind:value={projectTagInput}
							onkeydown={(e) => {
								if (e.key === 'Enter' || e.key === ',') {
									e.preventDefault();
									addProjectTagFromInput();
								}
							}}
							disabled={tagsSaving}
						/>
						<p class="tags-input-hint">You can enter multiple tags at once by separating them with “;” and then pressing Enter.</p>
					</div>
					{#if tagsSaving}
						<span class="save-hint">Saving…</span>
					{/if}
				</div>
				<div class="header-color-section">
					<span class="filter-label">Header color</span>
					<p class="header-color-help">Optional. Colors the project card and name in the header when viewing an app.</p>
					<div class="header-color-wrap">
						<input
							type="color"
							class="header-color-input"
							value={projectHeaderColor ?? '#6d5dfc'}
							oninput={(e) => {
								projectHeaderColor = (e.currentTarget as HTMLInputElement).value;
								saveHeaderColor();
							}}
							aria-label="Header color"
						/>
						{#if projectHeaderColor}
							<button type="button" class="header-color-clear" onclick={() => { projectHeaderColor = null; saveHeaderColor(); }}>Clear</button>
						{/if}
					</div>
					{#if headerColorSaving}
						<span class="save-hint">Saving…</span>
					{/if}
				</div>
				{#if data.project.id !== $quickRunsProject.id}
					<div class="delete-archive-section">
						<button
							type="button"
							class="delete-archive-btn"
							onclick={() => { deleteProjectDialogOpen = true; }}
						>
							Delete / Archive project
						</button>
					</div>
				{/if}
			</div>
			</section>
			<section class="left-panel-section filters" role="group" aria-label="Filter runs">
				<h3 class="section-title section-title-with-icon">
					<svg class="section-title-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
						<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>
					</svg>
					Filter runs
				</h3>
				<label class="filter-row">
					<span class="filter-label">Search in metadata</span>
					<div class="filter-input-wrap">
						<svg class="filter-input-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
							<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
						</svg>
						<input
							type="search"
							class="filter-input"
							placeholder="Search generations by metadata…"
							bind:value={filterMetaQ}
							title="Search in run metadata and input snapshot"
						/>
					</div>
				</label>
				<label class="filter-row">
					<span class="filter-label">App</span>
					<select
						class="filter-select"
						value={filterAppId}
						onchange={(e) => { filterAppId = (e.currentTarget as HTMLSelectElement).value; }}
					>
						<option value="">All apps</option>
						{#each appFilterOptions as app (app.id)}
							<option value={app.id}>{app.title}</option>
						{/each}
					</select>
				</label>
				<div class="filter-row filter-date-range" role="group" aria-label="Date range">
					<span class="filter-label">Date range</span>
					<div class="filter-date-row">
						<label class="filter-date-field">
							<span class="filter-date-field-label">From</span>
							<input type="date" class="filter-input filter-date" bind:value={filterFromDate} title="Show runs on or after this day" />
						</label>
						<label class="filter-date-field">
							<span class="filter-date-field-label">To</span>
							<input type="date" class="filter-input filter-date" bind:value={filterToDate} title="Show runs on or before this day" />
						</label>
					</div>
				</div>
				{#if filterActive}
					<div class="filter-active-row">
						<span class="filter-active-badge" aria-label="Filter active">Filter active</span>
						<button type="button" class="filter-clear-btn" onclick={() => { filterAppId = ''; filterFromDate = ''; filterToDate = ''; filterMetaQ = ''; filterFavoritesOnly = false; }}>Clear filters</button>
					</div>
				{/if}
			</section>
			<section class="left-panel-section project-notes" class:collapsed={notesCollapsed} role="group" aria-label="Notes">
				<div class="notes-header-row" role="button" tabindex="0" onclick={toggleNotesCollapsed} onkeydown={(e) => e.key === 'Enter' || e.key === ' ' ? (e.preventDefault(), toggleNotesCollapsed()) : null} aria-expanded={!notesCollapsed} aria-controls="notes-content">
					<span class="notes-chevron" aria-hidden="true">{notesCollapsed ? '▸' : '▾'}</span>
					<span class="notes-header-title">Notes</span>
				</div>
				{#if !notesCollapsed}
					<div id="notes-content" class="notes-content">
						<p class="notes-hint">Keep notes while working on this project.</p>
						<div class="notes-add">
							<textarea
								class="notes-draft"
								placeholder="Add a note…"
								bind:value={noteDraft}
								rows="5"
							></textarea>
							<button type="button" class="notes-add-btn" disabled={notesSaving || !noteDraft.trim()} onclick={addNote}>Add note</button>
						</div>
						{#if notes.length > 0}
							<div class="notes-search-wrap">
								<svg class="notes-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
									<circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
								</svg>
								<input
									type="search"
									class="notes-search-input"
									placeholder="Search notes…"
									bind:value={notesSearch}
									aria-label="Search notes"
								/>
							</div>
						{/if}
						<ul class="notes-list">
							{#each filteredNotes as note (note.id)}
								<li class="note-item">
									{#if editingNoteId === note.id}
										<textarea class="note-edit-input" bind:value={editingContent} rows="3"></textarea>
										<div class="note-edit-actions">
											<button type="button" class="note-btn save" onclick={() => updateNote(note.id, editingContent)}>Save</button>
											<button type="button" class="note-btn" onclick={cancelEditNote}>Cancel</button>
										</div>
									{:else}
										<p class="note-content">
											{#each parseNoteContent(note.content) as segment}
												{#if segment.type === 'link'}
													<a href={segment.url} target="_blank" rel="noopener noreferrer" class="note-link">{segment.url}
														<svg class="note-link-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" title="Open in new tab">
															<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
														</svg>
													</a>
												{:else}
													{segment.value}
												{/if}
											{/each}
										</p>
										<div class="note-meta">
											<span class="note-date">{new Date(note.created_at).toLocaleString()}</span>
											<button type="button" class="note-btn small" onclick={() => startEditNote(note)}>Edit</button>
											<button type="button" class="note-btn small delete" onclick={() => deleteNote(note.id)}>Delete</button>
										</div>
									{/if}
								</li>
							{/each}
						</ul>
						{#if notes.length === 0 && !notesSaving}
							<p class="notes-empty">No notes yet.</p>
						{:else if filteredNotes.length === 0}
							<p class="notes-empty">No notes match your search.</p>
						{/if}
					</div>
				{/if}
			</section>
			<section class="left-panel-section apps-used" role="group" aria-label="Apps used">
				<h3 class="section-title">Apps used</h3>
				<ul class="apps-used-list" role="list">
					{#each appsUsedSortedByRuns as app, i (app.id)}
						<li class="apps-used-item" style="animation-delay: {i * 40}ms">
							{#if app.removed}
								<span class="apps-used-removed-wrap" title="This app was deleted. No generated data was removed; run history is still available.">
									<RunAppBadge
										label="Deleted App"
										title="This app was deleted. No generated data was removed; run history is still available."
										removed={true}
									/>
									<svg class="apps-used-deleted-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
										<polyline points="3 6 5 6 21 6"/>
										<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
										<line x1="10" y1="11" x2="10" y2="17"/>
										<line x1="14" y1="11" x2="14" y2="17"/>
									</svg>
								</span>
							{:else}
								<button type="button" class="apps-used-badge-btn" onclick={() => openAppInProject(app.slug)} title="Open in project">
									<RunAppBadge
										appHeaderColor={app.header_color ?? undefined}
										label={app.title ?? app.slug ?? 'App'}
										title="Open in project"
										removed={false}
									/>
								</button>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
			<section class="left-panel-section storage-policy" role="group" aria-label="Storage policy">
				<div class="storage-policy-header">
					<h3 class="section-title">Storage policy</h3>
					{#if data.mediaStorage}
						<p class="storage-global">
							Global: {data.mediaStorage.enabled ? 'Enabled' : 'Disabled'} · Root: <code>{data.mediaStorage.rootPath}</code>
						</p>
					{/if}
					<p class="storage-global metadata-attached-note" role="status">
						Workflow metadata on download: <strong>{data.embedWorkflowuiMetadataOnDownload ? 'Yes' : 'No'}</strong>
						— {data.embedWorkflowuiMetadataOnDownload ? 'included when you download images (restore on Import page)' : 'enable in backend .env to attach metadata'}
					</p>
				</div>
				<div
					class="storage-segments"
					role="radiogroup"
					aria-label="Storage policy"
				>
					<button
						type="button"
						role="radio"
						aria-checked={storageMode === 'inherit'}
						class="storage-segment"
						class:selected={storageMode === 'inherit'}
						disabled={storageSaving}
						title="Use the global storage setting"
						onclick={() => { storageMode = 'inherit'; setProjectStorageMode('inherit'); }}
					>
						<span class="storage-segment-label">Inherit</span>
						<span class="storage-segment-sublabel">Global</span>
					</button>
					<button
						type="button"
						role="radio"
						aria-checked={storageMode === 'local'}
						class="storage-segment"
						class:selected={storageMode === 'local'}
						disabled={storageSaving}
						title="Always store outputs on this machine"
						onclick={() => { storageMode = 'local'; setProjectStorageMode('local'); }}
					>
						<span class="storage-segment-label">Local</span>
						<span class="storage-segment-sublabel">This machine</span>
					</button>
					<button
						type="button"
						role="radio"
						aria-checked={storageMode === 'remote'}
						class="storage-segment"
						class:selected={storageMode === 'remote'}
						disabled={storageSaving}
						title="Always store outputs in remote storage"
						onclick={() => { storageMode = 'remote'; setProjectStorageMode('remote'); }}
					>
						<span class="storage-segment-label">Remote</span>
						<span class="storage-segment-sublabel">Cloud</span>
					</button>
				</div>
				{#if storageError}
					<p class="storage-error">{storageError}</p>
				{/if}
				{#if storageMode === 'remote'}
					<p class="storage-warning">Manual save is disabled while storage is set to remote.</p>
				{/if}
				<p class="storage-note">Changes apply to future runs only.</p>
			</section>
			</div>
		</aside>
		{#if !leftPanelCollapsed}
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<div
			class="panel-resizer"
			class:resizing={leftPanelResizing}
			role="separator"
			aria-orientation="vertical"
			aria-valuenow={leftPanelWidth}
			aria-valuemin={LEFT_PANEL_MIN}
			aria-valuemax={LEFT_PANEL_MAX}
			title="Drag to resize"
			tabindex="-1"
			onmousedown={(e) => startResize(e)}
		></div>
		{/if}
		<div class="right-panel runs-list">
			<div class="runs-list-head">
				<div class="runs-list-head-left">
					<h2 class="runs-count-heading" aria-live="polite">
						{#if !loading && (runs.length > 0 || totalGroups > 0)}
							<span class="runs-count-heading-title">Runs</span>
							<span class="runs-count-heading-counts">
								{displayRunsCount} run{displayRunsCount === 1 ? '' : 's'}
								{#if displayGenerationsCount > 0}
									<span class="runs-count-generations">({displayGenerationsCount} generation{displayGenerationsCount === 1 ? '' : 's'})</span>
								{/if}
								{#if filterActive}<span class="runs-count-filtered">(filtered)</span>{/if}
							</span>
						{:else}
							<span class="runs-count-heading-title">Runs</span>
						{/if}
					</h2>
				</div>
				{#if !loading}
					<div class="runs-list-head-actions">
						<!-- Desktop: keep the existing inline controls -->
						<div class="runs-list-head-actions-desktop">
							{#if visibleRunGroups.length > 0}
								<div class="move-runs-actions">
									<button
										type="button"
										class="move-to-project-btn"
										disabled={selectedRunIds.size === 0}
										title={selectedRunIds.size === 0 ? 'Select at least one run using the checkbox on each group, then click here to move runs to another project' : `Move ${selectedRunIds.size} run(s) to another project`}
										aria-label={selectedRunIds.size === 0 ? 'Select at least one run using the checkbox on each group to enable move' : 'Move selected runs to another project'}
										onclick={() => (moveDialogOpen = true)}
									>
										Move to project
									</button>
									<span class="gallery-size-divider" aria-hidden="true"></span>
								</div>
							{/if}
							<label class="favorites-filter-option" title="Show only favorited runs">
								<span class="favorites-filter-label">Favorites only</span>
								<button
									type="button"
									role="switch"
									aria-checked={filterFavoritesOnly}
									class="favorites-filter-toggle"
									class:on={filterFavoritesOnly}
									aria-label="Show only favorited runs"
									onclick={() => (filterFavoritesOnly = !filterFavoritesOnly)}
								>
									<span class="favorites-filter-toggle-track">
										<span class="favorites-filter-toggle-thumb"></span>
									</span>
								</button>
							</label>
							{#if runGroups.length > 0}
								<div class="collapse-all-actions">
									<button type="button" class="collapse-all-btn" onclick={expandAll}>Expand all</button>
									<button type="button" class="collapse-all-btn" onclick={collapseAll}>Collapse all</button>
									<span class="gallery-size-divider" aria-hidden="true"></span>
									<div class="gallery-thumb-size">
										<label for="project-thumb-size">Thumbnail size</label>
										<input
											id="project-thumb-size"
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
									<span class="gallery-size-divider" aria-hidden="true"></span>
									<div class="gallery-thumb-fit" role="group" aria-label="Thumbnail render mode">
										<button
											type="button"
											class="collapse-all-btn thumb-fit-btn"
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
											class="collapse-all-btn thumb-fit-btn"
											class:active={thumbnailFitMode === 'contain'}
											onclick={() => setThumbnailFitMode('contain')}
											title="Fit into thumbnail"
											aria-label="Fit into thumbnail"
											aria-pressed={thumbnailFitMode === 'contain'}
										>
											Fit into thumbnail
										</button>
									</div>
									<span class="gallery-size-divider" aria-hidden="true"></span>
									<label class="favorites-filter-option" title="Show output filenames on thumbnails">
										<span class="favorites-filter-label">Filenames</span>
										<button
											type="button"
											role="switch"
											aria-checked={showThumbFilename}
											class="favorites-filter-toggle"
											class:on={showThumbFilename}
											aria-label="Show filenames on thumbnails"
											onclick={() => setShowThumbFilename(!showThumbFilename)}
										>
											<span class="favorites-filter-toggle-track">
												<span class="favorites-filter-toggle-thumb"></span>
											</span>
										</button>
									</label>
								</div>
							{/if}
						</div>

						<!-- Mobile: collapse the "gallery controls" into a drawer -->
						<div class="runs-list-head-actions-mobile">
							<label class="favorites-filter-option" title="Show only favorited runs">
								<span class="favorites-filter-label">Favorites only</span>
								<button
									type="button"
									role="switch"
									aria-checked={filterFavoritesOnly}
									class="favorites-filter-toggle"
									class:on={filterFavoritesOnly}
									aria-label="Show only favorited runs"
									onclick={() => (filterFavoritesOnly = !filterFavoritesOnly)}
								>
									<span class="favorites-filter-toggle-track">
										<span class="favorites-filter-toggle-thumb"></span>
									</span>
								</button>
							</label>

							{#if runGroups.length > 0}
								<details class="thumbnails-controls-drawer" aria-label="Thumbnail controls">
									<summary aria-label="Open thumbnail controls">
										<span>Thumbnails</span>
										<span class="thumb-drawer-summary-value">{thumbnailScale}%</span>
									</summary>

									<div class="thumbnails-controls-inner">
										{#if visibleRunGroups.length > 0}
											<button
												type="button"
												class="move-to-project-btn"
												disabled={selectedRunIds.size === 0}
												title={selectedRunIds.size === 0 ? 'Select at least one run using the checkbox on each group, then click here to move runs to another project' : `Move ${selectedRunIds.size} run(s) to another project`}
												aria-label={selectedRunIds.size === 0 ? 'Select at least one run using the checkbox on each group to enable move' : 'Move selected runs to another project'}
												onclick={() => (moveDialogOpen = true)}
											>
												Move to project
											</button>
										{/if}

										<div class="collapse-all-actions">
											<button type="button" class="collapse-all-btn" onclick={expandAll}>Expand all</button>
											<button type="button" class="collapse-all-btn" onclick={collapseAll}>Collapse all</button>
										</div>

										<div class="gallery-thumb-size">
											<label for="project-thumb-size-mobile">Thumbnail size</label>
											<input
												id="project-thumb-size-mobile"
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
												class="collapse-all-btn thumb-fit-btn"
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
												class="collapse-all-btn thumb-fit-btn"
												class:active={thumbnailFitMode === 'contain'}
												onclick={() => setThumbnailFitMode('contain')}
												title="Fit into thumbnail"
												aria-label="Fit into thumbnail"
												aria-pressed={thumbnailFitMode === 'contain'}
											>
												Fit into thumbnail
											</button>
										</div>

										<label class="favorites-filter-option" title="Show output filenames on thumbnails">
											<span class="favorites-filter-label">Filenames</span>
											<button
												type="button"
												role="switch"
												aria-checked={showThumbFilename}
												class="favorites-filter-toggle"
												class:on={showThumbFilename}
												aria-label="Show filenames on thumbnails"
												onclick={() => setShowThumbFilename(!showThumbFilename)}
											>
												<span class="favorites-filter-toggle-track">
													<span class="favorites-filter-toggle-thumb"></span>
												</span>
											</button>
										</label>
									</div>
								</details>
							{/if}
						</div>
					</div>
				{/if}
			</div>
			<div class="runs-list-body">
			{#if deleteError}
				<p class="delete-error" role="alert">
					{deleteError}
					<button type="button" class="delete-error-dismiss" onclick={() => (deleteError = null)} aria-label="Dismiss">×</button>
				</p>
			{/if}
			{#if loading}
				<div class="runs-loading-wrap">
					<PageLoadingIndicator />
				</div>
			{:else if !displayRunGroups.length}
				{#if data.project.run_count === 0 && (data.appsForNew?.length ?? 0) > 0}
					<div class="empty-project-state">
						<div class="empty-project-icon" aria-hidden="true">
							<svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
								<path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/>
							</svg>
						</div>
						<h2>Start generating</h2>
						<p class="empty-project-desc">Pick any app below to run in this project. Your generations will appear here.</p>
						<div class="empty-project-apps">
							{#each data.appsForNew ?? [] as app (app.id)}
								{#if app.slug}
									<a href="/app/{app.slug}?project={data.projectId}" class="empty-app-link">{app.title ?? app.slug}</a>
								{/if}
							{/each}
						</div>
					</div>
				{:else if filterFavoritesOnly && loadedGroupCount < totalGroups && totalGroups > 0}
					<div class="runs-scroll runs-scroll-empty-favorites" bind:this={runsScrollEl}>
						<p class="muted">No favorites in the first {loadedGroupCount} run group{loadedGroupCount === 1 ? '' : 's'}. Load more to find favorites.</p>
						<InfiniteScrollLoadMore
							loading={loadingMore}
							loadedCount={loadedGroupCount}
							totalCount={totalGroups}
							thumbScalePercent={thumbnailScale}
							buttonDisabled={loading}
							onLoadMore={loadMoreRuns}
							loadMoreLabel="Load more runs"
							statusTitle="Loading more runs"
							countNoun="run groups"
							statusAriaLabel="Loading more run groups for this project"
						></InfiniteScrollLoadMore>
					</div>
				{:else}
					<p class="muted">{filterActive ? 'No runs match the current filters.' : 'No runs in this project.'}</p>
				{/if}
			{:else}
				<div class="runs-scroll" bind:this={runsScrollEl}>
					{#key runsRenderKey}
					{#each displayRunGroups as group (group.groupId)}
						{@const storageSummary = getGroupStorageSummary(group)}
						{@const savingGroup = savingGroupIds.has(group.groupId)}
						{@const deletingGroup = deletingGroupIds.has(group.groupId)}
						{@const deletingLocalGroup = deletingLocalGroupIds.has(group.groupId)}
						{@const deletingBothGroup = deletingBothGroupIds.has(group.groupId)}
						{@const deletingRemoteHeader = deletingGroup || group.runs.some((r) => deletingImageKeys.has(`group-${group.groupId}-${r.id}`) || (r.images ?? []).some((_, i) => deletingImageKeys.has(imageKey(r.id, i))))}
						{@const deletingLocalHeader = deletingLocalGroup || group.runs.some((r) => (r.images ?? []).some((_, i) => deletingLocalImageKeys.has(imageKey(r.id, i))))}
						{@const deletingBothHeader = deletingBothGroup || group.runs.some((r) => (r.images ?? []).some((_, i) => deletingBothImageKeys.has(imageKey(r.id, i))))}
						{@const hasGroupSelection = hasSelection(group.groupId)}
						{@const groupHasLocalStorage = group.runs.some((r) => r.local_storage_status && r.local_storage_status !== 'none')}
						{@const groupHasRemoteToDelete = group.runs.some((r) => (r.images ?? []).some((img) => !(img as { remote_deleted?: boolean }).remote_deleted))}
						{@const selectedHasRemote = (() => {
							const sel = selectedInGroup[group.groupId];
							if (!sel?.size) return true;
							for (const r of group.runs) {
								for (let i = 0; i < (r.images?.length ?? 0); i++) {
									if (sel.has(imageKey(r.id, i)) && !(r.images![i] as { remote_deleted?: boolean }).remote_deleted) return true;
								}
							}
							return false;
						})()}
						{@const selectedHasLocal = (() => {
							const sel = selectedInGroup[group.groupId];
							if (!sel?.size) return true;
							for (const key of sel) {
								const lastUnderscore = key.lastIndexOf('_');
								if (lastUnderscore === -1) continue;
								const runId = key.slice(0, lastUnderscore);
								const run = group.runs.find((r) => r.id === runId);
								if (run && (run.local_storage_status === 'saved' || run.local_storage_status === 'partial')) return true;
							}
							return false;
						})()}
						{@const canDeleteRemote = hasGroupSelection ? selectedHasRemote : groupHasRemoteToDelete}
						{@const canDeleteLocal = hasGroupSelection ? selectedHasLocal : groupHasLocalStorage}
						{@const canDeleteBoth = hasGroupSelection ? (selectedHasRemote && selectedHasLocal) : (groupHasRemoteToDelete && groupHasLocalStorage)}
						<section class="run-section">
							<div class="thumb-sentinel" use:useSentinel={group.groupId} data-group-id={group.groupId} aria-hidden="true"></div>
							<header
								class="run-header"
								role="button"
								tabindex="0"
								onclick={() => toggleGroup(group.groupId)}
								onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleGroup(group.groupId); } }}
							>
								<div class="run-title">
									<label
										class="move-runs-group-checkbox-wrap"
										title="Select runs in this group to move to another project"
										onclick={(e) => e.stopPropagation()}
										onkeydown={(e) => e.stopPropagation()}
									>
										<input
											type="checkbox"
											class="move-runs-checkbox"
											aria-label="Select runs in this group for move"
											checked={group.runs.length > 0 && group.runs.every((r) => selectedRunIds.has(r.id))}
											use:setCheckboxIndeterminate={group.runs.some((r) => selectedRunIds.has(r.id)) && !group.runs.every((r) => selectedRunIds.has(r.id))}
											onchange={(e) => {
												const ids = group.runs.map((r) => r.id);
												if ((e.currentTarget as HTMLInputElement).checked) selectedRunIds = new Set([...selectedRunIds, ...ids]);
												else selectedRunIds = new Set([...selectedRunIds].filter((id) => !ids.includes(id)));
											}}
										/>
									</label>
									<span class="run-dot"></span>
									<RunAppBadge
										appHeaderColor={group.app_header_color ?? undefined}
										label={group.app_removed ? 'Deleted App' : (group.app_title ?? group.app_slug ?? 'App')}
										title={group.app_removed ? 'App was deleted. No generated data was removed; run history is still available.' : (group.app_title ?? group.app_slug ?? '')}
										removed={group.app_removed}
									/>
									{#if group.app_removed}
										<span class="badge-removed" title="This app was deleted. No generated data was removed; you can still view run details and outputs.">Removed</span>
									{/if}
									{#if group.status === 'error'}
										<span class="run-status error">✗ Error</span>
									{:else if group.status === 'running'}
										<span class="run-status running">⌛ Generating…</span>
										<button
											type="button"
											class="run-header-cancel-btn"
											disabled={cancellingGroupIds.has(group.groupId)}
											onclick={(e) => { e.stopPropagation(); cancelRunGroup(group); }}
											title="Cancel running and queued runs in this group"
											aria-label="Cancel"
										>
											{#if cancellingGroupIds.has(group.groupId)}…{:else}Cancel{/if}
										</button>
									{:else if group.status === 'queued'}
										<span class="run-status queued">In queue</span>
										<button
											type="button"
											class="run-header-cancel-btn"
											disabled={cancellingGroupIds.has(group.groupId)}
											onclick={(e) => { e.stopPropagation(); cancelRunGroup(group); }}
											title="Cancel running and queued runs in this group"
											aria-label="Cancel"
										>
											{#if cancellingGroupIds.has(group.groupId)}…{:else}Cancel{/if}
										</button>
									{:else if group.status === 'cancelled'}
										<span class="run-status cancelled">Cancelled</span>
									{/if}
									<span class="run-count">
										{#if group.latent_resolution}
											<span class="run-resolution" title="Latent resolution"> {group.latent_resolution}</span>
											<span class="run-count-sep">·</span>
										{/if}
										{group.runCount} prompt{group.runCount === 1 ? '' : 's'} · {group.runs.reduce((n, r) => n + (r.images?.length ?? 0), 0)} image{group.runs.reduce((n, r) => n + (r.images?.length ?? 0), 0) === 1 ? '' : 's'}
										{#if hasSelection(group.groupId)}
											<span class="run-count-filter"> · {(selectedInGroup[group.groupId]?.size ?? 0)} selected for lightbox</span>
										{/if}
									</span>
								</div>
								<RunHeaderActions
									storageSummary={storageSummary}
									localStorageBytes={storageSummary != null ? sumKnownStorageBytes(group, 'local_storage_bytes') : undefined}
									remoteStorageBytes={storageSummary != null ? sumKnownStorageBytes(group, 'remote_storage_bytes') : undefined}
									status={group.status}
									createdAt={group.createdAt}
									timeExtra=""
									saveDisabled={savingGroup || storageMode === 'remote' || (hasGroupSelection ? !selectedHasRemote : !groupHasRemoteToDelete)}
									saveLoading={savingGroup}
									onSave={() => saveSelectedOrRunGroup(group)}
									saveTitle={storageMode === 'remote' ? 'Manual save disabled for remote-only projects' : hasGroupSelection && !selectedHasRemote ? 'No remote files in selection to save' : !groupHasRemoteToDelete && !hasGroupSelection ? 'No remote files to save (all deleted on server)' : hasGroupSelection ? `Save ${selectedInGroup[group.groupId]?.size ?? 0} selected image(s) to local storage` : 'Save run: copy all images in this run to local storage (downloads from ComfyUI)'}
									remoteDisabled={(group.status !== 'done' && group.status !== 'cancelled') || deletingRemoteHeader || !data.comfyuiDeleteSupported || !canDeleteRemote}
									remoteLoading={deletingRemoteHeader}
									onDeleteRemote={() => deleteRemoteSelectedOrGroup(group)}
									remoteTitle={!data.comfyuiDeleteSupported ? 'Install WorkflowUIPlugin on ComfyUI to delete files on server' : !canDeleteRemote ? (hasGroupSelection ? 'No remote files in selection to delete' : 'No remote files to delete') : undefined}
									localDisabled={(group.status !== 'done' && group.status !== 'cancelled') || deletingLocalHeader || !canDeleteLocal}
									localLoading={deletingLocalHeader}
									onDeleteLocal={() => deleteLocalSelectedOrGroup(group)}
									localTitle={!canDeleteLocal ? (hasGroupSelection ? 'No local files in selection to delete' : 'No local files to delete (remote only)') : undefined}
									allDisabled={(group.status !== 'done' && group.status !== 'cancelled') || deletingBothHeader || !canDeleteBoth || !data.comfyuiDeleteSupported}
									allLoading={deletingBothHeader}
									onDeleteAll={() => deleteBothSelectedOrGroup(group)}
									allTitle={!data.comfyuiDeleteSupported ? 'Install WorkflowUIPlugin on ComfyUI to delete files on server' : !canDeleteBoth ? (hasGroupSelection ? 'Selection has no local and/or remote files to delete; use Delete remote or Delete local as appropriate' : 'No remote and/or local files to delete') : undefined}
									deleteRunDisabled={group.runs.some((r) => deletingRunIds.has(r.id))}
									deleteRunLoading={group.runs.some((r) => deletingRunIds.has(r.id))}
									onDeleteRun={() => requestDeleteRunGroup(group)}
									showReplicate={!group.app_removed && !!group.app_slug}
									replicateDisabled={group.app_removed}
									onReplicate={group.app_slug ? () => openAppWithParams(group.app_slug!, group.firstRunId) : undefined}
									replicateTitle={group.app_removed ? 'App was deleted; cannot replicate this run. No generated data was removed.' : 'Open this app with the same parameters to replicate the run'}
									showShowMetadata={true}
									onShowMetadata={() => { metadataPanelRunId = group.firstRunId; metadataPanelMode = 'run'; }}
									showFullscreenToggle={true}
									fullscreenActive={focusedGroupId === group.groupId}
									onToggleFullscreen={() => toggleGroupFocus(group.groupId)}
									fullscreenTitle="Focus this run in fullscreen (Esc to exit)"
									collapseIcon={collapsedGroups.has(group.groupId) ? '▸' : '▾'}
									hasSelection={hasGroupSelection}
								/>
							</header>
							{#if group.status === 'running'}
								<div class="progress">
									<div class="bar"></div>
								</div>
							{/if}
							{#if !collapsedGroups.has(group.groupId)}
								{#if group.status === 'error' && group.error}
									<div class="error-placeholder">{group.error}</div>
								{:else}
									<div class="run-body">
										{#if group.status === 'queued' && group.comfyui_unreachable_warning}
											<div class="comfyui-unreachable-warning" role="alert">
												<span>{group.comfyui_unreachable_warning}</span>
												<button
													type="button"
													class="run-action-btn retry-comfyui-btn"
													disabled={retryingGroupIds.has(group.groupId)}
													onclick={(e) => { e.stopPropagation(); retryRunGroup(group); }}
													title="Move run to front of queue and try again"
													aria-label="Retry run"
												>
													{#if retryingGroupIds.has(group.groupId)}
														<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
															<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
														</svg>
													{:else}
														<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
															<path d="M1 4v6h6"/>
															<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
														</svg>
													{/if}
													<span class="run-action-label">Retry</span>
												</button>
											</div>
										{/if}
										{#if hasSelection(group.groupId)}
											<div class="run-filter-bar">
												<span class="run-filter-label">Lightbox filter: {(selectedInGroup[group.groupId]?.size ?? 0)} selected</span>
												<button type="button" class="run-filter-clear" onclick={() => { selectedInGroup = { ...selectedInGroup, [group.groupId]: new Set() }; }}>Clear selection</button>
											</div>
										{/if}
										{#if group.runs.some((r) => r.status === 'queued' || r.status === 'running')}
											<div class="run-queue-strip" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
												{#each group.runs.filter((r) => r.status === 'queued' || r.status === 'running') as run (run.id)}
													<span class="run-queue-item">
														<span class="run-queue-status">{run.status === 'running' ? 'Generating…' : 'Queued'}{#if run.queue_position} (position {run.queue_position}){/if}</span>
														<button
															type="button"
															class="run-action-btn cancel-queued-btn"
															disabled={cancellingRunIds.has(run.id)}
															onclick={(e) => { e.stopPropagation(); cancelRun(run); }}
															title="Cancel this run"
															aria-label="Cancel run"
														>
															{#if cancellingRunIds.has(run.id)}
																<svg class="icon spinner" viewBox="0 0 24 24" aria-hidden="true">
																	<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-dasharray="28 10"/>
																</svg>
															{:else}
																<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
																	<circle cx="12" cy="12" r="10"/>
																	<line x1="15" y1="9" x2="9" y2="15"/>
																	<line x1="9" y1="9" x2="15" y2="15"/>
																</svg>
															{/if}
															<span class="run-action-label">Cancel</span>
														</button>
													</span>
												{/each}
											</div>
										{/if}
										<div
											class="output-section-body"
											style={`--thumb-size-scale:${thumbnailScale / 100};`}
											class:thumb-fit-contain={thumbnailFitMode === 'contain'}
										>
											{#each group.runs as run (run.id)}
												{@const visibleImages = (run.images ?? []).map((item, origI) => ({ item, origI })).filter(({ item }) => { const rd = !!(item as { remote_deleted?: boolean }).remote_deleted; if (!rd) return true; if (run.local_storage_status === 'saved' || run.local_storage_status === 'partial') return true; return false; })}
												{#each visibleImages as { item, origI } (run.id + '_' + origI)}
													{@const key = imageKey(run.id, origI)}
													{@const isRemoteDeleted = !!(item as { remote_deleted?: boolean }).remote_deleted}
													{@const itemType = mediaType(item)}
													{@const isVideo = itemType === 'video'}
													{@const isAudio = itemType === 'audio'}
													{@const thumbKey = `${group.groupId}-${run.id}-${origI}`}
													{@const thumbFailed = thumbLoadFailed.has(thumbKey)}
													{@const showDeletedPlaceholder = isRemoteDeleted && thumbFailed}
													{@const showNotFoundPlaceholder = !isRemoteDeleted && thumbFailed}
													{@const showAnyMediaPlaceholder = showDeletedPlaceholder || showNotFoundPlaceholder}
													{@const isLoaded = !!loadedThumbIds[thumbKey] || showAnyMediaPlaceholder}
													{@const isDeleting = deletingImageKeys.has(key) || deletingLocalImageKeys.has(key) || deletingBothImageKeys.has(key)}
													{@const hasLocalStorage = run.local_storage_status === 'saved' || run.local_storage_status === 'partial'}
													<div
														class="output-thumb thumb-media"
														class:thumb-loaded={isLoaded}
														class:output-thumb-video={isVideo}
														class:output-thumb-audio={isAudio}
														class:output-thumb-deleted={showDeletedPlaceholder}
														class:output-thumb-not-found={showNotFoundPlaceholder}
														class:output-thumb-deleting={isDeleting}
														class:audio-playing={isAudio && playingAudioThumbKey === thumbKey}
														class:thumb-selected={isImageSelected(group.groupId, key)}
														class:output-thumb-local-storage={hasLocalStorage}
														role="button"
														tabindex="0"
														use:thumbLoadFallback={{ groupId: group.groupId, runId: run.id, index: origI, thumbKey }}
														onclick={(e) => {
														if (showAnyMediaPlaceholder || isDeleting) return;
														const target = e.target as HTMLElement;
														const thumb = target.closest('.output-thumb');
														const audio = thumb?.querySelector<HTMLAudioElement>('audio');
														if (target.closest('.output-thumb-audio-play-btn') || target.closest('.output-thumb-audio-controls-wrap')) {
															if (audio) {
																if (audio.paused) {
																	document.querySelectorAll('audio').forEach((el) => { if (el !== audio) el.pause(); });
																	audio.play();
																} else {
																	audio.pause();
																}
															}
															return;
														}
														openLightboxFromImage(group, run, origI);
													}}
													onkeydown={(e) => {
														if (e.key !== 'Enter') return;
														if (showAnyMediaPlaceholder || isDeleting) return;
														if ((e.target as HTMLElement).closest('.output-thumb-audio-play-btn, .output-thumb-audio-controls-wrap')) return;
														openLightboxFromImage(group, run, origI);
													}}
														onmouseenter={() => { if (isVideo) { playingVideoThumbReady = false; playingVideoThumbKey = thumbKey; } }}
														onmouseleave={() => { if (isVideo && playingVideoThumbKey === thumbKey) playingVideoThumbKey = null; }}
													>
														<span class="thumb-loading" class:hide={isVideo && playingVideoThumbKey === thumbKey ? playingVideoThumbReady : isLoaded} aria-hidden="true">
															<span class="thumb-loading-spinner" aria-hidden="true"></span>
														</span>
														{#if isDeleting}
															<div class="output-thumb-deleting-overlay" aria-hidden="true" aria-live="polite">
																<span class="output-thumb-deleting-spinner" aria-hidden="true"></span>
																<span class="output-thumb-deleting-label">Deleting…</span>
															</div>
														{/if}
														<ThumbnailOverlay
															mediaType={isVideo ? 'video' : isAudio ? 'audio' : 'image'}
															resolution={isAudio ? undefined : mediaResolutionLabel(key)}
															seed={run.seed ?? undefined}
															executionTimeSec={run.execution_time ?? undefined}
															fileName={(item as { filename?: string }).filename}
															showFilenameAlways={showThumbFilename}
															isFavorite={isOutputFavorite(run.id, origI)}
															isSelected={isImageSelected(group.groupId, key)}
															showMetadata={true}
															showFavorite={true}
															showSelection={true}
															showSeed={true}
															showDownload={!showAnyMediaPlaceholder}
															showSendToApp={!showAnyMediaPlaceholder}
															onMetadataClick={() => { metadataPanelRunId = run.id; metadataPanelMode = 'output'; }}
															onToggleFavorite={() => toggleOutputFavorite(run.id, origI, run)}
															onToggleSelection={() => toggleImageSelection(group.groupId, key)}
															onDownload={() => thumbDownloadImage(item as { filename: string; subfolder?: string; type?: string }, run.id)}
															onSendToApp={() => { if (run?.id != null) { sendToAppRunId = run.id; sendToAppOutputIndex = origI; } }}
														>
															{#if showDeletedPlaceholder}
																<div class="output-thumb-deleted-placeholder" aria-hidden="true">
																	<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
																		<path d="M3 6h18"/>
																		<path d="M8 6V4h8v2"/>
																		<path d="M8 6l1 14h6l1-14"/>
																	</svg>
																	<span>Deleted</span>
																</div>
															{:else if showNotFoundPlaceholder}
																<div class="output-thumb-not-found-placeholder">
																	<span class="output-thumb-not-found-label" aria-hidden="true">Not found</span>
																	<span class="output-thumb-not-found-filename" title={(item as { filename?: string }).filename ?? ''}>{truncateOutputFilename((item as { filename?: string }).filename ?? '')}</span>
																	<button
																		type="button"
																		class="output-thumb-remove-from-run-btn"
																		disabled={isDeleting}
																		title="Remove this missing file from the run record"
																		aria-label="Remove missing output from run"
																		onkeydown={(e) => e.stopPropagation()}
																		onpointerdown={(e) => e.stopPropagation()}
																		onmousedown={(e) => e.stopPropagation()}
																		onclick={(e) => {
																			e.stopPropagation();
																			removeOutputsFromRun(group.groupId, run.id, origI);
																		}}
																	>
																		Remove from run
																	</button>
																</div>
															{:else if isVideo}
																{#if playingVideoThumbKey === thumbKey}
																	<video
																		src={imageUrl(item, run.id)}
																		preload="metadata"
																		autoplay
																		muted
																		playsinline
																		loop
																		aria-hidden="true"
																		onloadedmetadata={(e) => onVideoThumbMetadataLoad(group.groupId, run.id, origI, thumbKey, e)}
																		onerror={() => {
																			if (playingVideoThumbKey !== thumbKey) return;
																			playingVideoThumbReady = true;
																			markThumbLoaded(group.groupId, run.id, origI);
																			markThumbLoadFailed(thumbKey);
																		}}
																	></video>
																{:else}
																	<img
																		src={thumbSrc(thumbKey, videoThumbnailPreviewUrl(item, run.id))}
																		alt=""
																		loading="lazy"
																		onload={() => {
																			markThumbLoaded(group.groupId, run.id, origI);
																			preloadVideoResolutionOnce(run.id, origI, imageUrl(item, run.id));
																		}}
																		onerror={() => { markThumbLoaded(group.groupId, run.id, origI); markThumbLoadFailed(thumbKey); }}
																	/>
																{/if}
																<span class="output-thumb-play" aria-hidden="true" title="Play video">
																	<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
																</span>
															{:else if isAudio}
																<div class="output-thumb-audio-preview">
																	<div class="output-thumb-audio-center" aria-hidden="true">
																		<div class="output-thumb-audio-visual">
																			<svg class="output-thumb-audio-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
																				<path d="M12 3v9.28c-.47-.17-.97-.28-1.5-.28C8.01 12 6 14.01 6 16.5S8.01 21 10.5 21c2.31 0 4.2-1.75 4.45-4H15V6h4V3h-7z"/>
																			</svg>
																			<span class="output-thumb-audio-label">AUDIO</span>
																			<button
																				type="button"
																				class="output-thumb-audio-play-btn"
																				title="Play audio"
																				aria-label="Play audio"
																			>
																				<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
																			</button>
																		</div>
																	</div>
																	<div class="output-thumb-audio-controls-wrap">
																		<audio
																			src={thumbSrc(thumbKey, imageUrl(item, run.id))}
																			preload="metadata"
																			controls
																			playsinline
																			onloadeddata={() => markThumbLoaded(group.groupId, run.id, origI)}
																			onloadedmetadata={() => markThumbLoaded(group.groupId, run.id, origI)}
																			onerror={() => { markThumbLoaded(group.groupId, run.id, origI); markThumbLoadFailed(thumbKey); }}
																			onplay={(e) => {
																				const el = e.currentTarget as HTMLAudioElement;
																				document.querySelectorAll('audio').forEach((a) => { if (a !== el) a.pause(); });
																				playingAudioThumbKey = thumbKey;
																			}}
																			onpause={() => {
																				playingAudioThumbKey = null;
																			}}
																		></audio>
																	</div>
																</div>
															{:else}
																<img
																	src={thumbSrc(thumbKey, imageUrl(item, run.id))}
																	alt=""
																	loading="lazy"
																	onload={(e) => onImageThumbLoad(group.groupId, run.id, origI, e)}
																	onerror={() => { markThumbLoaded(group.groupId, run.id, origI); markThumbLoadFailed(thumbKey); }}
																/>
															{/if}
														</ThumbnailOverlay>
													</div>
												{/each}
											{/each}
										</div>
										{#if group.runs.every((r) => (r.images ?? []).filter((img: { remote_deleted?: boolean }) => !img.remote_deleted).length === 0)}
											<div class="run-group-no-images">No outputs</div>
										{/if}
									</div>
								{/if}
							{/if}
						</section>
					{/each}
					{/key}
					{#if loadedGroupCount < totalGroups && totalGroups > 0}
						<InfiniteScrollLoadMore
							loading={loadingMore}
							loadedCount={loadedGroupCount}
							totalCount={totalGroups}
							thumbScalePercent={thumbnailScale}
							buttonDisabled={loading}
							onLoadMore={loadMoreRuns}
							loadMoreLabel="Load more runs"
							statusTitle="Loading more runs"
							countNoun="run groups"
							statusAriaLabel="Loading more run groups for this project"
						>
							{#snippet sentinel()}
								<div
									class="load-more-sentinel"
									use:useLoadMoreSentinel={runsScrollEl}
									aria-hidden="true"
								></div>
							{/snippet}
						</InfiniteScrollLoadMore>
					{/if}
				</div>
			{/if}
			</div>
		</div>
	</div>

	{#if sendToAppRunId != null && sendToAppOutputIndex != null}
		<SendToAppDialog
			open={true}
			sendFromRun={sendToAppRunId}
			sendFromOutput={sendToAppOutputIndex}
			projectId={data.projectId}
			onClose={() => { sendToAppRunId = null; sendToAppOutputIndex = null; }}
		/>
	{/if}
	{#if moveDialogOpen && data.project}
		<MoveRunsDialog
			open={moveDialogOpen}
			sourceProjectId={data.projectId}
			sourceProjectName={data.project.name ?? ''}
			runIds={Array.from(selectedRunIds)}
			onClose={() => { moveDialogOpen = false; }}
			onMoved={() => {
				const moved = new Set(selectedRunIds);
				runs = runs.filter((r) => !moved.has(r.id));
				selectedRunIds = new Set();
				moveDialogOpen = false;
			}}
		/>
	{/if}
	{#if data.project && deleteProjectDialogOpen}
		<DeleteProjectDialog
			open={deleteProjectDialogOpen}
			projectId={data.project.id}
			projectName={data.project.name ?? ''}
			hasLocalData={data.project.has_local_data}
			hasRemoteData={data.project.has_remote_data}
			onClose={() => { deleteProjectDialogOpen = false; }}
			onSuccess={() => { goto('/projects'); invalidate('app:projects'); }}
		/>
	{/if}

	{#if metadataPanelRunId}
		<RunMetadataPanel
			runId={metadataPanelRunId}
			projectId={data.projectId}
			mode={metadataPanelMode}
			embedWorkflowuiMetadataOnDownload={data.embedWorkflowuiMetadataOnDownload ?? false}
			onClose={() => { metadataPanelRunId = null; }}
		/>
	{/if}

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
				class="confirm-delete-overlay"
				role="dialog"
				aria-modal="true"
				aria-labelledby="delete-run-fav-dialog-title"
				tabindex="-1"
				onclick={() => { deleteRunGroupPending = null; }}
				onkeydown={(e) => { if (e.key === 'Escape') deleteRunGroupPending = null; }}
			>
				<div class="confirm-delete-card delete-run-fav-card" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
					<p id="delete-run-fav-dialog-title" class="confirm-delete-title">Delete Run</p>
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
			{@const deleteRunMessage = mainMsg}
			<ConfirmDeleteDialog
				open={true}
				title="Delete Run with all of its generations"
				message={deleteRunMessage}
				confirmLabel="Delete Run"
				onConfirm={async (dontShowAgain) => {
					if (dontShowAgain) setSkipDeleteConfirmCookie('delete_run', true);
					await confirmDeleteRunGroup('all');
				}}
				onCancel={() => { deleteRunGroupPending = null; }}
			/>
		{/if}
	{/if}

	{#if deleteStorageRunGroupPending}
		{@const pending = deleteStorageRunGroupPending}
		{@const group = pending.group}
		{@const action = pending.action}
		{@const nonFavIds = group.runs.filter((r) => !runHasFavoritedOutput(r)).map((r) => r.id)}
		{@const hasNonFav = nonFavIds.length > 0}
		{@const title = action === 'delete_remote' ? 'Delete remote' : action === 'delete_local' ? 'Delete local' : 'Delete all'}
		{@const scopeLine = action === 'delete_remote'
			? 'Deletes files on the ComfyUI server where present.'
			: action === 'delete_local'
				? 'Deletes local files where present.'
				: 'Deletes files on both local storage and the ComfyUI server where present.'}
		{@const allLabel = action === 'delete_remote'
			? 'Delete remote (including favorites)'
			: action === 'delete_local'
				? 'Delete local (including favorites)'
				: 'Delete all (including favorites)'}
		<div
			class="confirm-delete-overlay"
			role="dialog"
			aria-modal="true"
			aria-labelledby="delete-storage-nonfav-dialog-title"
			tabindex="-1"
			onclick={() => { deleteStorageRunGroupPending = null; }}
			onkeydown={(e) => { if (e.key === 'Escape') deleteStorageRunGroupPending = null; }}
		>
			<div class="confirm-delete-card delete-run-fav-card" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
				<p id="delete-storage-nonfav-dialog-title" class="confirm-delete-title">{title}</p>
				<p class="confirm-delete-msg">This run group includes favorited runs. What do you want to do?</p>
				<p class="confirm-delete-msg">{scopeLine}</p>
				<div class="delete-run-fav-actions">
					<button
						type="button"
						class="confirm-delete-btn danger"
						disabled={!hasNonFav}
						title={!hasNonFav ? 'All runs in this group are favorited.' : undefined}
						onclick={async () => { await confirmDeleteStorageRunGroup('non_favorites'); }}
					>Delete non-favorites only</button>
					<button
						type="button"
						class="confirm-delete-btn danger"
						onclick={async () => { await confirmDeleteStorageRunGroup('all'); }}
					>{allLabel}</button>
					<button
						type="button"
						class="confirm-delete-btn secondary"
						onclick={() => { deleteStorageRunGroupPending = null; }}
					>Cancel</button>
				</div>
			</div>
		</div>
	{/if}

	{#if deleteConfirmPending}
		{@const p = deleteConfirmPending}
		<ConfirmDeleteDialog
			open={true}
			title={p.title}
			message={p.message}
			confirmLabel={p.confirmLabel}
			onConfirm={async (dontShowAgain) => {
				if (dontShowAgain) setSkipDeleteConfirmCookie(p.action, true);
				const fn = p.onConfirmed;
				deleteConfirmPending = null;
				await fn();
			}}
			onCancel={() => { deleteConfirmPending = null; }}
		/>
	{/if}

	<LightboxViewer
		open={lightboxOpen}
		items={lightboxImages}
		index={lightboxIndex}
		onIndexChange={(i) => { lightboxIndex = i; }}
		onClose={closeLightbox}
		onDownload={downloadLightboxItem}
		onMetadata={(item) => { closeLightbox(); metadataPanelRunId = item.runId!; metadataPanelMode = 'output'; }}
		onToggleFavorite={(item) => toggleOutputFavorite(item.runId!, item.outputIndex ?? 0, runForFavorite(item.runId!))}
		isFavorite={(item) => isOutputFavorite(item.runId!, item.outputIndex ?? 0)}
		onToggleSelection={lightboxGroupId ? (item) => toggleImageSelection(lightboxGroupId!, item.id) : undefined}
		isSelected={lightboxGroupId ? (item) => isImageSelected(lightboxGroupId!, item.id) : undefined}
		onSendToApp={(item) => { closeLightbox(); sendToAppRunId = item.runId!; sendToAppOutputIndex = item.outputIndex ?? 0; }}
		onDeleteLocal={requestDeleteLightboxLocal}
		onDeleteRemote={requestDeleteLightboxRemote}
		onDeleteBoth={requestDeleteLightboxBoth}
		showCloseLabel={false}
		ariaTitle="Media viewer"
	/>

	{#if lightboxFavoriteDeletePending}
		{@const fp = lightboxFavoriteDeletePending}
		<ConfirmDeleteDialog
			open={true}
			showDontAskAgain={false}
			title="Favorited generation"
			message="This will delete a favorited generation. Are you sure to delete the file?"
			confirmLabel="Continue"
			onConfirm={() => {
				const { item, kind } = fp;
				lightboxFavoriteDeletePending = null;
				// Defer so this click’s mouseup doesn’t hit the lightbox before the next dialog mounts.
				requestAnimationFrame(() => proceedLightboxDeletePrompt(item, kind));
			}}
			onCancel={() => {
				lightboxFavoriteDeletePending = null;
			}}
		/>
	{/if}

	{#if lightboxDeletePending}
		{@const p = lightboxDeletePending}
		<ConfirmDeleteDialog
			open={true}
			title="Delete file"
			message={p.message}
			confirmLabel={p.confirmLabel}
			onConfirm={async (dontShowAgain) => {
				if (dontShowAgain) setSkipDeleteConfirmCookie(p.action, true);
				const item = p.item;
				const action = p.action;
				try {
					if (action === 'delete_local') await deleteLightboxLocal(item);
					else if (action === 'delete_remote') await deleteLightboxRemote(item);
					else if (action === 'delete_all') await deleteLightboxBoth(item);
				} finally {
					// Close dialog only after delete finishes so the confirming click/mouseup
					// cannot fall through to the lightbox (which would treat it as backdrop → close).
					lightboxDeletePending = null;
				}
			}}
			onCancel={() => {
				lightboxDeletePending = null;
			}}
		/>
	{/if}
{/if}

<style>
	.fill-height {
		flex: 1;
		min-height: 0;
		padding: 1rem;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}
	.two-panel {
		display: flex;
		flex-direction: row;
		min-height: 0;
		flex: 1;
		overflow: hidden;
	}
	.left-panel {
		flex-shrink: 0;
		min-width: 220px;
		display: flex;
		flex-direction: column;
		gap: 0;
		min-height: 0;
		overflow: hidden;
		transition: width 0.2s ease;
		padding-right: 0.5rem;
	}
	.left-panel-toggle {
		flex-shrink: 0;
		display: flex;
		align-items: center;
		gap: 0.4rem;
		padding: 0.4rem 0.6rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.85rem;
		font-weight: 500;
		color: var(--text);
		transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
	}
	.left-panel-toggle:hover {
		background: var(--accent-soft);
		border-color: var(--accent);
		color: var(--accent);
	}
	.left-panel-toggle:focus-visible {
		outline: none;
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 40%, transparent);
	}
	.left-panel-toggle-chevron {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		opacity: 0.85;
	}
	.left-panel-toggle-chevron :global(svg) {
		display: block;
	}
	.left-panel-toggle-label {
		flex: 1;
		text-align: left;
		min-width: 0;
	}
	.left-panel-content {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		min-height: 0;
		overflow-y: auto;
		flex: 1;
		padding-top: 0.75rem;
	}
	.left-panel.collapsed .left-panel-content {
		display: none;
	}
	.left-panel.collapsed {
		width: 2.5rem !important;
		min-width: 2.5rem;
		padding-right: 0.25rem;
		align-items: center;
	}
	.left-panel.collapsed .left-panel-toggle {
		width: 2rem;
		height: 2rem;
		min-width: 2rem;
		min-height: 2rem;
		padding: 0;
		border-radius: 6px;
		justify-content: center;
		align-items: center;
		background: var(--surface);
		border: 1px solid var(--border);
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12);
	}
	.left-panel.collapsed .left-panel-toggle:hover {
		background: var(--accent-soft);
		border-color: var(--accent);
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.15);
	}
	.left-panel.collapsed .left-panel-toggle-chevron {
		opacity: 1;
	}
	.left-panel.collapsed .left-panel-toggle-chevron :global(svg) {
		width: 14px;
		height: 14px;
	}
	.left-panel-section {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.section-title {
		margin: 0 0 0.5rem 0;
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--text-muted);
		letter-spacing: 0.01em;
	}
	.section-title-with-icon {
		display: flex;
		align-items: center;
		gap: 0.4rem;
	}
	.section-title-icon {
		flex-shrink: 0;
		opacity: 0.85;
		color: var(--text-muted);
	}
	.panel-resizer {
		flex-shrink: 0;
		width: 6px;
		cursor: col-resize;
		background: var(--border);
		transition: background 0.15s;
	}
	.panel-resizer:hover,
	.panel-resizer.resizing {
		background: var(--accent);
	}
	.right-panel {
		position: relative;
		z-index: 1;
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		min-height: 0;
		overflow: hidden;
	}
	.runs-list-body {
		flex: 1;
		min-height: 0;
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}
	.project-meta-card {
		background: var(--card-bg);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 1rem;
	}
	.project-name-display {
		display: block;
		width: 100%;
		text-align: left;
		background: transparent;
		border: none;
		padding: 0.25rem 0;
		margin: 0 0 0.25rem 0;
		cursor: pointer;
		border-radius: 6px;
		transition: background 0.15s;
		box-shadow: none;
		appearance: none;
	}
	.project-name-display:hover {
		background: color-mix(in srgb, var(--accent) 12%, transparent);
	}
	.project-name-text {
		display: inline;
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--text);
		line-height: 1.3;
	}
	.project-name-edit-icon {
		display: inline-block;
		vertical-align: middle;
		margin-left: 0.35rem;
		opacity: 0.5;
		color: var(--text);
	}
	.project-name-edit {
		margin-bottom: 0.5rem;
	}
	.project-name-input {
		width: 100%;
		padding: 0.4rem 0.6rem;
		font-size: 1.25rem;
		font-weight: 600;
		line-height: 1.3;
		border-radius: 8px;
		border: 1px solid var(--accent);
		background: var(--input-bg);
		color: var(--text);
	}
	.project-name-input:focus {
		outline: none;
		box-shadow: 0 0 0 2px var(--accent-soft);
	}
	.description-label {
		display: block;
		margin-bottom: 0.5rem;
	}

	.project-tags-section {
		margin-top: 0.4rem;
		margin-bottom: 0.9rem;
	}

	.tags-input-wrap {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.tags-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.2rem;
	}

	.tags-placeholder {
		font-size: 0.8rem;
		color: var(--muted);
	}

	.tags-text-input {
		width: 100%;
		padding: 0.4rem 0.65rem;
		border-radius: 999px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
		font-size: 0.82rem;
	}

	.tags-text-input:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 1px var(--accent-soft);
	}
	.tags-input-hint {
		margin: 0.1rem 0 0 0.2rem;
		font-size: 0.76rem;
		color: var(--muted);
	}
	.project-tags-section .tag-chip {
		display: inline-flex;
		align-items: center;
		gap: 0.15rem;
		padding: 0.05rem 0.4rem;
		border-radius: 999px;
		font-size: 0.68rem;
		font-weight: 500;
		color: var(--muted);
		background: color-mix(in srgb, var(--accent) 10%, var(--surface));
		border: 1px solid color-mix(in srgb, var(--accent) 40%, var(--border));
		box-shadow:
			0 0 0 1px color-mix(in srgb, var(--accent) 30%, transparent),
			0 0 8px color-mix(in srgb, var(--accent) 30%, transparent);
		cursor: pointer;
	}
	.project-tags-section .tag-chip-label {
		max-width: 110px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.project-tags-section .tag-chip-remove {
		font-size: 0.7rem;
		line-height: 1;
	}
	.description-textarea {
		width: 100%;
		min-height: 6rem;
		resize: vertical;
		padding: 0.5rem 0.6rem;
		font-size: 0.9rem;
		line-height: 1.4;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--input-bg);
		color: var(--text);
		margin-top: 0.25rem;
	}
	.description-textarea:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent);
	}
	.save-hint {
		font-size: 0.75rem;
		color: var(--muted);
	}
	.header-color-section {
		margin-top: 1rem;
	}
	.header-color-section .filter-label {
		display: block;
		margin-bottom: 0.25rem;
	}
	.header-color-help {
		font-size: 0.8rem;
		color: var(--muted);
		margin: 0 0 0.35rem 0;
		line-height: 1.35;
	}
	.header-color-wrap {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.35rem;
	}
	.header-color-input {
		width: 2.5rem;
		height: 2.25rem;
		padding: 2px;
		border: 1px solid var(--border);
		border-radius: 6px;
		background: var(--surface);
		cursor: pointer;
	}
	.header-color-clear {
		padding: 0.35rem 0.6rem;
		font-size: 0.85rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 6px;
		color: var(--muted);
		cursor: pointer;
	}
	.header-color-clear:hover {
		color: var(--text);
		border-color: var(--accent);
	}
	.meta {
		margin: 0 0 0.75rem 0;
		font-size: 0.85rem;
		color: var(--text-muted);
	}
	.activity-link {
		background: none;
		border: none;
		padding: 0;
		color: var(--accent);
		text-decoration: none;
		cursor: pointer;
		font: inherit;
	}
	.activity-link:hover {
		text-decoration: underline;
	}
	.tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin-top: 0.5rem;
	}
	.tag {
		font-size: 0.75rem;
		padding: 0.2rem 0.5rem;
		background: var(--input-bg);
		border-radius: 4px;
		color: var(--text-muted);
	}
	.delete-archive-section {
		margin-top: 1rem;
	}
	.delete-archive-btn {
		padding: 0.5rem 0.75rem;
		font-size: 0.85rem;
		background: var(--surface);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--muted);
		cursor: pointer;
		transition: border-color 0.2s, color 0.2s, background 0.2s;
	}
	.delete-archive-btn:hover {
		color: var(--text);
		border-color: var(--accent);
		background: var(--accent-soft);
	}
	
	.left-panel-section.filters,
	.left-panel-section.apps-used,
	.left-panel-section.project-notes,
	.left-panel-section.storage-policy {
		background: var(--card-bg);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 1rem;
	}
	.left-panel-section.project-section {
		gap: 0;
	}
	.left-panel-section.project-section .project-meta-card {
		margin-top: 0;
	}
	.left-panel-section.project-section .project-meta-card .section-title {
		margin-top: 0;
	}
	.storage-policy {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}
	.storage-policy-header {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.left-panel-section .section-title,
	.project-notes .notes-header-title {
		margin: 0 0 0.5rem 0;
		font-size: 0.9rem;
		font-weight: 600;
		color: var(--text-muted);
		letter-spacing: 0.01em;
	}
	.storage-policy-header .section-title {
		margin-bottom: 0.25rem;
	}
	.storage-global {
		margin: 0;
		font-size: 0.75rem;
		color: var(--text-muted);
		line-height: 1.4;
	}
	.storage-global code {
		background: var(--input-bg);
		padding: 0.15rem 0.35rem;
		border-radius: 4px;
		font-size: 0.7rem;
		font-weight: 500;
	}
	.storage-segments {
		display: flex;
		background: var(--input-bg);
		border-radius: 10px;
		padding: 3px;
		border: 1px solid var(--border);
		gap: 2px;
	}
	.storage-segment {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.15rem;
		padding: 0.6rem 0.5rem;
		font-family: inherit;
		font-size: 0.8rem;
		font-weight: 500;
		color: var(--text-muted);
		background: transparent;
		border: none;
		border-radius: 8px;
		cursor: pointer;
		transition: color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
	}
	.storage-segment:hover:not(:disabled) {
		color: var(--text);
		background: color-mix(in srgb, var(--accent) 8%, transparent);
	}
	.storage-segment:focus-visible {
		outline: none;
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 40%, transparent);
	}
	.storage-segment.selected {
		color: var(--text);
		background: var(--card-bg);
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
		border: 1px solid var(--border);
	}
	.storage-segment.selected:hover:not(:disabled) {
		background: var(--card-bg);
	}
	.storage-segment:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.storage-segment-label {
		display: block;
		font-weight: 600;
		letter-spacing: 0.02em;
	}
	.storage-segment-sublabel {
		display: block;
		font-size: 0.65rem;
		font-weight: 400;
		opacity: 0.85;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}
	.storage-segment.selected .storage-segment-sublabel {
		opacity: 0.7;
	}
	.storage-error {
		margin: 0;
		font-size: 0.8rem;
		color: #e57373;
	}
	.storage-warning {
		margin: 0;
		font-size: 0.8rem;
		color: #f0c674;
	}
	.storage-note {
		margin: 0;
		font-size: 0.75rem;
		color: var(--muted);
	}
	.apps-used {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}
	.apps-used-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
	}
	.apps-used-item {
		opacity: 0;
		animation: app-tag-in 0.3s ease forwards;
	}
	@keyframes app-tag-in {
		from {
			opacity: 0;
			transform: translateY(4px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
	.apps-used-badge-btn {
		display: inline-flex;
		font-family: inherit;
		padding: 0;
		margin: 0;
		border: none;
		background: none;
		cursor: pointer;
		border-radius: 4px;
	}
	.apps-used-badge-btn:hover {
		opacity: 0.9;
	}
	.apps-used-badge-btn:focus-visible {
		outline: none;
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 40%, transparent);
	}
	.apps-used-removed-wrap {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		cursor: default;
	}
	.apps-used-deleted-icon {
		flex-shrink: 0;
		color: var(--muted);
		opacity: 0.9;
	}
	.filter-row {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		margin-bottom: 0.75rem;
	}
	.filter-row:last-of-type {
		margin-bottom: 0;
	}
	.filter-input-wrap {
		position: relative;
		display: flex;
		align-items: center;
	}
	.filter-input-wrap .filter-input-icon {
		position: absolute;
		left: 0.65rem;
		pointer-events: none;
		opacity: 0.6;
		color: var(--text-muted);
	}
	.filter-input-wrap .filter-input {
		padding-left: 2.25rem;
	}
	.filter-date-range {
		margin-bottom: 0;
	}
	.filter-date-range .filter-label {
		margin-bottom: 0.25rem;
	}
	.filter-date-row {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		align-items: stretch;
	}
	.filter-date-field {
		flex: none;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}
	.filter-date-field-label {
		font-size: 0.8rem;
		font-weight: 500;
		color: var(--text-muted);
	}
	.filter-date-field .filter-input {
		min-height: 2.25rem;
	}
	.filter-label {
		display: block;
		font-size: 0.85rem;
		font-weight: 500;
		color: var(--text);
	}
	.filter-select,
	.filter-input {
		width: 100%;
		min-height: 2.25rem;
		padding: 0.5rem 0.6rem;
		font-size: 0.95rem;
		line-height: 1.4;
		border-radius: 8px;
		border: 1px solid var(--border, rgba(255,255,255,0.12));
		background: var(--input-bg, var(--surface, #1c2333));
		color: var(--text);
		appearance: auto;
		cursor: pointer;
	}
	.filter-select option {
		background: var(--card-bg, var(--card, #161c2b));
		color: var(--text);
		padding: 0.35rem;
	}
	.filter-select:focus,
	.filter-input:focus {
		outline: none;
		border-color: var(--accent);
		box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 25%, transparent);
	}
	.filter-input {
		cursor: text;
	}
	.filter-date {
		cursor: pointer;
	}
	.filter-active-row {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-top: 0.75rem;
		padding-top: 0.75rem;
		border-top: 1px solid var(--border);
		flex-wrap: wrap;
	}
	.filter-active-badge {
		font-size: 0.75rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--accent);
		padding: 0.2rem 0.5rem;
		background: color-mix(in srgb, var(--accent) 18%, transparent);
		border-radius: 999px;
	}
	.filter-clear-btn {
		font-size: 0.8rem;
		padding: 0.25rem 0.5rem;
		background: transparent;
		color: var(--text-muted);
		border: 1px solid var(--border);
		border-radius: 6px;
		cursor: pointer;
	}
	.filter-clear-btn:hover {
		color: var(--text);
		border-color: var(--text-muted);
	}
	.project-notes {
		background: var(--card-bg);
		border: 1px solid var(--border);
		border-radius: 10px;
		padding: 1rem;
	}
	.project-notes.collapsed {
		padding: 0.5rem 1rem;
	}
	.notes-header-row {
		display: flex;
		align-items: center;
		gap: 0.35rem;
		cursor: pointer;
		padding: 0;
		margin: 0;
		background: none;
		border: none;
		width: 100%;
		text-align: left;
		color: inherit;
	}
	.notes-header-row:hover {
		opacity: 0.9;
	}
	.notes-header-row:focus-visible {
		outline: none;
	}
	.project-notes:not(.collapsed) .notes-header-row {
		margin-bottom: 0.5rem;
	}
	.notes-chevron {
		font-size: 0.75rem;
		color: var(--text-muted);
		flex-shrink: 0;
		line-height: 1;
	}
	.notes-header-title {
		margin: 0;
		font-size: 0.9rem;
		color: var(--text-muted);
		font-weight: 600;
	}
	.notes-content {
		display: flex;
		flex-direction: column;
		gap: 0;
	}
	.notes-hint {
		margin: 0 0 0.75rem 0;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.notes-add {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		margin-bottom: 0.75rem;
	}
	.notes-draft {
		width: 100%;
		min-height: 7rem;
		resize: vertical;
		padding: 0.5rem 0.6rem;
		font-size: 0.85rem;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--input-bg);
		color: var(--text);
	}
	.notes-add-btn {
		padding: 0.4rem 0.75rem;
		align-self: flex-start;
		background: var(--accent);
		color: var(--accent-fg, #fff);
		border: none;
		border-radius: 6px;
		font-size: 0.85rem;
		cursor: pointer;
	}
	.notes-add-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}
	.notes-search-wrap {
		position: relative;
		margin-bottom: 0.5rem;
	}
	.notes-search-icon {
		position: absolute;
		left: 0.5rem;
		top: 50%;
		transform: translateY(-50%);
		color: var(--muted);
		pointer-events: none;
	}
	.notes-search-input {
		width: 100%;
		padding: 0.4rem 0.6rem 0.4rem 1.75rem;
		font-size: 0.85rem;
		border-radius: 6px;
		border: 1px solid var(--border);
		background: var(--input-bg);
		color: var(--text);
	}
	.notes-search-input::placeholder {
		color: var(--muted);
	}
	.notes-search-input:focus {
		outline: none;
		border-color: var(--accent);
	}
	.notes-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-height: 360px;
		overflow-y: auto;
	}
	.note-item {
		padding: 0.5rem;
		background: var(--input-bg);
		border: 1px solid var(--border);
		border-radius: 6px;
		font-size: 0.85rem;
	}
	.note-content {
		margin: 0 0 0.35rem 0;
		white-space: pre-wrap;
		word-break: break-word;
	}
	.note-link {
		color: var(--accent);
		text-decoration: none;
		display: inline-flex;
		align-items: center;
		gap: 0.2rem;
		word-break: break-all;
	}
	.note-link:hover {
		text-decoration: underline;
	}
	.note-link-icon {
		flex-shrink: 0;
		opacity: 0.8;
	}
	.note-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.75rem;
		color: var(--muted);
	}
	.note-edit-input {
		width: 100%;
		min-height: 4rem;
		resize: vertical;
		padding: 0.4rem;
		font-size: 0.85rem;
		border-radius: 6px;
		border: 1px solid var(--border);
		background: var(--card-bg);
		color: var(--text);
		margin-bottom: 0.35rem;
	}
	.note-edit-actions {
		display: flex;
		gap: 0.35rem;
	}
	.note-btn {
		padding: 0.25rem 0.5rem;
		font-size: 0.75rem;
		border-radius: 4px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
		cursor: pointer;
	}
	.note-btn.save {
		background: var(--accent);
		color: var(--accent-fg, #fff);
		border-color: var(--accent);
	}
	.note-btn.small {
		padding: 0.15rem 0.35rem;
	}
	.note-btn.delete {
		color: #e57373;
		border-color: #e57373;
	}
	.notes-empty {
		margin: 0;
		font-size: 0.8rem;
		color: var(--muted);
	}
	.empty-project-state {
		text-align: center;
		padding: 2rem 1.5rem;
	}
	.empty-project-icon {
		color: var(--muted);
		opacity: 0.6;
		margin-bottom: 1rem;
	}
	.empty-project-state h2 {
		margin: 0 0 0.5rem 0;
		font-size: 1.2rem;
		color: var(--text);
	}
	.empty-project-desc {
		margin: 0 0 1.25rem 0;
		font-size: 0.9rem;
		color: var(--muted);
		max-width: 360px;
		margin-left: auto;
		margin-right: auto;
	}
	.empty-project-apps {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		justify-content: center;
	}
	.empty-app-link {
		display: inline-block;
		padding: 0.5rem 1rem;
		background: var(--card);
		border: 1px solid var(--border);
		border-radius: 8px;
		color: var(--accent);
		text-decoration: none;
		font-size: 0.9rem;
		transition: border-color 0.2s, background 0.2s;
	}
	.empty-app-link:hover {
		border-color: var(--accent);
		background: color-mix(in srgb, var(--accent) 12%, var(--card));
	}
	.runs-list-head-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.runs-list-head-actions-desktop {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.runs-list-head-actions-mobile {
		display: none;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.move-runs-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.move-runs-checkbox {
		width: 1rem;
		height: 1rem;
		cursor: pointer;
		accent-color: var(--accent);
	}
	.move-to-project-btn {
		padding: 0.4rem 0.75rem;
		font-size: 0.85rem;
		font-weight: 500;
		border-radius: 8px;
		border: 1px solid var(--border);
		background: var(--surface);
		color: var(--text);
		cursor: pointer;
		transition: border-color 0.2s, background 0.2s;
	}
	.move-to-project-btn:hover:not(:disabled) {
		border-color: var(--accent);
		background: var(--accent-soft, color-mix(in srgb, var(--accent) 12%, transparent));
	}
	.move-to-project-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.move-runs-group-checkbox-wrap {
		display: inline-flex;
		align-items: center;
		cursor: pointer;
		margin-right: 0.25rem;
		flex-shrink: 0;
	}
	.move-runs-group-checkbox-wrap .move-runs-checkbox {
		width: 0.95rem;
		height: 0.95rem;
	}
	.favorites-filter-option {
		display: inline-flex;
		align-items: center;
		gap: 0.5rem;
		cursor: pointer;
		user-select: none;
		font-size: 0.8rem;
		color: var(--text-muted, var(--muted));
	}
	.favorites-filter-label {
		white-space: nowrap;
		font-weight: 500;
	}
	.favorites-filter-toggle {
		display: inline-flex;
		align-items: center;
		cursor: pointer;
		background: none;
		border: none;
		padding: 0;
		margin: 0;
		color: inherit;
	}
	.favorites-filter-toggle:focus-visible {
		outline: 1px solid var(--accent);
		outline-offset: 2px;
		border-radius: 4px;
	}
	.favorites-filter-toggle-track {
		display: inline-flex;
		align-items: center;
		width: 32px;
		height: 18px;
		border-radius: 9px;
		background: var(--border);
		transition: background 0.2s;
		padding: 2px;
	}
	.favorites-filter-toggle:hover .favorites-filter-toggle-track {
		background: color-mix(in srgb, var(--text-muted) 25%, var(--border));
	}
	.favorites-filter-toggle.on .favorites-filter-toggle-track {
		background: color-mix(in srgb, var(--accent) 60%, var(--border));
	}
	.favorites-filter-toggle-thumb {
		width: 14px;
		height: 14px;
		border-radius: 50%;
		background: var(--surface);
		box-shadow: 0 1px 2px rgba(0,0,0,0.2);
		transition: transform 0.2s ease;
	}
	.favorites-filter-toggle.on .favorites-filter-toggle-thumb {
		transform: translateX(14px);
	}
	.badge-removed {
		font-size: 0.7rem;
		padding: 0.15rem 0.4rem;
		border-radius: 4px;
		background: var(--muted);
		color: var(--surface);
		opacity: 0.9;
	}
	.runs-list-head {
		position: sticky;
		top: 0;
		z-index: 10;
		isolation: isolate;
		flex-shrink: 0;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
		margin-bottom: 0.75rem;
		flex-wrap: wrap;
		background: var(--bg);
		pointer-events: auto;
		padding-bottom: 0.25rem;
		border-bottom: 1px solid var(--border);
	}
	.runs-list-head-left {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.runs-list-head h2 {
		margin: 0;
		font-size: 1.1rem;
	}
	.runs-count-heading {
		margin: 0;
		font-size: 1rem;
		font-weight: 400;
		color: var(--text);
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0.5rem;
	}
	.runs-count-heading-title {
		font-size: 1.25rem;
		font-weight: 700;
		letter-spacing: 0.02em;
		color: var(--text);
		text-transform: uppercase;
	}
	.runs-count-heading-counts {
		font-size: 0.95rem;
		font-weight: 500;
		color: var(--text-muted);
	}
	.runs-count-generations {
		margin-left: 0.15rem;
	}
	.runs-count-filtered {
		font-weight: 400;
		opacity: 0.9;
	}
	.collapse-all-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		flex-wrap: wrap;
	}
	.gallery-size-divider {
		width: 1px;
		height: 1.25rem;
		background: var(--border);
		margin: 0 0.15rem;
	}

	/* Mobile: collapse gallery controls (thumb size/fit, expand/collapse all) */
	@media (max-width: 639px) {
		.runs-list-head-actions-desktop {
			display: none;
		}
		.runs-list-head-actions-mobile {
			display: flex;
		}

		.thumbnails-controls-drawer {
			position: relative;
			z-index: 25;
		}
		.thumbnails-controls-drawer > summary {
			list-style: none;
			cursor: pointer;
			display: inline-flex;
			align-items: center;
			gap: 0.5rem;
			padding: 0.4rem 0.6rem;
			background: var(--surface);
			border: 1px solid var(--border);
			border-radius: 8px;
			color: var(--text);
			font-size: 0.85rem;
			font-weight: 600;
			user-select: none;
		}
		.thumbnails-controls-drawer > summary::-webkit-details-marker {
			display: none;
		}
		.thumb-drawer-summary-value {
			color: var(--muted);
			font-weight: 600;
			font-variant-numeric: tabular-nums;
		}
		.thumbnails-controls-inner {
			margin-top: 0.5rem;
			display: flex;
			flex-direction: column;
			gap: 0.75rem;
			background: var(--card);
			border: 1px solid var(--border);
			border-radius: 10px;
			padding: 0.75rem;
			box-shadow: 0 10px 26px rgba(0, 0, 0, 0.25);
			min-width: min(360px, 92vw);
		}
	}
	.gallery-thumb-size {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}
	.gallery-thumb-fit {
		display: flex;
		align-items: center;
		gap: 0.2rem;
	}
	.gallery-thumb-size label {
		font-size: 0.8rem;
		color: var(--muted);
	}
	.gallery-thumb-size input[type='range'] {
		width: min(280px, 48vw);
	}
	.thumb-size-value {
		min-width: 3.5rem;
		font-size: 0.8rem;
		color: var(--muted);
		text-align: right;
	}
	.thumb-fit-btn.active {
		background: color-mix(in srgb, var(--accent) 22%, var(--surface));
		border-color: var(--accent);
		color: var(--accent);
	}
	.collapse-all-btn {
		font-size: 0.8rem;
		padding: 0.35rem 0.6rem;
		background: var(--surface, #1c2333);
		color: var(--text);
		border: 1px solid var(--border);
		border-radius: 6px;
		cursor: pointer;
	}
	.collapse-all-btn:hover {
		background: color-mix(in srgb, var(--accent) 15%, var(--surface));
		border-color: var(--accent);
	}
	.run-count-filter {
		color: var(--accent);
		font-style: italic;
	}
	.run-filter-bar {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		padding: 0.35rem 0.5rem;
		background: var(--accent-soft, rgba(109, 93, 252, 0.12));
		border-radius: 6px;
		font-size: 0.75rem;
	}
	.run-filter-label {
		color: var(--muted);
	}
	.run-filter-clear {
		padding: 0.2rem 0.4rem;
		border: none;
		background: transparent;
		color: var(--accent);
		font-size: 0.75rem;
		cursor: pointer;
		border-radius: 4px;
	}
	.run-filter-clear:hover {
		background: rgba(255, 255, 255, 0.08);
	}
	.run-queue-strip {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.5rem 1rem;
		margin-bottom: 0.5rem;
		padding: 0.35rem 0.5rem;
		background: rgba(0, 0, 0, 0.2);
		border: 1px solid var(--border);
		border-radius: 6px;
		font-size: 0.75rem;
		color: var(--muted);
	}
	.run-queue-item {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
	}
	.run-queue-status {
		font-style: italic;
	}
	.runs-loading-wrap {
		flex: 1;
		display: flex;
		align-items: center;
		justify-content: center;
		min-height: 160px;
	}
	.runs-scroll {
		flex: 1;
		min-height: 0;
		overflow-y: auto;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		align-content: start;
		padding-right: 0.25rem;
	}
	.load-more-sentinel {
		height: 1px;
		min-height: 1px;
		margin: 0;
		padding: 0;
		visibility: hidden;
		pointer-events: none;
	}
	.run-section {
		background: var(--bg);
		border: 2px solid #1f1f1f;
		border-radius: 8px;
		padding: 0.75rem 1rem 1rem;
		margin-bottom: 0.5rem;
	}
	.thumb-sentinel {
		height: 1px;
		min-height: 1px;
		margin: 0;
		padding: 0;
		overflow: hidden;
		pointer-events: none;
	}
	.run-header {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		align-items: center;
		gap: 0.5rem 1rem;
		padding: 0.5rem 0.75rem 0.5rem 0.75rem;
		margin: 0 -0.25rem 0 0;
		background: color-mix(in srgb, var(--surface) 50%, transparent);
		border-bottom: 1px solid var(--border);
		border-left: 3px solid var(--accent);
		border-radius: 6px 6px 0 0;
		cursor: pointer;
		transition: background 0.15s ease;
	}
	.run-header:hover {
		background: color-mix(in srgb, var(--surface) 70%, transparent);
	}
	.run-title {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-weight: 500;
		min-width: 0;
		flex: 1 1 200px;
	}
	.run-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--accent);
		flex-shrink: 0;
	}
	.run-status.running {
		color: var(--muted, #888);
	}
	.run-status.queued {
		color: var(--muted, #888);
	}
	.run-status.error {
		color: #e57373;
	}
	.run-status.cancelled {
		color: var(--muted, #888);
	}
	.run-header-cancel-btn {
		flex-shrink: 0;
		margin-left: 0.25rem;
		padding: 0.2rem 0.5rem;
		font-size: 0.7rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.03em;
		color: var(--error, #e57373);
		background: color-mix(in srgb, var(--error, #e57373) 18%, transparent);
		border: 1px solid var(--error, #e57373);
		border-radius: 6px;
		cursor: pointer;
		transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
	}
	.run-header-cancel-btn:hover:not(:disabled) {
		background: color-mix(in srgb, var(--error, #e57373) 28%, transparent);
		border-color: #ef5350;
		color: #ff8a80;
	}
	.run-header-cancel-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.run-resolution {
		color: var(--text-muted, var(--muted));
	}
	.run-count-sep {
		margin: 0 0.25rem;
		color: var(--muted);
	}
	.progress {
		height: 6px;
		border-radius: 999px;
		background: color-mix(in srgb, var(--text) 14%, transparent);
		overflow: hidden;
		margin-bottom: 0.5rem;
	}
	.progress .bar {
		height: 100%;
		width: 40%;
		background: linear-gradient(90deg, transparent, var(--accent), transparent);
		animation: run-progress-slide 1.2s linear infinite;
	}
	@keyframes run-progress-slide {
		from { transform: translateX(-100%); }
		to { transform: translateX(250%); }
	}
	.run-count {
		font-size: 0.7rem;
		color: var(--muted);
		margin-left: 0.25rem;
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
	.run-action-btn:disabled {
		opacity: 0.4;
		cursor: not-allowed;
	}
	.run-action-btn.cancel-queued-btn {
		border-color: var(--error, #e57373);
		color: var(--error, #e57373);
		background: color-mix(in srgb, var(--error, #e57373) 18%, transparent);
	}
	.run-action-btn.cancel-queued-btn:hover:not(:disabled) {
		border-color: #ef5350;
		color: #ff8a80;
		background: color-mix(in srgb, var(--error, #e57373) 28%, transparent);
	}
	.icon {
		width: 16px;
		height: 16px;
	}
	.icon.spinner {
		animation: spin 0.9s linear infinite;
	}
	@keyframes spin {
		from { transform: rotate(0deg); }
		to { transform: rotate(360deg); }
	}
	.run-body {
		margin-top: 0;
		padding-left: 0.75rem;
		border-left: 3px solid var(--accent);
		border-top: 1px solid var(--border);
	}
	.error-placeholder {
		padding: 1.5rem;
		border: 1px solid var(--border);
		border-radius: 8px;
		color: #e57373;
		font-size: 0.9rem;
		text-align: center;
	}
	.comfyui-unreachable-warning {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		flex-wrap: wrap;
		padding: 0.75rem 1rem;
		margin-bottom: 0.5rem;
		border: 1px solid #e6a23c;
		border-radius: 8px;
		background: color-mix(in srgb, #e6a23c 12%, transparent);
		color: #b8860b;
		font-size: 0.9rem;
	}
	.comfyui-unreachable-warning span {
		flex: 1;
		min-width: 0;
	}
	.retry-comfyui-btn {
		flex-shrink: 0;
	}
	.output-section-body {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
		gap: 0.75rem;
		padding: 0.75rem;
		border-top: 1px solid var(--border);
	}
	.output-section-body {
		grid-template-columns: repeat(auto-fill, minmax(calc(260px * var(--thumb-size-scale, 1)), 1fr));
	}
	@media (max-width: 639px) {
		.output-section-body {
			gap: 0.5rem;
			padding: 0.5rem;
		}
		.output-section-body {
			grid-template-columns: repeat(auto-fill, minmax(calc(120px * var(--thumb-size-scale, 1)), 1fr));
		}
		.run-section {
			min-width: 0;
		}
		.run-header {
			min-width: 0;
			width: 100%;
		}
		.run-title {
			flex-wrap: wrap;
			min-width: 0;
			overflow-wrap: break-word;
		}
		.run-count,
		.run-resolution {
			overflow-wrap: break-word;
		}
	}
	.output-thumb {
		position: relative;
		aspect-ratio: 1;
		border-radius: 8px;
		overflow: hidden;
		cursor: pointer;
		background: #111;
		box-shadow: 0 0 0 1px #222;
		display: block;
		transition: box-shadow 0.15s;
	}
	.output-thumb.output-thumb-local-storage {
		box-shadow: 0 0 0 2px #d4af37;
	}
	.output-thumb img,
	.output-thumb video {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
	}
	.output-section-body.thumb-fit-contain .output-thumb img,
	.output-section-body.thumb-fit-contain .output-thumb video {
		object-fit: contain;
		background: #0b0b0b;
	}
	.thumb-loading {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		background: #111;
		z-index: 1;
		transition: opacity 0.15s ease;
	}
	.thumb-loading.hide {
		opacity: 0;
		pointer-events: none;
	}
	.thumb-media.thumb-loaded .thumb-loading {
		display: none;
	}
	.thumb-loading-spinner {
		width: 22px;
		height: 22px;
		border: 2px solid var(--border);
		border-top-color: var(--accent);
		border-radius: 50%;
		animation: thumb-spin 0.7s linear infinite;
	}
	@keyframes thumb-spin {
		to { transform: rotate(360deg); }
	}
	.output-thumb-deleted .thumb-loading,
	.output-thumb-not-found .thumb-loading {
		display: none;
	}
	.output-thumb-not-found-placeholder {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.35rem;
		padding: 0.5rem;
		text-align: center;
		background: var(--surface);
		color: var(--muted);
		font-size: 0.7rem;
		z-index: 1;
	}
	.output-thumb-not-found-label {
		font-weight: 600;
		color: var(--text);
		font-size: 0.72rem;
	}
	.output-thumb-not-found-filename {
		word-break: break-all;
		line-height: 1.2;
		max-height: 3.6em;
		overflow: hidden;
	}
	.output-thumb-remove-from-run-btn {
		margin-top: 0.25rem;
		padding: 0.25rem 0.5rem;
		font-size: 0.68rem;
		border-radius: 6px;
		border: 1px solid var(--border);
		background: var(--bg);
		color: var(--text);
		cursor: pointer;
	}
	.output-thumb-remove-from-run-btn:hover:not(:disabled) {
		border-color: var(--accent);
		color: var(--accent);
	}
	.output-thumb-remove-from-run-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
	.output-thumb-deleted-placeholder {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		background: var(--surface);
		color: var(--muted);
		font-size: 0.75rem;
	}
	.output-thumb-deleted-placeholder svg {
		width: 28px;
		height: 28px;
		opacity: 0.7;
	}
	.output-thumb-deleting {
		box-shadow: 0 0 0 2px var(--accent), 0 0 0 4px rgba(0, 0, 0, 0.3);
	}
	.output-thumb-deleting-overlay {
		position: absolute;
		inset: 0;
		z-index: 2;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.4rem;
		background: rgba(0, 0, 0, 0.75);
		color: var(--text);
		animation: output-thumb-deleting-pulse 1.2s ease-in-out infinite;
	}
	.output-thumb-deleting-spinner {
		width: 24px;
		height: 24px;
		border: 2px solid rgba(255, 255, 255, 0.4);
		border-top-color: #fff;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}
	.output-thumb-deleting-label {
		font-size: 0.8rem;
		font-weight: 600;
		opacity: 1;
		text-shadow: 0 1px 2px rgba(0, 0, 0, 0.5);
	}
	@keyframes output-thumb-deleting-pulse {
		0%, 100% { opacity: 1; }
		50% { opacity: 0.9; }
	}
	.output-thumb-play {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(0, 0, 0, 0.2);
		pointer-events: none;
		transition: background 0.15s ease;
	}
	.output-thumb:hover .output-thumb-play {
		background: rgba(0, 0, 0, 0.4);
	}
	.output-thumb-play svg {
		width: 48px;
		height: 48px;
		color: #fff;
		filter: drop-shadow(0 1px 3px rgba(0,0,0,0.8));
	}
	.output-thumb-audio-preview {
		position: absolute;
		inset: 0;
		display: flex;
		flex-direction: column;
		justify-content: flex-end;
		align-items: center;
		padding: 0.5rem;
		background: rgba(0, 0, 0, 0.4);
	}
	.output-thumb-audio-center {
		position: absolute;
		inset: 0;
		z-index: 3;
		display: flex;
		align-items: center;
		justify-content: center;
		padding-bottom: 2.5rem;
		pointer-events: none;
	}
	.output-thumb-audio-visual {
		pointer-events: auto;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.35rem;
		color: rgba(255, 255, 255, 0.9);
	}
	.output-thumb-audio-icon {
		width: 40px;
		height: 40px;
	}
	.output-thumb-audio-label {
		font-size: 0.65rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}
	.output-thumb-audio-preview audio {
		width: 100%;
		min-width: 0;
		flex-shrink: 0;
	}
	.output-thumb-audio-play-btn {
		position: relative;
		z-index: 4;
		margin-top: 0.35rem;
		width: 44px;
		height: 44px;
		border-radius: 50%;
		border: none;
		background: rgba(255, 255, 255, 0.9);
		color: #111;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0;
		flex-shrink: 0;
		transition: background 0.15s ease, transform 0.1s ease;
	}
	.output-thumb-audio-play-btn:hover {
		background: #fff;
		transform: scale(1.05);
	}
	.output-thumb-audio-play-btn svg {
		width: 22px;
		height: 22px;
		margin-left: 2px;
	}
	.output-thumb-audio-controls-wrap {
		position: relative;
		z-index: 10;
		width: 100%;
	}
	.output-thumb:hover {
		box-shadow: 0 0 0 2px var(--accent);
	}
	.output-thumb.output-thumb-audio.audio-playing {
		box-shadow: 0 0 0 2px var(--accent), 0 0 12px color-mix(in srgb, var(--accent) 70%, transparent);
		animation: audio-pulse-glow 1.5s ease-in-out infinite;
	}
	@keyframes audio-pulse-glow {
		0%, 100% {
			box-shadow: 0 0 0 2px var(--accent), 0 0 8px color-mix(in srgb, var(--accent) 50%, transparent);
		}
		50% {
			box-shadow: 0 0 0 2px var(--accent), 0 0 20px color-mix(in srgb, var(--accent) 85%, transparent);
		}
	}
	.output-thumb.thumb-selected {
		box-shadow: 0 0 0 2px var(--accent);
		outline: 2px solid var(--accent);
		outline-offset: 2px;
	}
	.delete-error {
		margin: 0.5rem 0 0;
		padding: 0.5rem 0.75rem;
		border-radius: 6px;
		background: color-mix(in srgb, #e57373 18%, transparent);
		border: 1px solid #e57373;
		color: #ffcdd2;
		font-size: 0.85rem;
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}
	.delete-error-dismiss {
		background: none;
		border: none;
		color: inherit;
		cursor: pointer;
		font-size: 1.2rem;
		line-height: 1;
		padding: 0 0.25rem;
		opacity: 0.9;
	}
	.delete-error-dismiss:hover {
		opacity: 1;
	}
	.run-group-no-images {
		padding: 1.5rem;
		text-align: center;
		color: var(--muted);
		font-size: 0.9rem;
		border-top: 1px solid var(--border);
	}
	.error {
		color: #e57373;
	}
	.muted {
		color: var(--text-muted, var(--muted));
	}
	.back-link {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		font-size: 0.9rem;
		color: var(--accent);
		text-decoration: none;
		margin-bottom: 0.5rem;
		padding: 0.35rem 0;
		border-radius: 6px;
		transition: color 0.15s ease, opacity 0.15s ease;
	}
	.back-link:hover {
		opacity: 0.9;
		text-decoration: underline;
	}
	
	.lightbox-deleted-placeholder {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.75rem;
		min-width: 200px;
		min-height: 200px;
		background: var(--surface);
		color: var(--muted);
		font-size: 1rem;
	}
	.lightbox-deleted-placeholder svg {
		width: 48px;
		height: 48px;
		opacity: 0.7;
	}
	.lightbox-carousel-deleted {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: center;
		justify-content: center;
		background: var(--surface);
		color: var(--muted);
		font-size: 0.7rem;
	}

	@media (max-width: 639px) {
		.two-panel {
			flex-direction: column;
			min-height: 0;
		}
		.left-panel {
			width: 100% !important;
			max-width: none;
			min-width: 0;
			flex: 0 0 auto;
			max-height: 45vh;
		}
		.left-panel.collapsed {
			width: 100% !important;
			min-width: 0;
			max-height: none;
			flex: 0 0 auto;
		}
		.left-panel.collapsed .left-panel-toggle {
			width: 100%;
			min-width: 0;
			flex-direction: row;
			justify-content: center;
		}
		.left-panel-content {
			min-height: 0;
			overflow-y: auto;
			-webkit-overflow-scrolling: touch;
		}
		.panel-resizer {
			display: none;
		}
		.right-panel {
			flex: 1 1 0;
			min-height: 0;
			overflow: hidden;
		}
		.runs-scroll {
			flex: 1;
			min-height: 0;
			overflow-y: auto;
			-webkit-overflow-scrolling: touch;
		}
	}

	/* Delete run with favorites dialog (matches ConfirmDeleteDialog look) */
	.confirm-delete-overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
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
</style>
