<script lang="ts">
    import { onMount, tick } from 'svelte';
    import AutoForm from '$lib/components/AutoForm.svelte';
    import Gallery from '$lib/components/Gallery.svelte';
    import RunParamGroup from '$lib/components/RunParamGroup.svelte';
    import RunMetadataPanel from '$lib/components/RunMetadataPanel.svelte';
    import SendToAppDialog from '$lib/components/SendToAppDialog.svelte';
    import PresetListDialog from '$lib/components/PresetListDialog.svelte';
    import type { AppPreset } from '$lib/types/presets';
    import { canEditLoras } from '$lib/stores/loraEdit';
    import { activeProject } from '$lib/stores/activeProject';
    import { projectRunsInvalidate } from '$lib/stores/projectRunsInvalidate';
    import { appBooting } from '$lib/stores/appBooting';
    import { presetHeaderStore, setPresetHeaderCreation, clearPresetListRequest } from '$lib/stores/presetHeader';
    import { page } from '$app/stores';
    import { goto } from '$app/navigation';
    import { appConfig, getApiBase } from '$lib/config';
    import { startQueue } from '$lib/queueApi';

    let { data } = $props();
    let currentProject = $state<{ id: string; name: string } | null>(null);
    $effect(() => {
        const unsub = activeProject.subscribe((v) => (currentProject = v));
        return unsub;
    });
    
    function getInitialFormValues(): Record<string, any> {
        const preload = data.sendFromPreload;
        if (preload) return { runs: 1, [preload.inputKey]: preload.filename };
        return { runs: 1 };
    }
    function getInitialSendFromContext(): { runId: string; outputIndex: number; inputKey: string; filename: string; subfolder?: string; type?: string } | null {
        const preload = data.sendFromPreload;
        if (!preload) return null;
        return {
            runId: preload.runId,
            outputIndex: preload.outputIndex,
            inputKey: preload.inputKey,
            filename: preload.filename,
            subfolder: preload.subfolder,
            type: preload.type
        };
    }
    let formValues = $state<Record<string, any>>({ runs: 1 });
    let randomizeSeedOnSubmit = $state(false);
    let extraLoraSlots = $state<Record<string, string[]>>({});
    let prefilledRunId = $state<string | null>(null);
    let prefilledFromImport = $state(false);
    let sendFromContext = $state<{ runId: string; outputIndex: number; inputKey: string; filename: string; subfolder?: string; type?: string } | null>(null);
    let prevWorkflowId = $state<string | undefined>(undefined);
    let prefilledSendFromKey = $state<string | null>(null);
    let triggerRun = $state<(() => void) | null>(null);
    let autoFormRef = $state<{ runWithRandomSeed?: (useRandom: boolean) => void } | null>(null);

    let presets = $state<AppPreset[]>([]);
    let presetCreationOn = $state(false);
    let presetKeysToSaveList = $state<string[]>([]);
    let presetListDialogOpen = $state(false);

    $effect(() => {
        if (!appConfig.presetsEnabled) return;
        const unsub = presetHeaderStore.subscribe((s) => {
            presetCreationOn = s.creationOn;
            if (s.openListDialogRequest) {
                presetListDialogOpen = true;
                clearPresetListRequest();
            }
        });
        return unsub;
    });

    $effect(() => {
        if (!appConfig.presetsEnabled) {
            presets = [];
            return;
        }
        const slug = data.workflowId;
        const appIdVal = data.appId;
        if (!appIdVal || !slug) {
            presets = [];
            return;
        }
        const apiBase = getApiBase() || '';
        fetch(`${apiBase}/app/${slug}/presets`)
            .then((r) => (r.ok ? r.json() : []))
            .then((list: AppPreset[]) => {
                presets = Array.isArray(list) ? list : [];
            })
            .catch(() => {
                presets = [];
            });
    });

    function getValidPresetKeys(): Set<string> {
        const wm = data.workflowModel;
        const keys = new Set<string>();
        if (wm?.inputs) for (const i of wm.inputs) keys.add(i.key);
        if (wm?.bindings) for (const b of wm.bindings) keys.add(b.key);
        return keys;
    }

    function handlePresetSelect(presetId: string) {
        const preset = presets.find((p) => p.id === presetId);
        if (!preset?.values || typeof preset.values !== 'object') return;
        const validKeys = getValidPresetKeys();
        for (const [k, v] of Object.entries(preset.values)) {
            if (validKeys.has(k)) formValues[k] = v;
        }
    }

    async function handleDeletePreset(presetId: string) {
        const slug = data.workflowId;
        if (!slug) return;
        const apiBase = getApiBase() || '';
        const res = await fetch(`${apiBase}/app/${slug}/presets/${presetId}`, { method: 'DELETE' });
        if (res.ok) presets = presets.filter((p) => p.id !== presetId);
    }

    function handleSavePreset(name: string, description: string) {
        const slug = data.workflowId;
        if (!slug || !presetKeysToSaveList.length) return;
        const keys = [...presetKeysToSaveList];
        const values: Record<string, unknown> = {};
        for (const k of keys) {
            if (k in formValues) values[k] = formValues[k];
        }
        const apiBase = getApiBase() || '';
        fetch(`${apiBase}/app/${slug}/presets`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, description: description || null, keys, values })
        })
            .then((r) => (r.ok ? r.json() : null))
            .then((created) => {
                if (created) {
                    presets = [...presets, created];
                    presetKeysToSaveList = [];
                    presetCreationOn = false;
                    setPresetHeaderCreation(false);
                }
            })
            .catch(() => {});
    }

    function handleCancelPresetCreation() {
        presetKeysToSaveList = [];
        presetCreationOn = false;
        setPresetHeaderCreation(false);
    }

    function handlePresetKeyToggle(key: string, included: boolean) {
        if (included) presetKeysToSaveList = [...presetKeysToSaveList, key];
        else presetKeysToSaveList = presetKeysToSaveList.filter((k) => k !== key);
    }

    const hasSeedInputs = $derived.by(() => {
        const wm = data.workflowModel;
        if (!wm?.inputs) return false;
        return wm.inputs.some((i: { role?: string; type?: string }) => i.role === 'seed' || i.type === 'seed');
    });

    const masterSeedHint = $derived.by(() => {
        const wm = data.workflowModel;
        if (!wm?.inputs) return null;
        const seedInputs = wm.inputs.filter((i: { role?: string }) => i.role === 'seed');
        if (seedInputs.length === 0) return null;
        const masterKey = wm.masterSeedInputKey;
        const master = (masterKey && seedInputs.find((i: { key: string }) => i.key === masterKey)) ?? seedInputs[0];
        return (master as { label?: string }).label ?? (master as { key: string }).key ?? null;
    });

    $effect(() => {
        const appParam = $page.params.id;
        if (appParam === prevWorkflowId) return;
        prevWorkflowId = appParam;
        formValues = { runs: 1 };
        extraLoraSlots = {};
        prefilledRunId = null;
        const preload = data.sendFromPreload;
        if (preload) {
            formValues = { ...formValues, [preload.inputKey]: preload.filename };
            sendFromContext = {
                runId: preload.runId,
                outputIndex: preload.outputIndex,
                inputKey: preload.inputKey,
                filename: preload.filename,
                subfolder: preload.subfolder,
                type: preload.type
            };
            prefilledSendFromKey = `${preload.runId}:${preload.outputIndex}`;
        } else {
            sendFromContext = null;
            prefilledSendFromKey = null;
        }
    });

    $effect(() => {
        const runId = $page.url.searchParams.get('run_id');
        const workflowId = data.workflowId;
        if (!runId || !workflowId || prefilledRunId === runId) return;
        const apiBase = getApiBase() || '';
        fetch(`${apiBase}/runs/${runId}`)
            .then((res) => (res.ok ? res.json() : null))
            .then(async (run: { input_snapshot?: { values?: Record<string, unknown> } } | null) => {
                if (!run?.input_snapshot?.values || typeof run.input_snapshot.values !== 'object') return;
                await tick();
                const runValues = run.input_snapshot.values as Record<string, unknown>;
                for (const [k, v] of Object.entries(runValues)) {
                    formValues[k] = v;
                }
                prefilledRunId = runId;
            })
            .catch(() => {});
    });

    $effect(() => {
        if (prefilledFromImport || typeof document === 'undefined') return;
        const workflowId = data.workflowId;
        if (!workflowId) return;
        try {
            const raw = sessionStorage.getItem('workflowui_import_prefill');
            if (!raw) return;
            const parsed = JSON.parse(raw) as { slug?: string; input_snapshot?: { values?: Record<string, unknown> } };
            if (parsed.slug !== workflowId || !parsed.input_snapshot?.values || typeof parsed.input_snapshot.values !== 'object') return;
            const runValues = parsed.input_snapshot.values as Record<string, unknown>;
            for (const [k, v] of Object.entries(runValues)) {
                formValues[k] = v;
            }
            sessionStorage.removeItem('workflowui_import_prefill');
            prefilledFromImport = true;
        } catch {
            sessionStorage.removeItem('workflowui_import_prefill');
        }
    });

    function filenameFromRunOutput(ent: unknown): string | undefined {
        if (typeof ent === 'string') return ent || undefined;
        if (Array.isArray(ent) && ent.length > 0 && typeof ent[0] === 'string') return ent[0];
        if (ent && typeof ent === 'object' && 'filename' in ent) {
            const f = (ent as { filename?: unknown }).filename;
            return typeof f === 'string' ? f : undefined;
        }
        return undefined;
    }
    $effect(() => {
        const sendFromRun = $page.url.searchParams.get('send_from_run');
        const sendFromOutput = $page.url.searchParams.get('send_from_output');
        const workflowId = data.workflowId;
        const inputs = data.workflowModel?.inputs;
        if (!sendFromRun || sendFromOutput == null || !workflowId || !Array.isArray(inputs)) return;
        const key = `${sendFromRun}:${sendFromOutput}`;
        if (prefilledSendFromKey === key) return;
        const outputIndex = parseInt(sendFromOutput, 10);
        if (Number.isNaN(outputIndex) || outputIndex < 0) return;
        const firstImageInput = inputs.find((i: { type?: string }) => i.type === 'image');
        if (!firstImageInput?.key) return;
        const apiBase = getApiBase() || '';
        fetch(`${apiBase}/runs/${sendFromRun}`)
            .then((res) => (res.ok ? res.json() : null))
            .then(async (run: { images?: unknown; media?: unknown } | null) => {
                let list = run?.media ?? run?.images;
                if (typeof list === 'string') {
                    try {
                        list = JSON.parse(list) as unknown[];
                    } catch {
                        return;
                    }
                }
                if (!Array.isArray(list) || outputIndex >= list.length) return;
                const ent = list[outputIndex];
                const filename = filenameFromRunOutput(ent);
                if (!filename || typeof filename !== 'string') return;
                const subfolder = ent && typeof ent === 'object' && 'subfolder' in ent ? String((ent as { subfolder?: unknown }).subfolder ?? '') : '';
                const type = ent && typeof ent === 'object' && ('type' in ent || 'kind' in ent)
                    ? String((ent as { type?: string; kind?: string }).type ?? (ent as { kind?: string }).kind ?? 'image')
                    : 'image';
                await tick();
                await new Promise((r) => setTimeout(r, 0));
                await tick();
    
                formValues[firstImageInput.key] = filename;
                sendFromContext = { runId: sendFromRun, outputIndex, inputKey: firstImageInput.key, filename, subfolder, type };
                prefilledSendFromKey = key;
                formValues = formValues;
            })
            .catch(() => {});
    });

    type GalleryImage = {
        id: string;
        url: string;
        filename?: string;
        promptId: string;
        backendRunId: string;
        seed?: number;
        outputIndex?: number;
        executionTimeSec?: number;
        mediaType?: 'image' | 'video' | 'audio';
        remote_deleted?: boolean;
    };

    type StorageState = {
        local_storage_status?: string;
        remote_status?: string;
        local_path?: string;
    };

    type RunGroup = {
        id: string;
        createdAt: number;
        images: GalleryImage[];
        seed?: number;
        inputs: Record<string, any>;
        status: 'queued' | 'running' | 'done' | 'error' | 'cancelled';
        queue_position?: number;
        workflowName?: string;
        appTitle?: string | null;
        runCount?: number;
        totalRuntimeSec?: number;
        error?: string;
        backendRunIds: string[];
        storageByBackend: Record<string, StorageState>;
    };

    type LayoutMode = 'split' | 'left-full' | 'right-full';
    let layoutMode = $state<LayoutMode>('split');
    let runFocusActive = $state(false);
    let layoutBeforeRunFocus = $state<LayoutMode | null>(null);
    let splitPosition = $state(0.45);
    let isDraggingDivider = $state(false);
    let layoutContainerEl = $state<HTMLDivElement | null>(null);
    let lightboxOpen = $state(false);

    let resultsCardEl = $state<HTMLDivElement | null>(null);
    let resultsPaneCardEl = $state<HTMLDivElement | null>(null);
    let resultsScrolledPastRunParam = $state(false);
    const RESULTS_SCROLL_THRESHOLD = 80;
    function onResultsCardScroll() {
        const el = isMobile ? resultsPaneCardEl : resultsCardEl;
        resultsScrolledPastRunParam = !!(el && el.scrollTop > RESULTS_SCROLL_THRESHOLD);
    }
    function scrollResultsToTop() {
        const el = isMobile ? resultsPaneCardEl : resultsCardEl;
        el?.scrollTo({ top: 0, behavior: 'smooth' });
    }

    const SPLIT_MIN = 0.2;
    const SPLIT_MAX = 0.8;
    const SNAP_LEFT_THRESHOLD = 0.15;
    const SNAP_RIGHT_THRESHOLD = 0.85;
    const DEFAULT_SPLIT = 0.45;

    let isMobile = $state(false);
    onMount(() => {
        if (typeof window === 'undefined') return;
        const mql = window.matchMedia('(max-width: 639px)');
        const update = () => { isMobile = mql.matches; };
        update();
        if ('addEventListener' in mql) mql.addEventListener('change', update);
        else mql.addListener(update);
        return () => {
            if ('removeEventListener' in mql) mql.removeEventListener('change', update);
            else mql.removeListener(update);
        };
    });

    function expandLeft() {
        layoutMode = 'left-full';
    }

    function expandRight() {
        layoutMode = 'right-full';
    }

    function restoreSplit() {
        layoutMode = 'split';
    }

    function handleRunFocusChange(focused: boolean) {
        if (focused) {
            if (!runFocusActive) layoutBeforeRunFocus = layoutMode;
            runFocusActive = true;
            layoutMode = 'right-full';
            return;
        }
        runFocusActive = false;
        if (layoutBeforeRunFocus) layoutMode = layoutBeforeRunFocus;
        layoutBeforeRunFocus = null;
    }

    function submitRunForm() {
        if (triggerRun) {
            triggerRun();
            return;
        }
        const form = typeof document !== 'undefined'
            ? (document.getElementById('workflow-run-form') as HTMLFormElement | null)
            : null;
        if (form) form.requestSubmit();
    }

    let mobileRunTapLock = $state(false);
    function triggerMobileRun(action: 'queue' | 'random') {
        if (mobileRunTapLock) return;
        if (data.appId && !currentProject?.id) {
            return;
        }
        mobileRunTapLock = true;
        if (action === 'queue') queueRun();
        else randomRun();
        setTimeout(() => { mobileRunTapLock = false; }, 300);
    }

    function queueRun() {
        if (autoFormRef?.runWithRandomSeed) {
            autoFormRef.runWithRandomSeed(false);
            return;
        }
        randomizeSeedOnSubmit = false;
        submitRunForm();
    }

    function randomRun() {
        if (autoFormRef?.runWithRandomSeed) {
            autoFormRef.runWithRandomSeed(true);
            return;
        }
        randomizeSeedOnSubmit = true;
        submitRunForm();
    }

    function setDefaultSplit() {
        layoutMode = 'split';
        splitPosition = DEFAULT_SPLIT;
    }

    let lastInitialMobileLayoutWorkflowId = $state<string | null>(null);
    $effect(() => {
        const wf = data.workflowId;
        if (typeof window === 'undefined' || !wf) return;
        if (lastInitialMobileLayoutWorkflowId === wf) return;
        if (window.matchMedia('(max-width: 639px)').matches) {
            layoutMode = 'left-full';
            lastInitialMobileLayoutWorkflowId = wf;
        }
    });

    function onDividerPointerDown(e: PointerEvent) {
        if (e.button !== 0 || layoutMode !== 'split') return;
        const target = e.currentTarget as HTMLElement;
        target.setPointerCapture(e.pointerId);
        isDraggingDivider = true;
    }

    function onDividerPointerMove(e: PointerEvent) {
        if (!isDraggingDivider || !layoutContainerEl) return;
        const rect = layoutContainerEl.getBoundingClientRect();
        const raw = (e.clientX - rect.left) / rect.width;
        if (raw <= SNAP_LEFT_THRESHOLD) {
            layoutMode = 'right-full';
            isDraggingDivider = false;
            return;
        }
        if (raw >= SNAP_RIGHT_THRESHOLD) {
            layoutMode = 'left-full';
            isDraggingDivider = false;
            return;
        }
        splitPosition = Math.max(SPLIT_MIN, Math.min(SPLIT_MAX, raw));
    }

    function onDividerPointerUp(e: PointerEvent) {
        const target = e.currentTarget as HTMLElement;
        if (target.hasPointerCapture(e.pointerId)) target.releasePointerCapture(e.pointerId);
        isDraggingDivider = false;
    }

    let runs = $state<RunGroup[]>([]);
    const hasActiveGeneratingRuns = $derived(
        runs.some((run) => run.status === 'queued' || run.status === 'running')
    );
    const hideRunParamGroup = $derived(hasActiveGeneratingRuns && runFocusActive);
    let runningPromptsCompleted = $state<Record<string, number>>({});
    let savingRunIds = $state<Set<string>>(new Set());
    let deletingRunIds = $state<Set<string>>(new Set());
    let deletingLocalRunIds = $state<Set<string>>(new Set());
    let deletingBothRunIds = $state<Set<string>>(new Set());
    let cancellingRunIds = $state<Set<string>>(new Set());
    let savingImageKeys = $state<Set<string>>(new Set());
    let deletingImageKeys = $state<Set<string>>(new Set());
    let deletingLocalImageKeys = $state<Set<string>>(new Set());
    let deletingBothImageKeys = $state<Set<string>>(new Set());
    let storageMode = $state<string>('inherit');
    let storageNote = $state<string | null>(null);

    let sendToAppRunId = $state<string | null>(null);
    let sendToAppOutputIndex = $state<number | null>(null);

    let metadataPanelRunId = $state<string | null>(null);

    let downloadingWorkflowInPage = $state(false);
    async function downloadAppWorkflowInPage() {
        const slug = data.workflowId;
        if (!slug || !data.appId || downloadingWorkflowInPage) return;
        const apiBase = getApiBase().replace(/\/$/, '');
        const url = `${apiBase}/app/${encodeURIComponent(slug)}/workflow/download`;
        downloadingWorkflowInPage = true;
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
            downloadingWorkflowInPage = false;
        }
    }
    
    function startRun(seed: number | undefined, inputs: Record<string, any>): string {
        const runId = safeUUID();

        const workflowName = data.workflows?.find((w: { id: string }) => w.id === data.workflowId)?.label ?? data.workflowId ?? 'Workflow';
        const runCount = inputs?.runs ?? 1;
        const appTitle = data.appConfig?.title ?? null;
        runs = [
            {
                id: runId,
                createdAt: Date.now(),
                images: [],
                seed,
                inputs,
                status: 'queued',
                workflowName,
                appTitle,
                runCount,
                backendRunIds: [],
                storageByBackend: {}
            },
            ...runs
        ];

        return runId;
    }

    function safeUUID(): string {
        try {
            if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
                return crypto.randomUUID();
            }
            if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
                const bytes = new Uint8Array(16);
                crypto.getRandomValues(bytes);
                bytes[6] = (bytes[6] & 0x0f) | 0x40;
                bytes[8] = (bytes[8] & 0x3f) | 0x80;
                const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0'));
                return `${hex[0]}${hex[1]}${hex[2]}${hex[3]}-${hex[4]}${hex[5]}-${hex[6]}${hex[7]}-${hex[8]}${hex[9]}-${hex[10]}${hex[11]}${hex[12]}${hex[13]}${hex[14]}${hex[15]}`;
            }
        } catch {}
        return `run-${Date.now()}-${Math.floor(Math.random() * 1e9)}`;
    }
    
    function onRunQueued(runId: string, queuePosition: number, backendRunId: string) {
        runs = runs.map(r =>
            r.id === runId
                ? {
                    ...r,
                    queue_position: r.queue_position === undefined
                        ? queuePosition
                        : Math.min(r.queue_position, queuePosition),
                    backendRunIds: r.backendRunIds.includes(backendRunId)
                        ? r.backendRunIds
                        : [...r.backendRunIds, backendRunId],
                    storageByBackend: r.storageByBackend[backendRunId]
                        ? r.storageByBackend
                        : { ...r.storageByBackend, [backendRunId]: {} }
                }
                : r
        );
        if (queuePosition === 1) {
            startQueue().catch(() => {});
        }
    }

    function onRunRunning(runId: string) {
        runs = runs.map(r =>
            r.id === runId ? { ...r, status: 'running' as const } : r
        );
    }
    
    function markRunDone(runId: string) {
        runs = runs.map(r => {
            if (r.id !== runId) return r;
            const totalRuntimeSec = Math.round((Date.now() - r.createdAt) / 1000);
            return { ...r, status: 'done' as const, totalRuntimeSec };
        });
        projectRunsInvalidate.invalidate(currentProject?.id ?? null);
    }
    
    function addImagesToRun(runId: string, newImages: GalleryImage[], backendRunId: string, storage?: StorageState) {
        runningPromptsCompleted = {
            ...runningPromptsCompleted,
            [runId]: (runningPromptsCompleted[runId] ?? 0) + 1
        };
        runs = runs.map(run =>
            run.id === runId
                ? {
                    ...run,
                    images: [...newImages, ...run.images],
                    storageByBackend: {
                        ...run.storageByBackend,
                        [backendRunId]: {
                            ...run.storageByBackend[backendRunId],
                            ...(storage ?? {})
                        }
                    }
                }
                : run
        );
    }

    function onRunError(runId: string, message: string) {
        runs = runs.map(r =>
            r.id === runId ? { ...r, status: 'error' as const, error: message } : r
        );
    }

    async function cancelRunGroup(runId: string, backendRunIds: string[]) {
        if (!backendRunIds.length) return;
        for (const id of backendRunIds) cancellingRunIds = new Set([...cancellingRunIds, id]);
        const apiBase = getApiBase() || '';
        try {
            for (const id of backendRunIds) {
                await fetch(`${apiBase}/runs/${id}/cancel`, { method: 'POST' });
            }
            runs = runs.map(r =>
                r.id === runId ? { ...r, status: 'cancelled' as const } : r
            );
            for (const id of backendRunIds) {
                await refetchRunImagesForBackendRun(runId, id);
            }
        } finally {
            for (const id of backendRunIds) {
                const next = new Set(cancellingRunIds);
                next.delete(id);
                cancellingRunIds = next;
            }
        }
    }

    let projectFavorites = $state<Set<string>>(new Set());
    let projectMetadata = $state<Record<string, unknown> | null>(null);
    let favoritesSaving = $state(false);

    $effect(() => {
        const projectId = currentProject?.id ?? null;
        if (!projectId) {
            storageMode = 'inherit';
            storageNote = null;
            projectFavorites = new Set();
            projectMetadata = null;
            return;
        }
        const apiBase = getApiBase() || '';
        fetch(`${apiBase}/projects/${projectId}`)
            .then((res) => (res.ok ? res.json() : null))
            .then((proj: { storage_mode?: string | null; metadata?: Record<string, unknown> & { favorites?: string[] } } | null) => {
                storageMode = proj?.storage_mode ?? 'inherit';
                storageNote = storageMode === 'remote'
                    ? 'Manual save is disabled while storage is set to remote.'
                    : null;
                const raw = proj?.metadata?.favorites;
                projectFavorites = Array.isArray(raw) ? new Set(raw) : new Set();
                projectMetadata = proj?.metadata ?? null;
            })
            .catch(() => {
                storageMode = 'inherit';
                storageNote = null;
                projectFavorites = new Set();
                projectMetadata = null;
            });
    });

    async function toggleFavorite(backendRunId: string) {
        const projectId = currentProject?.id;
        if (!projectId) return;
        const next = new Set(projectFavorites);
        if (next.has(backendRunId)) next.delete(backendRunId);
        else next.add(backendRunId);
        projectFavorites = next;
        favoritesSaving = true;
        const apiBase = getApiBase() || '';
        try {
            const meta = { ...(projectMetadata ?? {}), favorites: [...next] };
            const res = await fetch(`${apiBase}/projects/${projectId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ metadata: meta })
            });
            if (res.ok) {
                projectMetadata = meta;
            } else {
                projectFavorites = new Set(projectFavorites);
            }
        } catch {
            projectFavorites = new Set(projectFavorites);
        } finally {
            favoritesSaving = false;
        }
    }

    /** True if this backend run still has at least one output that can be viewed (remote or local). */
    function galleryBackendRunHasDisplayableMedia(run: (typeof runs)[0], backendRunId: string): boolean {
        const imgs = run.images.filter((i) => i.backendRunId === backendRunId);
        if (imgs.length === 0) return false;
        const st = run.storageByBackend?.[backendRunId];
        const hasLocal = st?.local_storage_status === 'saved' || st?.local_storage_status === 'partial';
        return imgs.some((img) => !img.remote_deleted || hasLocal);
    }

    /** Remove favorite IDs that no longer have any viewable media (e.g. deleted on Comfy with no local copy). */
    function pruneStaleOutputFavoritesForUiRun(run: (typeof runs)[0]) {
        const prev = new Set(projectFavorites);
        const next = new Set(projectFavorites);
        let changed = false;
        for (const bid of [...next]) {
            if (!run.backendRunIds.includes(bid)) continue;
            if (!galleryBackendRunHasDisplayableMedia(run, bid)) {
                next.delete(bid);
                changed = true;
            }
        }
        if (!changed) return;
        projectFavorites = next;
        const projectId = currentProject?.id;
        if (!projectId) return;
        favoritesSaving = true;
        const apiBase = getApiBase() || '';
        const meta = { ...(projectMetadata ?? {}), favorites: [...next] };
        fetch(`${apiBase}/projects/${projectId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ metadata: meta })
        })
            .then((res) => {
                if (res.ok) projectMetadata = meta;
                else projectFavorites = prev;
            })
            .catch(() => {
                projectFavorites = prev;
            })
            .finally(() => {
                favoritesSaving = false;
            });
    }

    function updateStorage(runId: string, backendRunId: string, patch: StorageState) {
        runs = runs.map(r =>
            r.id === runId
                ? {
                    ...r,
                    storageByBackend: {
                        ...r.storageByBackend,
                        [backendRunId]: {
                            ...r.storageByBackend[backendRunId],
                            ...patch
                        }
                    }
                }
                : r
        );
    }

    async function refetchRunImagesForBackendRun(runId: string, backendRunId: string) {
        const apiBase = getApiBase() || '';
        const res = await fetch(`${apiBase}/runs/${backendRunId}`);
        if (!res.ok) return;
        const run = await res.json().catch(() => null);
        const list = run?.images ?? run?.media;
        if (!run || !Array.isArray(list)) return;
        applyUpdatedRunToRuns(runId, backendRunId, run);
    }

    function applyUpdatedRunToRuns(
        runId: string,
        backendRunId: string,
        run: { images?: Array<{ filename: string; subfolder?: string; type?: string; kind?: string; remote_deleted?: boolean }>; media?: Array<{ filename: string; subfolder?: string; type?: string; kind?: string; remote_deleted?: boolean }>; prompt_id?: string; seed?: number; execution_time?: number; local_storage_status?: string; remote_status?: string; local_path?: string }
    ) {
        const list = run?.images ?? run?.media;
        if (!run || !Array.isArray(list)) return;
        const apiBase = getApiBase() || '';
        const newImages: GalleryImage[] = list.map(
            (img: { filename: string; subfolder?: string; type?: string; kind?: string; remote_deleted?: boolean }, index: number) => {
                const subfolder = img.subfolder ?? '';
                const type = img.type ?? img.kind ?? 'output';
                let url = `${apiBase}/image?filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(subfolder)}&type=${encodeURIComponent(type)}&run_id=${encodeURIComponent(backendRunId)}`;
                if (data.embedWorkflowuiMetadataOnDownload) url += '&embed_workflowui_metadata=1';
                const isVideo = type === 'video';
                const isAudio = type === 'audio';
                const mediaType = isVideo ? 'video' : isAudio ? 'audio' : 'image';
                return {
                    id: `${backendRunId}-${index}`,
                    url,
                    previewUrl: isVideo || isAudio ? undefined : `${url}&preview=webp`,
                    filename: img.filename,
                    promptId: run.prompt_id ?? backendRunId,
                    backendRunId,
                    seed: run.seed,
                    outputIndex: index,
                    executionTimeSec: run.execution_time,
                    mediaType: mediaType as 'image' | 'video' | 'audio',
                    remote_deleted: img.remote_deleted
                };
            }
        );
        runs = runs.map((r) => {
            if (r.id !== runId) return r;
            const otherImages = r.images.filter((img) => img.backendRunId !== backendRunId);
            return { ...r, images: [...otherImages, ...newImages] };
        });
        if (run.local_storage_status != null || run.remote_status != null) {
            updateStorage(runId, backendRunId, {
                local_storage_status: run.local_storage_status,
                remote_status: run.remote_status,
                local_path: run.local_path
            });
        }
    }

    async function saveRunGroup(runId: string, backendRunIds: string[]) {
        if (storageMode === 'remote') return;
        const apiBase = getApiBase() || '';
        for (const backendRunId of backendRunIds) {
            savingRunIds = new Set([...savingRunIds, backendRunId]);
			try {
				const res = await fetch(`${apiBase}/runs/${backendRunId}/save`, { method: 'POST' });
				const data = await res.json().catch(() => ({}));
				if (res.ok) {
					updateStorage(runId, backendRunId, {
						local_storage_status: data.local_storage_status,
						remote_status: data.remote_status,
						local_path: data.local_path
					});
					if (typeof window !== 'undefined') {
						window.dispatchEvent(new CustomEvent('workflowui-refresh-storage'));
					}
				}
            } catch {
                updateStorage(runId, backendRunId, { local_storage_status: 'failed' });
            } finally {
                const next = new Set(savingRunIds);
                next.delete(backendRunId);
                savingRunIds = next;
            }
        }
    }

    async function deleteRemoteRunGroup(runId: string, backendRunIds: string[]) {
        const apiBase = getApiBase() || '';
        for (const backendRunId of backendRunIds) {
            deletingRunIds = new Set([...deletingRunIds, backendRunId]);
            try {
                const res = await fetch(`${apiBase}/runs/${backendRunId}/delete-remote`, { method: 'POST' });
                const data = await res.json().catch(() => ({}));
                if (res.ok) {
                    await refetchRunImagesForBackendRun(runId, backendRunId);
                } else {
                    updateStorage(runId, backendRunId, { remote_status: 'exists' });
                }
            } catch {
                updateStorage(runId, backendRunId, { remote_status: 'exists' });
            } finally {
                const next = new Set(deletingRunIds);
                next.delete(backendRunId);
                deletingRunIds = next;
            }
        }
    }

    async function deleteLocalRunGroup(runId: string, backendRunIds: string[]) {
        const apiBase = getApiBase() || '';
        for (const backendRunId of backendRunIds) {
            deletingLocalRunIds = new Set([...deletingLocalRunIds, backendRunId]);
            try {
                const res = await fetch(`${apiBase}/runs/${backendRunId}/delete-local`, { method: 'POST' });
                const data = await res.json().catch(() => ({}));
                if (res.ok) {
                    updateStorage(runId, backendRunId, {
                        local_storage_status: data.local_storage_status,
                        local_path: data.local_path
                    });
                }
            } catch {
                updateStorage(runId, backendRunId, { local_storage_status: 'failed' });
            } finally {
                const next = new Set(deletingLocalRunIds);
                next.delete(backendRunId);
                deletingLocalRunIds = next;
            }
        }
    }

    let deleteRunPending = $state<{ runId: string; backendRunIds: string[] } | null>(null);

    async function saveProjectFavorites(nextFavorites: string[]) {
        const projectId = currentProject?.id;
        if (!projectId) return;
        favoritesSaving = true;
        try {
            const meta = { ...(projectMetadata ?? {}), favorites: nextFavorites };
            const res = await fetch(`${getApiBase() || ''}/projects/${projectId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ metadata: meta })
            });
            if (res.ok) {
                projectMetadata = meta;
                projectFavorites = new Set(nextFavorites);
            }
        } finally {
            favoritesSaving = false;
        }
    }

    async function deleteBothRunGroup(
        runId: string,
        backendRunIdsToDelete: string[],
        options?: { allBackendRunIdsForRun?: string[]; removeFromFavorites?: string[] }
    ) {
        const apiBase = getApiBase() || '';
        const run = runs.find((r) => r.id === runId);
        if (run?.status === 'queued' || run?.status === 'running') {
            for (const backendRunId of backendRunIdsToDelete) {
                await fetch(`${apiBase}/runs/${backendRunId}/cancel`, { method: 'POST' }).catch(() => {});
            }
        }
        let allSucceeded = true;
        const deletedIds = new Set<string>();
        for (const backendRunId of backendRunIdsToDelete) {
            deletingBothRunIds = new Set([...deletingBothRunIds, backendRunId]);
            try {
                const res = await fetch(`${apiBase}/runs/${backendRunId}/delete-both`, { method: 'POST' });
                const data = await res.json().catch(() => ({}));
                if (res.ok) {
                    deletedIds.add(backendRunId);
                    if (data.updated_runs?.length) {
                        for (const u of data.updated_runs) {
                            const r = runs.find((x) => x.backendRunIds?.includes(u.id));
                            if (r) applyUpdatedRunToRuns(r.id, u.id, u);
                        }
                    }
                } else {
                    allSucceeded = false;
                    updateStorage(runId, backendRunId, { remote_status: 'exists' });
                }
            } catch {
                allSucceeded = false;
                updateStorage(runId, backendRunId, { remote_status: 'exists' });
            } finally {
                const next = new Set(deletingBothRunIds);
                next.delete(backendRunId);
                deletingBothRunIds = next;
            }
        }
        const removeRunFromList = options?.allBackendRunIdsForRun == null
            || backendRunIdsToDelete.length === options.allBackendRunIdsForRun.length;
        if (allSucceeded && backendRunIdsToDelete.length > 0 && removeRunFromList) {
            runs = runs.filter((r) => r.id !== runId);
        }
        if (options?.removeFromFavorites?.length && deletedIds.size > 0) {
            const nextFav = [...projectFavorites].filter((id) => !deletedIds.has(id));
            if (nextFav.length !== projectFavorites.size) await saveProjectFavorites(nextFav);
        }
    }

    async function saveImage(runId: string, image: GalleryImage) {
        if (storageMode === 'remote') return;
        if (image.outputIndex == null) return;
        const apiBase = getApiBase() || '';
        const key = `${image.backendRunId}:${image.outputIndex}`;
        savingImageKeys = new Set([...savingImageKeys, key]);
        try {
            const res = await fetch(
                `${apiBase}/runs/${image.backendRunId}/save-image/${image.outputIndex}`,
                { method: 'POST' }
            );
            const data = await res.json().catch(() => ({}));
            if (res.ok) {
                updateStorage(runId, image.backendRunId, {
                    local_storage_status: data.local_storage_status,
                    remote_status: data.remote_status,
                    local_path: data.local_path
                });
            }
        } catch {
            updateStorage(runId, image.backendRunId, { local_storage_status: 'failed' });
        } finally {
            const next = new Set(savingImageKeys);
            next.delete(key);
            savingImageKeys = next;
        }
    }

    async function deleteRemoteImage(runId: string, image: GalleryImage) {
        if (image.outputIndex == null) return;
        const apiBase = getApiBase() || '';
        const key = `${image.backendRunId}:${image.outputIndex}`;
        deletingImageKeys = new Set([...deletingImageKeys, key]);
        try {
            const res = await fetch(
                `${apiBase}/runs/${image.backendRunId}/delete-remote-image/${image.outputIndex}`,
                { method: 'POST' }
            );
            const data = await res.json().catch(() => ({}));
            if (res.ok) {
                await refetchRunImagesForBackendRun(runId, image.backendRunId);
            } else {
                updateStorage(runId, image.backendRunId, { remote_status: 'exists' });
            }
        } catch {
            updateStorage(runId, image.backendRunId, { remote_status: 'exists' });
        } finally {
            const next = new Set(deletingImageKeys);
            next.delete(key);
            deletingImageKeys = next;
        }
    }

    async function deleteLocalImage(runId: string, image: GalleryImage) {
        if (image.outputIndex == null) return;
        const apiBase = getApiBase() || '';
        const key = `${image.backendRunId}:${image.outputIndex}`;
        deletingLocalImageKeys = new Set([...deletingLocalImageKeys, key]);
        try {
            const res = await fetch(
                `${apiBase}/runs/${image.backendRunId}/delete-local-image/${image.outputIndex}`,
                { method: 'POST' }
            );
            const data = await res.json().catch(() => ({}));
            if (res.ok) {
                if (data.updated_runs?.length) {
                    for (const u of data.updated_runs) {
                        const r = runs.find((x) => x.backendRunIds?.includes(u.id));
                        if (r) applyUpdatedRunToRuns(r.id, u.id, u);
                    }
                }
                updateStorage(runId, image.backendRunId, {
                    local_storage_status: data.local_storage_status,
                    local_path: data.local_path
                });
            }
        } finally {
            const next = new Set(deletingLocalImageKeys);
            next.delete(key);
            deletingLocalImageKeys = next;
        }
    }

    async function deleteBothImage(runId: string, image: GalleryImage) {
        if (image.outputIndex == null) return;
        const apiBase = getApiBase() || '';
        const key = `${image.backendRunId}:${image.outputIndex}`;
        deletingBothImageKeys = new Set([...deletingBothImageKeys, key]);
        try {
            const res = await fetch(
                `${apiBase}/runs/${image.backendRunId}/delete-both-image/${image.outputIndex}`,
                { method: 'POST' }
            );
            const data = await res.json().catch(() => ({}));
            if (res.ok) {
                await refetchRunImagesForBackendRun(runId, image.backendRunId);
            }
        } finally {
            const next = new Set(deletingBothImageKeys);
            next.delete(key);
            deletingBothImageKeys = next;
        }
    }

    function selectionIncludesFavorite(images: GalleryImage[]): boolean {
        return images.some((img) => projectFavorites.has(img.backendRunId));
    }

    async function deleteRemoteSelected(runId: string, images: GalleryImage[]) {
        if (selectionIncludesFavorite(images) && !window.confirm('Selection includes favorited run(s). Do you still want to delete?')) return;
        for (const img of images) {
            await deleteRemoteImage(runId, img);
        }
    }
    async function deleteLocalSelected(runId: string, images: GalleryImage[]) {
        if (selectionIncludesFavorite(images) && !window.confirm('Selection includes favorited run(s). Do you still want to delete?')) return;
        for (const img of images) {
            await deleteLocalImage(runId, img);
        }
    }
    async function deleteBothSelected(runId: string, images: GalleryImage[]) {
        if (selectionIncludesFavorite(images) && !window.confirm('Selection includes favorited run(s). Do you still want to delete?')) return;
        for (const img of images) {
            await deleteBothImage(runId, img);
        }
    }

    function onAddLora(nodeId: string, groupKey: string) {
        extraLoraSlots = {
            ...extraLoraSlots,
            [nodeId]: [...(extraLoraSlots[nodeId] ?? []), groupKey]
        };
        formValues[`${nodeId}.${groupKey}.on`] = true;
        formValues[`${nodeId}.${groupKey}.lora`] = '';
        formValues[`${nodeId}.${groupKey}.strength`] = 1;
    }

    function onRemoveLora(nodeId: string, groupKey: string) {
        const list = (extraLoraSlots[nodeId] ?? []).filter((k) => k !== groupKey);
        const next = { ...extraLoraSlots };
        if (list.length) next[nodeId] = list;
        else delete next[nodeId];
        extraLoraSlots = next;
        for (const f of ['on', 'lora', 'strength']) {
            delete formValues[`${nodeId}.${groupKey}.${f}`];
        }
    }
</script>

{#if data.appRemoved}
    <div class="page app-removed-stub">
        <div class="card app-removed-card">
            <span class="badge-removed">App removed</span>
            <h1>This app is no longer available</h1>
            <p class="app-removed-hint">The workflow or app was removed. Projects and run history were kept; you can still view runs and outputs from the project page.</p>
            <a href="/workflows" class="app-removed-link">Go to workflows</a>
            <a href="/projects" class="app-removed-link secondary">Go to projects</a>
        </div>
    </div>
{:else}
<div
    class="page app-layout app-layout-{layoutMode}"
    class:app-layout-dragging={isDraggingDivider}
    class:lightbox-open={lightboxOpen}
    bind:this={layoutContainerEl}
>
    <div class="app-mobile-tabs" role="tablist" aria-label="App view">
        <button
            type="button"
            role="tab"
            class="app-mobile-tab"
            class:active={layoutMode === 'left-full'}
            aria-selected={layoutMode === 'left-full'}
            aria-controls="app-pane-inputs"
            id="app-tab-inputs"
            onclick={() => (layoutMode = 'left-full')}
        >
            Inputs
        </button>
        <button
            type="button"
            role="tab"
            class="app-mobile-tab"
            class:active={layoutMode === 'right-full' || layoutMode === 'split'}
            aria-selected={layoutMode === 'right-full' || layoutMode === 'split'}
            aria-controls="app-pane-results"
            id="app-tab-results"
            onclick={() => (layoutMode = 'right-full')}
        >
            Results
        </button>
    </div>
    <div
        class="left"
        id="app-pane-inputs"
        role="tabpanel"
        aria-labelledby="app-tab-inputs"
        style={layoutMode === 'split' ? `flex: 0 0 ${splitPosition * 100}%` : ''}
    >
        <div class="card">
            {#key data.workflowId}
                <AutoForm
                        bind:this={autoFormRef}
                        workflowId={data.workflowId}
                        appId={data.appId ?? null}
                        projectId={currentProject?.id ?? null}
                        workflowModel={data.workflowModel}
                        workflowLoraPaths={data.workflowLoraPaths ?? []}
                        bind:values={formValues}
                        bind:randomizeSeedOnSubmit
                        bind:extraLoraSlots
                        canEditLoras={canEditLoras}
                        prefilledFromRun={!!prefilledRunId}
                        sendFromContext={sendFromContext}
                        registerRun={(fn) => { triggerRun = fn; }}
                        onAddLora={onAddLora}
                        onRemoveLora={onRemoveLora}
                        onRunStart={startRun}
                        onRunQueued={onRunQueued}
                        onRunRunning={onRunRunning}
                        onRunImages={addImagesToRun}
                        onRunDone={markRunDone}
                        onRunError={onRunError}
                        embedWorkflowuiMetadataOnDownload={data.embedWorkflowuiMetadataOnDownload ?? false}
                        presetCreationOn={appConfig.presetsEnabled ? presetCreationOn : false}
                        presetKeysToSave={appConfig.presetsEnabled ? presetKeysToSaveList : []}
                        onPresetKeyToggle={appConfig.presetsEnabled ? handlePresetKeyToggle : undefined}
                        onSavePreset={appConfig.presetsEnabled ? handleSavePreset : undefined}
                        onCancelPresetCreation={appConfig.presetsEnabled ? handleCancelPresetCreation : undefined}
                />
                {#if data.appId}
                    <p class="app-download-workflow-link">
                        <button
                            type="button"
                            class="app-download-workflow-btn"
                            disabled={downloadingWorkflowInPage}
                            onclick={downloadAppWorkflowInPage}
                        >
                            {downloadingWorkflowInPage ? 'Downloading…' : 'Download workflow with default settings'}
                        </button>
                    </p>
                {/if}
            {/key}
        </div>
    </div>

    <div
        class="app-divider"
        role="separator"
        aria-orientation="vertical"
        aria-label="Expand inputs or results"
        aria-valuenow={layoutMode === 'split' ? Math.round(splitPosition * 100) : undefined}
        aria-valuemin={layoutMode === 'split' ? 20 : undefined}
        aria-valuemax={layoutMode === 'split' ? 80 : undefined}
    >
        <div
            class="app-divider-drag-handle"
            role="presentation"
            onpointerdown={onDividerPointerDown}
            onpointermove={onDividerPointerMove}
            onpointerup={onDividerPointerUp}
            onpointercancel={onDividerPointerUp}
        ></div>
        <button
            type="button"
            class="divider-button divider-button-left"
            aria-label="Expand inputs"
            title="Expand inputs"
            onclick={expandLeft}
            disabled={layoutMode === 'left-full'}
        >
            ←
        </button>
        <button
            type="button"
            class="divider-button divider-button-right"
            aria-label="Expand results"
            title="Expand results"
            onclick={expandRight}
            disabled={layoutMode === 'right-full'}
        >
            →
        </button>
        <button
            type="button"
            class="divider-button divider-button-reset"
            aria-label="Reset to default split"
            title="Reset to default split"
            onclick={setDefaultSplit}
        >
            ⟷
        </button>
    </div>

    <div
        class="right"
        id="app-pane-results"
        role="tabpanel"
        aria-labelledby="app-tab-results"
    >
        <div
            class="card right-card"
            bind:this={resultsPaneCardEl}
            onscroll={onResultsCardScroll}
        >
            {#key data.workflowId}
                {#if !hideRunParamGroup}
                    <RunParamGroup
                            bind:values={formValues}
                            formId="workflow-run-form"
                            onSubmit={submitRunForm}
                            onQueueClick={() => (randomizeSeedOnSubmit = false)}
                            onRandomClick={() => (randomizeSeedOnSubmit = true)}
                            masterSeedHint={hasSeedInputs ? masterSeedHint : null}
                            hasSeedInputs={hasSeedInputs}
                            showActions={!isMobile}
                    />
                {/if}
            {/key}
            <div
                class="gallery-wrapper"
                bind:this={resultsCardEl}
                onscroll={onResultsCardScroll}
            >
                {#if storageNote}
                    <div class="storage-warning">{storageNote}</div>
                {/if}
                <Gallery
                    {runs}
                    appHeaderColor={data.appHeaderColor ?? null}
                    outputLabels={data.workflowModel?.outputs?.map((o) => o.label) ?? []}
                    runningProgress={runningPromptsCompleted}
                    savingRunIds={savingRunIds}
                    deletingRunIds={deletingRunIds}
                    deletingLocalRunIds={deletingLocalRunIds}
                    deletingBothRunIds={deletingBothRunIds}
                    savingImageKeys={savingImageKeys}
                    deletingImageKeys={deletingImageKeys}
                    deletingLocalImageKeys={deletingLocalImageKeys}
                    deletingBothImageKeys={deletingBothImageKeys}
                    manualSaveDisabled={storageMode === 'remote'}
                    showPreviewActions={false}
                    comfyuiDeleteSupported={data.comfyuiDeleteSupported ?? false}
                    favoriteRunIds={currentProject ? projectFavorites : new Set()}
                    onToggleFavorite={currentProject ? toggleFavorite : undefined}
                    onSaveRun={saveRunGroup}
                    onDeleteRemoteRun={deleteRemoteRunGroup}
                    onDeleteLocalRun={deleteLocalRunGroup}
                    onDeleteBothRun={deleteBothRunGroup}
                    onCancelRunGroup={cancelRunGroup}
                    cancellingRunIds={cancellingRunIds}
                    onSaveImage={saveImage}
                    onDeleteRemoteImage={deleteRemoteImage}
                    onDeleteLocalImage={deleteLocalImage}
                    onDeleteBothImage={deleteBothImage}
                    onSendToApp={currentProject ? (backendRunId, outputIndex) => { sendToAppRunId = backendRunId; sendToAppOutputIndex = outputIndex; } : undefined}
                    onMetadataClick={(_run, image) => { metadataPanelRunId = image.backendRunId; }}
                    onDeleteRemoteSelected={deleteRemoteSelected}
                    onDeleteLocalSelected={deleteLocalSelected}
                    onDeleteBothSelected={deleteBothSelected}
                    onDeleteRun={(runId, backendRunIds) => {
                        const run = runs.find((r) => r.id === runId);
                        if (run) pruneStaleOutputFavoritesForUiRun(run);
                        const hasFav =
                            run?.images.some(
                                (img) =>
                                    projectFavorites.has(img.backendRunId) &&
                                    galleryBackendRunHasDisplayableMedia(run, img.backendRunId)
                            ) ?? false;
                        if (hasFav) {
                            deleteRunPending = { runId, backendRunIds };
                            return;
                        }
                        deleteBothRunGroup(runId, backendRunIds);
                    }}
                    appSlugForReplicate={data.workflowId ?? $page.params.id}
                    onReplicateRun={(runId, appSlug) => {
                        appBooting.set(true);
                        const q = new URLSearchParams();
                        if (currentProject?.id) q.set('project', currentProject.id);
                        q.set('run_id', runId);
                        goto(`/app/${appSlug}?${q.toString()}`);
                    }}
                    onShowRunMetadata={(backendRunId) => { metadataPanelRunId = backendRunId; }}
                    onLightboxOpenChange={(open) => { lightboxOpen = open; }}
                    onRunFocusChange={handleRunFocusChange}
                />
            </div>
        </div>
        {#if resultsScrolledPastRunParam}
            <button
                type="button"
                class="scroll-to-run-param"
                onclick={scrollResultsToTop}
                aria-label="Scroll to run parameter"
                title="Run parameter"
            >
                <span class="scroll-to-run-param-icon" aria-hidden="true">↑</span>
                <span class="scroll-to-run-param-label">Run parameter</span>
            </button>
        {/if}
    </div>

    {#if layoutMode !== 'left-full' && !lightboxOpen}
        <div class="app-mobile-run-bar" role="group" aria-label="Run actions">
            <button
                type="button"
                onclick={() => triggerMobileRun('queue')}
                onpointerup={(e) => { if ((e as PointerEvent).pointerType === 'touch') { e.preventDefault(); triggerMobileRun('queue'); } }}
                ontouchend={(e) => { e.preventDefault(); triggerMobileRun('queue'); }}
            >
                Queue for generation ({formValues.runs ?? 1}x)
            </button>
            {#if hasSeedInputs}
                <button
                    type="button"
                    class="secondary"
                    onclick={() => triggerMobileRun('random')}
                    onpointerup={(e) => { if ((e as PointerEvent).pointerType === 'touch') { e.preventDefault(); triggerMobileRun('random'); } }}
                    ontouchend={(e) => { e.preventDefault(); triggerMobileRun('random'); }}
                    title="Generate with a random seed"
                >
                    🎲 Random seed ({formValues.runs ?? 1}x)
                </button>
            {/if}
        </div>
    {/if}

    <!-- Delete run with favorites: choose non-favorites only / all / cancel -->
    {#if deleteRunPending}
        {@const pending = deleteRunPending}
        <div
            class="confirm-delete-overlay"
            role="dialog"
            aria-modal="true"
            aria-labelledby="app-delete-run-fav-title"
            tabindex="-1"
            onclick={() => { deleteRunPending = null; }}
            onkeydown={(e) => { if (e.key === 'Escape') deleteRunPending = null; }}
        >
            <div class="confirm-delete-card delete-run-fav-card" role="presentation" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
                <p id="app-delete-run-fav-title" class="confirm-delete-title">Delete Run</p>
                <p class="confirm-delete-msg">This run includes favorited generations. What do you want to do?</p>
                <div class="delete-run-fav-actions">
                    <button
                        type="button"
                        class="confirm-delete-btn danger"
                        onclick={async () => {
                            const nonFav = pending.backendRunIds.filter((id) => !projectFavorites.has(id));
                            deleteRunPending = null;
                            if (nonFav.length > 0) await deleteBothRunGroup(pending.runId, nonFav, { allBackendRunIdsForRun: pending.backendRunIds });
                        }}
                    >Delete non-favorites only</button>
                    <button
                        type="button"
                        class="confirm-delete-btn danger"
                        onclick={async () => {
                            deleteRunPending = null;
                            await deleteBothRunGroup(pending.runId, pending.backendRunIds, { allBackendRunIdsForRun: pending.backendRunIds, removeFromFavorites: pending.backendRunIds });
                        }}
                    >Delete all (including favorites)</button>
                    <button
                        type="button"
                        class="confirm-delete-btn secondary"
                        onclick={() => { deleteRunPending = null; }}
                    >Cancel</button>
                </div>
            </div>
        </div>
    {/if}

    <!-- Run metadata panel (from thumbnail (i) icon) -->
    {#if metadataPanelRunId}
        <RunMetadataPanel
            runId={metadataPanelRunId}
            projectId={currentProject?.id ?? null}
            onClose={() => { metadataPanelRunId = null; }}
        />
    {/if}
    <!-- Send to App mini dialog (same as project page) -->
    {#if sendToAppRunId != null && sendToAppOutputIndex != null && currentProject?.id}
        <SendToAppDialog
            open={true}
            sendFromRun={sendToAppRunId}
            sendFromOutput={sendToAppOutputIndex}
            projectId={currentProject.id}
            onClose={() => { sendToAppRunId = null; sendToAppOutputIndex = null; }}
        />
    {/if}
    {#if appConfig.presetsEnabled}
        <PresetListDialog
            open={presetListDialogOpen}
            presets={presets}
            onClose={() => { presetListDialogOpen = false; }}
            onSelect={handlePresetSelect}
            onDelete={handleDeletePreset}
        />
    {/if}
    {#if layoutMode === 'left-full'}
        <div class="edge-toggle-group edge-toggle-group-right">
            <button
                type="button"
                class="edge-toggle"
                aria-label="Show results"
                title="Show results"
                onclick={restoreSplit}
            >
                Show results
            </button>
            <button
                type="button"
                class="edge-toggle edge-toggle-default"
                aria-label="Show default split"
                title="Show default split (inputs and results)"
                onclick={setDefaultSplit}
            >
                Default split
            </button>
        </div>
    {:else if layoutMode === 'right-full'}
        <div class="edge-toggle-group edge-toggle-group-left">
            <button
                type="button"
                class="edge-toggle"
                aria-label="Show inputs"
                title="Show inputs"
                onclick={restoreSplit}
            >
                Show inputs
            </button>
            <button
                type="button"
                class="edge-toggle edge-toggle-default"
                aria-label="Show default split"
                title="Show default split (inputs and results)"
                onclick={setDefaultSplit}
            >
                Default split
            </button>
        </div>
    {/if}
</div>
{/if}

<style>
    .app-download-workflow-link {
        margin: 0.75rem 0 0;
        padding-top: 0.5rem;
        border-top: 1px solid var(--border, rgba(255, 255, 255, 0.08));
    }

    .app-download-workflow-btn {
        background: none;
        border: none;
        padding: 0;
        font-size: 0.9rem;
        color: var(--muted);
        cursor: pointer;
        text-decoration: underline;
        text-underline-offset: 2px;
    }

    .app-download-workflow-btn:hover:not(:disabled) {
        color: var(--accent);
    }

    .app-download-workflow-btn:disabled {
        cursor: wait;
        opacity: 0.8;
    }

    .page.app-layout {
        position: relative;
        align-items: stretch;
    }

    .app-layout .left,
    .app-layout .right {
        transition:
            flex-basis 0.22s ease,
            width 0.22s ease,
            opacity 0.18s ease;
    }

    .app-layout-dragging .left,
    .app-layout-dragging .right {
        transition: none;
    }

    .app-layout-split .left {
        flex: 0 0 45%;
        max-width: 1400px;
    }

    .app-layout-split .right {
        flex: 1 1 auto;
    }

    .app-layout-left-full .left {
        flex: 1 1 100%;
        max-width: none;
    }

    .app-layout-left-full .right {
        flex: 0 0 0;
        width: 0;
        opacity: 0;
        pointer-events: none;
    }

    .app-layout-right-full .right {
        flex: 1 1 100%;
    }

    .app-layout-right-full .left {
        flex: 0 0 0;
        width: 0;
        opacity: 0;
        pointer-events: none;
    }

    .app-divider {
        position: relative;
        align-self: stretch;
        width: 1px;
        margin: 0 0.75rem;
        background: linear-gradient(
            to bottom,
            rgba(148, 163, 184, 0.1),
            rgba(148, 163, 184, 0.35),
            rgba(148, 163, 184, 0.1)
        );
        border-radius: 999px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 0.4rem;
    }

    .app-divider-drag-handle {
        position: absolute;
        left: -10px;
        right: -10px;
        top: 0;
        bottom: 0;
        cursor: col-resize;
        user-select: none;
        z-index: 0;
    }

    .app-divider .divider-button {
        position: relative;
        z-index: 1;
    }

    .app-layout-left-full .app-divider,
    .app-layout-right-full .app-divider {
        display: none;
    }

    .divider-button {
        width: 28px;
        height: 28px;
        padding: 0;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.8rem;
        line-height: 1;
        background: rgba(15, 23, 42, 0.9);
        color: var(--muted);
        border: 1px solid rgba(148, 163, 184, 0.45);
        box-shadow:
            0 0 0 1px rgba(15, 23, 42, 0.6),
            0 8px 16px rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(10px);
        cursor: pointer;
        transition:
            background 0.18s ease,
            color 0.18s ease,
            border-color 0.18s ease,
            transform 0.12s ease,
            box-shadow 0.18s ease;
    }

    .divider-button:hover:not(:disabled) {
        background: rgba(15, 23, 42, 0.98);
        color: var(--accent);
        border-color: var(--accent);
        transform: translateY(-1px);
        box-shadow:
            0 0 0 1px rgba(15, 23, 42, 0.7),
            0 10px 22px rgba(15, 23, 42, 0.8);
    }

    .divider-button:disabled {
        opacity: 0.4;
        cursor: default;
        box-shadow: none;
    }

    .divider-button-left::before,
    .divider-button-right::before {
        content: '';
    }

    .divider-button-reset {
        font-size: 0.95em;
    }

    :global([data-theme='light']) .app-divider {
        background: linear-gradient(
            to bottom,
            rgba(15, 23, 42, 0.08),
            rgba(15, 23, 42, 0.22),
            rgba(15, 23, 42, 0.08)
        );
    }
    :global([data-theme='light']) .divider-button {
        background: rgba(255, 255, 255, 0.95);
        color: var(--text);
        border: 1px solid rgba(15, 23, 42, 0.18);
        box-shadow:
            0 0 0 1px rgba(15, 23, 42, 0.06),
            0 4px 12px rgba(15, 23, 42, 0.12);
    }
    :global([data-theme='light']) .divider-button:hover:not(:disabled) {
        background: #fff;
        color: var(--accent);
        border-color: var(--accent);
        box-shadow:
            0 0 0 1px rgba(15, 23, 42, 0.08),
            0 6px 16px rgba(15, 23, 42, 0.15);
    }
    :global([data-theme='light']) .edge-toggle {
        background: rgba(255, 255, 255, 0.95);
        color: var(--text);
        border: 1px solid rgba(15, 23, 42, 0.18);
        box-shadow:
            0 0 0 1px rgba(15, 23, 42, 0.06),
            0 4px 12px rgba(15, 23, 42, 0.12);
    }
    :global([data-theme='light']) .edge-toggle:hover {
        color: var(--accent);
        border-color: var(--accent);
        background: #fff;
    }

    .edge-toggle-group {
        position: fixed;
        top: 50%;
        transform: translateY(-50%);
        z-index: 40;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
    }

    .edge-toggle-group-left {
        left: 0.6rem;
    }

    .edge-toggle-group-right {
        right: 0.6rem;
    }

    .lightbox-open .edge-toggle-group {
        visibility: hidden;
        pointer-events: none;
    }

    .edge-toggle {
        position: relative;
        writing-mode: vertical-rl;
        text-orientation: mixed;
        padding: 0.55rem 0.4rem;
        font-size: 0.75rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        background: rgba(15, 23, 42, 0.96);
        color: var(--muted);
        border-radius: 999px;
        border: 1px solid rgba(148, 163, 184, 0.45);
        box-shadow:
            0 0 0 1px rgba(15, 23, 42, 0.6),
            0 10px 26px rgba(15, 23, 42, 0.9);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.25rem;
        backdrop-filter: blur(12px);
    }

    .edge-toggle:hover {
        color: var(--accent);
        border-color: var(--accent);
        background: rgba(15, 23, 42, 0.99);
    }

    .edge-toggle-default {
        font-size: 0.7rem;
        padding: 0.4rem 0.35rem;
    }

    @media (max-width: 900px) {
        .app-divider {
            display: none;
        }

        .edge-toggle-group {
            top: auto;
            bottom: 1rem;
            transform: none;
            flex-direction: row;
        }

        .edge-toggle {
            writing-mode: horizontal-tb;
            border-radius: 999px;
        }
    }

    .app-mobile-tabs {
        display: none;
    }

    .app-mobile-run-bar {
        display: none;
    }

    @media (max-width: 639px) {
        .page.app-layout {
            --mobile-run-bar-height: 58px;
        }

        .app-mobile-tabs {
            display: flex;
            flex-shrink: 0;
            width: 100%;
            gap: 0;
            padding: 0.35rem;
            background: var(--surface);
            border-bottom: 1px solid var(--border);
            position: sticky;
            /* AppHeader is sticky at the top on mobile; offset tabs below it. */
            top: 5.8rem;
            z-index: 30;
        }
        .app-mobile-tab {
            flex: 1;
            min-height: 44px;
            padding: 0.5rem 1rem;
            font-size: 0.95rem;
            font-weight: 500;
            border: none;
            border-radius: 8px;
            background: transparent;
            color: var(--muted);
            cursor: pointer;
            transition: background 0.2s ease, color 0.2s ease;
        }
        .app-mobile-tab:hover {
            color: var(--text);
            background: rgba(255, 255, 255, 0.05);
        }
        .app-mobile-tab.active {
            background: var(--accent-soft);
            color: var(--accent);
        }
        .app-mobile-tab.active:hover {
            background: var(--accent-soft);
            color: var(--accent);
        }

        .page.app-layout {
            flex-direction: column;
        }

        .right {
            position: relative;
            justify-content: flex-start;
            align-items: stretch;
        }

        .app-layout .left,
        .app-layout .right {
            width: 100%;
            max-width: none;
            min-width: 0;
        }

        .app-layout-split .left {
            flex: 0 0 0;
            width: 0;
            min-width: 0;
            opacity: 0;
            pointer-events: none;
            overflow: hidden;
        }

        .app-layout-split .right {
            flex: 1 1 100%;
        }

        .edge-toggle-group {
            display: none;
        }

        .right .card {
            flex: 1;
            min-height: 0;
            overflow-y: auto;
            overflow-x: hidden;
            -webkit-overflow-scrolling: touch;
            justify-content: flex-start;
            align-items: stretch;
        }
        .right .card .gallery-wrapper {
            flex: none;
            overflow: visible;
        }

        .scroll-to-run-param {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            position: absolute;
            bottom: calc(var(--app-footer-height, 72px) + var(--mobile-run-bar-height, 0px) + 12px + env(safe-area-inset-bottom, 0));
            left: 50%;
            transform: translateX(-50%);
            z-index: 20;
            padding: 0.4rem 0.75rem;
            font-size: 0.8rem;
            font-weight: 500;
            color: var(--text);
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 999px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            cursor: pointer;
            transition: background 0.2s ease, border-color 0.2s ease;
        }
        .scroll-to-run-param:hover {
            background: var(--accent-soft);
            border-color: var(--accent);
            color: var(--accent);
        }
        .scroll-to-run-param-icon {
            font-size: 1rem;
            line-height: 1;
            opacity: 0.9;
        }
        .scroll-to-run-param-label {
            white-space: nowrap;
        }

        .app-mobile-run-bar {
            position: fixed;
            left: 0;
            right: 0;
            bottom: calc(var(--app-footer-height, 72px) + env(safe-area-inset-bottom, 0));
            z-index: 10000;
            display: flex;
            gap: 0.5rem;
            padding: 0.5rem;
            background: var(--surface);
            border-top: 1px solid var(--border);
            pointer-events: auto;
            touch-action: manipulation;
        }
        .app-mobile-run-bar button {
            flex: 1;
            min-height: 44px;
        }
    }

    .app-removed-stub {
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 40vh;
    }
    .app-removed-card {
        max-width: 28rem;
        padding: 1.5rem;
        text-align: center;
    }
    .app-removed-card .badge-removed {
        font-size: 0.75rem;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        background: var(--muted);
        color: var(--surface);
        margin-bottom: 1rem;
        display: inline-block;
    }
    .app-removed-card h1 {
        font-size: 1.25rem;
        margin: 0 0 0.75rem 0;
    }
    .app-removed-hint {
        color: var(--muted);
        font-size: 0.9rem;
        margin-bottom: 1.25rem;
        line-height: 1.4;
    }
    .app-removed-link {
        display: inline-block;
        margin: 0 0.35rem 0.35rem 0;
        padding: 0.5rem 1rem;
        background: var(--accent);
        color: white;
        border-radius: 8px;
        text-decoration: none;
        font-weight: 500;
    }
    .app-removed-link:hover {
        opacity: 0.9;
    }
    .app-removed-link.secondary {
        background: var(--surface);
        color: var(--text);
        border: 1px solid var(--border);
    }
    .app-removed-link.secondary:hover {
        background: var(--accent-soft);
        border-color: var(--accent);
    }
    .storage-warning {
        margin: 0 0 0.5rem 0;
        padding: 0.35rem 0.5rem;
        border-radius: 6px;
        font-size: 0.75rem;
        color: #f0c674;
        border: 1px solid #f0c674;
        background: rgba(240, 198, 116, 0.08);
    }
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
