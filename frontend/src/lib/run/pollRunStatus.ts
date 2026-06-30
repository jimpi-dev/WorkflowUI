import type { GalleryImage } from '$lib/components/Gallery.svelte';
import { api } from '$lib/api';
import { getApiBase } from '$lib/config';

export type PollRunStatusCallbacks = {
    onRunning: (runId: string) => void;
    onImages: (
        runId: string,
        images: GalleryImage[],
        backendRunId: string,
        storage?: {
            local_storage_status?: string;
            remote_status?: string;
            local_path?: string;
        }
    ) => void;
    onError: (runId: string, message: string) => void;
    onComplete: () => void;
};

export type PollRunStatusOptions = {
    embedWorkflowuiMetadataOnDownload?: boolean;
    generateId: () => string;
};

const runStatusFailures = new Map<string, number>();

export function pollRunStatus(
    backendRunId: string,
    runId: string,
    callbacks: PollRunStatusCallbacks,
    options: PollRunStatusOptions
): void {
    const { onRunning, onImages, onError, onComplete } = callbacks;
    const { embedWorkflowuiMetadataOnDownload = false, generateId } = options;

    function scheduleNextPoll(ms: number): void {
        // Hidden tabs can delay/throttle timers heavily; use a slightly larger delay there.
        const hiddenBoost =
            typeof document !== 'undefined' && document.hidden ? 1500 : 0;
        setTimeout(poll, ms + hiddenBoost);
    }

    function mapImages(
        data: any,
        backendId: string,
        media: Array<{
            filename: string;
            subfolder?: string;
            type?: string;
            kind?: string;
        }>
    ): GalleryImage[] {
        const executionTimeSec =
            data.execution_time != null
                ? Math.round(Number(data.execution_time))
                : undefined;
        return media
            .filter((img) => img && typeof img.filename === 'string')
            .map(
                (
                    img: {
                        filename: string;
                        subfolder?: string;
                        type?: string;
                        kind?: string;
                    },
                    index: number
                ) => {
                    const subfolder = img.subfolder ?? '';
                    const type = img.type ?? img.kind ?? 'output';
                    const base = getApiBase().replace(/\/$/, '');
                    let imageUrl = `${base}/image?filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(subfolder)}&type=${encodeURIComponent(type)}&run_id=${encodeURIComponent(backendId)}`;
                    if (embedWorkflowuiMetadataOnDownload)
                        imageUrl += '&embed_workflowui_metadata=1';
                    const isVideo = type === 'video';
                    const isAudio = type === 'audio';
                    const mediaType = isVideo
                        ? 'video'
                        : isAudio
                          ? 'audio'
                          : 'image';
                    return {
                        id: generateId(),
                        url: imageUrl,
                        previewUrl:
                            isVideo || isAudio
                                ? undefined
                                : `${imageUrl}&preview=webp`,
                        filename: img.filename,
                        promptId: data.prompt_id ?? backendId,
                        backendRunId: backendId,
                        seed: data.seed,
                        outputIndex: index,
                        executionTimeSec,
                        mediaType: mediaType as
                            | 'image'
                            | 'video'
                            | 'audio'
                    };
                }
            );
    }

    async function poll(): Promise<void> {
        let data: any;
        try {
            const res = await api.get(`run/${backendRunId}/status`);
            if (!res.ok) throw new Error(res.statusText || 'Status request failed');
            data = await res.json();
            runStatusFailures.delete(backendRunId);
        } catch (err) {
            const prev = runStatusFailures.get(backendRunId) ?? 0;
            const next = prev + 1;
            runStatusFailures.set(backendRunId, next);
            if (next >= 3) {
                // Fallback to run detail endpoint before giving up. This helps after
                // tab inactivity where status polling can temporarily fail.
                try {
                    const detailRes = await api.get(`runs/${backendRunId}`);
                    if (detailRes.ok) {
                        const detail = await detailRes.json();
                        const status = detail?.status;
                        if (status === 'running' || status === 'queued') {
                            if (status === 'running') onRunning(runId);
                            scheduleNextPoll(2500 + next * 500);
                            return;
                        }
                        if (status === 'done') {
                            const rawImages = Array.isArray(detail.images)
                                ? detail.images
                                : Array.isArray(detail.media)
                                  ? detail.media
                                  : [];
                            const images = mapImages(detail, backendRunId, rawImages);
                            if (images.length) {
                                onImages(runId, images, backendRunId, {
                                    local_storage_status: detail.local_storage_status,
                                    remote_status: detail.remote_status,
                                    local_path: detail.local_path
                                });
                            }
                            onComplete();
                            return;
                        }
                        if (status === 'error') {
                            const detailErr =
                                detail?.error != null
                                    ? String(detail.error)
                                    : 'Unknown error';
                            onError(runId, detailErr);
                            onComplete();
                            return;
                        }
                    }
                } catch {
                    // Ignore and continue polling below.
                }
            }
            // Do not stop polling after intermittent failures; keep retrying.
            scheduleNextPoll(1500 + Math.min(next, 10) * 1000);
            return;
        }

        if (data.status === 'running') {
            onRunning(runId);
        }

        if (data.status === 'done') {
            let rawImages: {
                filename: string;
                subfolder?: string;
                type?: string;
                kind?: string;
            }[] = Array.isArray(data.images)
                ? data.images
                : Array.isArray(data.media)
                  ? data.media
                  : [];
            if (rawImages.length === 0) {
                await new Promise((r) => setTimeout(r, 400));
                try {
                    const detailRes = await api.get(`runs/${backendRunId}`);
                    if (detailRes.ok) {
                        const detail = await detailRes.json();
                        rawImages = Array.isArray(detail.images)
                            ? detail.images
                            : Array.isArray(detail.media)
                              ? detail.media
                              : [];
                    }
                } catch {
                }
            }
            const images = mapImages(data, backendRunId, rawImages);
            if (images.length) {
                onImages(runId, images, backendRunId, {
                    local_storage_status: data.local_storage_status,
                    remote_status: data.remote_status,
                    local_path: data.local_path
                });
            }
            onComplete();
            return;
        }

        if (data.status === 'error') {
            const err =
                data.error != null ? String(data.error) : 'Unknown error';
            try {
                console.error('Run error:', err);
            } catch {
                console.error('Run error: [encoding error displaying message]');
            }
            onComplete();
            return;
        }

        scheduleNextPoll(1500);
    }

    poll();
}
