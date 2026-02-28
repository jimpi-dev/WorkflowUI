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

    async function poll(): Promise<void> {
        let data: any;
        try {
            const res = await api.get(`run/${backendRunId}/status`);
            if (!res.ok) throw new Error(res.statusText || 'Status request failed');
            data = await res.json();
        } catch (err) {
            const prev = runStatusFailures.get(backendRunId) ?? 0;
            const next = prev + 1;
            runStatusFailures.set(backendRunId, next);
            if (next >= 3) {
                const msg =
                    err instanceof Error ? err.message : 'Status request failed';
                onError(runId, `Failed to fetch run status (${msg}).`);
                onComplete();
                return;
            }
            setTimeout(poll, 1500 + next * 1000);
            return;
        }

        if (data.status === 'running') {
            onRunning(runId);
        }

        if (data.status === 'done') {
            const executionTimeSec =
                data.execution_time != null
                    ? Math.round(Number(data.execution_time))
                    : undefined;
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
            const images = rawImages
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
                        let imageUrl = `${base}/image?filename=${encodeURIComponent(img.filename)}&subfolder=${encodeURIComponent(subfolder)}&type=${encodeURIComponent(type)}&run_id=${encodeURIComponent(backendRunId)}`;
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
                            promptId: data.prompt_id ?? backendRunId,
                            backendRunId,
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

        setTimeout(poll, 1500);
    }

    poll();
}
