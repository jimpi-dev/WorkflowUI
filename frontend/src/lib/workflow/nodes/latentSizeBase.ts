import type { NodeSpec, NodeInputSpec } from '../types';

export const LATENT_SIZE_WIDTH_FIELDS = ['width', 'width_override'] as const;
export const LATENT_SIZE_HEIGHT_FIELDS = ['height', 'height_override'] as const;
export const LATENT_SIZE_BATCH_FIELD = 'batch_size';

const DEFAULT_NUMBER_OPTIONS = { min: 64, max: 2048, step: 8 };
const BATCH_OPTIONS = { min: 1, max: 64 };

export type LatentSizeSpecOptions = {
    widthField?: string;
    heightField?: string;
    batchField?: string | null;
    headerBadge?: string;
};

export function createLatentSizeSpec(
    classType: string,
    options?: LatentSizeSpecOptions
): NodeSpec {
    const w = options?.widthField ?? 'width';
    const h = options?.heightField ?? 'height';
    const batch = options?.batchField ?? 'batch_size';

    const fixedInputs: Record<string, NodeInputSpec> = {
        [w]: {
            type: 'number',
            label: 'Width',
            ...DEFAULT_NUMBER_OPTIONS
        },
        [h]: {
            type: 'number',
            label: 'Height',
            ...DEFAULT_NUMBER_OPTIONS
        }
    };
    if (batch) {
        fixedInputs[batch] = {
            type: 'number',
            label: 'Batch size',
            ...BATCH_OPTIONS
        };
    }

    const rows: string[][] = [[w, h]];
    if (batch) rows.push([batch]);

    return {
        classType,
        template: 'latent-resolution',
        headerBadge: options?.headerBadge ?? 'LATENT',
        fixedInputs,
        layout: { rows }
    };
}
