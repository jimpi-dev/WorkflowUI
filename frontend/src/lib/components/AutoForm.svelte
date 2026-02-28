<script lang="ts">
    import { tick } from 'svelte';
    import { onMount } from 'svelte';
    import { getApiBase, COMFYUI_MAX_SEED } from '$lib/config';
    import InputRenderer from '$lib/components/InputRenderer.svelte';
    import type { WorkflowModel } from '$lib/workflow/types';
    import type { GalleryImage } from '$lib/components/Gallery.svelte';
    import { buildRunValues } from '$lib/run/buildRunPayload';
    import { pollRunStatus } from '$lib/run/pollRunStatus';
    import { safeUUID } from '$lib/utils/id';

    export let workflowId: string;
    export let appId: string | null = null;
    export let projectId: string | null = null;

    export let onRunDone: (runId: string) => void;
    export let onRunStart: (seed?: number, inputs?: Record<string, any>) => string;
    export let onRunQueued: (runId: string, queuePosition: number, backendRunId: string) => void;
    export let onRunRunning: (runId: string) => void;
    export let onRunImages: (runId: string, images: GalleryImage[], backendRunId: string, storage?: { local_storage_status?: string; remote_status?: string; local_path?: string }) => void;
    export let onRunError: ((runId: string, message: string) => void) | undefined = undefined;
    export let workflowModel: WorkflowModel;
    export let workflowLoraPaths: string[] = [];
    export let randomizeSeedOnSubmit = false;
    export let values: Record<string, any> = {};
    export let extraLoraSlots: Record<string, string[]> = {};
    export let canEditLoras = false;
    export let prefilledFromRun = false;
    export let sendFromContext: { runId: string; outputIndex: number; inputKey: string; filename: string; subfolder?: string; type?: string } | null = null;
    export let onAddLora: ((nodeId: string, groupKey: string) => void) | undefined = undefined;
    export let onRemoveLora: ((nodeId: string, groupKey: string) => void) | undefined = undefined;
    export let registerRun: ((fn: () => void) => void) | undefined = undefined;
    export let embedWorkflowuiMetadataOnDownload = false;

    export let presetCreationOn = false;
    export let onPresetCreationToggle: (() => void) | undefined = undefined;
    export let presetKeysToSave: Set<string> | string[] = [];
    export let onPresetKeyToggle: ((key: string, included: boolean) => void) | undefined = undefined;
    export let onSavePreset: ((name: string, description: string) => void) | undefined = undefined;
    export let onCancelPresetCreation: (() => void) | undefined = undefined;

    $: presetKeysSize = Array.isArray(presetKeysToSave) ? presetKeysToSave.length : presetKeysToSave.size;
    let savePresetName = '';
    let savePresetDescription = '';

    const DEFAULT_RUNS = 1;
    values.runs ??= DEFAULT_RUNS;

    $: if (workflowModel?.inputs) {
        for (const input of workflowModel.inputs) {
            const isSendFromImage = input.type === 'image' && sendFromContext?.inputKey === input.key;
            if (isSendFromImage) {
                if (!(input.key in values)) values[input.key] = '';
                continue;
            }
            if (!(input.key in values)) {
                values[input.key] = input.type === 'image'
                    ? (input.default ?? '')
                    : (input.default ?? (input.type === 'number' ? 0 : ''));
            }
        }
        values.runs ??= DEFAULT_RUNS;
    }
    
    const runIdToBackendIds = new Map<string, Set<string>>();

    function getMergedBindings(): { key: string; nodeId: string; field: string }[] {
        const base = workflowModel.bindings ?? [];
        const extra: { key: string; nodeId: string; field: string }[] = [];
        for (const [nodeId, groupKeys] of Object.entries(extraLoraSlots)) {
            for (const gk of groupKeys) {
                for (const f of ['on', 'lora', 'strength']) {
                    extra.push({
                        key: `${nodeId}.${gk}.${f}`,
                        nodeId,
                        field: `${gk}.${f}`
                    });
                }
            }
        }
        return [...base, ...extra];
    }

    async function runWorkflow(event?: SubmitEvent) {
        event?.preventDefault();

        const seedInputs = workflowModel.inputs.filter(
            (i) => i.role === 'seed' || i.type === 'seed'
        );
        const masterKeyRaw = workflowModel.masterSeedInputKey;
        const masterKeyNorm = masterKeyRaw != null && typeof masterKeyRaw === 'string' ? masterKeyRaw.trim() : '';
        const norm = (k: string | undefined) => (k != null ? String(k).trim() : '');
        const parentSeedInput =
            (masterKeyNorm && seedInputs.find((i) => norm(i.key) === masterKeyNorm)) ?? seedInputs[0];
        const useRandomSeedPerRun = !!randomizeSeedOnSubmit;

        let baseSeed: number | undefined = undefined;
        if (parentSeedInput && !useRandomSeedPerRun) {
            const fromValues = values[parentSeedInput.key];
            const numFromValues = fromValues != null ? Number(fromValues) : NaN;
            if (Number.isInteger(numFromValues) && numFromValues >= 0) {
                baseSeed = numFromValues;
            } else {
                const fromDom = readDimensionFromForm(parentSeedInput.key);
                const raw = fromDom !== null ? fromDom : fromValues;
                const num = Number(raw);
                baseSeed = Number.isNaN(num) ? 0 : Math.max(0, Math.round(num));
            }
        }

        randomizeSeedOnSubmit = false;

        let inputsSnapshot: Record<string, any>;
        try {
            inputsSnapshot = typeof structuredClone === 'function'
                ? structuredClone({ ...values })
                : JSON.parse(JSON.stringify({ ...values }));
        } catch {
            inputsSnapshot = { ...values };
        }
        const runId = onRunStart(useRandomSeedPerRun ? undefined : baseSeed, inputsSnapshot);

        if (appId && !projectId) {
            onRunError?.(runId, 'Select or create a project first.');
            return;
        }

        const runs = values.runs ?? 1;
        const backendIds = new Set<string>();
        runIdToBackendIds.set(runId, backendIds);

        const promises: Promise<void>[] = [];
        for (let i = 0; i < runs; i++) {
            const runValues = buildRunValues(
                values,
                workflowModel,
                getMergedBindings(),
                DEFAULT_RUNS
            );

            if (parentSeedInput && useRandomSeedPerRun) {
                runValues[parentSeedInput.key] = Math.floor(Math.random() * (COMFYUI_MAX_SEED + 1));
            } else if (parentSeedInput && baseSeed !== undefined) {
                runValues[parentSeedInput.key] = baseSeed + i;
            }
            
            const apiBase = getApiBase() || '';
            const body: Record<string, unknown> = {
                values: runValues,
                bindings: getMergedBindings(),
                run_group_id: runId
            };
            if (appId) body.app_id = appId;
            if (projectId) body.project_id = projectId;
            if (sendFromContext && runValues[sendFromContext.inputKey] === sendFromContext.filename) {
                body.parent_run_id = sendFromContext.runId;
                body.parent_media_id = `${sendFromContext.runId}:${sendFromContext.outputIndex}`;
                body.input_from_run = {
                    run_id: sendFromContext.runId,
                    output_index: sendFromContext.outputIndex,
                    input_key: sendFromContext.inputKey
                };
            }
            const url = appId ? `${apiBase}/run` : `${apiBase}/run/${workflowId}`;

            const p = fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            })
                .then(async (res) => {
                    const data = await res.json().catch(() => ({}));
                    if (!res.ok) {
                        const msg = (typeof data?.detail === 'string' ? data.detail : data?.message) ?? res.statusText ?? 'Run failed';
                        onRunError?.(runId, msg);
                        return;
                    }
                    const backendRunId = data.run_id ?? data.runId;
                    const queuePosition = data.queue_position ?? data.queuePosition;
                    if (!backendRunId) {
                        onRunError?.(runId, 'Server did not return run_id');
                        return;
                    }
                    backendIds.add(backendRunId);
                    onRunQueued(runId, queuePosition, backendRunId);
                    pollRunStatus(
                        backendRunId,
                        runId,
                        {
                            onRunning: onRunRunning,
                            onImages: onRunImages,
                            onError: (rid, msg) => onRunError?.(rid, msg),
                            onComplete: () => {
                                backendIds.delete(backendRunId);
                                if (backendIds.size === 0) {
                                    runIdToBackendIds.delete(runId);
                                    onRunDone(runId);
                                }
                            }
                        },
                        {
                            embedWorkflowuiMetadataOnDownload,
                            generateId: safeUUID
                        }
                    );
                })
                .catch(() => {
                    onRunError?.(runId, 'Network error (request failed)');
                });
            promises.push(p);
        }

        await Promise.all(promises);
    }

    async function handleLoraToggle() {
        await tick();
    }

    onMount(() => {
        registerRun?.(() => runWorkflow());
    });

    export function runWithRandomSeed(useRandom: boolean) {
        randomizeSeedOnSubmit = useRandom;
        runWorkflow();
    }

    function submitRunForm() {
        runWorkflow();
    }

    let mobileRunTapLock = false;
    function triggerMobileRun(action: 'queue' | 'random') {
        if (mobileRunTapLock) return;
        if (appId && !projectId) {
            return;
        }
        mobileRunTapLock = true;
        randomizeSeedOnSubmit = action === 'random';
        submitRunForm();
        setTimeout(() => { mobileRunTapLock = false; }, 300);
    }
