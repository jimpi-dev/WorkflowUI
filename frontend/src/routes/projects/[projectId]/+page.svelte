<script lang="ts">
	import { getApiBase } from '$lib/config';
	import { goto, invalidate } from '$app/navigation';
	import { page } from '$app/stores';
	import { browser } from '$app/environment';
	import { onMount, onDestroy, tick, untrack } from 'svelte';
	import { getThumbSizeCookie, setThumbSizeCookie, getNotesCollapsedCookie, setNotesCollapsedCookie, getLeftPanelCollapsedCookie, setLeftPanelCollapsedCookie, getSkipDeleteConfirmCookie, setSkipDeleteConfirmCookie, type ThumbSize, type DeleteConfirmKey } from '$lib/cookie';
	import SendToAppDialog from '$lib/components/SendToAppDialog.svelte';
	import ThumbnailOverlay from '$lib/components/ThumbnailOverlay.svelte';
	import PageLoadingIndicator from '$lib/components/PageLoadingIndicator.svelte';
	import RunHeaderActions from '$lib/components/RunHeaderActions.svelte';
	import RunAppBadge from '$lib/components/RunAppBadge.svelte';
	import RunMetadataPanel from '$lib/components/RunMetadataPanel.svelte';
	import DeleteProjectDialog from '$lib/components/DeleteProjectDialog.svelte';
	import ConfirmDeleteDialog from '$lib/components/ConfirmDeleteDialog.svelte';
	import LightboxViewer, { type LightboxItem } from '$lib/components/LightboxViewer.svelte';
	import { appBooting } from '$lib/stores/appBooting';
	import { QUICK_RUNS_PROJECT_ID } from '$lib/constants';

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
		comfyui_unreachable_warning?: string | null;
	};
	let runs = $state<ApiRun[]>([]);
	let totalGroups = $state<number>(0);
	let statsTotalRuns = $state<number | null>(null);
	let statsTotalGenerations = $state<number | null>(null);
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


	let playingAudioThumbKey = $state<string | null>(null);

	let sendToAppRunId = $state<string | null>(null);
	let sendToAppOutputIndex = $state<number | null>(null);

	let deleteProjectDialogOpen = $state(false);

	let metadataPanelRunId = $state<string | null>(null);
	let metadataPanelMode = $state<'output' | 'run'>('output');

	let deleteRunGroupPending = $state<{ groupId: string; runs: ApiRun[] } | null>(null);

	type DeleteConfirmPending = {
		action: DeleteConfirmKey;
		title: string;
		message: string;
		confirmLabel: string;
		onConfirmed: () => void | Promise<void>;
	};
	let deleteConfirmPending = $state<DeleteConfirmPending | null>(null);

	let favorites = $state<Set<string>>(new Set());
	$effect(() => {
		const raw = data.project?.metadata?.favorites;
		favorites = Array.isArray(raw) ? new Set(raw) : new Set();
	});

	const filterActive = $derived(!!(filterAppId.trim() || filterFromDate.trim() || filterToDate.trim() || filterMetaQ.trim() || filterFavoritesOnly));

	const runGroups = $derived.by(() => {
		let list = runs;
		if (filterFavoritesOnly && favorites.size > 0) {
			list = list.filter((r) => favorites.has(r.id));
		} else if (filterFavoritesOnly) {
			list = [];
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
			const app_removed = !!(first.app_id && first.app_slug == null && first.app_title == null);
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

	const displayRunsCount = $derived(
		filterFavoritesOnly ? runGroups.length : (statsTotalGenerations ?? totalGroups)
	);

	const displayGenerationsCount = $derived(
		filterFavoritesOnly ? runGroups.reduce((n, g) => n + g.runs.length, 0) : (statsTotalRuns ?? 0)
	);

	const loadedGroupCount = $derived.by(() => {
		const seen = new Set<string>();
		for (const r of runs) seen.add(r.run_group_id ?? r.id);
		return seen.size;
	});

	const appsUsedSortedByRuns = $derived.by(() => {
		const apps = data.project?.apps_used ?? [];
		if (apps.length === 0) return [];
		const countByAppId = new Map<string, number>();
		for (const r of runs) {
			if (r.app_id) countByAppId.set(r.app_id, (countByAppId.get(r.app_id) ?? 0) + 1);
		}
		return [...apps].sort((a, b) => (countByAppId.get(b.id) ?? 0) - (countByAppId.get(a.id) ?? 0));
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
			return u ? { ...r, ...u, run_group_id: u.run_group_id ?? r.run_group_id } : r;
		});
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
				} else {
					updateRunStorage(run.id, { local_storage_status: 'failed' });
				}
			}
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
					} else {
						updateRunStorage(runId, { local_storage_status: 'failed' });
					}
				}
			}
		} finally {
			const next = new Set(savingGroupIds);
			next.delete(group.groupId);
			savingGroupIds = next;
		}
	}

	async function deleteRemoteRunGroup(group: (typeof runGroups)[0]) {
		const doDelete = async () => {
			deletingGroupIds = new Set([...deletingGroupIds, group.groupId]);
			try {
				for (const run of group.runs) {
					const res = await fetch(`${apiBase}/runs/${run.id}/delete-remote`, { method: 'POST' });
					const data = await res.json().catch(() => ({}));
					if (res.ok) {
						mergeUpdatedRuns(data.updated_runs);
					} else {
						updateRunStorage(run.id, { remote_status: 'exists' });
					}
				}
			} finally {
				const next = new Set(deletingGroupIds);
				next.delete(group.groupId);
				deletingGroupIds = next;
			}
		};
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

	async function deleteLocalRunGroup(group: (typeof runGroups)[0]) {
		const doDelete = async () => {
			deletingLocalGroupIds = new Set([...deletingLocalGroupIds, group.groupId]);
			try {
				for (const run of group.runs) {
					const res = await fetch(`${apiBase}/runs/${run.id}/delete-local`, { method: 'POST' });
					const data = await res.json().catch(() => ({}));
					if (res.ok) {
						updateRunStorage(run.id, {
							local_storage_status: data.local_storage_status,
							local_path: data.local_path
						});
					} else {
						updateRunStorage(run.id, { local_storage_status: 'failed' });
					}
				}
			} finally {
				const next = new Set(deletingLocalGroupIds);
				next.delete(group.groupId);
				deletingLocalGroupIds = next;
			}
		};
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

	async function deleteBothRunGroup(group: (typeof runGroups)[0]) {
		const doDelete = async () => {
			deletingBothGroupIds = new Set([...deletingBothGroupIds, group.groupId]);
			try {
				for (const run of group.runs) {
					const res = await fetch(`${apiBase}/runs/${run.id}/delete-both`, { method: 'POST' });
					const data = await res.json().catch(() => ({}));
					if (res.ok) {
						mergeUpdatedRuns(data.updated_runs);
					} else {
						updateRunStorage(run.id, { remote_status: 'exists' });
					}
				}
			} finally {
				const next = new Set(deletingBothGroupIds);
				next.delete(group.groupId);
				deletingBothGroupIds = next;
			}
		};
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

	async function deleteRunGroup(group: { groupId: string; runs: ApiRun[] }) {
		const runIds = group.runs.map((r) => r.id);
		const n = runIds.length;
		deleteError = null;
		for (const id of runIds) deletingRunIds = new Set([...deletingRunIds, id]);
		try {
			let anyDeleted = false;
			for (const runId of runIds) {
				const res = await fetch(`${apiBase}/runs/${runId}/delete-run`, { method: 'POST' });
				const data = await res.json().catch(() => ({}));
				if (res.ok && data.deleted_run_id) {
					runs = runs.filter((r) => r.id !== data.deleted_run_id);
					anyDeleted = true;
				} else {
					deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete run failed';
				}
				deletingRunIds = new Set([...deletingRunIds].filter((id) => id !== runId));
			}
			if (anyDeleted) totalGroups = Math.max(0, totalGroups - 1);
			await loadStats();
		} finally {
			deletingRunIds = new Set([...deletingRunIds].filter((id) => !runIds.includes(id)));
		}
	}

	function requestDeleteRunGroup(group: (typeof runGroups)[0]) {
		if (getSkipDeleteConfirmCookie('delete_run')) {
			deleteRunGroup(group).catch(() => {});
			return;
		}
		deleteRunGroupPending = { groupId: group.groupId, runs: group.runs };
	}

	async function confirmDeleteRunGroup() {
		const group = deleteRunGroupPending;
		if (!group) return;
		deleteRunGroupPending = null;
		await deleteRunGroup(group);
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
	function toggleFavorite(runId: string) {
		const next = new Set(favorites);
		if (next.has(runId)) next.delete(runId);
		else next.add(runId);
		favorites = next;
		saveFavoritesMetadata([...next]);
	}

	let notesInitialized = false;
	let notesCollapsed = $state(browser ? getNotesCollapsedCookie() : false);
	$effect(() => {
		if (data.project && !notesInitialized) {
			const hasNotes = (data.project.metadata?.notes?.length ?? 0) > 0;
			notesCollapsed = hasNotes ? false : (browser ? getNotesCollapsedCookie() : false);
			notesInitialized = true;
		}
	});
	function toggleNotesCollapsed() {
		notesCollapsed = !notesCollapsed;
		if (browser) setNotesCollapsedCookie(notesCollapsed);
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

	async function loadRuns(offset: number = 0) {
		const projectIdWeFetch = data.projectId;
		const isInitial = offset === 0;
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
			if (filterAppId.trim()) q.set('app_id', filterAppId.trim());
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
			const res = await fetch(url);
			if (data.projectId !== projectIdWeFetch) return;
			if (!res.ok) {
				if (isInitial) {
					runs = [];
					totalGroups = 0;
				}
				return;
			}
			const raw = await res.json();
			if (data.projectId !== projectIdWeFetch) return;
			const mapRun = (r: ApiRun) => ({ ...r, run_group_id: r.run_group_id ?? null });
			if (raw && typeof raw === 'object' && Array.isArray(raw.runs)) {
				const newRuns = raw.runs.map(mapRun);
				if (isInitial) {
					runs = newRuns;
					totalGroups = typeof raw.total === 'number' ? raw.total : newRuns.length;
				} else {
					runs = [...runs, ...newRuns];
				}
			} else if (isInitial) {
				runs = Array.isArray(raw) ? raw.map(mapRun) : [];
				totalGroups = runs.length;
			}
		} catch {
			if (data.projectId !== projectIdWeFetch) return;
			if (isInitial) {
				runs = [];
				totalGroups = 0;
			}
		} finally {
			if (data.projectId === projectIdWeFetch) {
				if (isInitial) loading = false;
				else loadingMore = false;
			}
		}
	}

	function loadMoreRuns() {
		if (loading || loadingMore || loadedGroupCount >= totalGroups) return;
		loadRuns(loadedGroupCount);
	}

	async function loadStats() {
		const projectIdWeFetch = data.projectId;
		const q = new URLSearchParams();
		if (filterAppId.trim()) q.set('app_id', filterAppId.trim());
		if (filterFromDate.trim()) {
			q.set('since', String(new Date(filterFromDate.trim()).setHours(0, 0, 0, 0)));
		}
		if (filterToDate.trim()) {
			q.set('until', String(new Date(filterToDate.trim()).setHours(23, 59, 59, 999)));
		}
		if (filterMetaQ.trim()) q.set('meta_q', filterMetaQ.trim());
		try {
			const res = await fetch(`${apiBase}/projects/${projectIdWeFetch}/runs/stats?${q.toString()}`);
			if (data.projectId !== projectIdWeFetch || !res.ok) return;
			const raw = await res.json();
			if (data.projectId !== projectIdWeFetch) return;
			if (typeof raw.total_runs === 'number') statsTotalRuns = raw.total_runs;
			if (typeof raw.total_generations === 'number') statsTotalGenerations = raw.total_generations;
		} catch {
			if (data.projectId === projectIdWeFetch) {
				statsTotalRuns = null;
				statsTotalGenerations = null;
			}
		}
	}

	$effect(() => {
		const projectId = data.projectId;
		filterAppId;
		filterFromDate;
		filterToDate;
		filterMetaQ;
		if (projectId && browser) {
			loadRuns();
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

	function openAppInProject(appSlug: string) {
		appBooting.set(true);
		goto(`/app/${appSlug}?project=${data.projectId}`);
	}

	function openAppWithParams(appSlug: string, runId: string) {
		appBooting.set(true);
		goto(`/app/${appSlug}?project=${data.projectId}&run_id=${encodeURIComponent(runId)}`);
	}

	const fromPath = $derived($page.url.searchParams.get('from') ?? '');
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

	let leftPanelCollapsed = $state(browser ? getLeftPanelCollapsedCookie() : false);
	function toggleLeftPanel() {
		leftPanelCollapsed = !leftPanelCollapsed;
		if (browser) setLeftPanelCollapsedCookie(leftPanelCollapsed);
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

	let thumbnailSize = $state<ThumbSize>(browser ? getThumbSizeCookie() : 'medium');
	function setThumbnailSize(size: ThumbSize) {
		thumbnailSize = size;
		if (browser) setThumbSizeCookie(size);
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
			} else {
				deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete failed';
			}
		} finally {
			const next = new Set(deletingLocalImageKeys);
			next.delete(key);
			deletingLocalImageKeys = next;
		}
	}

	async function deleteBothImage(runId: string, imageIndex: number) {
		deleteError = null;
		const key = `${runId}_${imageIndex}`;
		deletingBothImageKeys = new Set([...deletingBothImageKeys, key]);
		try {
			const res = await fetch(`${apiBase}/runs/${runId}/delete-both-image/${imageIndex}`, { method: 'POST' });
			const data = await res.json().catch(() => ({}));
			if (res.ok) {
				mergeUpdatedRuns(data.updated_runs);
			} else {
				deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete failed';
			}
		} finally {
			const next = new Set(deletingBothImageKeys);
			next.delete(key);
			deletingBothImageKeys = next;
		}
	}

	async function deleteRemoteSelectedOrGroup(group: (typeof runGroups)[0]) {
		const byRun = getSelectedByRun(group);
		if (byRun.size > 0) {
			const total = [...byRun.values()].reduce((s, arr) => s + arr.length, 0);
			if (total > 0) {
				const hasFav = [...byRun.keys()].some((runId) => favorites.has(runId));
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
				};
				if (getSkipDeleteConfirmCookie('delete_remote')) {
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
			await deleteRemoteRunGroup(group);
		}
	}

	async function deleteLocalSelectedOrGroup(group: (typeof runGroups)[0]) {
		const byRun = getSelectedByRun(group);
		if (byRun.size > 0) {
			const total = [...byRun.values()].reduce((s, arr) => s + arr.length, 0);
			if (total > 0) {
				const hasFav = [...byRun.keys()].some((runId) => favorites.has(runId));
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
							} else deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete failed';
						} finally {
							const next = new Set(deletingLocalImageKeys);
							for (const k of imageKeys) next.delete(k);
							deletingLocalImageKeys = next;
						}
					}
				};
				if (getSkipDeleteConfirmCookie('delete_local')) {
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
			await deleteLocalRunGroup(group);
		}
	}

	async function deleteBothSelectedOrGroup(group: (typeof runGroups)[0]) {
		const byRun = getSelectedByRun(group);
		if (byRun.size > 0) {
			const total = [...byRun.values()].reduce((s, arr) => s + arr.length, 0);
			if (total > 0) {
				const hasFav = [...byRun.keys()].some((runId) => favorites.has(runId));
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
							if (res.ok) {
								if (data.updated_runs?.length) mergeUpdatedRuns(data.updated_runs);
								updateRunStorage(runId, { local_storage_status: data.local_storage_status, remote_status: data.remote_status });
							} else deleteError = typeof data?.detail === 'string' ? data.detail : data?.error ?? 'Delete failed';
						} finally {
							const next = new Set(deletingBothImageKeys);
							for (const k of imageKeys) next.delete(k);
							deletingBothImageKeys = next;
						}
					}
				};
				if (getSkipDeleteConfirmCookie('delete_all')) {
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
			await deleteBothRunGroup(group);
		}
	}

	let lightboxOpen = $state(false);
	let lightboxImages = $state<LightboxItem[]>([]);
	let lightboxIndex = $state(0);
	let lightboxGroupId = $state<string | null>(null);
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
				list.push({
					id: imageKey(run.id, i),
					url: imageUrl(img, run.id),
					runId: run.id,
					filename: img.filename,
					mediaType: mt,
					remote_deleted,
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
				{#if data.project.id !== QUICK_RUNS_PROJECT_ID}
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
					<select class="filter-select" bind:value={filterAppId}>
						<option value="">All apps</option>
						{#each data.project.apps_used ?? [] as app (app.id)}
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
										label="App removed"
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
						<div class="gallery-thumb-size" role="group" aria-label="Thumbnail size">
							<button
								type="button"
								class="collapse-all-btn thumb-size-btn"
								class:active={thumbnailSize === 'small'}
								onclick={() => setThumbnailSize('small')}
								title="Small thumbnails"
								aria-label="Small thumbnails"
								aria-pressed={thumbnailSize === 'small'}
							>
								<svg class="thumb-size-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
									<rect x="2" y="2" width="8" height="8" rx="1"/>
									<rect x="14" y="2" width="8" height="8" rx="1"/>
									<rect x="2" y="14" width="8" height="8" rx="1"/>
									<rect x="14" y="14" width="8" height="8" rx="1"/>
								</svg>
							</button>
							<button
								type="button"
								class="collapse-all-btn thumb-size-btn"
								class:active={thumbnailSize === 'medium'}
								onclick={() => setThumbnailSize('medium')}
								title="Medium thumbnails"
								aria-label="Medium thumbnails"
								aria-pressed={thumbnailSize === 'medium'}
							>
								<svg class="thumb-size-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
									<rect x="2" y="4" width="9" height="9" rx="1"/>
									<rect x="13" y="4" width="9" height="9" rx="1"/>
									<rect x="2" y="15" width="9" height="7" rx="1"/>
									<rect x="13" y="15" width="9" height="7" rx="1"/>
								</svg>
							</button>
							<button
								type="button"
								class="collapse-all-btn thumb-size-btn"
								class:active={thumbnailSize === 'large'}
								onclick={() => setThumbnailSize('large')}
								title="Large thumbnails"
								aria-label="Large thumbnails"
								aria-pressed={thumbnailSize === 'large'}
							>
								<svg class="thumb-size-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
									<rect x="3" y="3" width="18" height="18" rx="2"/>
								</svg>
							</button>
						</div>
						</div>
						{/if}
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
			{:else if !runGroups.length}
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
						<button type="button" class="load-more-favorites-btn" onclick={() => loadMoreRuns()} disabled={loading || loadingMore}>
							{#if loadingMore}Loading…{:else}Load more runs{/if}
						</button>
						{#if loadingMore}
							<div class="load-more-loading" aria-live="polite">Loading more runs…</div>
						{/if}
					</div>
				{:else}
					<p class="muted">{filterActive ? 'No runs match the current filters.' : 'No runs in this project.'}</p>
				{/if}
			{:else}
				<div class="runs-scroll" bind:this={runsScrollEl}>
					{#each runGroups as group (group.groupId)}
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
									<span class="run-dot"></span>
									<RunAppBadge
										appHeaderColor={group.app_header_color ?? undefined}
										label={group.app_removed ? 'App removed' : (group.app_title ?? group.app_slug ?? 'App')}
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
											class:thumb-size-small={thumbnailSize === 'small'}
											class:thumb-size-medium={thumbnailSize === 'medium'}
											class:thumb-size-large={thumbnailSize === 'large'}
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
													{@const showDeletedPlaceholder = isRemoteDeleted && thumbLoadFailed.has(thumbKey)}
													{@const isLoaded = !!loadedThumbIds[thumbKey] || showDeletedPlaceholder}
													{@const isDeleting = deletingImageKeys.has(key) || deletingLocalImageKeys.has(key) || deletingBothImageKeys.has(key)}
													{@const hasLocalStorage = run.local_storage_status === 'saved' || run.local_storage_status === 'partial'}
													<div
														class="output-thumb thumb-media"
														class:thumb-loaded={isLoaded}
														class:output-thumb-video={isVideo}
														class:output-thumb-audio={isAudio}
														class:output-thumb-deleted={showDeletedPlaceholder}
														class:output-thumb-deleting={isDeleting}
														class:audio-playing={isAudio && playingAudioThumbKey === thumbKey}
														class:thumb-selected={isImageSelected(group.groupId, key)}
														class:output-thumb-local-storage={hasLocalStorage}
														role="button"
														tabindex="0"
														use:thumbLoadFallback={{ groupId: group.groupId, runId: run.id, index: origI, thumbKey }}
														onclick={(e) => {
														if (showDeletedPlaceholder || isDeleting) return;
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
														if (showDeletedPlaceholder || isDeleting) return;
														if ((e.target as HTMLElement).closest('.output-thumb-audio-play-btn, .output-thumb-audio-controls-wrap')) return;
														openLightboxFromImage(group, run, origI);
													}}
														onmouseenter={(e) => { if (isVideo) (e.currentTarget as HTMLElement).querySelector<HTMLVideoElement>('video')?.play().catch(() => {}); }}
														onmouseleave={(e) => { if (isVideo) (e.currentTarget as HTMLElement).querySelector<HTMLVideoElement>('video')?.pause(); }}
													>
														<span class="thumb-loading" class:hide={isLoaded} aria-hidden="true">
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
															seed={run.seed ?? undefined}
															executionTimeSec={run.execution_time ?? undefined}
															isFavorite={favorites.has(run.id)}
															isSelected={isImageSelected(group.groupId, key)}
															showMetadata={true}
															showFavorite={true}
															showSelection={true}
															showSeed={true}
															showDownload={!showDeletedPlaceholder}
															showSendToApp={!showDeletedPlaceholder}
															onMetadataClick={() => { metadataPanelRunId = run.id; metadataPanelMode = 'output'; }}
															onToggleFavorite={() => toggleFavorite(run.id)}
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
															{:else if isVideo}
																<video
																	src={thumbSrc(thumbKey, imageUrl(item, run.id))}
																	preload="metadata"
																	muted
																	playsinline
																	loop
																	aria-hidden="true"
																	onloadeddata={(e) => {
																		const v = e.currentTarget;
																		if (v) { v.currentTime = 0; v.pause(); }
																		markThumbLoaded(group.groupId, run.id, origI);
																	}}
																	onloadedmetadata={(e) => {
																		const v = e.currentTarget;
																		if (v) { v.currentTime = 0; v.pause(); }
																		markThumbLoaded(group.groupId, run.id, origI);
																	}}
																	onerror={() => { markThumbLoaded(group.groupId, run.id, origI); if (isRemoteDeleted) markThumbLoadFailed(thumbKey); }}
																></video>
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
																			onerror={() => { markThumbLoaded(group.groupId, run.id, origI); if (isRemoteDeleted) markThumbLoadFailed(thumbKey); }}
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
																	onload={() => markThumbLoaded(group.groupId, run.id, origI)}
																	onerror={() => { markThumbLoaded(group.groupId, run.id, origI); if (isRemoteDeleted) markThumbLoadFailed(thumbKey); }}
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
					{#if loadedGroupCount < totalGroups && totalGroups > 0}
						<div
							class="load-more-sentinel"
							use:useLoadMoreSentinel={runsScrollEl}
							aria-hidden="true"
						></div>
						{#if loadingMore}
							<div class="load-more-loading" aria-live="polite">Loading more runs…</div>
						{/if}
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
			onClose={() => { metadataPanelRunId = null; }}
		/>
	{/if}

	{#if deleteRunGroupPending}
		{@const group = deleteRunGroupPending}
		{@const runIds = group.runs.map((r) => r.id)}
		{@const n = runIds.length}
		{@const hasFav = runIds.some((id) => favorites.has(id))}
		{@const mainMsg = n > 1
			? `Delete ${n} generations permanently? This cannot be undone.`
			: 'Delete this prompt (and all its files) permanently? This cannot be undone.'}
		{@const deleteRunMessage = hasFav ? `This run includes favorited generations. They will be removed from favorites.\n\n${mainMsg}` : mainMsg}
		<ConfirmDeleteDialog
			open={true}
			title="Delete Run with all of its generations"
			message={deleteRunMessage}
			confirmLabel="Delete Run"
			onConfirm={async (dontShowAgain) => {
				if (dontShowAgain) setSkipDeleteConfirmCookie('delete_run', true);
				await confirmDeleteRunGroup();
			}}
			onCancel={() => { deleteRunGroupPending = null; }}
		/>
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
		onToggleFavorite={(item) => toggleFavorite(item.runId!)}
		isFavorite={(item) => favorites.has(item.runId!)}
		onToggleSelection={lightboxGroupId ? (item) => toggleImageSelection(lightboxGroupId!, item.id) : undefined}
		isSelected={lightboxGroupId ? (item) => isImageSelected(lightboxGroupId!, item.id) : undefined}
		onSendToApp={(item) => { closeLightbox(); sendToAppRunId = item.runId!; sendToAppOutputIndex = item.outputIndex ?? 0; }}
		showCloseLabel={false}
		ariaTitle="Media viewer"
	/>
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
	.gallery-thumb-size {
		display: flex;
		align-items: center;
		gap: 0.2rem;
	}
	.thumb-size-btn {
		padding: 0.35rem 0.45rem;
	}
	.thumb-size-btn .thumb-size-icon {
		width: 18px;
		height: 18px;
		display: block;
	}
	.thumb-size-btn.active {
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
	.load-more-loading {
		padding: 0.75rem;
		text-align: center;
		color: var(--muted);
		font-size: 0.875rem;
	}
	.load-more-favorites-btn {
		display: block;
		margin: 1rem auto;
		padding: 0.5rem 1rem;
		background: var(--accent);
		color: var(--accent-contrast, #fff);
		border: none;
		border-radius: 8px;
		font-size: 0.9rem;
		font-weight: 500;
		cursor: pointer;
	}
	.load-more-favorites-btn:hover:not(:disabled) {
		background: var(--accent-hover);
	}
	.load-more-favorites-btn:disabled {
		opacity: 0.7;
		cursor: not-allowed;
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
	.output-section-body.thumb-size-small {
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
	}
	.output-section-body.thumb-size-medium {
		grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
	}
	.output-section-body.thumb-size-large {
		grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
	}
	@media (max-width: 639px) {
		.output-section-body {
			gap: 0.5rem;
			padding: 0.5rem;
		}
		.output-section-body.thumb-size-small {
			grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
		}
		.output-section-body.thumb-size-medium {
			grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
		}
		.output-section-body.thumb-size-large {
			grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
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
	.output-thumb-deleted .thumb-loading {
		display: none;
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
</style>