</script>

<form id="workflow-run-form" class="card card-form" onsubmit={(e) => {
  e.preventDefault();
  runWorkflow(e);
}}>
    <div class="form-scroll">
        {#if presetKeysSize > 0 && (onSavePreset || onCancelPresetCreation)}
            <div class="preset-save-bar">
                <label for="preset-save-name-input" class="preset-save-label">Save as preset</label>
                <input
                    id="preset-save-name-input"
                    type="text"
                    class="preset-save-name"
                    placeholder="Preset name"
                    bind:value={savePresetName}
                />
                <input
                    type="text"
                    class="preset-save-desc"
                    placeholder="Description (optional)"
                    bind:value={savePresetDescription}
                />
                <div class="preset-save-actions">
                    <button
                        type="button"
                        class="preset-save-btn"
                        disabled={!savePresetName.trim()}
                        onclick={() => {
                            if (savePresetName.trim() && onSavePreset) {
                                onSavePreset(savePresetName.trim(), savePresetDescription.trim());
                                savePresetName = '';
                                savePresetDescription = '';
                            }
                        }}
                    >Save</button>
                    <button type="button" class="preset-cancel-btn" onclick={() => onCancelPresetCreation?.()}>Cancel</button>
                </div>
            </div>
        {/if}
        <InputRenderer
                inputs={workflowModel.inputs}
                masterSeedInputKey={workflowModel.masterSeedInputKey}
                bind:values
                appId={appId}
                extraLoraSlots={extraLoraSlots}
                canEditLoras={canEditLoras}
                prefilledFromRun={prefilledFromRun}
                prefillImageRunId={sendFromContext?.runId ?? null}
                prefillImageInputKey={sendFromContext?.inputKey ?? null}
                prefillImageFilename={sendFromContext?.filename ?? ''}
                prefillImageSubfolder={sendFromContext?.subfolder ?? ''}
                prefillImageType={sendFromContext?.type ?? 'image'}
                onAddLora={onAddLora}
                onRemoveLora={onRemoveLora}
                workflowLoraPaths={workflowLoraPaths}
                onLoraToggle={handleLoraToggle}
                onResolutionChange={handleLoraToggle}
                presetCreationOn={presetCreationOn}
                presetKeysToSave={presetKeysToSave}
                onPresetKeyToggle={onPresetKeyToggle}
        />
        <div class="mobile-run-actions" role="group" aria-label="Run actions">
            <button
                type="button"
                onclick={() => triggerMobileRun('queue')}
                onpointerup={(e) => { if ((e as PointerEvent).pointerType === 'touch') { e.preventDefault(); triggerMobileRun('queue'); } }}
                ontouchend={(e) => { e.preventDefault(); triggerMobileRun('queue'); }}
            >
                Queue for generation ({values.runs ?? DEFAULT_RUNS}x)
            </button>
            <button
                type="button"
                class="secondary"
                onclick={() => triggerMobileRun('random')}
                onpointerup={(e) => { if ((e as PointerEvent).pointerType === 'touch') { e.preventDefault(); triggerMobileRun('random'); } }}
                ontouchend={(e) => { e.preventDefault(); triggerMobileRun('random'); }}
                title="Generate with a random seed"
            >
                🎲 Random seed ({values.runs ?? DEFAULT_RUNS}x)
            </button>
        </div>
    </div>
</form>

<style>
    .card-form {
        display: flex;
        flex-direction: column;
        gap: 1rem;
        overflow: hidden;
        height: 100%;
    }
    .form-scroll {
        flex: 1;
        overflow-y: auto;
        overflow-x: hidden;
        min-height: 0;
        min-width: 0;
    }
    .preset-save-bar {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.5rem 1rem;
        padding: 0.75rem;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        margin-bottom: 0.75rem;
    }
    .preset-save-label {
        font-size: 0.9rem;
        color: var(--muted);
        margin-right: 0.25rem;
    }
    .preset-save-name, .preset-save-desc {
        padding: 0.4rem 0.6rem;
        border: 1px solid var(--border);
        border-radius: 6px;
        background: var(--bg);
        color: var(--text);
        font: inherit;
        min-width: 120px;
    }
    .preset-save-desc {
        min-width: 160px;
    }
    .preset-save-actions {
        display: flex;
        gap: 0.5rem;
    }
    .preset-save-btn, .preset-cancel-btn {
        padding: 0.4rem 0.75rem;
        border-radius: 6px;
        font: inherit;
        cursor: pointer;
    }
    .preset-save-btn {
        background: var(--accent);
        color: var(--accent-contrast);
        border: none;
    }
    .preset-save-btn:hover:not(:disabled) {
        background: var(--accent-hover);
    }
    .preset-save-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    .preset-cancel-btn {
        background: transparent;
        color: var(--muted);
        border: 1px solid var(--border);
    }
    .preset-cancel-btn:hover {
        color: var(--text);
    }

    .mobile-run-actions {
        display: none;
    }

    @media (max-width: 639px) {
        .mobile-run-actions {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }
        .mobile-run-actions button {
            flex: 1;
            min-height: 44px;
        }
    }
</style>
